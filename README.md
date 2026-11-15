# Atoms Demo

自然语言 → 多智能体编排 → 生成完整 Web 项目 → 真实 URL 预览。

一个迷你版 [Atoms](https://atoms.dev/)：三位智能体分工协作——**Mike（团队领导）**理解需求、拆解任务并决定下一位；**Bob（架构师）**判断形态、数据模型与 API；**Alex（工程师）**生成 Vite + React + TypeScript 页面、FastAPI + SQLite 接口，并完成自检、预览构建与后端启动。对话按智能体分组，支持输入 `@` 指定成员；构建类请求按依赖顺序串行交接，咨询类请求由被 @ 的成员并行回答。全程 SSE 实时展示，生成后可以继续对话修改。

## 技术栈

- 前端：Vite + React 18 + TypeScript + Tailwind CSS（Atoms 工作台本身）
- 后端：Python 3.11 + FastAPI + uvicorn（单 worker）
- 数据库：SQLite（WAL），Atoms 自己的库在 `backend/data/atoms.db`
- 实时通信：SSE（`StreamingResponse`），不用 WebSocket
- 部署：Docker Compose + Nginx + Let's Encrypt，单机 2C2G
- LLM：DeepSeek（OpenAI 兼容接口）远程流式调用；无 Key 自动 Mock

## 注册登录与用户隔离

账号体系对齐 atoms.dev 的登录页，包含：

- **邮箱 + 密码**：先判断邮箱是否已注册；已注册进入密码登录，未注册进入「设置密码 → 邮箱验证」。
- **Google 账号与密码并存**：Google 创建的账号没有初始密码（`password_hash=NULL`）。已注册的 Google 邮箱和其他账号一样进入密码登录页；未设置密码时登录会提示失败，可点「忘记密码」通过邮件设置密码。设置后既可用 Google，也可用邮箱 + 密码登录。
- **邮箱验证**：注册后发送验证邮件，点击按钮激活账号。未配置 SMTP 时自动进入开发模式，注册后的页面直接展示可点击/复制的验证链接，离线也能完整演示。
- **忘记密码**：发送带 token 的重置链接（`/password/reset?token=...&email=...`），重置后注销该账号的全部会话。Google 无密码账号也通过同一流程设置首个密码。
- **快捷登录（演示）**：登录页输入邮箱后点「快捷登录（演示）」。新邮箱自动创建账号并使用默认密码 `AtomsDemo2026`，弹窗明确提示；已有邮箱免密直接登录。用于 HR 快速体验，生产部署建议设置 `AUTH_DEMO_QUICK_LOGIN=0`。
- **Google OAuth**：配置 `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` 后启用真实的 Authorization Code 流程。Google 不允许公网 IP 的 HTTP 回调，因此需要 HTTPS 域名；项目已内置 Let's Encrypt 配置。
- **会话安全**：HttpOnly + SameSite=Lax 的随机 token cookie，服务端只存 token 的 SHA-256；密码使用标准库 `scrypt` 加盐哈希；登录/注册/发信接口有内存级限流。
- **用户隔离**：`projects.user_id` 归属校验覆盖项目列表、详情、生成、SSE、导出、删除和 `/apps/{id}/` HTML 入口，越权统一返回 404。
- **公开站点例外**：发布后的项目走 `/s/{id}/`（含 `/s/{id}/api/*`），不要求登录；未发布或暂停时统一 404。工作台预览 `/apps/{id}/` 仍仅项目所有者可打开。
- **已知演示边界**：沙箱 iframe 自身的 `fetch()` 默认不携带 cookie，因此 `/apps/{id}/api/*` 和静态资源不额外校验登录；预览 HTML 入口仍要求项目所有者登录。真实生产化需要把生成项目放到独立域名/容器中做隔离。

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
├── ...                          # .gitignore / .preview / .runtime.log 等
├── .preview/                    # 工作台预览构建产物（构建成功即刷新）
└── .published/                  # 发布快照（仅显式发布时替换）
    ├── site/                    # 构建产物副本，<base> 改写为 /s/{id}/
    ├── backend/                 # 后端源码副本；data 软链到工作区 backend/data
    └── manifest.json            # version / mode / title / published_at
```

所有前端请求统一使用相对路径 `api/...`。预览时页面有 `<base href="/apps/{id}/">`，因此同一个前端源码在本地 Vite、独立部署和 Atoms 子路径预览下都能工作。发布快照里的 `<base>` 会改写为 `/s/{id}/`。

### 生命周期与发布

| 状态 | 含义 | 进入方式 |
| --- | --- | --- |
| `draft` / 未构建 | 创建后还没有成功构建 | 新建项目 |
| `unpublished` / 未发布 | 至少一次构建成功，但还没有发布 | 首次构建成功 |
| `online` / 在线 | 公开链接可访问 | 点击发布 |
| `paused` / 暂停 | 公开链接统一 404 | 在线时暂停 |

- 构建成功才写 `built_version`；失败 / 回滚不更新，所以不会出现“发布了半成品”。
- `has_changes = built_version > published_version`：发布后继续 chat 构建，线上仍跑旧快照，概览提示“线上有未发布的变更”。
- 发布 = 把 `.preview` 与后端源码复制成 `.published/` 快照，并为发布快照启动独立 uvicorn（`pid#published`，`APP_ROOT_PATH=/s/{id}`）；工作台构建只改写工作区，不会碰到线上进程与快照。
- 暂停 / 恢复只改 `projects.paused` 并停止发布运行时，不重新构建；恢复后首个访问懒启动。
- 线上与工作台共用 `backend/data/app.db`，访客写入的数据在工作台预览也能看到。

## 架构

```
浏览器 (React 工作台)
 ├─ /api/auth/* ──► FastAPI 账号 / 会话 / 邮箱验证 / Google OAuth
 ├─ POST /api/projects/{id}/generate ──► FastAPI（需登录，校验项目归属）
 │                                        ├─ 意图判断：build / consult
 │                                        ├─ build: Mike → (Bob | Alex)，尾部 @ 交接
 │                                        │    Mike: 需求拆解 / 复杂度判断
 │                                        │    Bob:  形态 / 数据模型 / API / 文件清单
 │                                        │    Alex: 脚手架 / 代码 / 回修 / 预览 / 运行时
 │                                        └─ consult: 被 @ 的角色并行回答，不修改文件
 │◄────────── SSE: project / agent_start / execution / token / artifact / preview / message / agent_end / done
 │
 ├─ SQLite (WAL): users / sessions / email_tokens / projects(user_id) /
 │                 conversations(agent, run_id, run_index) / artifacts / executions(run_id)
 │
 ├─ iframe /apps/{id}/ ───────────────► Nginx ──► FastAPI 预览静态文件（需登录）
 │                                        └─► /apps/{id}/api/* ──► 工作区 uvicorn
 │
 ├─ /s/{id}/（公开）──────────────────► 发布快照静态文件（暂停/未发布 404）
 │                                        └─► /s/{id}/api/* ──► 发布快照独立 uvicorn
 │
 ├─ 生命周期: draft → unpublished → online ⇄ paused
 │              built_version / published_version / paused 持久化在 projects
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
cp backend/.env.local.example backend/.env.local
# 编辑 backend/.env，填入 LLM_API_KEY 等两个环境共享的密钥

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

配置分两层，加载优先级：**进程环境变量 > `backend/.env.{APP_ENV}` > `backend/.env`**。

| 文件 | 内容 | 说明 |
| --- | --- | --- |
| `backend/.env` | LLM / SMTP / Google Client ID+Secret 等共享密钥 | 不写环境相关值；本地和线上共用 |
| `backend/.env.local` | `PUBLIC_BASE_URL=http://127.0.0.1:5173`、`AUTH_COOKIE_SECURE=0`、`AUTH_DEV_LINKS=1` | 模板 `.env.local.example`；本地默认加载 |
| `backend/.env.production` | `PUBLIC_BASE_URL=https://hajimi.site`、`AUTH_COOKIE_SECURE=1`、`AUTH_DEV_LINKS=0` | 模板 `.env.production.example`；仅服务器使用 |

`APP_ENV` 由进程环境提供（不要写进 `.env`，它在加载文件前读取）：本地默认 `local`，Docker Compose 设为 `production`。

`PUBLIC_BASE_URL` 留空时后端会用请求的 origin，Vite 代理保留了原始 Host，所以本地链接也会是 5173。注意统一使用 `127.0.0.1` 或 `localhost`，不要混用，否则 cookie 与 OAuth 回调的 host 不一致。

登录页：http://127.0.0.1:5173/login 。快捷登录默认密码为 `AtomsDemo2026`。

### 环境变量（`backend/.env` + `backend/.env.{APP_ENV}`）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | 进程环境变量，选择加载 `.env.{APP_ENV}`；Docker Compose 设为 `production` |
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
| `PUBLIC_BASE_URL` | 空（用请求 origin） | 验证/重置邮件链接与 OAuth 回调的对外 origin；本地放 `.env.local`（5173 或留空），线上放 `.env.production`（`https://hajimi.site`） |
| `AUTH_COOKIE_SECURE` | `0` | HTTPS 部署设为 `1`（放 `.env.production`） |
| `AUTH_SESSION_DAYS` | `30` | 登录会话有效天数 |
| `AUTH_VERIFY_TTL_HOURS` | `24` | 邮箱验证链接有效小时数 |
| `AUTH_RESET_TTL_MINUTES` | `60` | 重置密码链接有效分钟数 |
| `AUTH_DEMO_QUICK_LOGIN` | `1` | 是否开启快捷登录（演示用，生产建议 `0`） |
| `AUTH_DEMO_PASSWORD` | `AtomsDemo2026` | 快捷登录新账号的默认密码 |
| `AUTH_DEV_LINKS` | 自动 | SMTP 未配置时自动在页面展示验证/重置链接；设为 `1` 强制开启（即使 SMTP 已配置，邮件仍会真实发送），`0` 关闭（生产） |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | 空 | Google OAuth 凭据（共享 `.env`） |
| `GOOGLE_REDIRECT_URI` | `{PUBLIC_BASE_URL}/api/auth/google/callback` | 留空即可按环境推导；Google Console 中本地与线上两个回调地址都要登记 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_TLS` | 空 / `465` / `ssl` | SMTP 服务器；QQ 邮箱用 `smtp.qq.com:465` + SSL |
| `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | 空 | SMTP 账号、授权码、发件人 |
| `SMTP_FROM_NAME` | `Atoms Demo` | 发件人显示名 |

## Docker 部署（HTTPS）

生产域名为 `https://hajimi.site`，证书由 Let's Encrypt 自动签发。

前置条件：

1. DNS：`hajimi.site` 的 A 记录指向服务器公网 IP。
2. 腾讯云安全组放行 TCP `80` 和 `443`。
3. 服务器上准备 `backend/.env`（共享密钥）和 `backend/.env.production`（线上 origin、Cookie、开发模式开关）。

```bash
cp backend/.env.example backend/.env                         # 填 LLM / SMTP / Google 凭据
cp backend/.env.production.example backend/.env.production   # 确认 PUBLIC_BASE_URL 等
docker compose up -d --build               # HTTP 启动，nginx 先使用临时自签名证书
CERTBOT_EMAIL=you@example.com ./scripts/init-letsencrypt.sh
```

> `docker-compose.yml` 的 `env_file` 同时加载 `.env` 与 `.env.production`（后者覆盖前者），并设置 `APP_ENV=production`。缺少 `backend/.env.production` 时 Compose 会直接报错，请先从模板创建。

完成后打开 `https://hajimi.site`。证书续期：

```cron
0 3 * * * cd /path/to/atoms-demo && ./scripts/renew-cert.sh >> /var/log/atoms-cert.log 2>&1
```

- `web`：Nginx，托管工作台构建产物，反代 `/api/` 与 `/apps/`；80 端口负责 ACME 验证并跳转 HTTPS，443 关闭 SSE 缓冲。
- `backend`：FastAPI 单 worker + Node 共享 esbuild 工具链；内存上限 1G，生成项目后端另受 LRU 与单进程内存上限约束。
- `certbot/conf` 与 `certbot/www` 是证书与 ACME 验证目录，已加入 `.gitignore`。
- `backend/data/` 是宿主机挂载卷，容器重建后账号、项目、demo SQLite 与每个项目自己的 SQLite 都保留。

详细的 Google OAuth、QQ 邮箱 SMTP、DNS/HTTPS 配置步骤见 `docs-local/auth-setup.md`（本地参考文档，不提交到仓库）。

## API

### 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/check-email` | 判断邮箱是否已注册 |
| POST | `/api/auth/register` | `{email,password,redirect?}` 注册并发验证邮件 |
| POST | `/api/auth/verify-email` | `{token}` 验证邮箱并自动登录 |
| POST | `/api/auth/resend-verification` | 重新发送验证邮件（60s 冷却） |
| POST | `/api/auth/login` | `{email,password}` 邮箱密码登录 |
| POST | `/api/auth/quick` | `{email}` 快捷注册/登录（演示） |
| POST | `/api/auth/logout` | 注销当前会话 |
| GET | `/api/auth/me` | 当前登录用户 |
| POST | `/api/auth/password/forgot` | 发送重置密码邮件 |
| POST | `/api/auth/password/reset` | `{token,password}` 重置密码并注销全部会话 |
| GET | `/api/auth/google/start` | 跳转 Google OAuth |
| GET | `/api/auth/google/callback` | Google OAuth 回调 |
| GET | `/api/auth/providers` | 当前启用的登录方式 |

> 除 `/api/health`、`/api/auth/*` 和已发布站点 `/s/{id}/` 外，所有 `/api/projects*` 以及 `/apps/{id}/` HTML 入口都需要登录，并校验项目归属。

### 项目

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查，返回 LLM 模式、运行中的项目与认证能力 |
| GET | `/api/projects` | 项目列表（含 `mode`、`status`、`has_changes`） |
| POST | `/api/projects` | 创建项目 `{prompt?, name?}`；省略 `name` 时后台用 LLM 把首条需求概括为短名称 |
| GET | `/api/projects/{id}` | 完整状态（对话、最新文件、执行记录、`mode`、`preview_url`、`status`、`published_url`） |
| DELETE | `/api/projects/{id}` | 删除项目、生成物、发布快照并停止工作区 / 发布运行时 |
| POST | `/api/projects/{id}/generate` | `{message}`，返回 SSE 流 |
| POST | `/api/projects/{id}/publish` | 把最近一次成功构建快照为公开站点；构建中返回 409 |
| POST | `/api/projects/{id}/pause` | 暂停公开站点（不重建） |
| POST | `/api/projects/{id}/resume` | 恢复公开站点（懒启动发布运行时） |
| GET | `/api/projects/{id}/export` | 下载最新源代码 ZIP 仓库包（`Content-Disposition: attachment`） |
| GET | `/apps/{id}/` | 工作台预览入口（需登录 + 项目归属） |
| GET/POST/... | `/apps/{id}/api/*` | 代理到工作区项目的 FastAPI 后端 |
| GET | `/apps/{id}/docs` | 工作区项目的 Swagger 文档 |
| GET | `/s/{id}/` | 已发布公开站点（无需登录；未发布/暂停 404） |
| GET/POST/... | `/s/{id}/api/*` | 代理到发布快照的独立 FastAPI 后端 |

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

0. 打开首页 → 输入任意邮箱 → 点「快捷登录（演示）」。新邮箱会自动创建账号并提示默认密码 `AtomsDemo2026`；已有邮箱直接登录。也可以走「邮箱 + 密码 + 邮箱验证」或 Google OAuth。
1. 首页输入「做一个团队任务看板，支持新增/完成/筛选，数据保存到 SQLite」→ 对话按智能体分组：Mike（拆解 + 判定复杂度）→ Bob（形态 / 数据模型 / API）→ Alex（脚手架、代码、回修、构建预览、启动运行时）→ 右侧 iframe 出现可交互应用。
2. 在应用里新增几条任务 → 刷新页面 / 刷新 iframe → 数据仍在（来自 `apps/{id}/backend/data/app.db`）。
3. 继续输入「加一个按负责人筛选」→ Mike 判断改动范围，生成 v2，已有任务不丢。
4. 输入 `@Alex 把主按钮文案改成「立即联系」` → 只出现 Alex 的 group，直接修改前端并刷新预览。
5. 输入 `@Mike @Bob @Alex 简单介绍下这个项目` → 三个 group 并行返回产品、架构、实现三个视角，不修改任何文件。
6. 输入 `@Alex 今天天气怎么样？` 换行 `@Mike 曹操是谁？` → 后端按 @ 切段，Alex 只收到天气问题、Mike 只收到曹操问题，各自回答自己的那一段。
7. 输入「今天天气怎么样？」→ 识别为咨询，Mike 回答并明确说明没有接入实时外部数据，不会触发构建。
8. 清空 `LLM_API_KEY` 重启 → 进入 Mock 演示模式：链路照常执行，但生成明确标注的中性占位页，不会伪装成需求中的应用。
9. 首次构建成功后顶栏出现「概览」tab → 点「发布」→「发布应用」→ 复制公开链接，在无登录窗口打开 `/s/{id}/` → 回工作台继续对话生成 v2：线上仍是 v1，概览出现「线上有未发布的变更」→「发布新变更」更新线上 → 概览「暂停访问」后公开链接 404 →「恢复在线」立即恢复，不需要构建。

## 验收对照

- [x] 打开域名先登录；支持邮箱密码、快捷登录、真实 Google OAuth
- [x] 邮箱注册需验证；未配置 SMTP 时开发模式直接展示验证链接
- [x] 忘记密码 / 重置密码；重置后注销全部会话
- [x] 用户只能看到自己的项目；越权访问项目、生成、导出、删除与预览入口统一 404
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
- [x] 生命周期状态：未构建 / 未发布 / 在线 / 暂停；首次构建成功后工作台出现「概览」
- [x] 发布快照与公开链接 `/s/{id}/`；发布后继续构建不影响线上，概览提示变更并可重新发布
- [x] 暂停 / 恢复只切状态不重建；项目列表显示状态徽标；顶栏发布按钮按状态展示不同弹窗

## 设计边界与安全说明

- 已有账号、会话与项目归属隔离；不做团队 / 角色权限 / 多租户。快捷登录是演示功能（任意邮箱可免密登录），生产部署应设置 `AUTH_DEMO_QUICK_LOGIN=0`。不做 Stripe 支付；不接 Kafka/Redis/ES。
- 生成的前端运行在 `sandbox` iframe 中（不含 `allow-same-origin`），通过 CORS 访问自己的后端。因此 iframe 自身的 `fetch()` 不携带 demo 登录 cookie：`/apps/{id}/api/*` 和静态资源不做额外登录校验，预览 HTML 入口仍要求项目所有者登录。
- 生成的后端是**在本机（Docker 容器内）执行的不可信代码**：它有内存上限、只监听 127.0.0.1、环境变量被裁剪，但没有真正的进程/文件系统沙箱。这个 demo 定位为单用户演示；生产化需要把每个项目放进独立容器或 microVM。
- 不执行 `npm install` 级别的服务端构建；预览用共享 esbuild 打包生成的前端源码。
- 发布只保留一份最新快照，不做真正的版本历史 / 回滚 / 多版本并存；不做自定义域名、SEO、Google Ads、分析、推广素材。变更判断用 `built_version > published_version`，不做内容哈希。
- 线上快照与工作台共用项目的 `backend/data/app.db`（演示取舍）：访客写入的数据工作台可见，但工作台后续构建若修改表结构，可能与线上旧代码不兼容。需要强隔离时应拆成独立数据库。
- `/s/{id}/` 是公开入口，生成的后端同样是在本机执行的不可信代码；发布不会额外增加沙箱能力。
