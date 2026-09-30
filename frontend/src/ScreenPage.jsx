import { createSignal, onMount, Show, For } from "solid-js";
import {
  createPreset,
  deletePreset,
  fetchPresetLogs,
  fetchPresets,
  fetchSubmissions,
} from "./api";

const statusLabel = {
  pending: "待复核",
  processing: "复核中",
  done: "已完成",
};

const actionLabel = {
  create: "新建",
  delete: "删除",
};

function ScreenPage() {
  // toolPrefix 是输入框里的值；activePrefix 是已提交给后台的查询条件。
  const [toolPrefix, setToolPrefix] = createSignal("");
  const [activePrefix, setActivePrefix] = createSignal("");
  const [rows, setRows] = createSignal([]);
  const [presets, setPresets] = createSignal([]);
  const [logs, setLogs] = createSignal([]);
  const [newName, setNewName] = createSignal("");
  const [loading, setLoading] = createSignal(false);
  const [presetBusy, setPresetBusy] = createSignal(false);
  const [error, setError] = createSignal("");
  const [notice, setNotice] = createSignal("");

  async function reload(prefix) {
    setLoading(true);
    setError("");
    try {
      // 命中表与列表唯一取数口径：始终带条件重新请求后台，前端不藏行。
      const data = await fetchSubmissions(prefix);
      setRows(data);
      setActivePrefix(prefix || "");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function reloadPresets() {
    try {
      setPresets(await fetchPresets());
    } catch (e) {
      setError(e.message);
    }
  }

  async function reloadLogs() {
    try {
      setLogs(await fetchPresetLogs());
    } catch (e) {
      setError(e.message);
    }
  }

  onMount(() => {
    reload("");
    reloadPresets();
    reloadLogs();
  });

  function handleSearch(e) {
    if (e) e.preventDefault();
    setNotice("");
    reload(toolPrefix().trim());
  }

  function handleClear() {
    setToolPrefix("");
    setNewName("");
    setNotice("条件已清空，回到整表");
    reload("");
  }

  // 一点切换：以预设字头重新向后台拉数。
  function handlePick(preset) {
    setToolPrefix(preset.prefix);
    setNotice(`已切换到预设「${preset.name}」，按字头「${preset.prefix}」后台重查`);
    reload(preset.prefix);
  }

  async function handleCreatePreset(e) {
    e.preventDefault();
    setError("");
    const prefix = toolPrefix().trim();
    const name = newName().trim();
    if (!name) {
      setError("请先填写预设称呼");
      return;
    }
    if (!prefix) {
      setError("请先在字头框输入字头并筛查，再把当前条件存为预设");
      return;
    }
    setPresetBusy(true);
    try {
      await createPreset(name, prefix);
      setNewName("");
      setNotice(`预设「${name}」已新建并记入流水`);
      await Promise.all([reloadPresets(), reloadLogs()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setPresetBusy(false);
    }
  }

  async function handleDelete(preset) {
    setError("");
    if (!window.confirm(`确认删除预设「${preset.name}」？删除会记入改动流水。`)) return;
    setPresetBusy(true);
    try {
      await deletePreset(preset.id);
      setNotice(`预设「${preset.name}」已删除，流水保留痕迹`);
      await Promise.all([reloadPresets(), reloadLogs()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setPresetBusy(false);
    }
  }

  return (
    <>
      <section class="card">
        <h2>按刀号字头筛查</h2>
        <form onSubmit={handleSearch} class="form inline">
          <label>
            字头（刀具编号前缀）
            <input
              placeholder="如 甲"
              value={toolPrefix()}
              onInput={(e) => setToolPrefix(e.currentTarget.value)}
            />
          </label>
          <button type="submit" disabled={loading()}>
            {loading() ? "后台拉数中…" : "筛查"}
          </button>
          <button type="button" class="ghost" onClick={handleClear} disabled={loading()}>
            清空条件（回整表）
          </button>
        </form>
        <p class="hint">
          当前命中口径：
          <strong>{activePrefix() ? `刀具编号以「${activePrefix()}」开头` : "整表（无条件）"}</strong>
          ，共 {rows().length} 笔。
        </p>
      </section>

      <section class="card">
        <div class="toolbar">
          <h2>命名预设</h2>
        </div>
        <p class="hint">操作员与复核员均可新建命名预设；点击预设即按其字头由后台重新拉数。只能删除本人新建的预设。</p>
        <div class="preset-chips">
          <For each={presets()} fallback={<span class="hint">尚无预设，先在下方把当前字头存为命名预设。</span>}>
            {(preset) => (
              <span
                class={`preset-chip${activePrefix() === preset.prefix ? " active" : ""}`}
              >
                <button type="button" class="linklike" onClick={() => handlePick(preset)}>
                  {preset.name}
                  <span class="preset-meta">字头「{preset.prefix}」· {preset.created_by}</span>
                </button>
                <Show when={preset.owned_by_me}>
                  <button
                    type="button"
                    class="chip-del"
                    title="删除本人预设（记入流水）"
                    onClick={() => handleDelete(preset)}
                    disabled={presetBusy()}
                  >
                    ×
                  </button>
                </Show>
              </span>
            )}
          </For>
        </div>
        <form onSubmit={handleCreatePreset} class="form inline preset-create">
          <label>
            预设称呼
            <input
              placeholder="如 预设甲"
              value={newName()}
              onInput={(e) => setNewName(e.currentTarget.value)}
            />
          </label>
          <button type="submit" disabled={presetBusy()}>
            把当前字头「{toolPrefix().trim() || "—"}」存为预设
          </button>
        </form>
      </section>

      <Show when={error()}>
        <div class="banner error">{error()}</div>
      </Show>
      <Show when={notice()}>
        <div class="banner ok">{notice()}</div>
      </Show>

      <section class="card">
        <div class="toolbar">
          <h2>命中表</h2>
          <button type="button" class="ghost" onClick={() => reload(activePrefix())} disabled={loading()}>
            {loading() ? "刷新中…" : "按当前条件重查"}
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>刀具</th>
              <th>刀补 µm</th>
              <th>状态</th>
              <th>结论</th>
              <th>提交时间</th>
            </tr>
          </thead>
          <tbody>
            <For each={rows()}>
              {(row) => (
                <tr>
                  <td>{row.tool_code}</td>
                  <td>{row.offset_um}</td>
                  <td>{statusLabel[row.status] || row.status}</td>
                  <td class={row.verdict === "合格" ? "pass" : row.verdict === "超差" ? "fail" : ""}>
                    {row.verdict || "—"}
                  </td>
                  <td>{new Date(row.created_at).toLocaleString()}</td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
        <Show when={!rows().length && !loading()}>
          <p class="hint">没有命中的刀补记录</p>
        </Show>
      </section>

      <section class="card">
        <h2>命中表口径说明</h2>
        <ul class="spec-list">
          <li>筛查条件为「刀具编号字头」，服务端按前缀（startswith）匹配：字头「甲」命中「甲刀01」，不命中「乙刀01」。</li>
          <li>条件留空或点「清空条件」即回到整表，两笔都会露脸。</li>
          <li>命中表与复核列表走同一后台接口、同一取数口径；每次切换预设/清空都重新请求后台，前端不私下藏行。</li>
          <li>预设保存在后台，操作员与复核员都能新建并一点切换；仅创建人可删除自己的预设。</li>
          <li>预设的新建与删除都记入下方改动流水；删预设只删预设本身，流水长期留痕、不得抹除。</li>
        </ul>
      </section>

      <section class="card">
        <h2>预设改动流水</h2>
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>动作</th>
              <th>预设称呼</th>
              <th>字头</th>
              <th>操作人</th>
            </tr>
          </thead>
          <tbody>
            <For each={logs()}>
              {(log) => (
                <tr>
                  <td>{new Date(log.created_at).toLocaleString()}</td>
                  <td class={log.action === "delete" ? "fail" : "pass"}>
                    {actionLabel[log.action] || log.action}
                  </td>
                  <td>{log.preset_name}</td>
                  <td>{log.prefix}</td>
                  <td>{log.actor_name}</td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
        <Show when={!logs().length}>
          <p class="hint">暂无改动流水</p>
        </Show>
      </section>
    </>
  );
}

export default ScreenPage;
