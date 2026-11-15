import { useEffect, useState } from "react";
import type { Execution } from "../types";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Code,
  FileText,
  Folder,
  Globe,
  Search,
  Spinner,
  Terminal,
  X,
} from "./Icons";

const VIEW_LABEL: Record<string, string> = {
  diff: "diff",
  terminal: "终端",
  file: "文件",
  files: "列表",
  search: "搜索",
  http: "请求",
  json: "JSON",
};

function ViewIcon({ type, size = 10 }: { type: string; size?: number }) {
  if (type === "terminal") return <Terminal size={size} />;
  if (type === "files") return <Folder size={size} />;
  if (type === "search") return <Search size={size} />;
  if (type === "http") return <Globe size={size} />;
  if (type === "json") return <Code size={size} />;
  return <FileText size={size} />;
}

function StatusIcon({ status, size = 14 }: { status: Execution["status"]; size?: number }) {
  if (status === "running") return <Spinner size={size} className="text-brand" />;
  if (status === "success") return <CheckCircle size={size} className="text-positive" />;
  if (status === "warning") return <AlertTriangle size={size} className="text-warning" />;
  return <X size={size} className="text-danger" />;
}

interface Props {
  executions: Execution[];
  live?: boolean;
  onOpenStep?: (execution: Execution) => void;
}

export default function ExecutionSteps({
  executions,
  live = false,
  onOpenStep,
}: Props) {
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
                {(() => {
                  const changeCount =
                    execution.change_count ??
                    (execution.change_id ? 1 : 0);
                  const viewType =
                    changeCount > 0 ? "diff" : execution.view_type ?? null;
                  const canOpen = Boolean(
                    viewType &&
                      onOpenStep &&
                      execution.status !== "running"
                  );
                  const label = viewType
                    ? VIEW_LABEL[viewType] ?? viewType
                    : null;
                  const pillLabel =
                    viewType === "diff" && changeCount > 1
                      ? `diff ${changeCount}`
                      : label;
                  return (
                    <div
                      onClick={
                        canOpen ? () => onOpenStep?.(execution) : undefined
                      }
                      onKeyDown={
                        canOpen
                          ? (event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                onOpenStep?.(execution);
                              }
                            }
                          : undefined
                      }
                      role={canOpen ? "button" : undefined}
                      tabIndex={canOpen ? 0 : undefined}
                      title={
                        canOpen
                          ? viewType === "diff"
                            ? "查看本次改动的 diff"
                            : "查看步骤详情"
                          : undefined
                      }
                      className={`rounded-[8px] border border-line-4 bg-white/70 px-3 py-2 ${
                        canOpen
                          ? "cursor-pointer transition hover:border-brand/40 hover:bg-white focus:outline-none focus-visible:border-brand/60"
                          : ""
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <span className="min-w-0 flex-1 break-words text-[13px] leading-[20px] text-ink-80">
                          {execution.step}
                        </span>
                        {canOpen && pillLabel ? (
                          <span className="mt-0.5 inline-flex flex-none items-center gap-1 rounded-full bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-text">
                            <ViewIcon type={viewType ?? "json"} />
                            {pillLabel}
                          </span>
                        ) : null}
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
                  );
                })()}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
