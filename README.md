# Atoms Demo

自然语言 → 多智能体编排 → 生成完整 Web 项目 → 真实 URL 预览。

一个迷你版 [Atoms](https://atoms.dev/)：输入一句需求，Planner 判断应该做纯前端、前后端一体还是纯后端 API；Coder 生成 Vite + React + TypeScript 页面与 FastAPI + SQLite 接口；Reviewer 检查并自动回修；Deployer 发布静态预览、启动项目自己的后端进程。全程 SSE 实时展示，生成后可以继续对话修改。

## 技术栈

- 前端：Vite + React 18 + TypeScript + Tailwind CSS（Atoms 工作台本身）
- 后端：Python 3.11 + FastAPI + uvicorn（单 worker）
- 数据库：SQLite（WAL），Atoms 自己的库在 `backend/data/atoms.db`
- 实时通信：SSE（`StreamingResponse`），不用 WebSocket
- 部署：Docker Compose + Nginx，单机 2C2G
- LLM：DeepSeek（OpenAI 兼容接口）远程流式调用；无 Key 自动 Mock

## 生成物形态

Planner 根据需求选择三种形态：

| 形态 | 何时使用 | 生成物 |
| --- | --- | --- |
| `frontend` | 落地页、官网、纯展示页面 | Vite + React 18 + TS 前端 |
| `fullstack` | 需要保存数据、CRUD、账号、订单、留言等 | 前端 + FastAPI 后端 + SQLite |
| `backend` | 用户明确只要后端 / API | FastAPI 后端 + SQLite |

生成的项目是一个可独立运行的完整仓库：

```
apps/{project_id}/
├── frontend/                    # 仅 frontend/fullstack 形态
│   ├── package.json
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx             # 系统生成
│       ├── App.tsx              # LLM 生成
│       ├── styles.css           # LLM 生成
│       └── ...                  # 按需的组件 / hooks
├── backend/                     # 仅 backend/fullstack 形态
│   ├── main.py                  # LLM 生成（FastAPI 路由）
│   ├── db.py                    # 系统生成（SQLite 路径与迁移）
│   ├── schema.sql               # 由 Planner 的数据模型生成
│   ├── requirements.txt
│   └── data/app.db              # 项目自己的 SQLite，随项目目录持久化
├── README.md
└── .gitignore
```

所有前端请求统一使用相对路径 `api/...`。预览时页面有 `<base href="/apps/{id}/">`，因此同一个前端源码在本地 Vite、独立部署和 Atoms 子路径预览下都能工作。

## 架构

```
浏览器 (React 工作台)
 ├─ POST /api/projects/{id}/generate ──► FastAPI
 │                                        ├─► Planner   (判断形态 / 数据模型 / API 合约)
 │                                        ├─► Scaffold  (确定性生成 Vite/FastAPI/SQLite 基础文件)
 │                                        ├─► Coder     (逐个应用文件流式生成)
 │                                        ├─► Reviewer  (结构、样式、API 路径、构建检查)
 │                                        └─► Deployer  (写文件 + 构建预览 + 启动项目后端)
 │◄────────── SSE: execution / token / artifact / preview / message / done
 │
 ├─ SQLite (WAL): projects / conversations / artifacts / executions
 │
 ├─ iframe /apps/{id}/ ───────────────► Nginx ──► FastAPI 预览静态文件
 │                                        └─► /apps/{id}/api/* ──► 项目 uvicorn 进程
 │
 └─ 项目 SQLite: apps/{id}/backend/data/app.db（与 demo 数据库完全隔离）
```

运行时细节：

- 每个 fullstack/backend 项目启动一个独立的 `uvicorn main:app` 子进程，只监听 `127.0.0.1` 的随机端口。
- 生成的数据库路径固定为 `Path(__file__).parent / "data" / "app.db"`，即 `apps/{id}/backend/data/app.db`；重写项目代码时会保留该目录。
- 最多同时运行 `MAX_RUNNING_APPS` 个项目后端（默认 2），超出按 LRU 停掉最久未用的进程；数据不丢，下次请求自动拉起。
- 子进程有内存上限（Linux `RLIMIT_AS`，默认 256MB），且环境变量被裁剪，不会拿到 demo 的 `LLM_API_KEY`。
- 前端预览由共享的 esbuild 工具链在发布时打包，不针对每个项目执行 `npm install`；生成仓库本身仍然是标准 Vite 项目，用户本地可以 `npm install && npm run dev/build`。

可靠性设计：

- DeepSeek 单次输出上限 8K token。文件被 `finish_reason=length` 截断时，自动携带已生成内容请求**续写**；续写后仍不完整则整轮回退到一致的 Mock 模板，绝不发布半截页面。
- Reviewer 检查文件完整性、样式缺口、移动端媒体查询、前端是否调用后端 API、API 路径是否以 `/` 开头、Python 语法等；命中后自动让 Coder 回修。
- 前端预览用 esbuild 做真实构建；构建失败时先带着错误信息回修对应文件，仍失败则整轮回退 Mock 模板。
- 后端启动失败时读取 `.runtime.log` 回修 `main.py`，仍失败则整轮回退 Mock 模板。
- 真实生成约 60–180s（含多文件生成与自动回修），Mock 模式 < 5s。

## 本地开发

要求：Python 3.11+、Node 20+。

```bash
# 1. 配置（不填 Key 也能跑 Mock）
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 LLM_API_KEY

# 2. 预览构建工具链（一次即可；Docker 镜像内已预装）
npm --prefix backend/runtime/frontend install

# 3. 后端
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000

# 4. 前端（另开终端）
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173 。前端 dev server 会把 `/api`、`/apps` 代理到 8000，并允许沙箱 iframe 的 `Origin: null` 预检请求。

### 环境变量（`backend/.env`）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_API_KEY` | 空 | 为空时使用 Mock Agent |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容地址 |
| `LLM_MODEL` | `deepseek-flash` | 模型名 |
| `LLM_TIMEOUT` | `180` | 流式读取超时（秒） |
| `DATA_DIR` | `backend/data` | demo SQLite 与生成项目根目录 |
| `MAX_RUNNING_APPS` | `2` | 同时运行的生成项目后端数量 |
| `GENERATED_APP_MEMORY_MB` | `256` | 单个生成后端的内存上限（Linux） |
| `RUNTIME_START_TIMEOUT` | `20` | 生成后端启动等待秒数 |
| `FRONTEND_BUILD_TIMEOUT` | `120` | 预览构建超时秒数 |
| `PREVIEW_NODE_MODULES` | `backend/runtime/frontend/node_modules` | 共享 esbuild / React 工具链位置 |

## Docker 部署

```bash
cp backend/.env.example backend/.env   # 填入 Key（可留空跑 Mock）
docker compose up -d --build
```

打开 `http://服务器IP/` 。`backend/data/` 是宿主机挂载卷，容器重建后项目、demo SQLite 与每个项目自己的 SQLite 都保留。

- `web`：Nginx，托管工作台构建产物，反代 `/api/` 与 `/apps/`；SSE 与生成项目 API 都关闭了缓冲。
- `backend`：FastAPI 单 worker + Node 共享 esbuild 工具链；内存上限 1G，生成项目后端另受 LRU 与单进程内存上限约束。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查，返回 LLM 模式与运行中的项目 |
| GET | `/api/projects` | 项目列表（含 `mode`） |
| POST | `/api/projects` | 创建项目 `{prompt?, name?}` |
| GET | `/api/projects/{id}` | 完整状态（对话、最新文件、执行记录、`mode`、`preview_url`） |
| DELETE | `/api/projects/{id}` | 删除项目、生成物并停止其运行时 |
| POST | `/api/projects/{id}/generate` | `{message}`，返回 SSE 流 |
| GET | `/apps/{id}/` | 已发布项目预览 |
| GET/POST/... | `/apps/{id}/api/*` | 代理到该项目自己的 FastAPI 后端 |
| GET | `/apps/{id}/docs` | 生成项目的 Swagger 文档 |

SSE 事件：

| event | payload |
| --- | --- |
| `execution` | `{id, agent, step, status, log}`，`status: running/success/warning/error` |
| `token` | `{filename, delta}` 流式代码片段 |
| `file_start` | `{filename, purpose}` 开始写某个文件 |
| `artifact` | `{filename, content, version}` 文件完成 |
| `preview` | `{url, version, mode}` 已发布 |
| `message` | `{role, content}` 助手总结 |
| `error` | `{message}` |
| `done` | `{project_id}` |

## 演示脚本

1. 首页输入「做一个团队任务看板，支持新增/完成/筛选，数据保存到 SQLite」→ 时间线依次出现 Planner（判定 fullstack）、Scaffold、Coder×N、Reviewer（可能自动回修）、Deployer（构建预览 + 启动运行时）→ 右侧 iframe 出现可交互应用。
2. 在应用里新增几条任务 → 刷新页面 / 刷新 iframe → 数据仍在（来自 `apps/{id}/backend/data/app.db`）。
3. 继续输入「加一个按负责人筛选」→ 生成 v2，前端与后端一起更新，已有任务不丢。
4. 输入「做一个 SaaS 产品落地页，纯展示，不要后端」→ Planner 判定 frontend，只生成前端，`/api` 返回 404。
5. 输入「做一个记账 API，只要后端」→ Planner 判定 backend，右侧显示内置 API 控制台与 Swagger 文档链接。
6. 清空 `LLM_API_KEY` 重启 → 同一条链路走 Mock 模板，UI 无感知，时间线标注降级。

## 验收对照

- [x] 打开 IP 直接用，无需注册登录
- [x] 需求 → Agent 时间线 → 代码 → iframe 预览
- [x] Planner 按需选择 frontend / fullstack / backend
- [x] 生成 Vite + React 18 + TypeScript 前端与 FastAPI + SQLite 后端
- [x] 每个项目独立 SQLite：`apps/{id}/backend/data/app.db`，与 demo `atoms.db` 隔离
- [x] 全栈项目在沙箱 iframe 中真实调用后端（CORS + 相对路径）
- [x] 刷新/重启后项目与业务数据都保留
- [x] 对话续改（版本递增、按 need 更新前后端、其余文件合并保留、SQLite 数据保留）
- [x] 无 Key 可降级 Mock；运行中 LLM 失败整轮回退为一致的 Mock 模板
- [x] Docker Compose + Nginx + 内存上限与运行时 LRU

## 设计边界与安全说明

- 不做真实鉴权/多用户；不做 Stripe 支付；不接 Kafka/Redis/ES。
- 生成的前端运行在 `sandbox` iframe 中（不含 `allow-same-origin`），通过 CORS 访问自己的后端。
- 生成的后端是**在本机（Docker 容器内）执行的不可信代码**：它有内存上限、只监听 127.0.0.1、环境变量被裁剪，但没有真正的进程/文件系统沙箱。这个 demo 定位为单用户演示；生产化需要把每个项目放进独立容器或 microVM。
- 不执行 `npm install` 级别的服务端构建；预览用共享 esbuild 打包生成的前端源码。
