import { useEffect, useState } from "react";
import type { Execution } from "../types";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Spinner,
  X,
} from "./Icons";

function StatusIcon({ status, size = 14 }: { status: Execution["status"]; size?: number }) {
  if (status === "running") return <Spinner size={size} className="text-brand" />;
  if (status === "success") return <CheckCircle size={size} className="text-positive" />;
  if (status === "warning") return <AlertTriangle size={size} className="text-warning" />;
  return <X size={size} className="text-danger" />;
}

interface Props {
  executions: Execution[];
  live?: boolean;
}

export default function ExecutionSteps({ executions, live = false }: Props) {
  const active = executions.some((execution) => execution.status === "running");
  const failed = executions.some((execution) => execution.status === "error");
  const warned = executions.some((execution) => execution.status === "warning");
  const [open, setOpen] = useState(live || active);

  useEffect(() => {
    if (active) setOpen(true);
    else if (!live) setOpen(false);
  }, [active, live]);

  if (!executions.length) {
    if (!live) return null;
    return (
      <div className="mt-3 flex items-center gap-2 text-[14px] text-ink-55">
        <Spinner size={14} className="text-brand" />
        正在启动智能体…
      </div>
    );
  }

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 rounded-lg text-left text-[14px] text-ink-55 transition hover:text-ink-80"
      >
        {active ? (
          <Spinner size={15} className="text-brand" />
        ) : failed ? (
          <X size={15} className="text-danger" />
        ) : warned ? (
          <AlertTriangle size={15} className="text-warning" />
        ) : (
          <CheckCircle size={15} className="text-ink-30" />
        )}
        <span>{active ? `正在处理 ${executions.length} 步` : `已处理 ${executions.length} 步`}</span>
        <ChevronDown
          size={14}
          className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="mt-2.5 pl-1">
          {executions.map((execution, index) => (
            <div key={execution.id} className="flex gap-2.5">
              <div className="flex w-3 flex-none flex-col items-center pt-2">
                <span className="h-1.5 w-1.5 rounded-full bg-ink-30" />
                {index < executions.length - 1 ? (
                  <span className="mt-1 min-h-[12px] w-px flex-1 border-l border-dashed border-line-8" />
                ) : null}
              </div>
              <div className="min-w-0 flex-1 pb-2">
                <div className="rounded-[8px] border border-line-4 bg-white/70 px-3 py-2">
                  <div className="flex items-start gap-2">
                    <span className="min-w-0 flex-1 break-words text-[13px] leading-[20px] text-ink-80">
                      {execution.step}
                    </span>
                    <span className="mt-0.5 flex-none">
                      <StatusIcon status={execution.status} />
                    </span>
                  </div>
                  {execution.log ? (
                    <p
                      className={`mt-0.5 break-words text-[12px] leading-[18px] ${
                        execution.status === "error"
                          ? "text-danger"
                          : execution.status === "warning"
                            ? "text-warning"
                            : "text-ink-55"
                      }`}
                    >
                      {execution.log}
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
