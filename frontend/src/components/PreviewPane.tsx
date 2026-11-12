import { useState } from "react";
import { ExternalLink, Refresh, Sparkle, Spinner } from "./Icons";

interface Props {
  url: string | null;
  running: boolean;
  version: number;
}

export default function PreviewPane({ url, running, version }: Props) {
  const [nonce, setNonce] = useState(0);
  const src = url ? `${url}${url.includes("?") ? "&" : "?"}r=${nonce}` : null;

  return (
    <section className="flex min-h-[70vh] min-w-0 flex-col bg-ink-950/40 xl:min-h-0">
      <div className="flex h-12 flex-none items-center justify-between gap-2 border-b border-white/5 px-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex flex-none gap-1">
            <i className="h-2 w-2 rounded-full bg-rose-400/70" />
            <i className="h-2 w-2 rounded-full bg-amber-300/70" />
            <i className="h-2 w-2 rounded-full bg-mint/70" />
          </span>
          <span className="text-xs font-semibold text-slate-300">实时预览</span>
          <span className="flex-none rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-slate-500">
            v{version || 1}
          </span>
        </div>
        <div className="flex flex-none items-center gap-1">
          <button
            type="button"
            onClick={() => setNonce((value) => value + 1)}
            disabled={!url}
            title="刷新预览"
            className="grid h-7 w-7 place-items-center rounded-lg text-slate-400 transition hover:bg-white/[0.06] hover:text-slate-200 disabled:opacity-30"
          >
            <Refresh className={`h-3.5 w-3.5 ${running ? "animate-spin" : ""}`} />
          </button>
          <a
            href={url ?? "#"}
            target="_blank"
            rel="noreferrer"
            title="在新窗口打开"
            className={`grid h-7 w-7 place-items-center rounded-lg text-slate-400 transition hover:bg-white/[0.06] hover:text-slate-200 ${
              url ? "" : "pointer-events-none opacity-30"
            }`}
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-[#0b101d]">
        {src ? (
          <iframe
            key={src}
            src={src}
            title="生成应用预览"
            sandbox="allow-scripts allow-forms allow-popups allow-modals"
            className="h-full w-full border-0 bg-white"
          />
        ) : (
          <div className="dot-grid flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/10 bg-white/[0.03] text-accent-soft">
              {running ? <Spinner className="h-5 w-5" /> : <Sparkle className="h-5 w-5" />}
            </div>
            <p className="text-sm text-slate-400">
              {running ? "Agent 正在构建你的应用…" : "应用会在这里实时运行"}
            </p>
            <p className="max-w-[280px] text-[11px] leading-relaxed text-slate-600">
              在左侧描述需求，Planner、Coder、Reviewer、Deployer 依次执行，完成后自动加载预览。
            </p>
          </div>
        )}

        {running && src ? (
          <div className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-ink-950/90 px-3 py-1.5 text-[10px] text-accent-soft shadow-lg">
            <Spinner className="h-3 w-3" />
            更新中
          </div>
        ) : null}
      </div>
    </section>
  );
}
