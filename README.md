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

## 验收

1. machinist 登录后，种子数据应显示刀具 T01 合格（刀补 5 µm）、T09 超差（刀补 20 µm）。
2. 提交一条新刀补后，状态先为「待复核」，数秒内 worker 处理为「已完成」并给出结论。
3. auditor 登录后只能看列表，没有提交表单。

## 筛查台（按刀号筛查预设）

菜单「筛查台」进入专页，包含字头输入框、命名预设、命中表、口径说明与改动流水。

- 命中表与复核总览共用同一列表查询接口 `GET /api/submissions`，字头过滤由服务端完成（`?tool_prefix=甲`），前端不私下藏行。
- 操作员与复核员都能新建命名预设；点名预设即按其字头由后台重新拉数；清空条件回到整表。
- 预设的新建与删除都记入改动流水，删除与写流水在同一事务；流水留存称呼与字头快照，删预设后痕迹仍在。
- 只能删除自己创建的预设，复核员不得抹掉别人的预设（服务端返回 403）。

接口：`GET/POST /api/presets`、`DELETE /api/presets/{id}`、`GET /api/preset-logs`。

验收流程：先各交甲刀乙刀各一笔 → 建字头为「甲」的预设 → 甲列表只剩甲刀 → 清空条件后两笔都露脸 → 删掉预设甲后流水留有新建与删除两条痕迹。

## 测试

无 PostgreSQL 时可用 SQLite 配置跑验收测试：

```bash
cd backend
python manage.py test --settings=config.test_settings
```

## 目录

```text
backend/          Django 工程（config/、desk/、worker.py）
frontend/         SolidJS 单页
docker-compose.yml
PRD.md
```
