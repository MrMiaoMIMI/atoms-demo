# CLAUDE.md — Atoms-style Demo

## 项目目标

做一个迷你版 Atoms (https://atoms.dev/ 平台)：自然语言 → 多智能体编排 → 生成可运行网页应用 → iframe 实时预览。
用于 ROOT AI Native 全栈工程师笔试，6-8 小时交付。

## 技术栈（锁定，不要替换）

- 前端：Vite + React 18 + TypeScript + Tailwind CSS
- 后端：Python 3.11 + FastAPI + uvicorn（单 worker）
- 数据库：SQLite（WAL 模式），不引入 Postgres/Redis
- 实时通信：SSE（Server-Sent Events），不用 WebSocket
- 部署：Docker Compose + Nginx + Let's Encrypt，单机 2C2G 腾讯云轻量服务器，域名 `hajimi.site` HTTPS 访问
- LLM：远程调用（OpenAI 兼容接口），服务端不加载任何模型

## 架构约束

- 两栏布局：左侧对话（执行步骤内联折叠，角色执行中自动展开）/ 右侧 App Viewer（预览、概览、代码三个模式；概览仅在首次构建成功后显示；代码模式内可切换「文件 / 未发布改动」，时间线中带 diff 的步骤可点击查看单次工具改动），两栏分界线可拖拽
- 生成代码写入 `backend/data/apps/{project_id}/`，nginx 将 `/apps/` 反代到 FastAPI；FastAPI 托管 `.preview/` 静态产物，并把 `/apps/{id}/api/*` 代理到项目自己的 uvicorn 进程
- 项目生命周期：`draft`（未构建）→ `unpublished`（首次构建成功）→ `online`（发布）⇄ `paused`（暂停）；`projects.built_version/built_at/published_version/published_at/paused` 持久化，派生 `status` 与 `has_changes = built_version > published_version`。只有完整构建成功才写 `built_version`，失败/回滚不写
- 发布是构建快照：`apps/{id}/.published/{site,backend,manifest.json,source.json}`；`source.json` 是发布时的源码基线，用于「未发布改动」diff；`site` 的 `<base>` 改写为 `/s/{id}/`，`backend/data` 软链到工作区 `backend/data/app.db`；发布快照由独立 uvicorn 进程（`pid#published`，`APP_ROOT_PATH=/s/{id}`）运行。发布后的 chat 构建只改写工作区，不得触碰 `.published/` 或发布进程
- `/s/{id}/` 与 `/s/{id}/api/*` 是公开入口（未发布/暂停统一 404），`/apps/{id}/` 仍仅项目所有者可打开；nginx 与 Vite dev proxy 都要加 `/s/`（Vite 必须写成 `/s/`，写成 `/s` 会把 `/src/*` 也代理走）
- 暂停/恢复只改 `projects.paused` 并停止发布运行时，不重新构建；恢复后首个请求懒启动。线上与工作台共用项目 SQLite
- 生成物是按需的完整 Web 项目：`frontend`（Vite + React 18 + TS）、`fullstack`（前端 + FastAPI + SQLite）、`backend`（FastAPI + SQLite）；不针对每个项目执行 `npm install`，预览用共享 esbuild 打包
- 每个生成项目拥有独立 SQLite：`apps/{id}/backend/data/app.db`，与 demo 的 `backend/data/atoms.db` 完全隔离；重写代码时保留该数据目录
- 生成后端按项目启动独立 uvicorn 子进程（仅 127.0.0.1、随机端口、LRU 上限、内存上限）；环境变量裁剪，不泄露 demo 的 LLM Key
- 一次生成请求返回单一 SSE 流，事件类型：`project` / `agent_start` / `execution` / `token` / `file_start` / `artifact` / `file_change` / `changes_reset` / `preview` / `message` / `agent_end` / `error` / `done`；事件带 `agent` + `run_id`，消息另带 `run_index`
- 项目名由后端在创建后后台生成：用一次轻量 LLM 调用把首条需求概括为 ≤24 字的名称；无 Key 或失败时回退到首句启发式；最终名称通过生成流的 `project` 事件回填前端
- 多智能体用“单 LLM + 角色 prompt 路由”模拟，不真起多进程：Mike（团队领导）→ Bob（架构师）→ Alex（工程师）；Bob 在有现有项目时用只读工具循环查看文件后输出 JSON 方案；Alex 用统一 tool loop 完成首建和迭代；构建请求按依赖顺序串行、尾部 `@` 交接，咨询请求由被 `@` 的角色并行回答；超时/循环用队列去重、单角色 2 次、整轮 5 次上限
- 用户消息按 `@` 位置确定性切段，每个 Agent 只收到自己名下的问题文本；同一 Agent 的多个问题合并为一轮；分段不额外调用 LLM
- 分段规则：未被 @ 的独立问题默认给 Mike；`请/麻烦/帮我` 等连接词附着到第一个被 @ 的角色；含 `你们/大家/两位/两个人/分别/各自/每个人` 的句子由所有被 @ 角色共同处理；每段再独立判断 build / consult
- 角色能力靠 `AgentSpec.tools` 白名单 + `Toolbox` 强制隔离（Mike 只读，Bob 只读文件工具 + 校验方案，Alex 可读写文件/精确编辑/删除/构建/启动运行时/读日志）；工具是进程内 Python 函数，不用 MCP
- 所有 AI 调用必须可降级：无 API Key 时 Mock Agent 走确定性 tool 序列（写中性占位文件 → build），仍能演示工具时间线与 diff；运行中 LLM 失败按 `LLM_MAX_RETRIES`（默认 3 次）重试，仍失败则回滚本轮并保留上一个可用版本，不静默替换项目；前端构建或后端启动失败同样回滚并报错
- 首建与迭代共用一条链路：Workspace 暂存树 → 确定性脚手架 → Alex tool loop（list/read/grep/write/edit/delete/build/runtime/health/log）→ Reviewer → 只写变更文件的 `apply_changes` → build/health → `mark_built`。首建只多一步“脚手架补基础设施”，不再有第二套整文件生成路径；旧链路仅作为 provider 不支持 tools 时的 `AGENT_TOOL_LOOP=0` 兜底
- 文件编辑精确匹配：`edit_file` 默认要求 `old_string` 唯一命中；`write_file` 对已有文件要求显式 `overwrite=true`；路径限制在 `apps/{id}/`，禁止 `.published` / `.preview` / `backend/data` / `node_modules`
- per-tool diff：每次写/编辑/删除记录 `file_changes(filename, change_type, diff, additions, deletions, version, run_id, execution_id, rolled_back)`，通过 `file_change` SSE 实时下发；时间线步骤可点击查看。回滚保留记录并标记 `rolled_back=1`
- 未发布改动：发布成功时写 `.published/source.json`；`GET /api/projects/{id}/changes` 对比发布源码基线与当前 artifacts，返回变更文件清单与 unified diff；代码模式「文件 / 未发布改动」切换；发布后 diff 为空
- artifacts 删除用 tombstone（`deleted=1`），`latest_artifacts` / `get_state` / 导出 / 项目列表均排除；回滚删除本轮 version 的 artifacts
- 工具循环预算按计划文件数动态计算（首建 40–96 步、迭代 24–64 步，默认墙钟 1200s/600s）；80% 时提示收敛；超限时构建通过则带 warning 提交，否则回滚；`AGENT_*` 环境变量可调
- 单次 LLM 输出预算由 `LLM_MAX_TOKENS` 控制（默认 16384，上游 400 时自动降回 8192）；`finish_reason=length` 时按 `LLM_CONTINUATION_PASSES`（默认 3）续写；生成后单文件 >12000 字符告警，>20000 字符的前端 TS/TSX 尝试自动拆分
- 发现模块：登录后可见，只列 `published_version` 非空且未暂停的项目，并**排除当前用户自己的项目**；自己的项目只在「项目」页 / 工作台展示，发现页侧边栏与首页一致（仍显示自己的最近项目）。分类对齐官方九类 + 其他，发布时手选，自动识别只给建议；支持最新/最热、搜索、收藏/已保存；每次打开详情页浏览数 +1，首页项目 tab 和项目列表卡片展示浏览数并去掉「N 条对话 · N 个文件」。详情页 iframe 运行 `/s/{id}/`。封面：构建成功后由浏览器 sandbox iframe + `html-to-image` 生成 build cover，发布后生成 published cover；项目卡片按 published > build > CSS 展示，发现页只用 published cover；服务端不引入 Chromium
- 账号体系：邮箱 + 密码（scrypt 加盐哈希）、邮箱验证、忘记密码、快捷登录（演示）、真实 Google OAuth；会话为 HttpOnly + SameSite=Lax 的随机 token cookie，服务端只存 SHA-256；`/api/auth/*` 与 `/api/health` 公开，其余项目 API 和 `/apps/{id}/` HTML 入口必须登录并校验 `projects.user_id`
- Google 创建的账号 `password_hash` 为 NULL、不设初始密码；登录时与普通账号一样进入密码校验，未设置密码则提示失败，用户可通过「忘记密码」邮件设置密码，之后支持 Google 与邮箱密码双方式登录
- 邮件：SMTP（QQ 邮箱 465/SSL）发送验证/重置链接；SMTP 未配置时自动进入开发模式，在页面展示链接；`AUTH_DEV_LINKS` 可强制开启，生产关闭
- 配置分环境：`backend/.env` 只放共享密钥，`backend/.env.local` / `.env.production` 放环境相关值；加载优先级为进程环境变量 > `.env.{APP_ENV}` > `.env`，`APP_ENV` 默认 local、Compose 设 production；`PUBLIC_BASE_URL` 本地留空按请求 origin 推导
- 生成项目预览的 sandbox iframe（不含 `allow-same-origin`）自身 fetch 不携带 cookie，因此 `/apps/{id}/api/*` 与静态资源不做登录校验；这是单用户演示边界，需在 README 中明确

## 前端视觉规范（对齐 atoms.dev）

- 浅色单主题：主区 `#F6F6F6`，侧边栏 `#EBEBEA`，卡片白底
- 主色 `#4267FF` / 文本主色 `#425CE1`；文字层级 `rgba(12,12,12,.95/.8/.55/.3)`
- 字体自托管：IBM Plex Sans / Serif / Mono（`frontend/public/fonts`，中文回退 PingFang SC / Noto Sans CJK）
- 首页：270px 侧边栏 + 最大 1100px 内容卡 + 720px composer
- 工作台：44px 顶栏 + 左侧对话（默认 500px，可拖拽）+ 右侧 App Viewer（预览 / 概览 / 代码；代码内「文件 / 未发布改动」二级切换）
- 无实际功能的官方入口不展示；保留的结构位标注“占位”

## 数据模型

- users(id, email UNIQUE COLLATE NOCASE, name, password_hash, provider, email_verified, created_at, last_login_at)
- sessions(token_hash PK, user_id, created_at, expires_at, user_agent, ip)
- email_tokens(token_hash PK, user_id, kind, email, expires_at, used_at, created_at)
- projects(id, name, user_id, created_at, built_version, built_at, published_version, published_at, paused, description, category, view_count, cover_version, cover_at, build_cover_version, build_cover_at)
- project_saves(user_id, project_id, created_at) — 发现页收藏
- conversations(id, project_id, role, content, agent, run_id, run_index, created_at)
- artifacts(id, project_id, filename, content, version, deleted) — `deleted=1` 是 tombstone，最新版本为 tombstone 时文件从当前树消失
- executions(id, project_id, agent, step, status, log, run_id, tool, target, created_at)
- file_changes(id, project_id, version, run_id, agent, execution_id, filename, change_type, diff, additions, deletions, rolled_back, truncated, created_at) — 单次工具改动的 diff 历史

## 目录结构

atoms-demo/
├── frontend/ # Vite React（Atoms 工作台）
│ ├── src/components/DiscoverPage.tsx / DiscoverDetailPage.tsx / DiscoverCard.tsx
│ ├── src/components/CodePanel.tsx # 代码模式：文件 / 未发布改动 / 步骤 diff
│ ├── src/components/DiffView.tsx # unified diff 渲染
│ ├── src/lib/discover.ts # 分类 / 计数格式化
│ ├── src/lib/cover.ts # 发布后浏览器端封面截图与上传
│ └── scripts/copy-capture-tool.mjs # 把 html-to-image 复制到 public/preview-assets
├── backend/ # FastAPI
│ ├── main.py # 入口 + REST/SSE + 发现 API + 预览托管 / changes API
│ ├── categories.py # 发现分类常量 / 关键词启发式 / LLM 分类建议
│ ├── agents.py # 角色表 / prompt / 意图判断 / @ 解析 / 依赖排序
│ ├── agent.py # 编排器：Mike/Bob/Alex、统一 tool loop 构建流水线
│ ├── tool_loop.py # 原生 function calling 有界循环（预算/无进展/回滚）
│ ├── tools.py # Toolbox + 角色白名单工具 + LLM tool schema
│ ├── workspace.py # 暂存工作区 / 路径安全 / 精确编辑 / apply_to
│ ├── diffing.py # unified diff / 源码树对比
│ ├── scaffold.py # 确定性脚手架（Vite/FastAPI/SQLite/预览壳）
│ ├── frontend_builder.py # 共享 esbuild 预览构建
│ ├── publisher.py # 发布快照（.published/、source.json、base 改写、数据软链）
│ ├── runtime.py # 生成项目 uvicorn 进程管理（工作区/发布双实例，LRU/内存上限）
│ ├── llm.py # 流式 + 原生 tool calling LLM 调用
│ ├── naming.py # 项目命名（LLM 概括 + 启发式回退）
│ ├── auth.py # 密码哈希 / 会话 / 邮箱 token / 限流 / OAuth 辅助
│ ├── mailer.py # SMTP 验证邮件与重置邮件（未配置时开发模式）
│ ├── db.py # demo SQLite 封装（users/sessions/email_tokens/projects/file_changes）
│ ├── tests/ # unittest：workspace / diff / db / tool loop / build / publish / rollback
│ ├── .env.example # 环境变量模板（LLM / Agent loop / Auth / Google / SMTP）
│ ├── mocks/ # Mock 演示模板（仅无 Key 时使用：中性占位页 + agents.py 角色回复）
│ ├── runtime/frontend/ # 共享 React + esbuild 工具链（node_modules 不入库）
│ └── data/ # sqlite 与生成项目挂载（apps/{id}/backend/data/app.db）
├── nginx/ # HTTP→HTTPS、ACME challenge、API/SSE/预览反代、临时自签名证书
├── scripts/ # init-letsencrypt.sh / renew-cert.sh
├── certbot/ # 证书与 ACME webroot（gitignored，运行时生成）
└── docker-compose.yml

## 代码规范

- 后端全 async/await，SSE 用 StreamingResponse
- 前端用 hooks，不准用 class 组件
- 每个接口必须有错误处理和超时
- 不引入未声明的依赖（账号/邮件只使用标准库 `hashlib`/`secrets`/`hmac`/`smtplib`）
- 密码、会话 token、邮件 token 不得明文写库；日志不输出密码或 token；项目 API 必须校验 `user_id`
- Docker 容器必须设 memory 上限
- 工具 / 工作区 / DB 变更必须有单元测试：`cd backend && .venv/bin/python -m unittest discover -s tests`

## 当前阶段

Phase 5：注册登录与用户隔离。
登录页视觉对齐 atoms.dev，支持邮箱 + 密码、邮箱验证、忘记密码/重置、快捷登录（演示）和真实 Google OAuth；
项目、生成、SSE、导出、删除、预览入口全部按 `user_id` 隔离；旧 DB 迁移已验证。
每个项目独立 FastAPI 运行时与 SQLite；预览构建、CORS、LRU 运行时、数据保留均已本地验证。

Phase 6：项目状态管理与发布概览。
`draft / unpublished / online / paused` 状态派生；发布快照 `.published/` 与独立发布运行时；公开站点 `/s/{id}/`；暂停/恢复；工作台「概览」tab（仅首次构建成功后显示）、按状态弹窗的顶栏发布入口、项目列表状态徽标。本期不做真正的版本历史/回滚。

Phase 7：发现模块。
登录后 `/discover` 浏览其他用户已发布的应用（内容排除自己的项目，侧边栏与首页一致）；官方九类 + 其他、最新/最热、搜索、收藏/已保存；每次打开详情页浏览数 +1，首页项目 tab 和项目列表卡片展示浏览数并去掉对话/文件数；`/discover/{id}` 详情页 16:9 iframe 运行发布快照；发布弹窗增加简介/分类/自动识别；构建成功后浏览器端生成 build cover，发布后生成 published cover，项目卡片按 published > build > CSS 展示，发现页只用 published cover，失败回退 CSS。本期不做克隆/Remix/点赞/模板 tab。
Phase 8：迭代能力重构（统一 tool loop + diff）。
首建与迭代共用 Workspace + 原生 function calling 工具循环（Alex）；Bob 增加只读文件工具，先读后规划；`edit_file` 精确匹配、`write_file` 覆盖保护、tombstone 删除；每次工具改动写 `file_changes` 并通过 `file_change` SSE 实时下发；代码模式增加「文件 / 未发布改动」切换与时间线步骤 diff；发布成功写 `.published/source.json` 作为未发布 diff 基线；回滚保留 diff 并标记 `rolled_back=1`；旧 per-file 生成链路保留为 `AGENT_TOOL_LOOP=0` 兜底。
下一步：在 `https://hajimi.site` 完成 Let's Encrypt 签发、Google OAuth 与 QQ 邮箱 SMTP 配置；跑一遍完整验收（含 diff 交互）并整理截图。

## 硬性验收

1. 打开域名先登录；支持快捷登录 / 邮箱密码 / 真实 Google OAuth
2. 邮箱注册需验证；未配置 SMTP 时开发模式展示验证链接；忘记密码可重置
3. 用户只能看到自己的项目；越权访问项目、生成、导出、删除与预览入口统一 404
4. 输入需求 → 看到 Agent 执行时间线（消息内联，执行中自动展开）→ 按需生成前端/后端 → iframe 真实预览
5. 可对话续改，前后端文件按需更新
6. 刷新页面项目不丢失（demo SQLite 持久化）
7. 全栈项目的业务数据刷新/重启不丢失（项目自己的 SQLite）
8. 首次构建成功后工作台出现「概览」；未构建时不显示
9. 发布后公开链接未登录可访问；继续 chat 构建不影响线上并提示「有未发布变更」；重新发布后线上更新
10. 暂停/恢复只切状态不重建；项目列表显示状态徽标；顶栏发布按钮按状态展示不同弹窗
11. 发现内容只展示其他用户的在线应用；自己的项目不在发现列表、详情和相关推荐出现；发现页侧边栏与首页一致
12. 发现支持分类、搜索、最新/最热、收藏/已保存；详情页 iframe 运行发布快照
13. 每次打开详情页浏览数 +1；首页项目 tab 和项目列表卡片展示浏览量，不再展示对话/文件数
14. 构建成功后生成 build cover，发布成功后生成 published cover；项目卡片按 published > build > CSS 展示
15. 发布可填简介、选分类并「自动识别」；封面失败回退 CSS；暂停/删除的项目从发现消失
16. 迭代时只改动相关文件：Agent 通过工具读取/编辑文件，时间线显示 tool 步骤；每个写操作生成 diff，点击步骤在右侧查看
17. 代码模式可切换「文件 / 未发布改动」：按发布源码基线展示变更文件清单与逐文件 diff；发布后 diff 清空；回滚的 diff 标记为已回滚

## 明确不做

- 不做团队 / 角色权限 / 多租户；快捷登录是演示功能，生产部署应关闭 `AUTH_DEMO_QUICK_LOGIN`
- 不做 Stripe 真实支付
- 不做真正的代码沙箱 / 多租户隔离：生成后端在 demo 容器内以独立进程运行，只有内存上限、localhost 绑定与环境变量裁剪，属于单用户演示边界
- 不为每个生成项目执行 `npm install` 或完整 Vite 构建（预览用共享 esbuild 工具链）
- 不接 Kafka/Redis/ES
- 不引入 LangChain / LangGraph / MCP：3 角色 + 有界交接用显式状态机 + Toolbox 足够，框架会增加依赖、内存与 SSE 事件映射成本
- 不做 Emma / David / Iris / Sarah / Adrian 等其他角色（本轮只实现 Mike / Bob / Alex 三个构建角色）
- 不做可浏览/可切换的版本历史与任意版本回滚：只保留本轮失败回滚、发布快照和 per-tool diff 记录；`file_changes` 不是多版本代码库
- 发现页不做克隆 / Remix / 点赞 / 模板 tab / 多 tag；不做服务端 Chromium 截图（封面由浏览器端 html-to-image 生成，项目卡片 published > build > CSS，失败回退 CSS）；发现页保持登录后可见，不改成公开免登录页面
- 不做自定义域名 / SEO / Google Ads / 分析 / 推广素材；线上快照与工作台共用同一个项目 SQLite（需要强隔离时再拆独立库）
