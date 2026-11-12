import type { FormEvent, KeyboardEvent, MouseEvent as ReactMouseEvent } from "react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { timeAgo } from "../lib/format";
import type { Health, ProjectSummary } from "../types";
import HealthPill from "./HealthPill";
import { ArrowRight, Code, Sparkle, Spinner, Trash } from "./Icons";

const EXAMPLES = [
  "做一个待办清单应用",
  "做一个 SaaS 产品落地页",
  "做一个数据看板",
];

interface Props {
  health: Health | null;
  onStart: (projectId: string, prompt: string) => void;
  onOpen: (projectId: string) => void;
}

export default function Home({ health, onStart, onOpen }: Props) {
  const [prompt, setPrompt] = useState("");
  const [creating, setCreating] = useState(false);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listProjects()
      .then((items) => {
        if (!cancelled) setProjects(items);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "项目列表加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = prompt.trim();
    if (!text || creating) return;
    setCreating(true);
    setError(null);
    try {
      const project = await api.createProject(text);
      onStart(project.id, text);
    } catch (err) {
      setError((err as Error).message || "创建项目失败");
      setCreating(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  async function removeProject(event: ReactMouseEvent, id: string) {
    event.stopPropagation();
    if (!window.confirm("删除这个项目？该操作不可恢复。")) return;
    setDeleting(id);
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setError((err as Error).message || "删除失败");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="min-h-full overflow-y-auto">
      <header className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-accent to-mint text-sm font-black text-ink-950">
            A
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight text-slate-100">Atoms Demo</p>
            <p className="text-[10px] text-slate-500">AI Native · 多智能体构建器</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[10px] text-slate-500 md:inline">
            FastAPI · SSE · SQLite
          </span>
          <HealthPill health={health} />
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-5 pb-24 sm:px-8">
        <section className="pt-12 text-center sm:pt-20">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-accent-soft">
            <Sparkle className="h-3 w-3" />
            Natural language → running app
          </p>
          <h1 className="text-balance text-4xl font-bold leading-[1.12] tracking-tight text-slate-100 sm:text-6xl">
            说出你的想法，
            <br className="sm:hidden" />
            <span className="bg-gradient-to-r from-accent-soft via-mint to-fuchsia-300 bg-clip-text text-transparent">
              应用即刻上线
            </span>
            。
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-sm leading-relaxed text-slate-400 sm:text-[15px]">
            Planner 拆解需求，Coder 多文件生成，Reviewer 静态检查，Deployer 发布到服务器。
            全过程可视化，生成后还能继续对话修改。
          </p>
        </section>

        <form
          onSubmit={submit}
          className="glass mx-auto mt-10 max-w-2xl rounded-3xl p-3 shadow-[0_30px_80px_rgba(0,0,0,0.35)]"
        >
          <div className="flex items-start gap-2">
            <div className="mt-1.5 hidden h-9 w-9 flex-none place-items-center rounded-xl bg-accent/15 text-accent-soft sm:grid">
              <Sparkle />
            </div>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              maxLength={4000}
              placeholder="描述你想构建的应用，例如：做一个极简风格的待办清单，支持筛选和进度统计…"
              className="min-h-[84px] w-full resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-slate-100 outline-none placeholder:text-slate-600"
            />
          </div>

          <div className="mt-2 flex flex-col gap-3 border-t border-white/5 pt-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setPrompt(example)}
                  className="rounded-full border border-white/10 bg-white/[0.02] px-2.5 py-1 text-[10px] text-slate-400 transition hover:border-accent/40 hover:text-slate-200"
                >
                  {example}
                </button>
              ))}
            </div>
            <button
              type="submit"
              disabled={!prompt.trim() || creating}
              className="inline-flex flex-none items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent to-[#8f6cff] px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-accent/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {creating ? <Spinner className="h-4 w-4" /> : <Sparkle className="h-4 w-4" />}
              {creating ? "正在创建…" : "生成应用"}
              {!creating ? <ArrowRight className="h-4 w-4" /> : null}
            </button>
          </div>
        </form>

        {error ? (
          <p className="mx-auto mt-3 max-w-2xl rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-center text-[11px] text-rose-200">
            {error}
          </p>
        ) : null}

        <section className="mt-16">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">最近项目</h2>
            <span className="text-[10px] text-slate-600">
              {loading ? "加载中…" : `${projects.length} 个项目`}
            </span>
          </div>

          {loading ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((index) => (
                <div key={index} className="h-36 animate-pulse rounded-2xl border border-white/5 bg-white/[0.02]" />
              ))}
            </div>
          ) : projects.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 px-6 py-12 text-center">
              <Code className="mx-auto h-6 w-6 text-slate-600" />
              <p className="mt-3 text-xs text-slate-500">还没有项目，从上面的输入框开始第一个应用。</p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {projects.map((project) => (
                <div
                  key={project.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onOpen(project.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") onOpen(project.id);
                  }}
                  className="group relative cursor-pointer rounded-2xl border border-white/10 bg-white/[0.025] p-5 text-left transition hover:-translate-y-0.5 hover:border-accent/40 hover:bg-white/[0.04]"
                >
                  <div className="flex items-start justify-between">
                    <div className="grid h-9 w-9 place-items-center rounded-xl bg-accent/15 text-accent-soft">
                      <Code />
                    </div>
                    <span className="rounded-full border border-white/10 px-2 py-0.5 text-[9px] text-slate-500">
                      v{project.latest_version ?? 0}
                    </span>
                  </div>
                  <h3 className="mt-4 truncate text-sm font-semibold text-slate-100">{project.name}</h3>
                  <p className="mt-1.5 text-[10px] text-slate-500">
                    {project.message_count} 条对话 · {project.artifact_count} 个文件 ·{" "}
                    {timeAgo(project.created_at)}
                  </p>
                  <div className="mt-4 flex items-center justify-between">
                    <span className="inline-flex items-center gap-1 text-[10px] text-accent-soft opacity-0 transition group-hover:opacity-100">
                      打开工作台
                      <ArrowRight className="h-3 w-3" />
                    </span>
                    <button
                      type="button"
                      title="删除项目"
                      onClick={(event) => void removeProject(event, project.id)}
                      disabled={deleting === project.id}
                      className="grid h-7 w-7 place-items-center rounded-lg text-slate-600 opacity-0 transition hover:bg-rose-400/10 hover:text-rose-300 group-hover:opacity-100 disabled:opacity-40"
                    >
                      {deleting === project.id ? <Spinner className="h-3 w-3" /> : <Trash className="h-3 w-3" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-white/5 px-6 py-6 text-center text-[10px] text-slate-600">
        Atoms Demo · 自然语言 → 多智能体编排 → 可运行网页应用 · Built for ROOT AI Native 全栈工程师笔试
      </footer>
    </div>
  );
}
