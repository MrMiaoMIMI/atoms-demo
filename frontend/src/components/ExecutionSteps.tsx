import { useEffect, useState } from "react";
import type { Execution } from "../types";
import { agentFor } from "../lib/agents";
import { AgentAvatar } from "./Avatar";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Spinner,
  X,
} from "./Icons";

function StatusIcon({ status }: { status: Execution["status"] }) {
  if (status === "running") return <Spinner size={14} className="text-brand" />;
  if (status === "success") return <CheckCircle size={14} className="text-positive" />;
  if (status === "warning") return <AlertTriangle size={14} className="text-warning" />;
  return <X size={14} className="text-danger" />;
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
        className="flex items-center gap-2 rounded-lg text-left text-[14px] text-ink-55 transition hover:text-ink-80"
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
        <div className="mt-3 space-y-3 border-l border-line-6 pl-3">
          {executions.map((execution) => {
            const persona = agentFor(execution.agent);
            return (
              <div key={execution.id} className="animate-rise flex items-start gap-2.5">
                <AgentAvatar agent={execution.agent} size={22} ringColor="#F6F6F6" />
                <div className="min-w-0 flex-1 pb-0.5">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span className="text-[13px] font-medium text-ink-95">{persona.name}</span>
                    <span className="text-[12px] text-ink-55">{persona.role}</span>
                    <span className="min-w-0 truncate text-[13px] text-ink-80">{execution.step}</span>
                    <span className="ml-auto flex-none">
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
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
