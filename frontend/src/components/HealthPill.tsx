import type { Health } from "../types";

export default function HealthPill({ health }: { health: Health | null }) {
  if (!health) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-500">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-500" />
        连接中…
      </span>
    );
  }

  const live = health.llm_mode === "deepseek";
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] ${
        live
          ? "border-mint/25 bg-mint/10 text-mint"
          : "border-amber-300/25 bg-amber-300/10 text-amber-200"
      }`}
      title={live ? `模型 ${health.model}` : "未配置 API Key，正在使用预置模板"}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-mint" : "bg-amber-300"}`} />
      {live ? `DeepSeek · ${health.model}` : "Mock 模式"}
    </span>
  );
}
