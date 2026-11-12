import { useEffect, useRef } from "react";
import type { Execution, ExecutionStatus } from "../types";
import { AlertTriangle, Check, Spinner, X } from "./Icons";

const AGENT_STYLE: Record<string, string> = {
  orchestrator: "border-white/10 bg-white/[0.05] text-slate-300",
  planner: "border-amber-300/20 bg-amber-300/10 text-amber-200",
  coder: "border-accent/25 bg-accent/10 text-accent-soft",
  reviewer: "border-mint/20 bg-mint/10 text-mint",
  deployer: "border-fuchsia-300/20 bg-fuchsia-300/10 text-fuchsia-200",
};

function StatusIcon({ status }: { status: ExecutionStatus }) {
  if (status === "running") return <Spinner className="h-3.5 w-3.5 text-accent-soft" />;
  if (status === "success")
    return (
      <span className="grid h-4 w-4 place-items-center rounded-full bg-mint/15 text-mint">
        <Check className="h-3 w-3" />
      </span>
    );
  if (status === "warning")
    return (
      <span className="grid h-4 w-4 place-items-center rounded-full bg-amber-300/15 text-amber-200">
        <AlertTriangle className="h-2.5 w-2.5" />
      </span>
    );
  return (
    <span className="grid h-4 w-4 place-items-center rounded-full bg-rose-400/15 text-rose-300">
      <X className="h-2.5 w-2.5" />
    </span>
  );
}

interface Props {
  executions: Execution[];
  running: boolean;
}

export default function Timeline({ executions, running }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [executions.length]);

  return (
    <aside className="hidden min-h-0 flex-col border-r border-white/5 bg-ink-900/60 xl:flex">
      <div className="flex h-12 flex-none items-center justify-between border-b border-white/5 px-4">
        <span className="text-xs font-semibold tracking-wide text-slate-300">执行时间线</span>
        <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-slate-500">
          {executions.length} steps
        </span>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {executions.length === 0 ? (
          <div className="mt-10 text-center">
            <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/[0.03] text-slate-600">
              <Spinner className="h-4 w-4" />
            </div>
            <p className="text-xs text-slate-500">Agent 尚未开始执行</p>
          </div>
        ) : (
          <ol className="relative space-y-4 border-l border-white/10 pl-4">
            {executions.map((exec) => (
              <li key={exec.id} className="relative animate-rise">
                <span className="absolute -left-[25px] top-0.5 flex h-4 w-4 items-center justify-center bg-ink-900">
                  <StatusIcon status={exec.status} />
                </span>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest ${
                      AGENT_STYLE[exec.agent.toLowerCase()] ?? AGENT_STYLE.orchestrator
                    }`}
                  >
                    {exec.agent}
                  </span>
                  <span className="truncate text-xs font-medium text-slate-200">{exec.step}</span>
                </div>
                {exec.log ? (
                  <p
                    className={`mt-1.5 break-words text-[11px] leading-relaxed ${
                      exec.status === "warning"
                        ? "text-amber-200/80"
                        : exec.status === "error"
                          ? "text-rose-300/80"
                          : "text-slate-500"
                    }`}
                  >
                    {exec.log}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="flex-none border-t border-white/5 px-4 py-3">
        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              running ? "animate-pulse bg-accent" : "bg-mint/70"
            }`}
          />
          {running ? "Agent 正在协作…" : executions.length ? "本轮执行结束" : "等待指令"}
        </div>
      </div>
    </aside>
  );
}
