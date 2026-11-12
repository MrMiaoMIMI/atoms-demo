"""Pre-built static site templates used by MockLLM.

Each template is a flat multi-file site so the real and mock paths produce the
same shape: index.html + styles.css + app.js.
"""
import json
import re

TODO = {
    "index.html": """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE__</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <main class="app">
    <header class="app__header">
      <div>
        <p class="eyebrow">TASK FLOW</p>
        <h1>__TITLE__</h1>
        <p class="subtitle">保持专注，一件一件完成。</p>
      </div>
      <div class="ring" id="ring"><span id="ringText">0%</span></div>
    </header>

    <form class="composer" id="composer">
      <input id="todoInput" type="text" placeholder="添加一个新任务…" autocomplete="off" maxlength="80" />
      <button type="submit">添加</button>
    </form>

    <div class="toolbar">
      <div class="filters" id="filters">
        <button class="filter is-active" data-filter="all" type="button">全部</button>
        <button class="filter" data-filter="active" type="button">进行中</button>
        <button class="filter" data-filter="done" type="button">已完成</button>
      </div>
      <span class="count" id="count"></span>
    </div>

    <ul class="list" id="list"></ul>
    <p class="empty" id="empty" hidden>这里还没有任务，先添加一个吧。</p>

    <footer class="app__footer">
      <span>双击任务文字可以编辑</span>
      <button class="clear" id="clearDone" type="button">清除已完成</button>
    </footer>
  </main>
  <script src="app.js"></script>
</body>
</html>
""",
    "styles.css": """* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 16px;
  color: #e9edf9;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background:
    radial-gradient(900px 600px at 8% -10%, rgba(108, 140, 255, .3), transparent 60%),
    radial-gradient(700px 520px at 110% 15%, rgba(56, 225, 198, .18), transparent 55%),
    #0a0f1f;
}

.app {
  width: min(680px, 100%);
  padding: 34px;
  border: 1px solid rgba(255, 255, 255, .09);
  border-radius: 26px;
  background: linear-gradient(180deg, rgba(255, 255, 255, .07), rgba(255, 255, 255, .02));
  box-shadow: 0 32px 90px rgba(0, 0, 0, .5);
  backdrop-filter: blur(16px);
}

.app__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.eyebrow { margin: 0 0 10px; font-size: 11px; letter-spacing: .26em; color: #7f8bab; font-weight: 600; }
h1 { margin: 0; font-size: clamp(24px, 4vw, 32px); letter-spacing: -.02em; }
.subtitle { margin: 8px 0 0; color: #8f98b3; font-size: 14px; }

.ring {
  --p: 0;
  flex: none;
  width: 74px;
  height: 74px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  background: conic-gradient(#6c8cff calc(var(--p) * 1%), rgba(255, 255, 255, .08) 0);
  position: relative;
}
.ring::before { content: ""; position: absolute; inset: 6px; border-radius: 50%; background: #101731; }
.ring span { position: relative; z-index: 1; }

.composer { display: flex; gap: 10px; margin: 28px 0 22px; }
.composer input {
  flex: 1;
  min-width: 0;
  padding: 14px 16px;
  font-size: 15px;
  color: inherit;
  background: rgba(8, 13, 28, .72);
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: 14px;
  outline: none;
  transition: border-color .2s, box-shadow .2s;
}
.composer input::placeholder { color: #66708c; }
.composer input:focus { border-color: #6c8cff; box-shadow: 0 0 0 4px rgba(108, 140, 255, .16); }
.composer button {
  padding: 0 22px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  border: 0;
  border-radius: 14px;
  cursor: pointer;
  background: linear-gradient(135deg, #6c8cff, #8f6cff);
  box-shadow: 0 10px 26px rgba(108, 140, 255, .35);
  transition: transform .15s, box-shadow .2s;
}
.composer button:hover { transform: translateY(-1px); box-shadow: 0 14px 30px rgba(108, 140, 255, .45); }

.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.filters { display: flex; gap: 6px; padding: 4px; border-radius: 12px; background: rgba(255, 255, 255, .04); }
.filter {
  padding: 7px 14px;
  font-size: 13px;
  color: #8f98b3;
  background: transparent;
  border: 0;
  border-radius: 9px;
  cursor: pointer;
  transition: background .2s, color .2s;
}
.filter:hover { color: #d7ddf0; }
.filter.is-active { color: #0a0f1f; background: #e9edf9; font-weight: 600; }
.count { font-size: 12px; color: #737d99; }

.list { list-style: none; margin: 18px 0 0; padding: 0; display: grid; gap: 9px; }
.todo {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, .07);
  border-radius: 14px;
  background: rgba(255, 255, 255, .025);
  animation: rise .28s ease both;
}
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.todo__check {
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  border: 1.5px solid rgba(255, 255, 255, .22);
  background: transparent;
  cursor: pointer;
  position: relative;
  transition: background .2s, border-color .2s;
}
.todo__check::after {
  content: "";
  position: absolute;
  left: 7px;
  top: 3px;
  width: 6px;
  height: 11px;
  border: solid #08111f;
  border-width: 0 2px 2px 0;
  transform: rotate(42deg) scale(0);
  transition: transform .18s ease;
}
.todo.is-done .todo__check { background: #38e1c6; border-color: #38e1c6; }
.todo.is-done .todo__check::after { transform: rotate(42deg) scale(1); }

.todo__text { flex: 1; font-size: 15px; line-height: 1.45; word-break: break-word; cursor: default; }
.todo.is-done .todo__text { color: #66708c; text-decoration: line-through; }

.todo__edit {
  flex: 1;
  padding: 6px 8px;
  font: inherit;
  color: inherit;
  background: rgba(8, 13, 28, .9);
  border: 1px solid #6c8cff;
  border-radius: 8px;
  outline: none;
}

.todo__delete {
  flex: none;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  color: #6b7490;
  font-size: 17px;
  background: transparent;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  opacity: 0;
  transition: opacity .15s, color .15s, background .15s;
}
.todo:hover .todo__delete { opacity: 1; }
.todo__delete:hover { color: #ff6b81; background: rgba(255, 107, 129, .1); }

.empty { margin: 30px 0; text-align: center; color: #66708c; font-size: 14px; }

.app__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, .07);
  font-size: 12px;
  color: #66708c;
}
.clear { color: #8f98b3; background: transparent; border: 0; font-size: 12px; cursor: pointer; }
.clear:hover { color: #ff9bab; }

@media (max-width: 560px) {
  .app { padding: 24px 20px; border-radius: 20px; }
  .app__header { flex-direction: column-reverse; align-items: flex-start; }
  .ring { width: 60px; height: 60px; }
}
""",
    "app.js": """const state = {
  filter: "all",
  todos: [
    { id: "1", text: "梳理今天最重要的三件事", done: true },
    { id: "2", text: "完成 Atoms Demo 的生成链路", done: false },
    { id: "3", text: "部署到服务器并截图验收", done: false },
  ],
};

const els = {
  list: document.getElementById("list"),
  empty: document.getElementById("empty"),
  composer: document.getElementById("composer"),
  input: document.getElementById("todoInput"),
  filters: document.getElementById("filters"),
  count: document.getElementById("count"),
  ring: document.getElementById("ring"),
  ringText: document.getElementById("ringText"),
  clearDone: document.getElementById("clearDone"),
};

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, function (ch) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
  });
}

function visibleTodos() {
  if (state.filter === "active") return state.todos.filter(function (t) { return !t.done; });
  if (state.filter === "done") return state.todos.filter(function (t) { return t.done; });
  return state.todos;
}

function render() {
  const items = visibleTodos();
  els.list.innerHTML = items
    .map(function (todo) {
      return (
        '<li class="todo ' + (todo.done ? "is-done" : "") + '" data-id="' + todo.id + '">' +
          '<button class="todo__check" data-action="toggle" aria-label="切换完成"></button>' +
          '<span class="todo__text" data-action="edit">' + escapeHtml(todo.text) + "</span>" +
          '<button class="todo__delete" data-action="delete" aria-label="删除">×</button>' +
        "</li>"
      );
    })
    .join("");

  els.empty.hidden = state.todos.length > 0;
  const done = state.todos.filter(function (t) { return t.done; }).length;
  const total = state.todos.length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  els.count.textContent = done + " / " + total + " 已完成";
  els.ringText.textContent = pct + "%";
  els.ring.style.setProperty("--p", String(pct));
}

function addTodo(text) {
  const value = text.trim();
  if (!value) return;
  state.todos.unshift({ id: uid(), text: value, done: false });
  els.input.value = "";
  render();
}

function startEdit(id) {
  const item = els.list.querySelector('[data-id="' + id + '"]');
  if (!item) return;
  const todo = state.todos.find(function (t) { return t.id === id; });
  const label = item.querySelector(".todo__text");
  const input = document.createElement("input");
  input.className = "todo__edit";
  input.value = todo.text;
  input.maxLength = 80;
  label.replaceWith(input);
  input.focus();
  input.select();

  let finished = false;
  function commit(save) {
    if (finished) return;
    finished = true;
    if (save) {
      const next = input.value.trim();
      if (next) todo.text = next;
    }
    render();
  }
  input.addEventListener("blur", function () { commit(true); });
  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter") commit(true);
    if (event.key === "Escape") commit(false);
  });
}

els.composer.addEventListener("submit", function (event) {
  event.preventDefault();
  addTodo(els.input.value);
});

els.filters.addEventListener("click", function (event) {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  els.filters.querySelectorAll(".filter").forEach(function (el) {
    el.classList.toggle("is-active", el === button);
  });
  render();
});

els.list.addEventListener("click", function (event) {
  const action = event.target.closest("[data-action]");
  if (!action) return;
  const item = event.target.closest("[data-id]");
  if (!item) return;
  const id = item.dataset.id;
  if (action.dataset.action === "toggle") {
    const todo = state.todos.find(function (t) { return t.id === id; });
    if (todo) todo.done = !todo.done;
    render();
  }
  if (action.dataset.action === "delete") {
    state.todos = state.todos.filter(function (t) { return t.id !== id; });
    render();
  }
});

els.list.addEventListener("dblclick", function (event) {
  const target = event.target.closest('[data-action="edit"]');
  if (!target) return;
  const item = target.closest("[data-id]");
  if (item) startEdit(item.dataset.id);
});

els.clearDone.addEventListener("click", function () {
  state.todos = state.todos.filter(function (t) { return !t.done; });
  render();
});

render();
""",
}

LANDING = {
    "index.html": """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE__</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <div class="glow glow--a"></div>
  <div class="glow glow--b"></div>

  <header class="nav">
    <a class="brand" href="#top">
      <span class="brand__mark">◆</span>
      <span>__TITLE__</span>
    </a>
    <nav class="nav__links">
      <a href="#features">特性</a>
      <a href="#showcase">案例</a>
      <a href="#cta">开始</a>
    </nav>
    <a class="nav__cta" href="#cta">免费试用</a>
  </header>

  <main id="top">
    <section class="hero">
      <p class="pill">全新 2.0 版本 · 由 AI 驱动</p>
      <h1>把想法，<span class="grad">变成产品</span>。</h1>
      <p class="hero__desc">
        从一句话描述到可上线的网页应用，自动完成规划、编码与部署。
        无需样板代码，无需等待。
      </p>
      <div class="hero__actions">
        <a class="btn btn--primary" href="#cta">立即开始 <span>→</span></a>
        <a class="btn btn--ghost" href="#features">看看能做什么</a>
      </div>
      <div class="stats">
        <div class="stat"><strong data-count="128">0</strong><span>个项目已上线</span></div>
        <div class="stat"><strong data-count="96">0</strong><span>% 用户满意度</span></div>
        <div class="stat"><strong data-count="43">0</strong><span>秒平均生成时间</span></div>
      </div>
    </section>

    <section class="features" id="features">
      <p class="section__eyebrow">FEATURES</p>
      <h2>从灵感到上线，只需要一步</h2>
      <div class="grid">
        <article class="card reveal">
          <div class="card__icon">✦</div>
          <h3>自然语言生成</h3>
          <p>描述你的需求，Planner 自动拆解页面结构与交互，不再从空白文件开始。</p>
        </article>
        <article class="card reveal">
          <div class="card__icon">◈</div>
          <h3>实时预览</h3>
          <p>代码生成的同时即可预览，随时对话修改，所见即所得。</p>
        </article>
        <article class="card reveal">
          <div class="card__icon">◇</div>
          <h3>一键部署</h3>
          <p>生成完成即拥有独立访问地址，分享给任何人即可查看。</p>
        </article>
      </div>
    </section>

    <section class="showcase" id="showcase">
      <div class="showcase__copy">
        <p class="section__eyebrow">SHOWCASE</p>
        <h2>一个下午，上线三个产品</h2>
        <p>落地页、数据看板、内部工具——用同一套工作流快速验证你的想法。</p>
        <a class="btn btn--primary" href="#cta">创建你的第一个项目 <span>→</span></a>
      </div>
      <div class="showcase__mock">
        <div class="mock__bar"><i></i><i></i><i></i></div>
        <div class="mock__body">
          <div class="mock__side"></div>
          <div class="mock__main">
            <div class="mock__line mock__line--lg"></div>
            <div class="mock__line"></div>
            <div class="mock__cards"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>
    </section>

    <section class="cta" id="cta">
      <h2>准备好构建你的下一个产品了吗？</h2>
      <p>打开页面即可使用，无需注册。</p>
      <a class="btn btn--primary" href="#top">开始构建 <span>→</span></a>
    </section>
  </main>

  <footer class="footer">
    <span>© 2026 __TITLE__</span>
    <span>Built with Atoms Demo</span>
  </footer>
  <script src="app.js"></script>
</body>
</html>
""",
    "styles.css": """* { box-sizing: border-box; }
html { scroll-behavior: smooth; }

body {
  margin: 0;
  color: #eef1fb;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background: #070b16;
  overflow-x: hidden;
}

a { color: inherit; text-decoration: none; }

.glow { position: fixed; border-radius: 50%; filter: blur(120px); pointer-events: none; z-index: 0; }
.glow--a { width: 520px; height: 520px; top: -180px; left: -120px; background: rgba(108, 140, 255, .32); }
.glow--b { width: 460px; height: 460px; top: 30%; right: -180px; background: rgba(56, 225, 198, .16); }

.nav {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px clamp(20px, 5vw, 72px);
  background: rgba(7, 11, 22, .72);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(255, 255, 255, .06);
}
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: -.01em; }
.brand__mark { color: #6c8cff; }
.nav__links { display: flex; gap: 28px; font-size: 14px; color: #9aa4bf; }
.nav__links a:hover { color: #fff; }
.nav__cta {
  padding: 9px 18px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, .16);
  border-radius: 999px;
  transition: background .2s, border-color .2s;
}
.nav__cta:hover { background: rgba(255, 255, 255, .08); border-color: rgba(255, 255, 255, .3); }

main { position: relative; z-index: 1; padding: 0 clamp(20px, 5vw, 72px); }

.hero { max-width: 920px; margin: 0 auto; padding: clamp(70px, 12vw, 130px) 0 90px; text-align: center; }
.pill {
  display: inline-block;
  margin: 0 0 26px;
  padding: 7px 14px;
  font-size: 12px;
  color: #aab4cf;
  border: 1px solid rgba(255, 255, 255, .12);
  border-radius: 999px;
  background: rgba(255, 255, 255, .04);
}
h1 {
  margin: 0;
  font-size: clamp(42px, 8vw, 82px);
  line-height: 1.05;
  letter-spacing: -.04em;
}
.grad {
  background: linear-gradient(100deg, #7d9bff, #38e1c6 55%, #c38bff);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero__desc {
  max-width: 580px;
  margin: 26px auto 0;
  font-size: clamp(15px, 2vw, 18px);
  line-height: 1.75;
  color: #98a2bd;
}
.hero__actions { display: flex; justify-content: center; flex-wrap: wrap; gap: 12px; margin-top: 38px; }
.btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 26px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 14px;
  transition: transform .18s, box-shadow .2s, background .2s;
}
.btn:hover { transform: translateY(-2px); }
.btn--primary {
  color: #06101f;
  background: linear-gradient(135deg, #8fa8ff, #38e1c6);
  box-shadow: 0 16px 40px rgba(108, 140, 255, .35);
}
.btn--primary:hover { box-shadow: 0 20px 50px rgba(108, 140, 255, .5); }
.btn--ghost { color: #dfe4f5; background: rgba(255, 255, 255, .06); border: 1px solid rgba(255, 255, 255, .12); }
.btn--ghost:hover { background: rgba(255, 255, 255, .1); }

.stats { display: flex; justify-content: center; flex-wrap: wrap; gap: clamp(28px, 6vw, 72px); margin-top: 64px; }
.stat { display: grid; gap: 6px; }
.stat strong { font-size: clamp(26px, 4vw, 36px); letter-spacing: -.02em; }
.stat span { font-size: 13px; color: #7c87a4; }

section { max-width: 1080px; margin: 0 auto; padding: 80px 0; }
.section__eyebrow { margin: 0 0 12px; font-size: 11px; letter-spacing: .28em; color: #6c8cff; font-weight: 700; }
h2 { margin: 0 0 14px; font-size: clamp(26px, 4vw, 40px); letter-spacing: -.03em; }
section > p { color: #98a2bd; line-height: 1.7; }

.features { text-align: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; margin-top: 46px; text-align: left; }
.card {
  padding: 28px;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, .05), rgba(255, 255, 255, .015));
  transition: transform .25s, border-color .25s;
}
.card:hover { transform: translateY(-4px); border-color: rgba(108, 140, 255, .4); }
.card__icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  margin-bottom: 18px;
  font-size: 18px;
  color: #8fa8ff;
  background: rgba(108, 140, 255, .12);
  border-radius: 12px;
}
.card h3 { margin: 0 0 10px; font-size: 17px; }
.card p { margin: 0; font-size: 14px; line-height: 1.7; color: #8b96b2; }

.showcase { display: grid; grid-template-columns: 1fr 1.1fr; align-items: center; gap: 48px; }
.showcase__copy p { max-width: 420px; }
.showcase__copy .btn { margin-top: 26px; }
.showcase__mock {
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: 20px;
  overflow: hidden;
  background: #0d1424;
  box-shadow: 0 40px 90px rgba(0, 0, 0, .5);
  transform: perspective(1000px) rotateY(-6deg) rotateX(2deg);
}
.mock__bar { display: flex; gap: 7px; padding: 13px 16px; border-bottom: 1px solid rgba(255, 255, 255, .07); }
.mock__bar i { width: 10px; height: 10px; border-radius: 50%; background: rgba(255, 255, 255, .16); }
.mock__bar i:first-child { background: #ff6b81; }
.mock__bar i:nth-child(2) { background: #ffd166; }
.mock__bar i:nth-child(3) { background: #38e1c6; }
.mock__body { display: flex; min-height: 260px; }
.mock__side { width: 90px; background: rgba(255, 255, 255, .025); border-right: 1px solid rgba(255, 255, 255, .06); }
.mock__main { flex: 1; padding: 24px; display: grid; align-content: start; gap: 14px; }
.mock__line { height: 10px; border-radius: 6px; background: rgba(255, 255, 255, .08); }
.mock__line--lg { width: 58%; height: 16px; background: linear-gradient(90deg, rgba(108, 140, 255, .55), rgba(56, 225, 198, .4)); }
.mock__cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
.mock__cards span { height: 70px; border-radius: 12px; background: rgba(255, 255, 255, .05); border: 1px solid rgba(255, 255, 255, .06); }

.cta {
  text-align: center;
  padding: 90px 24px;
  margin-bottom: 40px;
  border: 1px solid rgba(255, 255, 255, .09);
  border-radius: 28px;
  background:
    radial-gradient(600px 240px at 50% 0, rgba(108, 140, 255, .22), transparent 70%),
    rgba(255, 255, 255, .02);
}
.cta .btn { margin-top: 26px; }

.footer {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 28px clamp(20px, 5vw, 72px);
  font-size: 12px;
  color: #66708c;
  border-top: 1px solid rgba(255, 255, 255, .06);
}

.reveal { opacity: 0; transform: translateY(18px); transition: opacity .6s ease, transform .6s ease; }
.reveal.is-visible { opacity: 1; transform: none; }

@media (max-width: 820px) {
  .nav__links { display: none; }
  .showcase { grid-template-columns: 1fr; }
  .showcase__mock { transform: none; }
}
""",
    "app.js": """const counters = document.querySelectorAll("[data-count]");

const counterObserver = new IntersectionObserver(function (entries) {
  entries.forEach(function (entry) {
    if (!entry.isIntersecting) return;
    const el = entry.target;
    const target = Number(el.dataset.count || 0);
    counterObserver.unobserve(el);
    const start = performance.now();
    const duration = 1100;

    function tick(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = String(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
}, { threshold: 0.5 });

counters.forEach(function (el) { counterObserver.observe(el); });

const revealObserver = new IntersectionObserver(function (entries) {
  entries.forEach(function (entry) {
    if (entry.isIntersecting) {
      entry.target.classList.add("is-visible");
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.15 });

document.querySelectorAll(".reveal").forEach(function (el, index) {
  el.style.transitionDelay = index * 90 + "ms";
  revealObserver.observe(el);
});

const nav = document.querySelector(".nav");
window.addEventListener("scroll", function () {
  nav.style.borderBottomColor = window.scrollY > 20
    ? "rgba(255, 255, 255, .12)"
    : "rgba(255, 255, 255, .06)";
}, { passive: true });
""",
}

DASHBOARD = {
    "index.html": """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE__</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><span>◆</span> __TITLE__</div>
      <nav class="menu">
        <a class="menu__item is-active" href="#">概览</a>
        <a class="menu__item" href="#">流量</a>
        <a class="menu__item" href="#">转化</a>
        <a class="menu__item" href="#">用户</a>
        <a class="menu__item" href="#">设置</a>
      </nav>
      <div class="sidebar__foot">
        <div class="avatar">AI</div>
        <div><strong>Atoms Demo</strong><span>管理员</span></div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <p class="eyebrow">OVERVIEW</p>
          <h1>数据概览</h1>
        </div>
        <div class="range" id="range">
          <button class="is-active" data-range="7" type="button">近 7 天</button>
          <button data-range="30" type="button">近 30 天</button>
        </div>
      </header>

      <section class="kpis" id="kpis"></section>

      <section class="panels">
        <article class="panel panel--chart">
          <div class="panel__head">
            <div><h2>访问趋势</h2><p>按天统计的页面浏览量</p></div>
            <span class="badge" id="trendBadge">+0%</span>
          </div>
          <div class="chart" id="chart"></div>
        </article>

        <article class="panel">
          <div class="panel__head"><div><h2>来源分布</h2><p>流量渠道占比</p></div></div>
          <div class="donut" id="donut"><span id="donutText">0%</span></div>
          <ul class="legend" id="legend"></ul>
        </article>
      </section>

      <section class="panel">
        <div class="panel__head"><div><h2>最近活动</h2><p>系统实时事件</p></div><button class="ghost" id="refresh" type="button">刷新</button></div>
        <ul class="activity" id="activity"></ul>
      </section>
    </main>
  </div>
  <script src="app.js"></script>
</body>
</html>
""",
    "styles.css": """* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  color: #e8edf9;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  background:
    radial-gradient(800px 500px at 80% -10%, rgba(108, 140, 255, .18), transparent 60%),
    #080d18;
}

.shell { display: grid; grid-template-columns: 220px 1fr; min-height: 100vh; }

.sidebar {
  display: flex;
  flex-direction: column;
  gap: 30px;
  padding: 26px 18px;
  border-right: 1px solid rgba(255, 255, 255, .07);
  background: rgba(255, 255, 255, .02);
}
.brand { display: flex; align-items: center; gap: 9px; font-size: 15px; font-weight: 700; padding: 0 8px; }
.brand span { color: #7d9bff; }
.menu { display: grid; gap: 4px; }
.menu__item {
  padding: 10px 12px;
  font-size: 14px;
  color: #8b96b2;
  text-decoration: none;
  border-radius: 10px;
  transition: background .18s, color .18s;
}
.menu__item:hover { color: #dce3f5; background: rgba(255, 255, 255, .04); }
.menu__item.is-active { color: #fff; background: rgba(108, 140, 255, .16); box-shadow: inset 0 0 0 1px rgba(108, 140, 255, .28); }
.sidebar__foot { margin-top: auto; display: flex; align-items: center; gap: 10px; padding: 0 8px; font-size: 12px; }
.sidebar__foot strong { display: block; font-size: 13px; }
.sidebar__foot span { color: #7c87a4; }
.avatar { width: 34px; height: 34px; display: grid; place-items: center; font-size: 12px; font-weight: 700; border-radius: 10px; background: linear-gradient(135deg, #6c8cff, #38e1c6); color: #06101f; }

.main { padding: 30px clamp(20px, 4vw, 48px) 48px; display: grid; align-content: start; gap: 20px; }
.topbar { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 16px; }
.eyebrow { margin: 0 0 8px; font-size: 11px; letter-spacing: .26em; color: #6c8cff; font-weight: 700; }
h1 { margin: 0; font-size: clamp(24px, 4vw, 32px); letter-spacing: -.02em; }
.range { display: flex; gap: 4px; padding: 4px; border: 1px solid rgba(255, 255, 255, .08); border-radius: 12px; background: rgba(255, 255, 255, .03); }
.range button { padding: 8px 14px; font-size: 13px; color: #8b96b2; background: transparent; border: 0; border-radius: 9px; cursor: pointer; }
.range button.is-active { color: #08111f; background: #dfe6f7; font-weight: 600; }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
.kpi {
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, .05), rgba(255, 255, 255, .015));
}
.kpi span { display: block; font-size: 12px; color: #8b96b2; }
.kpi strong { display: block; margin: 10px 0 8px; font-size: 28px; letter-spacing: -.02em; }
.kpi em { font-style: normal; font-size: 12px; color: #38e1c6; }
.kpi em.is-down { color: #ff7a8f; }

.panels { display: grid; grid-template-columns: 1.6fr 1fr; gap: 14px; }
.panel {
  padding: 22px;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 18px;
  background: rgba(255, 255, 255, .022);
}
.panel--chart { display: flex; min-height: 300px; flex-direction: column; }
.panel__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 22px; }
.panel__head h2 { margin: 0 0 4px; font-size: 16px; }
.panel__head p { margin: 0; font-size: 12px; color: #7c87a4; }
.badge { padding: 5px 10px; font-size: 12px; font-weight: 600; color: #38e1c6; background: rgba(56, 225, 198, .12); border-radius: 999px; }
.badge.is-down { color: #ff7a8f; background: rgba(255, 122, 143, .12); }

.chart { display: flex; align-items: flex-end; gap: 8px; height: 190px; }
.bar { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 8px; height: 100%; }
.bar__fill {
  width: 100%;
  min-height: 4px;
  border-radius: 7px 7px 3px 3px;
  background: linear-gradient(180deg, #8fa8ff, rgba(108, 140, 255, .25));
  transition: height .5s cubic-bezier(.2, .8, .2, 1);
}
.bar__label { font-size: 10px; color: #66708c; }

.donut {
  --p: 0;
  width: 150px;
  height: 150px;
  margin: 6px auto 20px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: conic-gradient(#6c8cff calc(var(--p) * 1%), rgba(255, 255, 255, .07) 0);
  position: relative;
}
.donut::before { content: ""; position: absolute; inset: 16px; border-radius: 50%; background: #0c1322; }
.donut span { position: relative; z-index: 1; font-size: 20px; font-weight: 700; }
.legend { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; font-size: 12px; color: #8b96b2; }
.legend li { display: flex; align-items: center; gap: 8px; }
.legend i { width: 8px; height: 8px; border-radius: 3px; }
.legend b { margin-left: auto; color: #dce3f5; font-weight: 600; }

.activity { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.activity li { display: flex; align-items: center; gap: 12px; padding: 11px 8px; font-size: 13px; border-bottom: 1px solid rgba(255, 255, 255, .05); }
.activity li:last-child { border-bottom: 0; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #38e1c6; flex: none; }
.activity time { margin-left: auto; font-size: 11px; color: #66708c; }
.ghost { padding: 7px 12px; font-size: 12px; color: #aab4cf; background: transparent; border: 1px solid rgba(255, 255, 255, .12); border-radius: 9px; cursor: pointer; }
.ghost:hover { background: rgba(255, 255, 255, .06); }

@media (max-width: 900px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar { flex-direction: row; align-items: center; gap: 16px; padding: 16px; border-right: 0; border-bottom: 1px solid rgba(255, 255, 255, .07); overflow-x: auto; }
  .menu { display: flex; }
  .sidebar__foot { display: none; }
  .panels { grid-template-columns: 1fr; }
}
""",
    "app.js": """const RANGES = {
  7: [42, 58, 51, 76, 64, 92, 88],
  30: [30, 44, 38, 52, 61, 58, 72, 69, 84, 78, 91, 96, 88, 102, 118, 110, 126, 139, 131, 148, 142, 160, 155, 171, 166, 182, 178, 196, 190, 208],
};

const KPIS = {
  7: [
    { label: "页面浏览量", value: "24.8K", delta: "+12.4%" },
    { label: "独立访客", value: "8,142", delta: "+6.8%" },
    { label: "转化率", value: "3.62%", delta: "+0.42%" },
    { label: "平均停留", value: "4m 12s", delta: "-1.3%", down: true },
  ],
  30: [
    { label: "页面浏览量", value: "96.3K", delta: "+28.1%" },
    { label: "独立访客", value: "31,576", delta: "+19.2%" },
    { label: "转化率", value: "3.18%", delta: "+0.17%" },
    { label: "平均停留", value: "3m 58s", delta: "+2.1%" },
  ],
};

const SOURCES = [
  { label: "自然搜索", pct: 42, color: "#6c8cff" },
  { label: "直接访问", pct: 27, color: "#38e1c6" },
  { label: "社交媒体", pct: 19, color: "#c38bff" },
  { label: "其他渠道", pct: 12, color: "#ffd166" },
];

const ACTIVITIES = [
  { text: "新用户注册：alex@nova.dev", time: "刚刚" },
  { text: "部署完成：portfolio-site v3", time: "2 分钟前" },
  { text: "页面访问量突破 10,000", time: "18 分钟前" },
  { text: "新项目创建：team-dashboard", time: "1 小时前" },
  { text: "订阅方案升级：Pro 年付", time: "3 小时前" },
];

let range = "7";

const els = {
  kpis: document.getElementById("kpis"),
  chart: document.getElementById("chart"),
  range: document.getElementById("range"),
  donut: document.getElementById("donut"),
  donutText: document.getElementById("donutText"),
  legend: document.getElementById("legend"),
  activity: document.getElementById("activity"),
  refresh: document.getElementById("refresh"),
  trendBadge: document.getElementById("trendBadge"),
};

function renderKpis() {
  els.kpis.innerHTML = KPIS[range]
    .map(function (kpi) {
      return (
        '<article class="kpi"><span>' + kpi.label + "</span><strong>" + kpi.value + "</strong>" +
        '<em class="' + (kpi.down ? "is-down" : "") + '">' + kpi.delta + " 较上期</em></article>"
      );
    })
    .join("");
}

function renderChart() {
  const values = RANGES[range];
  const max = Math.max.apply(null, values);
  const showEvery = range === "30" ? 5 : 1;
  els.chart.innerHTML = values
    .map(function (value, index) {
      const height = Math.max(6, Math.round((value / max) * 100));
      const label = range === "7"
        ? "周" + "一二三四五六日"[index]
        : (index % showEvery === 0 ? "第" + (index + 1) + "天" : "");
      return (
        '<div class="bar"><div class="bar__fill" style="height:' + height + '%"></div>' +
        '<span class="bar__label">' + label + "</span></div>"
      );
    })
    .join("");

  const first = values[0];
  const last = values[values.length - 1];
  const growth = Math.round(((last - first) / first) * 100);
  els.trendBadge.textContent = (growth >= 0 ? "+" : "") + growth + "%";
  els.trendBadge.classList.toggle("is-down", growth < 0);
}

function renderDonut() {
  const total = SOURCES.reduce(function (sum, item) { return sum + item.pct; }, 0);
  const top = SOURCES[0];
  els.donut.style.setProperty("--p", String(Math.round((top.pct / total) * 100)));
  els.donutText.textContent = top.pct + "%";
  els.legend.innerHTML = SOURCES.map(function (source) {
    return (
      '<li><i style="background:' + source.color + '"></i>' + source.label +
      "<b>" + source.pct + "%</b></li>"
    );
  }).join("");
}

function renderActivity() {
  els.activity.innerHTML = ACTIVITIES.map(function (item) {
    return '<li><span class="dot"></span>' + item.text + "<time>" + item.time + "</time></li>";
  }).join("");
}

function renderAll() {
  renderKpis();
  renderChart();
  renderDonut();
  renderActivity();
}

els.range.addEventListener("click", function (event) {
  const button = event.target.closest("[data-range]");
  if (!button) return;
  range = button.dataset.range;
  els.range.querySelectorAll("button").forEach(function (el) {
    el.classList.toggle("is-active", el === button);
  });
  renderAll();
});

els.refresh.addEventListener("click", function () {
  renderAll();
  els.refresh.textContent = "已刷新";
  setTimeout(function () { els.refresh.textContent = "刷新"; }, 1200);
});

renderAll();
""",
}

TEMPLATES = {"todo": TODO, "landing": LANDING, "dashboard": DASHBOARD}
DEFAULT_TITLE = {"todo": "我的待办清单", "landing": "Nova · 用 AI 构建产品", "dashboard": "数据概览"}


def _detect_existing_template(existing: dict[str, str] | None) -> str | None:
    if not existing:
        return None
    html = existing.get("index.html", "")
    if 'id="todoInput"' in html or "TASK FLOW" in html:
        return "todo"
    if 'id="kpis"' in html or "OVERVIEW" in html:
        return "dashboard"
    if html:
        return "landing"
    return None


def pick_template(prompt: str, existing: dict[str, str] | None = None) -> str:
    p = prompt.lower()
    if any(k in p for k in ("待办", "todo", "任务", "清单", "checklist", "习惯")):
        return "todo"
    if any(k in p for k in ("仪表盘", "dashboard", "看板", "数据", "图表", "统计", "分析", "报表")):
        return "dashboard"
    if any(k in p for k in ("落地页", "官网", "landing", "主页", "产品页")):
        return "landing"
    # Follow-up edits ("换成暖色") must not silently swap the app type.
    return _detect_existing_template(existing) or "landing"


def extract_title(prompt: str, template: str) -> str:
    text = re.sub(r"^\s*(帮我|请|我想|想要|做一个|做|生成|开发|设计|搭建|一个|一款|一套)+", "", prompt.strip())
    text = re.sub(r"[。！!？?，,；;：:].*$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if 2 <= len(text) <= 24:
        return text
    return DEFAULT_TITLE[template]


PALETTES = {
    "暖色": ("#ff9f68", "#ffd166", "#ff7a8f"),
    "橙色": ("#ff9f68", "#ffd166", "#ff7a8f"),
    "红色": ("#ff7a8f", "#ffb199", "#ff5470"),
    "绿色": ("#34d399", "#a3e635", "#22c55e"),
    "紫色": ("#a78bfa", "#f0abfc", "#8b5cf6"),
}
DEFAULT_PALETTE = ("#6c8cff", "#38e1c6", "#8f6cff")
BASE_ACCENT = "#6c8cff"
BASE_ACCENT_SOFT = "#8fa8ff"
BASE_MINT = "#38e1c6"
BASE_VIOLET = "#8f6cff"
BASE_ACCENT_RGB = "108, 140, 255"
BASE_MINT_RGB = "56, 225, 198"


def _hex_rgb(color: str) -> str:
    value = color.lstrip("#")
    return f"{int(value[0:2], 16)}, {int(value[2:4], 16)}, {int(value[4:6], 16)}"


def _existing_title(existing: dict[str, str] | None) -> str | None:
    if not existing:
        return None
    html = existing.get("index.html", "")
    match = re.search(r"<title>(.*?)</title>", html, re.S)
    if match and match.group(1).strip():
        return match.group(1).strip()[:60]
    return None


def _apply_palette(content: str, prompt: str) -> str:
    palette = next((value for key, value in PALETTES.items() if key in prompt), None)
    if not palette:
        return content
    accent, accent2, accent3 = palette
    replacements = {
        BASE_ACCENT: accent,
        BASE_ACCENT_SOFT: accent,
        BASE_MINT: accent2,
        BASE_VIOLET: accent3,
        BASE_ACCENT_RGB: _hex_rgb(accent),
        BASE_MINT_RGB: _hex_rgb(accent2),
    }
    for old, new in replacements.items():
        content = content.replace(old, new)
    return content


def _render(
    template: str, prompt: str, title_override: str | None = None
) -> dict[str, str]:
    title = title_override or extract_title(prompt, template)
    return {
        name: _apply_palette(content.replace("__TITLE__", title), prompt)
        for name, content in TEMPLATES[template].items()
    }


def mock_plan(prompt: str, existing: dict[str, str] | None = None) -> str:
    template = pick_template(prompt, existing)
    purposes = {
        "index.html": "页面结构与内容",
        "styles.css": "视觉样式与响应式布局",
        "app.js": "交互逻辑与状态管理",
    }
    plan = {
        "summary": f"基于「{prompt.strip()[:40]}」生成一个可交互的静态 Web 应用（{template} 模板）。",
        "files": [
            {"path": name, "purpose": purposes[name]} for name in TEMPLATES[template]
        ],
    }
    return json.dumps(plan, ensure_ascii=False)


def mock_file(
    prompt: str, filename: str, existing: dict[str, str] | None = None
) -> str:
    template = pick_template(prompt, existing)
    files = _render(template, prompt, _existing_title(existing))
    if filename in files:
        return files[filename]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "css":
        return files["styles.css"]
    if ext == "js":
        return files["app.js"]
    return files["index.html"]
