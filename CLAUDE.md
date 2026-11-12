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
- 一次生成请求返回单一 SSE 流，事件类型：`execution` / `token` / `file_start` / `artifact` / `preview` / `message` / `error` / `done`
- 多智能体用“单 LLM + 角色 prompt 路由”模拟，不真起多进程
- 所有 AI 调用必须可降级：无 API Key 时走 Mock Agent 返回预置模板；运行中 LLM 失败自动降级并记录 warning；前端构建或后端启动失败也会整轮回退 Mock

## 前端视觉规范（对齐 atoms.dev）

- 浅色单主题：主区 `#F6F6F6`，侧边栏 `#EBEBEA`，卡片白底
- 主色 `#4267FF` / 文本主色 `#425CE1`；文字层级 `rgba(12,12,12,.95/.8/.55/.3)`
- 字体自托管：IBM Plex Sans / Serif / Mono（`frontend/public/fonts`，中文回退 PingFang SC / Noto Sans CJK）
- 首页：270px 侧边栏 + 最大 1100px 内容卡 + 720px composer
- 工作台：44px 顶栏 + 左侧对话（默认 500px，可拖拽）+ 右侧 App Viewer（预览 / 代码）
- 无实际功能的官方入口不展示；保留的结构位标注“占位”

## 数据模型

- projects(id, name, created_at)
- conversations(id, project_id, role, content)
- artifacts(id, project_id, filename, content, version)
- executions(id, project_id, agent, step, status, log)

## 目录结构

atoms-demo/
├── frontend/ # Vite React（Atoms 工作台）
├── backend/ # FastAPI
│ ├── main.py # 入口 + REST/SSE + 预览托管与 API 代理
│ ├── agent.py # 多角色编排：形态规划/生成/回修/发布
│ ├── scaffold.py # 确定性脚手架（Vite/FastAPI/SQLite/预览壳）
│ ├── frontend_builder.py # 共享 esbuild 预览构建
│ ├── runtime.py # 生成项目 uvicorn 进程管理（LRU/内存上限）
│ ├── llm.py # 流式 LLM 调用
│ ├── db.py # demo SQLite 封装
│ ├── mocks/ # Mock 模板（frontend/fullstack/backend）
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

Phase 3.5：生成模式已从“纯静态前端”升级为“按需生成完整 Web 项目”。
Planner 判定 frontend / fullstack / backend；确定性脚手架 + LLM 应用代码；
每个项目独立 FastAPI 运行时与 SQLite；预览构建、CORS、LRU 运行时、数据保留均已本地验证。
前端已按 atoms.dev 真实页面重构为“首页 Dashboard + 两栏工作台”，执行步骤内联、文件树位于代码模式。
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
