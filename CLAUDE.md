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

- 三栏布局：左侧执行时间线 / 中间对话+文件树 / 右侧 iframe 预览
- 生成代码写入 `backend/data/apps/{project_id}/`，由 nginx 以 `/apps/{id}/` 真实托管；前端 iframe 加载该 URL，sandbox 禁止 allow-same-origin
- 生成物限定为可直接运行的多文件静态站点（HTML/CSS/JS + CDN），不做服务端构建
- 一次生成请求返回单一 SSE 流，事件类型：`execution` / `token` / `file_start` / `artifact` / `preview` / `message` / `error` / `done`
- 多智能体用“单 LLM + 角色 prompt 路由”模拟，不真起多进程
- 所有 AI 调用必须可降级：无 API Key 时走 Mock Agent 返回预置模板；运行中 LLM 失败自动降级并记录 warning

## 数据模型

- projects(id, name, created_at)
- conversations(id, project_id, role, content)
- artifacts(id, project_id, filename, content, version)
- executions(id, project_id, agent, step, status, log)

## 目录结构

atoms-demo/
├── frontend/ # Vite React
├── backend/ # FastAPI
│ ├── main.py # 入口 + 路由
│ ├── agent.py # 多角色编排
│ ├── llm.py # 流式 LLM 调用
│ ├── db.py # SQLite 封装
│ ├── mocks/ # Mock 模板
│ └── data/ # sqlite 挂载
├── nginx/
└── docker-compose.yml

## 代码规范

- 后端全 async/await，SSE 用 StreamingResponse
- 前端用 hooks，不准用 class 组件
- 每个接口必须有错误处理和超时
- 不引入未声明的依赖
- Docker 容器必须设 memory 上限

## 当前阶段

Phase 2：DeepSeek 真实链路已验证（流式生成、8K 截断自动续写、Reviewer 自动回修、异常整轮回退 Mock），
Docker Compose 本地全栈跑通，对话续改与刷新恢复验收通过。
下一步：部署到腾讯云服务器（安全组 80、数据卷持久化），整理演示脚本与验收截图。

## 硬性验收

1. 打开 IP 能直接用，无需注册登录
2. 输入需求 → 看到 Agent 执行时间线 → 生成代码 → iframe 预览
3. 可对话续改
4. 刷新页面项目不丢失（SQLite 持久化）

## 明确不做

- 不做真实鉴权/多用户
- 不做 Stripe 真实支付
- 不做服务端代码沙箱执行
- 不接 Kafka/Redis/ES
