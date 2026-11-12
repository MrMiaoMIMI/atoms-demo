# Atoms Demo

自然语言 → 多智能体编排 → 生成可运行网页应用 → 真实 URL 预览。

一个迷你版 [Atoms](https://atoms.dev/)：输入一句需求，Planner 拆解、Coder 多文件生成、Reviewer 检查、Deployer 发布，全程通过 SSE 实时展示，生成物直接托管在服务器上，可对话续改，刷新不丢失。

## 技术栈

- 前端：Vite + React 18 + TypeScript + Tailwind CSS（三栏工作台）
- 后端：Python 3.11 + FastAPI + uvicorn（单 worker）
- 数据库：SQLite（WAL），挂载在 `backend/data/`
- 实时通信：SSE（`StreamingResponse`），不用 WebSocket
- 部署：Docker Compose + Nginx，单机 2C2G
- LLM：DeepSeek（OpenAI 兼容接口）远程流式调用；无 Key 自动 Mock

## 架构

```
浏览器 (React)
 ├─ POST /api/projects/{id}/generate ──► FastAPI
 │                                        ├─► Planner  (prompt 路由)
 │                                        ├─► Coder    (逐文件流式生成)
 │                                        ├─► Reviewer (确定性静态检查)
 │                                        └─► Deployer (写入 data/apps/{id}/)
 │◄────────── SSE: execution / token / artifact / preview / message / done
 │
 ├─ SQLite (WAL): projects / conversations / artifacts / executions
 └─ iframe /apps/{id}/index.html ◄──── Nginx 静态托管（sandbox，无 allow-same-origin）
```

生成物是**多文件静态站点**（`index.html` + `styles.css` + `app.js`），不依赖服务端构建；任何 CDN 库都可以用。每次生成递增 `version`，最新版本即线上版本。

可靠性设计：

- DeepSeek 单次输出上限 8K token。文件被 `finish_reason=length` 截断时，自动携带已生成内容请求**续写**；续写后仍不完整则整轮回退到一致的 Mock 模板，绝不发布半截页面。
- Reviewer 不只查结构，还检查「HTML 中的 class 是否都有 CSS」和「是否包含 `@media`」，命中后自动让 Coder 回修（最多 2 轮），时间线上可见。
- 真实生成约 60–120s（含必要的自动回修），Mock 模式 < 2s。

## 本地开发

要求：Python 3.11+、Node 18+。

```bash
# 1. 配置（不填 Key 也能跑 Mock）
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 LLM_API_KEY

# 2. 后端
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000

# 3. 前端（另开终端）
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173 。前端 dev server 会把 `/api` 和 `/apps` 代理到 8000。

### 环境变量（`backend/.env`）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_API_KEY` | 空 | 为空时使用 Mock Agent |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容地址 |
| `LLM_MODEL` | `deepseek-flash` | 模型名 |
| `LLM_TIMEOUT` | `180` | 流式读取超时（秒） |
| `DATA_DIR` | `backend/data` | SQLite 与生成物根目录 |

## Docker 部署

```bash
cp backend/.env.example backend/.env   # 填入 Key（可留空跑 Mock）
docker compose up -d --build
```

打开 `http://服务器IP/` 。`backend/data/` 是宿主机挂载卷，容器重建后项目与 SQLite 都保留。

- `web`：Nginx，托管前端构建产物 + `/apps/` 生成物 + 反代 `/api/`；已关闭 SSE 缓冲（`proxy_buffering off`、`proxy_read_timeout 600s`）。
- `backend`：FastAPI 单 worker，内存上限 768M；`web` 上限 192M。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查，返回当前 LLM 模式 |
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 `{prompt?, name?}` |
| GET | `/api/projects/{id}` | 完整状态（对话、最新文件、执行记录） |
| DELETE | `/api/projects/{id}` | 删除项目与生成物 |
| POST | `/api/projects/{id}/generate` | `{message}`，返回 SSE 流 |
| GET | `/apps/{id}/index.html` | 已发布应用 |

SSE 事件：

| event | payload |
| --- | --- |
| `execution` | `{id, agent, step, status, log}`，`status: running/success/warning/error` |
| `token` | `{filename, delta}` 流式代码片段 |
| `file_start` | `{filename, purpose}` 开始写某个文件 |
| `artifact` | `{filename, content, version}` 文件完成 |
| `preview` | `{url, version}` 已发布 |
| `message` | `{role, content}` 助手总结 |
| `error` | `{message}` |
| `done` | `{project_id}` |

## 演示脚本

1. 首页输入「做一个待办清单应用」→ 左侧时间线依次出现 Planner / Coder×3 / Reviewer / Deployer → 右侧 iframe 出现可交互应用。真实模型下 Reviewer 若发现样式缺口，会自动触发 Coder 回修。
2. 继续输入「把主色调换成暖色」→ 生成 v2，仅更新需要的文件，预览自动更新。
3. 刷新页面 → 对话、文件、执行记录、预览全部恢复（URL 带 `?p=<project_id>`）。
4. 清空 `LLM_API_KEY` 重启 → 同一条链路走 Mock 模板，UI 无感知，时间线标注降级。

## 验收对照

- [x] 打开 IP 直接用，无需注册登录
- [x] 需求 → Agent 时间线 → 代码 → iframe 预览
- [x] 真实 DeepSeek 流式生成；8K 截断自动续写；Reviewer 自动回修
- [x] 对话续改（版本递增、只重写需要改的文件、其余文件合并保留）
- [x] 刷新不丢项目（SQLite 持久化 + URL 项目 ID）
- [x] 无 Key 可降级 Mock；运行中 LLM 失败整轮回退为一致的 Mock 模板
- [x] Docker Compose + Nginx + 内存上限

## 设计边界（明确不做）

- 不做真实鉴权/多用户；不做 Stripe 支付
- 不做服务端代码沙箱执行；生成物限定静态站点，不跑 `npm build`
- 不接 Kafka/Redis/ES
- 预览 iframe 禁用 `allow-same-origin`；生成代码不得依赖 `localStorage`（「在新窗口打开」为同一 IP 下的普通页面，演示环境无敏感数据）
