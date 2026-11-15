"""Standalone HTML pages for unavailable public apps.

A visitor who opens a published link can hit two dead ends: the app was paused
by its author, or the link never existed / was never published. Both used to
render FastAPI's default JSON error, which looks broken in a browser tab.

These pages are server-rendered and self-contained: the request never reaches
the React workspace, so they carry their own minimal styles and reuse the
publicly hosted IBM Plex webfonts with a system-font fallback.
"""
from __future__ import annotations

import html
from urllib.parse import quote

_FONT_FACES = """
@font-face{font-family:'IBM Plex Sans';src:url('/fonts/ibm-plex-sans-latin-400-normal.woff2') format('woff2');font-weight:400;font-style:normal;font-display:swap}
@font-face{font-family:'IBM Plex Sans';src:url('/fonts/ibm-plex-sans-latin-500-normal.woff2') format('woff2');font-weight:500;font-style:normal;font-display:swap}
@font-face{font-family:'IBM Plex Sans';src:url('/fonts/ibm-plex-sans-latin-600-normal.woff2') format('woff2');font-weight:600;font-style:normal;font-display:swap}
"""

_STYLES = """
:root{color-scheme:light}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  background:#F6F6F6;
  color:rgba(12,12,12,.95);
  font-family:'IBM Plex Sans',-apple-system,BlinkMacSystemFont,'PingFang SC',
    'Noto Sans CJK SC','Microsoft YaHei',sans-serif;
  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;
}
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;
  background:
    radial-gradient(720px 400px at 50% -10%,rgba(66,103,255,.10),transparent 70%),
    radial-gradient(560px 340px at 88% 108%,rgba(66,103,255,.05),transparent 70%);
}
.brand{
  position:fixed;top:28px;left:36px;z-index:1;
  font-size:15px;font-weight:600;letter-spacing:-.2px;
  color:rgba(12,12,12,.95);text-decoration:none;
}
.brand span{color:#4267FF}
.shell{
  position:relative;min-height:100%;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:26px;padding:104px 20px 56px;
}
.card{
  width:min(560px,100%);
  padding:44px 40px 40px;
  border:1px solid rgba(12,12,12,.06);
  border-radius:24px;
  background:#fff;
  text-align:center;
  box-shadow:0 1px 2px rgba(12,12,12,.03),
    0 24px 60px -28px rgba(12,12,12,.18);
}
.art{display:flex;justify-content:center;margin-bottom:26px}
.art svg{display:block}
.badge{
  display:inline-flex;align-items:center;gap:7px;
  margin:0 0 16px;padding:5px 12px;
  border-radius:999px;
  font-size:11.5px;font-weight:500;letter-spacing:.04em;
}
.badge--paused{background:#FFF6E8;color:#B5730F}
.badge--missing{background:#EEF2FF;color:#3D5BE0}
.dot{width:5px;height:5px;border-radius:50%;background:currentColor;opacity:.75}
h1{
  margin:0;
  font-size:28px;line-height:1.35;font-weight:600;letter-spacing:-.6px;
  color:rgba(12,12,12,.95);
}
.lede{
  max-width:400px;margin:12px auto 0;
  font-size:14px;line-height:1.75;color:rgba(12,12,12,.55);
}
.actions{
  display:flex;flex-wrap:wrap;justify-content:center;gap:10px;
  margin-top:30px;
}
.btn{
  display:inline-flex;align-items:center;justify-content:center;
  height:40px;padding:0 20px;
  border:1px solid rgba(12,12,12,.12);border-radius:999px;
  background:#fff;color:rgba(12,12,12,.8);
  font-size:13.5px;font-weight:500;text-decoration:none;
  transition:background .16s ease,border-color .16s ease,color .16s ease;
}
.btn:hover{background:#FAFAFA;border-color:rgba(12,12,12,.2)}
.btn--primary{
  border-color:#4267FF;background:#4267FF;color:#fff;
  box-shadow:0 8px 18px -10px rgba(66,103,255,.75);
}
.btn--primary:hover{background:#3A5CE8;border-color:#3A5CE8}
.btn:focus-visible{outline:2px solid rgba(66,103,255,.45);outline-offset:2px}
.foot{margin:0;font-size:12px;color:rgba(12,12,12,.3);letter-spacing:.01em}
@media (max-width:520px){
  .brand{left:20px;top:22px}
  .shell{padding:80px 16px 40px}
  .card{padding:36px 24px 32px;border-radius:20px}
  h1{font-size:24px}
  .actions .btn{flex:1 1 100%}
}
"""

_PAUSED_ART = """
<svg width="96" height="96" viewBox="0 0 96 96" fill="none" role="img" aria-label="已暂停">
  <rect width="96" height="96" rx="28" fill="#FFF6E8"/>
  <circle cx="48" cy="48" r="30" stroke="#E8B45A" stroke-opacity=".55"
    stroke-width="1.5" stroke-dasharray="2 6" stroke-linecap="round"/>
  <rect x="38" y="33" width="8" height="30" rx="4" fill="#D9912B"/>
  <rect x="50" y="33" width="8" height="30" rx="4" fill="#D9912B"/>
</svg>
"""

_MISSING_ART = """
<svg width="96" height="96" viewBox="0 0 96 96" fill="none" role="img" aria-label="页面不存在">
  <rect width="96" height="96" rx="28" fill="#EEF2FF"/>
  <rect x="26" y="30" width="44" height="36" rx="9" stroke="#4267FF"
    stroke-opacity=".55" stroke-width="2" stroke-dasharray="5 5"/>
  <path d="M37 43h22" stroke="#4267FF" stroke-opacity=".28"
    stroke-width="2" stroke-linecap="round"/>
  <path d="M37 52h13" stroke="#4267FF" stroke-opacity=".18"
    stroke-width="2" stroke-linecap="round"/>
</svg>
"""

_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex, nofollow" />
<title>{title} · Atoms</title>
<style>{fonts}{styles}</style>
</head>
<body>
<a class="brand" href="/">Atoms<span>.</span></a>
<main class="shell">
  <section class="card" role="status">
    <div class="art">{art}</div>
    <p class="badge badge--{tone}"><span class="dot"></span>{badge}</p>
    <h1>{headline}</h1>
    <p class="lede">{body}</p>
    <div class="actions">
      <a class="btn btn--primary" href="{primary_href}">{primary_label}</a>
      <a class="btn" href="{secondary_href}">{secondary_label}</a>
    </div>
  </section>
  <p class="foot">{foot}</p>
</main>
</body>
</html>
"""


def _render(
    *,
    title: str,
    tone: str,
    badge: str,
    headline: str,
    body: str,
    primary_href: str,
    primary_label: str,
    secondary_href: str,
    secondary_label: str,
    foot: str,
) -> str:
    art = _PAUSED_ART if tone == "paused" else _MISSING_ART
    values = {
        "title": html.escape(title),
        "tone": tone,
        "badge": html.escape(badge),
        "headline": html.escape(headline),
        "body": html.escape(body),
        "primary_href": html.escape(primary_href, quote=True),
        "primary_label": html.escape(primary_label),
        "secondary_href": html.escape(secondary_href, quote=True),
        "secondary_label": html.escape(secondary_label),
        "foot": html.escape(foot),
        "fonts": _FONT_FACES,
        "styles": _STYLES,
        "art": art,
    }
    return _TEMPLATE.format(**values)


def paused_page(pid: str = "") -> str:
    """Shown when a published app exists but its author paused access."""
    refresh = f"/s/{quote(pid, safe='')}/" if pid else "/"
    return _render(
        title="应用已暂停",
        tone="paused",
        badge="已暂停",
        headline="这个应用正在休息",
        body="创作者暂时关闭了公开访问。恢复后，使用原来的链接即可继续打开它。",
        primary_href="/discover",
        primary_label="去发现页逛逛",
        secondary_href=refresh,
        secondary_label="刷新看看",
        foot="链接已保留 · 恢复公开访问后即可继续使用",
    )


def not_found_page() -> str:
    """Shown when the app never existed, was deleted, or was never published."""
    return _render(
        title="页面不存在",
        tone="missing",
        badge="404",
        headline="页面走丢了",
        body="这个链接对应的应用不存在，或者尚未公开发布。请检查链接是否完整。",
        primary_href="/discover",
        primary_label="去发现页逛逛",
        secondary_href="/",
        secondary_label="返回首页",
        foot="如果你确信链接无误，请联系应用作者",
    )
