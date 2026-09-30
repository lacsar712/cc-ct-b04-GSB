import { createSignal, onMount, Show, For, createEffect } from "solid-js";
import {
  clearSession,
  createPreset,
  createSubmission,
  deletePreset,
  fetchPresetLogs,
  fetchPresets,
  fetchSubmission,
  fetchSubmissions,
  getUser,
  login,
  setSession,
} from "./api";

const statusLabel = {
  pending: "待复核",
  processing: "复核中",
  done: "已完成",
};

const roleLabel = {
  machinist: "操作员",
  auditor: "复核员",
};

const presetActionLabel = {
  create: "新建",
  delete: "删除",
};

function readHash() {
  const raw = (location.hash || "#/").replace(/^#/, "") || "/";
  const m = raw.match(/^\/detail\/(\d+)/);
  if (m) return { name: "detail", id: Number(m[1]) };
  if (raw === "/screening") return { name: "screening", id: null };
  return { name: "home", id: null };
}

function App() {
  const [user, setUser] = createSignal(getUser());
  const [rows, setRows] = createSignal([]);
  const [detail, setDetail] = createSignal(null);
  const [route, setRoute] = createSignal(readHash());
  const [error, setError] = createSignal("");
  const [loading, setLoading] = createSignal(false);

  const [loginUser, setLoginUser] = createSignal("machinist");
  const [loginPass, setLoginPass] = createSignal("machine123456");

  const [toolCode, setToolCode] = createSignal("");
  const [offsetUm, setOffsetUm] = createSignal("");

  function goHome() {
    location.hash = "#/";
  }

  function goDetail(id) {
    location.hash = `#/detail/${id}`;
  }

  function goScreening() {
    location.hash = "#/screening";
  }

  async function loadRows() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchSubmissions();
      setRows(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(id) {
    setLoading(true);
    setError("");
    try {
      setDetail(await fetchSubmission(id));
    } catch (e) {
      setError(e.message);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }

  onMount(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    if (user()) {
      if (route().name === "detail") loadDetail(route().id);
      else loadRows();
    }
    return () => window.removeEventListener("hashchange", onHash);
  });

  createEffect(() => {
    const r = route();
    if (!user()) return;
    if (r.name === "detail" && r.id) loadDetail(r.id);
    if (r.name === "home") loadRows();
  });

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await login(loginUser(), loginPass());
      setSession(data.token, {
        username: data.username,
        role: data.role,
        can_write: data.can_write,
      });
      setUser(getUser());
      goHome();
      await loadRows();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setRows([]);
    setDetail(null);
    goHome();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      await createSubmission(toolCode(), offsetUm());
      setToolCode("");
      setOffsetUm("");
      await loadRows();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <h1>数控刀补复核台</h1>
          <p class="hint">刀补绝对值不超过十二微米判合格，否则超差。后台认领进程用行锁跳过已占行领取待复核。</p>
        </div>
        <Show when={user()}>
          <nav class="topnav">
            <a
              href="#/"
              class={route().name === "home" ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                goHome();
              }}
            >
              复核总览
            </a>
            <a
              href="#/screening"
              class={route().name === "screening" ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                goScreening();
              }}
            >
              筛查台
            </a>
          </nav>
        </Show>
      </header>

      <Show when={error()}>
        <div class="banner error">{error()}</div>
      </Show>

      <Show
        when={user()}
        fallback={
          <section class="card">
            <h2>登录</h2>
            <form onSubmit={handleLogin} class="form">
              <label>
                用户名
                <input
                  value={loginUser()}
                  onInput={(e) => setLoginUser(e.currentTarget.value)}
                />
              </label>
              <label>
                密码
                <input
                  type="password"
                  value={loginPass()}
                  onInput={(e) => setLoginPass(e.currentTarget.value)}
                />
              </label>
              <button type="submit">进入系统</button>
            </form>
            <p class="hint">操作员 machinist / machine123456；复核员 auditor / audit123456（只读）</p>
          </section>
        }
      >
        <section class="card toolbar">
          <div>
            当前用户：<strong>{user().username}</strong>（{roleLabel[user().role] || user().role}）
          </div>
          <button type="button" class="ghost" onClick={handleLogout}>
            退出
          </button>
        </section>

        <Show when={route().name === "home"}>
          <Show when={user().can_write}>
            <section class="card">
              <h2>提交刀补</h2>
              <form onSubmit={handleSubmit} class="form inline">
                <label>
                  刀具编号
                  <input
                    placeholder="如 T01"
                    value={toolCode()}
                    onInput={(e) => setToolCode(e.currentTarget.value)}
                    required
                  />
                </label>
                <label>
                  刀补（微米）
                  <input
                    type="number"
                    value={offsetUm()}
                    onInput={(e) => setOffsetUm(e.currentTarget.value)}
                    required
                  />
                </label>
                <button type="submit">提交待复核</button>
              </form>
            </section>
          </Show>

          <section class="card">
            <div class="toolbar">
              <h2>复核列表</h2>
              <button type="button" class="ghost" onClick={loadRows} disabled={loading()}>
                {loading() ? "刷新中…" : "刷新"}
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
                  <th></th>
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
                      <td>
                        <button type="button" class="ghost" onClick={() => goDetail(row.id)}>
                          详情
                        </button>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={!rows().length && !loading()}>
              <p class="hint">暂无记录</p>
            </Show>
          </section>
        </Show>

        <Show when={route().name === "detail"}>
          <section class="card">
            <div class="toolbar">
              <h2>刀补详情</h2>
              <button type="button" class="ghost" onClick={goHome}>
                返回总览
              </button>
            </div>
            <Show when={detail()} fallback={<p class="hint">{loading() ? "加载中…" : "未找到记录"}</p>}>
              {(d) => (
                <div class="detail-grid">
                  <p>编号：{d().id}</p>
                  <p>刀具：{d().tool_code}</p>
                  <p>刀补 µm：{d().offset_um}</p>
                  <p>状态：{statusLabel[d().status] || d().status}</p>
                  <p class={d().verdict === "合格" ? "pass" : d().verdict === "超差" ? "fail" : ""}>
                    结论：{d().verdict || "—"}
                  </p>
                  <p>提交时间：{new Date(d().created_at).toLocaleString()}</p>
                  <p>
                    复核时间：
                    {d().reviewed_at ? new Date(d().reviewed_at).toLocaleString() : "—"}
                  </p>
                </div>
              )}
            </Show>
          </section>
        </Show>
        <Show when={route().name === "screening"}>
          <ScreeningDesk user={user()} />
        </Show>
      </Show>
    </div>
  );
}

function ScreeningDesk(props) {
  const [prefixInput, setPrefixInput] = createSignal("");
  const [appliedPrefix, setAppliedPrefix] = createSignal("");
  const [hits, setHits] = createSignal([]);
  const [presets, setPresets] = createSignal([]);
  const [logs, setLogs] = createSignal([]);
  const [presetName, setPresetName] = createSignal("");
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal("");

  async function loadHits(prefix) {
    // 命中表与复核总览共用同一个列表查询接口，字头交给服务端过滤，前端不私下藏行
    setHits(await fetchSubmissions(prefix));
  }

  async function loadPresets() {
    setPresets(await fetchPresets());
  }

  async function loadLogs() {
    setLogs(await fetchPresetLogs());
  }

  async function refreshAll() {
    setBusy(true);
    setError("");
    try {
      await Promise.all([loadHits(appliedPrefix()), loadPresets(), loadLogs()]);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  onMount(refreshAll);

  async function applyPrefix(prefix) {
    const p = (prefix ?? prefixInput()).trim();
    setPrefixInput(p);
    setAppliedPrefix(p);
    setError("");
    try {
      await loadHits(p);
    } catch (e) {
      setError(e.message);
    }
  }

  async function clearCondition() {
    setPrefixInput("");
    setAppliedPrefix("");
    setError("");
    try {
      await loadHits("");
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleCreatePreset(e) {
    e.preventDefault();
    setError("");
    try {
      await createPreset(presetName().trim(), prefixInput().trim());
      setPresetName("");
      await Promise.all([loadPresets(), loadLogs()]);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeletePreset(preset) {
    setError("");
    try {
      await deletePreset(preset.id);
      await Promise.all([loadPresets(), loadLogs()]);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <Show when={error()}>
        <div class="banner error">{error()}</div>
      </Show>

      <section class="card">
        <h2>筛查条件</h2>
        <form
          class="form inline"
          onSubmit={(e) => {
            e.preventDefault();
            applyPrefix();
          }}
        >
          <label>
            刀号字头
            <input
              placeholder="如 甲 或 T0"
              value={prefixInput()}
              onInput={(e) => setPrefixInput(e.currentTarget.value)}
            />
          </label>
          <button type="submit">应用筛查</button>
          <button type="button" class="ghost" onClick={clearCondition}>
            清空条件
          </button>
        </form>
        <p class="hint">
          当前条件：
          {appliedPrefix() ? `字头「${appliedPrefix()}」` : "无（整表）"}
          ；切换或清空都会由后台重新拉数。
        </p>
      </section>

      <section class="card">
        <h2>命名预设</h2>
        <Show when={presets().length} fallback={<p class="hint">暂无预设，可用下方表单新建。</p>}>
          <ul class="preset-list">
            <For each={presets()}>
              {(preset) => (
                <li class="preset-item">
                  <button
                    type="button"
                    class={appliedPrefix() === preset.tool_prefix ? "preset-btn active" : "preset-btn"}
                    title={`按字头「${preset.tool_prefix}」筛查`}
                    onClick={() => applyPrefix(preset.tool_prefix)}
                  >
                    {preset.name}
                    <span class="preset-prefix">字头「{preset.tool_prefix}」</span>
                  </button>
                  <span class="hint">由 {preset.created_by || "—"} 创建</span>
                  <Show when={preset.created_by === props.user.username}>
                    <button
                      type="button"
                      class="ghost danger"
                      onClick={() => handleDeletePreset(preset)}
                    >
                      删除
                    </button>
                  </Show>
                </li>
              )}
            </For>
          </ul>
        </Show>
        <form class="form inline" onSubmit={handleCreatePreset}>
          <label>
            预设称呼
            <input
              placeholder="给当前字头的预设起个名"
              value={presetName()}
              onInput={(e) => setPresetName(e.currentTarget.value)}
              required
            />
          </label>
          <button type="submit" disabled={!prefixInput().trim()}>
            保存当前字头为预设
          </button>
        </form>
        <p class="hint">
          操作员与复核员都可新建；保存的字头来自上方输入框（当前：
          {prefixInput().trim() ? `「${prefixInput().trim()}」` : "未填写"}）。
        </p>
      </section>

      <section class="card">
        <div class="toolbar">
          <h2>命中表</h2>
          <button type="button" class="ghost" onClick={refreshAll} disabled={busy()}>
            {busy() ? "刷新中…" : "刷新"}
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
            <For each={hits()}>
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
        <Show when={!hits().length && !busy()}>
          <p class="hint">当前条件下无命中记录</p>
        </Show>
      </section>

      <section class="card">
        <h2>口径说明</h2>
        <ul class="rules">
          <li>命中表与复核总览共用同一列表查询接口（GET /api/submissions），字头过滤在服务端按刀具编号前缀完成，前端不私下藏行。</li>
          <li>点名预设即按其字头重新向后台拉数；清空条件则回到整表。</li>
          <li>预设的新建与删除都会记入改动流水，删除与记流水在同一事务，流水留存预设称呼与字头快照。</li>
          <li>只能删除自己创建的预设，复核员不得抹掉别人的预设。</li>
        </ul>
      </section>

      <section class="card">
        <h2>改动流水</h2>
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
                  <td>{presetActionLabel[log.action] || log.action}</td>
                  <td>{log.preset_name}</td>
                  <td>{log.tool_prefix}</td>
                  <td>{log.actor || "—"}</td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
        <Show when={!logs().length && !busy()}>
          <p class="hint">暂无改动流水</p>
        </Show>
      </section>
    </>
  );
}

export default App;
