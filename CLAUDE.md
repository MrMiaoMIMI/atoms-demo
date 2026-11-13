# CLAUDE.md — Atoms-style Demo

## 项目目标

做一个迷你版 Atoms (https://atoms.dev/ 平台)：自然语言 → 多智能体编排 → 生成可运行网页应用 → iframe 实时预览。
用于 ROOT AI Native 全栈工程师笔试，6-8 小时交付。

## 技术栈（锁定，不要替换）

- 前端：Vite + React 18 + TypeScript + Tailwind CSS
- 后端：Python 3.11 + FastAPI + uvicorn（单 worker）
- 数据库：SQLite（WAL 模式），不引入 Postgres/Redis
- 实时通信：SSE（Server-Sent Events），不用 WebSocket
- 部署：Docker Compose + Nginx，单机 2C2G 腾讯云轻量服务器，仅 IP 访问
- LLM：远程调用（OpenAI 兼容接口），服务端不加载任何模型

## 架构约束

- 两栏布局：左侧对话（执行步骤内联折叠，角色执行中自动展开）/ 右侧 App Viewer（预览、代码两个模式；文件树位于代码模式的右侧面板内），两栏分界线可拖拽
- 生成代码写入 `backend/data/apps/{project_id}/`，nginx 将 `/apps/` 反代到 FastAPI；FastAPI 托管 `.preview/` 静态产物，并把 `/apps/{id}/api/*` 代理到项目自己的 uvicorn 进程
- 生成物是按需的完整 Web 项目：`frontend`（Vite + React 18 + TS）、`fullstack`（前端 + FastAPI + SQLite）、`backend`（FastAPI + SQLite）；不针对每个项目执行 `npm install`，预览用共享 esbuild 打包
- 每个生成项目拥有独立 SQLite：`apps/{id}/backend/data/app.db`，与 demo 的 `backend/data/atoms.db` 完全隔离；重写代码时保留该数据目录
- 生成后端按项目启动独立 uvicorn 子进程（仅 127.0.0.1、随机端口、LRU 上限、内存上限）；环境变量裁剪，不泄露 demo 的 LLM Key
- 一次生成请求返回单一 SSE 流，事件类型：`project` / `agent_start` / `execution` / `token` / `file_start` / `artifact` / `preview` / `message` / `agent_end` / `error` / `done`；事件带 `agent` + `run_id`，消息另带 `run_index`
- 项目名由后端在创建后后台生成：用一次轻量 LLM 调用把首条需求概括为 ≤24 字的名称；无 Key 或失败时回退到首句启发式；最终名称通过生成流的 `project` 事件回填前端
- 多智能体用“单 LLM + 角色 prompt 路由”模拟，不真起多进程：Mike（团队领导）→ Bob（架构师）→ Alex（工程师）；构建请求按依赖顺序串行、尾部 `@` 交接，咨询请求由被 `@` 的角色并行回答；超时/循环用队列去重、单角色 2 次、整轮 5 次上限
- 用户消息按 `@` 位置确定性切段，每个 Agent 只收到自己名下的问题文本；同一 Agent 的多个问题合并为一轮；分段不额外调用 LLM
- 分段规则：未被 @ 的独立问题默认给 Mike；`请/麻烦/帮我` 等连接词附着到第一个被 @ 的角色；含 `你们/大家/两位/两个人/分别/各自/每个人` 的句子由所有被 @ 角色共同处理；每段再独立判断 build / consult
- 角色能力靠 `AgentSpec.tools` 白名单 + `Toolbox` 强制隔离（Mike 只读，Bob 可校验方案，Alex 可写文件/构建/启动运行时）；工具是进程内 Python 函数，不用 MCP
- 所有 AI 调用必须可降级：无 API Key 时走 Mock Agent 返回中性占位模板（不再伪装成 Todo/落地页）；运行中 LLM 失败按 `LLM_MAX_RETRIES`（默认 3 次）重试，仍失败则回滚本轮并保留上一个可用版本，不静默替换项目；前端构建或后端启动失败同样回滚并报错
- 单次 LLM 输出预算由 `LLM_MAX_TOKENS` 控制（默认 16384，上游 400 时自动降回 8192）；`finish_reason=length` 时按 `LLM_CONTINUATION_PASSES`（默认 3）续写；生成后单文件 >12000 字符告警，>20000 字符的前端 TS/TSX 尝试自动拆分

## 前端视觉规范（对齐 atoms.dev）

- 浅色单主题：主区 `#F6F6F6`，侧边栏 `#EBEBEA`，卡片白底
- 主色 `#4267FF` / 文本主色 `#425CE1`；文字层级 `rgba(12,12,12,.95/.8/.55/.3)`
- 字体自托管：IBM Plex Sans / Serif / Mono（`frontend/public/fonts`，中文回退 PingFang SC / Noto Sans CJK）
- 首页：270px 侧边栏 + 最大 1100px 内容卡 + 720px composer
- 工作台：44px 顶栏 + 左侧对话（默认 500px，可拖拽）+ 右侧 App Viewer（预览 / 代码）
- 无实际功能的官方入口不展示；保留的结构位标注“占位”

## 数据模型

- projects(id, name, created_at)
- conversations(id, project_id, role, content, agent, run_id, run_index, created_at)
- artifacts(id, project_id, filename, content, version)
- executions(id, project_id, agent, step, status, log, run_id, created_at)

## 目录结构

atoms-demo/
├── frontend/ # Vite React（Atoms 工作台）
├── backend/ # FastAPI
│ ├── main.py # 入口 + REST/SSE + 预览托管与 API 代理
│ ├── agents.py # 角色表 / prompt / 意图判断 / @ 解析 / 依赖排序
│ ├── agent.py # 编排器：Mike/Bob/Alex、尾部交接、循环上限、构建流水线
│ ├── tools.py # Toolbox + 角色白名单工具（读状态/写文件/构建/运行时）
│ ├── scaffold.py # 确定性脚手架（Vite/FastAPI/SQLite/预览壳）
│ ├── frontend_builder.py # 共享 esbuild 预览构建
│ ├── runtime.py # 生成项目 uvicorn 进程管理（LRU/内存上限）
│ ├── llm.py # 流式 LLM 调用
│ ├── naming.py # 项目命名（LLM 概括 + 启发式回退）
│ ├── db.py # demo SQLite 封装
│ ├── mocks/ # Mock 演示模板（仅无 Key 时使用：中性占位页 + agents.py 角色回复）
│ ├── runtime/frontend/ # 共享 React + esbuild 工具链（node_modules 不入库）
│ └── data/ # sqlite 与生成项目挂载（apps/{id}/backend/data/app.db）
├── nginx/
└── docker-compose.yml

## 代码规范

- 后端全 async/await，SSE 用 StreamingResponse
- 前端用 hooks，不准用 class 组件
- 每个接口必须有错误处理和超时
- 不引入未声明的依赖
- Docker 容器必须设 memory 上限

## 当前阶段

Phase 4：多智能体交互已对齐 atoms.dev。
对话按智能体分组（头像 + 名字 + 角色 + 已处理 N 步），支持 `@` 指定 Mike / Bob / Alex；
构建请求 Mike → Bob/Alex 串行交接，咨询请求多角色并行回答；刷新后按 agent/run_id 重建分组。
每个项目独立 FastAPI 运行时与 SQLite；预览构建、CORS、LRU 运行时、数据保留均已本地验证。
下一步：部署到腾讯云服务器（安全组 80、数据卷持久化），整理演示脚本与验收截图。

## 硬性验收

1. 打开 IP 能直接用，无需注册登录
2. 输入需求 → 看到 Agent 执行时间线（消息内联，执行中自动展开）→ 按需生成前端/后端 → iframe 真实预览
3. 可对话续改，前后端文件按需更新
4. 刷新页面项目不丢失（demo SQLite 持久化）
5. 全栈项目的业务数据刷新/重启不丢失（项目自己的 SQLite）

## 明确不做

- 不做真实鉴权/多用户
- 不做 Stripe 真实支付
- 不做真正的代码沙箱 / 多租户隔离：生成后端在 demo 容器内以独立进程运行，只有内存上限、localhost 绑定与环境变量裁剪，属于单用户演示边界
- 不为每个生成项目执行 `npm install` 或完整 Vite 构建（预览用共享 esbuild 工具链）
- 不接 Kafka/Redis/ES
- 不引入 LangChain / LangGraph / MCP：3 角色 + 有界交接用显式状态机 + Toolbox 足够，框架会增加依赖、内存与 SSE 事件映射成本
- 不做 Emma / David / Iris / Sarah / Adrian 等其他角色（本轮只实现 Mike / Bob / Alex 三个构建角色）
