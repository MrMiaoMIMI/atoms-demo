# Atoms Demo

自然语言 → 多智能体编排 → 生成完整 Web 项目 → 真实 URL 预览。

一个迷你版 [Atoms](https://atoms.dev/)：三位智能体分工协作——**Mike（团队领导）**理解需求、拆解任务并决定下一位；**Bob（架构师）**判断形态、数据模型与 API；**Alex（工程师）**生成 Vite + React + TypeScript 页面、FastAPI + SQLite 接口，并完成自检、预览构建与后端启动。对话按智能体分组，支持输入 `@` 指定成员；构建类请求按依赖顺序串行交接，咨询类请求由被 @ 的成员并行回答。全程 SSE 实时展示，生成后可以继续对话修改。

## 技术栈

- 前端：Vite + React 18 + TypeScript + Tailwind CSS（Atoms 工作台本身）
- 后端：Python 3.11 + FastAPI + uvicorn（单 worker）
- 数据库：SQLite（WAL），Atoms 自己的库在 `backend/data/atoms.db`
- 实时通信：SSE（`StreamingResponse`），不用 WebSocket
- 部署：Docker Compose + Nginx，单机 2C2G
- LLM：DeepSeek（OpenAI 兼容接口）远程流式调用；无 Key 自动 Mock

## 生成物形态

Bob 根据需求选择三种形态：

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
│   ├── schema.sql               # 由 Bob 的数据模型生成
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
 │                                        ├─ 意图判断：build / consult
 │                                        ├─ build: Mike → (Bob | Alex)，尾部 @ 交接
 │                                        │    Mike: 需求拆解 / 复杂度判断
 │                                        │    Bob:  形态 / 数据模型 / API / 文件清单
 │                                        │    Alex: 脚手架 / 代码 / 回修 / 预览 / 运行时
 │                                        └─ consult: 被 @ 的角色并行回答，不修改文件
 │◄────────── SSE: project / agent_start / execution / token / artifact / preview / message / agent_end / done
 │
 ├─ SQLite (WAL): projects / conversations(agent, run_id, run_index) / artifacts / executions(run_id)
 │
 ├─ iframe /apps/{id}/ ───────────────► Nginx ──► FastAPI 预览静态文件
 │                                        └─► /apps/{id}/api/* ──► 项目 uvicorn 进程
 │
 └─ 项目 SQLite: apps/{id}/backend/data/app.db（与 demo 数据库完全隔离）
```

### 多智能体编排

> `@` 分派的完整调研、问题演进与取舍见 [docs/atoms-mention-design.md](docs/atoms-mention-design.md)。

| 角色 | 职责 | 可用工具（由 Toolbox 白名单强制） |
| --- | --- | --- |
| **Mike** 团队领导 | 理解需求、拆解任务、判断复杂度、选择下一位 | `read_project_state` |
| **Bob** 架构师 | 形态判断、数据模型、API 合约、文件规划 | `read_project_state`、`validate_plan` |
| **Alex** 工程师 | 脚手架、代码生成、自检回修、预览构建、后端运行时 | `read_project_state`、`read_file`、`write_file`、`publish_files`、`build_preview`、`start_runtime`、`check_health` |

- **按 @ 分段**：一条消息可以给不同角色分配不同问题，后端按 `@` 位置切段，每个 Agent 只拿到自己名下的文本；同一 Agent 的多个问题合并成一轮。
  - 未被 @ 的独立问题默认交给 Mike（团队领导）；`请/麻烦/帮我` 这类连接词会附着到第一个被 @ 的角色。
  - 含 `你们/大家/两位/两个人/分别/各自/每个人` 的句子由所有被 @ 的角色共同处理。
  - 示例：`今天天气怎么样？` + `@Alex 介绍下NBA的湖人队？` + `@Mike 曹操是谁？` + `你们2个人介绍下当前项目` → Mike 回答天气、曹操、项目介绍；Alex 回答湖人队、项目介绍，两人都不会收到对方专属的问题。
- **意图分流**：构建类请求（做/改/修复/部署等）按 Mike → Bob → Alex 的依赖顺序执行；咨询类请求（介绍/说明/分析/问答）由被 @ 的角色并行回答，不改文件。混合消息按出现顺序执行，构建后会刷新项目快照再处理后续咨询。
- **尾部交接**：任意角色的最终答复最后一行用 `@Bob` / `@Alex` 指定下一位；后端只解析最后一行，正文里的 @ 不触发交接。
- **循环保护**：待执行队列去重、忽略自交接、单角色单轮最多 2 次、整轮最多 5 次 Agent run；达到上限时在当前 group 记录 warning。
- **按智能体分组**：对话与执行记录都持久化 `agent + run_id + run_index`，刷新后仍按“一个智能体一个 group”重建；同一 Agent 的多步操作聚合在「已处理 N 步」里。
- **不用 LangChain / LangGraph**：编排拓扑固定且规模小（3 个角色、有界交接），这里用显式状态机 + 尾部 @ 路由 + SQLite checkpoint；工具是进程内 Python 函数，由 `Toolbox` 做角色白名单，不使用 MCP。引入框架会增加依赖、内存与 SSE 事件映射成本，当前收益不大。

运行时细节：

- 每个 fullstack/backend 项目启动一个独立的 `uvicorn main:app` 子进程，只监听 `127.0.0.1` 的随机端口。
- 生成的数据库路径固定为 `Path(__file__).parent / "data" / "app.db"`，即 `apps/{id}/backend/data/app.db`；重写项目代码时会保留该目录。
- 最多同时运行 `MAX_RUNNING_APPS` 个项目后端（默认 2），超出按 LRU 停掉最久未用的进程；数据不丢，下次请求自动拉起。
- 子进程有内存上限（Linux `RLIMIT_AS`，默认 256MB），且环境变量被裁剪，不会拿到 demo 的 `LLM_API_KEY`。
- 前端预览由共享的 esbuild 工具链在发布时打包，不针对每个项目执行 `npm install`；生成仓库本身仍然是标准 Vite 项目，用户本地可以 `npm install && npm run dev/build`。

可靠性设计：

- 所有 LLM 调用失败按 `LLM_MAX_RETRIES`（默认首次失败后再重试 3 次）与指数退避重试；仍失败则**回滚本轮**、保留上一个可用版本并向前端报错，不再静默替换成 Mock 模板。
- 单次请求的输出预算由 `LLM_MAX_TOKENS` 控制（默认 16384；若上游返回 400 会自动降回 8192）。文件被 `finish_reason=length` 截断时，自动携带已生成内容请求**续写**，最多 `LLM_CONTINUATION_PASSES`（默认 3）次；仍不完整则进入上述重试/回滚流程，绝不发布半截页面。
- 生成完成后做大小检查：超过 12,000 字符在时间线告警；超过 20,000 字符的前端 TS/TSX 会尝试自动拆分为 `components/` / `hooks/`。拆分失败只告警，不阻塞本轮。
- Alex 在实现阶段自检文件完整性、样式缺口、移动端媒体查询、前端是否调用后端 API、API 路径是否以 `/` 开头、Python 语法等；命中后自动回修。
- 前端预览用 esbuild 做真实构建；构建失败时先带着当前文件内容与错误信息回修，仍失败则回滚到上一个可用版本并展示错误横幅。
- 后端启动失败时读取 `.runtime.log` 回修 `main.py`，仍失败同样回滚并报错。
- 真实生成约 60–180s（含多文件生成与自动回修），Mock 演示模式 < 5s。

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
| POST | `/api/projects` | 创建项目 `{prompt?, name?}`；省略 `name` 时后台用 LLM 把首条需求概括为短名称 |
| GET | `/api/projects/{id}` | 完整状态（对话、最新文件、执行记录、`mode`、`preview_url`） |
| DELETE | `/api/projects/{id}` | 删除项目、生成物并停止其运行时 |
| POST | `/api/projects/{id}/generate` | `{message}`，返回 SSE 流 |
| GET | `/api/projects/{id}/export` | 下载最新源代码 ZIP 仓库包（`Content-Disposition: attachment`） |
| GET | `/apps/{id}/` | 已发布项目预览 |
| GET/POST/... | `/apps/{id}/api/*` | 代理到该项目自己的 FastAPI 后端 |
| GET | `/apps/{id}/docs` | 生成项目的 Swagger 文档 |

SSE 事件：

| event | payload |
| --- | --- |
| `project` | `{id, name}` 项目名（后台 LLM 概括首条需求后回填） |
| `agent_start` | `{run_id, agent, name, role, index}` 某个智能体开始一轮 |
| `execution` | `{id, run_id, agent, step, status, log}`，`status: running/success/warning/error` |
| `token` | `{filename, delta, run_id}` 流式代码片段 |
| `file_start` | `{filename, purpose, run_id}` 开始写某个文件 |
| `artifact` | `{filename, content, version, run_id}` 文件完成 |
| `preview` | `{url, version, mode}` 已发布 |
| `message` | `{role, agent, run_id, run_index, content}` 该智能体的最终答复 |
| `agent_end` | `{run_id, agent, status}` 一轮结束 |
| `error` | `{message}` |
| `done` | `{project_id}` |

## 演示脚本

1. 首页输入「做一个团队任务看板，支持新增/完成/筛选，数据保存到 SQLite」→ 对话按智能体分组：Mike（拆解 + 判定复杂度）→ Bob（形态 / 数据模型 / API）→ Alex（脚手架、代码、回修、构建预览、启动运行时）→ 右侧 iframe 出现可交互应用。
2. 在应用里新增几条任务 → 刷新页面 / 刷新 iframe → 数据仍在（来自 `apps/{id}/backend/data/app.db`）。
3. 继续输入「加一个按负责人筛选」→ Mike 判断改动范围，生成 v2，已有任务不丢。
4. 输入 `@Alex 把主按钮文案改成「立即联系」` → 只出现 Alex 的 group，直接修改前端并刷新预览。
5. 输入 `@Mike @Bob @Alex 简单介绍下这个项目` → 三个 group 并行返回产品、架构、实现三个视角，不修改任何文件。
6. 输入 `@Alex 今天天气怎么样？` 换行 `@Mike 曹操是谁？` → 后端按 @ 切段，Alex 只收到天气问题、Mike 只收到曹操问题，各自回答自己的那一段。
7. 输入「今天天气怎么样？」→ 识别为咨询，Mike 回答并明确说明没有接入实时外部数据，不会触发构建。
8. 清空 `LLM_API_KEY` 重启 → 进入 Mock 演示模式：链路照常执行，但生成明确标注的中性占位页，不会伪装成需求中的应用。

## 验收对照

- [x] 打开 IP 直接用，无需注册登录
- [x] 需求 → 按智能体分组的执行时间线 → 代码 → iframe 预览
- [x] Mike / Bob / Alex 三角色分工，构建链按依赖顺序交接
- [x] 输入 `@` 指定智能体，支持多 @；咨询类请求并行回答且不修改文件
- [x] Bob 按需选择 frontend / fullstack / backend
- [x] 生成 Vite + React 18 + TypeScript 前端与 FastAPI + SQLite 后端
- [x] 每个项目独立 SQLite：`apps/{id}/backend/data/app.db`，与 demo `atoms.db` 隔离
- [x] 全栈项目在沙箱 iframe 中真实调用后端（CORS + 相对路径）
- [x] 刷新/重启后项目、对话分组与业务数据都保留
- [x] 对话续改（版本递增、按 need 更新前后端、其余文件合并保留、SQLite 数据保留）
- [x] 无 Key 提供 Mock 演示占位页；LLM 失败按配置重试，最终失败回滚并保留上一个可用版本（含前端构建 / 后端启动失败）
- [x] Docker Compose + Nginx + 内存上限与运行时 LRU

## 设计边界与安全说明

- 不做真实鉴权/多用户；不做 Stripe 支付；不接 Kafka/Redis/ES。
- 生成的前端运行在 `sandbox` iframe 中（不含 `allow-same-origin`），通过 CORS 访问自己的后端。
- 生成的后端是**在本机（Docker 容器内）执行的不可信代码**：它有内存上限、只监听 127.0.0.1、环境变量被裁剪，但没有真正的进程/文件系统沙箱。这个 demo 定位为单用户演示；生产化需要把每个项目放进独立容器或 microVM。
- 不执行 `npm install` 级别的服务端构建；预览用共享 esbuild 打包生成的前端源码。
