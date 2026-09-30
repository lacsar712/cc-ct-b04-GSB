# 数控刀补复核台

操作员提交刀具编号与刀补微米值；后台 worker 用 PostgreSQL 行锁（`select_for_update(skip_locked=True)`）认领待复核记录，按绝对值是否不超过 12 微米给出「合格」或「超差」。

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Django 5 + django-ninja（ASGI / uvicorn） |
| 前端 | SolidJS + Vite，nginx 反代 `/api` |
| 数据库 | PostgreSQL 16 |
| 鉴权 | JWT（python-jose），令牌存浏览器 localStorage |

## 端口

| 服务 | 地址 |
|------|------|
| 页面 | http://localhost:3196 |
| 接口 | http://localhost:8196 |
| PostgreSQL | localhost:54396（库名 `cncoffset`） |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| machinist | machine123456 | 可提交刀补 |
| auditor | audit123456 | 只读列表 |

## 启动

```bash
cd projects/17-cnc-tool-offset-desk
docker compose up --build
```

健康检查：`GET http://localhost:8196/api/health` → `{"status":"ok"}`

## 筛查台（按刀号字头）

顶栏「筛查台」（`#/screen`）提供按刀号字头（刀具编号前缀）的后台筛查：

- 字头输入框提交后由服务端 `startswith` 过滤；清空条件即回整表。命中表与复核列表同源（`GET /api/submissions?tool_prefix=`），前端不藏行。
- 操作员、复核员均可新建命名预设（`POST /api/presets`），一点切换即按预设字头重新向后台拉数；只能删除本人新建的预设（`DELETE /api/presets/{id}`，跨人删除返回 403）。
- 预设的新建/删除写入改动流水（`GET /api/preset-logs`）；删除预设与写流水在同一数据库事务内，流水只追加、不可抹除。

## 验收

1. machinist 登录后，种子数据应显示刀具 T01 合格（刀补 5 µm）、T09 超差（刀补 20 µm）。
2. 提交一条新刀补后，状态先为「待复核」，数秒内 worker 处理为「已完成」并给出结论。
3. auditor 登录后只能看列表，没有提交表单。
4. 筛查台：machinist 各交「甲刀」「乙刀」一笔，新建字头为「甲」的命名预设后命中表只剩甲刀；清空条件后两笔都在；删除该预设后改动流水同时留下新建与删除痕迹。

## 目录

```text
backend/          Django 工程（config/、desk/、worker.py）
frontend/         SolidJS 单页
docker-compose.yml
PRD.md
```
