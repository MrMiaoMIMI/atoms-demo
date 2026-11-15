import { useEffect, useState } from "react";
import type {
  Artifact,
  ChangeFile,
  ChangeType,
  ChangesResponse,
  FileChange,
} from "../types";
import { fileBadge } from "../lib/files";
import DiffView from "./DiffView";
import FilePanel from "./FilePanel";
import {
  AlertTriangle,
  ChevronLeft,
  Code,
  FileText,
  Refresh,
  Spinner,
} from "./Icons";

export interface StepDiff {
  title: string;
  changes: FileChange[];
}

interface Props {
  projectId: string;
  artifacts: Record<string, Artifact>;
  activeFile: string | null;
  onSelect: (filename: string) => void;
  streamingFile: string | null;
  streamingBuffer: string;
  view: "files" | "changes";
  onViewChange: (view: "files" | "changes") => void;
  changes: ChangesResponse | null;
  changesLoading: boolean;
  changesError: string | null;
  onRefreshChanges: () => void;
  stepDiff: StepDiff | null;
  stepDiffLoading: boolean;
  stepDiffError: string | null;
  onCloseStepDiff: () => void;
  hasChanges: boolean;
}

const CHANGE_LABEL: Record<ChangeType, string> = {
  created: "新增",
  modified: "修改",
  deleted: "删除",
};

const CHANGE_CLASS: Record<ChangeType, string> = {
  created: "bg-[rgba(34,197,94,0.12)] text-[#15803d]",
  modified: "bg-brand-50 text-brand-text",
  deleted: "bg-[rgba(239,68,68,0.12)] text-[#b91c1c]",
};

function FileBadge({ name }: { name: string }) {
  const badge = fileBadge(name);
  return (
    <span
      className="grid h-4 w-4 flex-none place-items-center rounded-[4px] font-mono font-medium"
      style={{
        background: badge.bg,
        color: badge.color,
        fontSize: 8,
        lineHeight: 1,
      }}
    >
      {badge.label}
    </span>
  );
}

function toChangeFile(change: FileChange): ChangeFile {
  return {
    filename: change.filename,
    change_type: change.change_type,
    additions: change.additions,
    deletions: change.deletions,
    diff: change.diff,
    truncated: Boolean(change.truncated),
  };
}

function DiffBrowser({
  files,
  title,
  subtitle,
  loading,
  error,
  notice,
  emptyLabel,
  onRetry,
}: {
  files: ChangeFile[];
  title: string;
  subtitle?: string;
  loading?: boolean;
  error?: string | null;
  notice?: string | null;
  emptyLabel: string;
  onRetry?: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setSelected((current) =>
      current && files.some((file) => file.filename === current)
        ? current
        : files[0]?.filename ?? null
    );
  }, [files]);

  const active = files.find((file) => file.filename === selected) ?? files[0];

  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[16px] border border-line-4 bg-white md:flex-row">
        <div className="flex w-full flex-none flex-col border-b border-line-6 bg-white md:w-[270px] md:border-b-0 md:border-r">
          <div className="flex h-11 flex-none items-center justify-between gap-2 border-b border-line-4 px-3">
            <span className="truncate text-[12px] font-medium text-ink-95">
              {title}
            </span>
            {subtitle ? (
              <span className="flex-none text-[11px] text-ink-30">{subtitle}</span>
            ) : null}
          </div>
          <div className="max-h-[220px] min-h-0 flex-1 overflow-y-auto p-1.5 md:max-h-none">
            {files.length === 0 && loading ? (
              <p className="px-2 py-2 text-[12px] text-ink-30">正在加载变更…</p>
            ) : (
              files.map((file) => {
                const isActive = file.filename === active?.filename;
                return (
                  <button
                    key={file.filename}
                    type="button"
                    title={file.filename}
                    onClick={() => setSelected(file.filename)}
                    className={`mb-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-[12px] transition ${
                      isActive
                        ? "bg-line-6 text-ink-95"
                        : "text-ink-80 hover:bg-line-4 hover:text-ink-95"
                    }`}
                  >
                    <FileBadge name={file.filename} />
                    <span className="min-w-0 flex-1 truncate">
                      {file.filename.split("/").pop()}
                    </span>
                    <span
                      className={`flex-none rounded px-1.5 py-0.5 text-[10px] font-medium ${CHANGE_CLASS[file.change_type]}`}
                    >
                      {CHANGE_LABEL[file.change_type]}
                    </span>
                    <span className="flex flex-none items-center gap-1 font-mono text-[10px]">
                      <span className="text-[#15803d]">+{file.additions}</span>
                      <span className="text-[#b91c1c]">−{file.deletions}</span>
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {active ? (
            <>
              <div className="flex h-11 flex-none items-center justify-between gap-3 border-b border-line-4 px-3">
                <div className="flex min-w-0 items-center gap-2">
                  <FileBadge name={active.filename} />
                  <span className="truncate text-[13px] font-medium text-ink-95">
                    {active.filename.split("/").pop()}
                  </span>
                  <span className="hidden truncate text-[11px] text-ink-30 sm:inline">
                    {active.filename}
                  </span>
                </div>
                <div className="flex flex-none items-center gap-1 font-mono text-[11px]">
                  <span className="text-[#15803d]">+{active.additions}</span>
                  <span className="text-[#b91c1c]">−{active.deletions}</span>
                </div>
              </div>
              {error ? (
                <p className="border-b border-line-4 bg-[rgba(239,68,68,0.06)] px-3 py-1.5 text-[11px] text-danger">
                  {error}
                </p>
              ) : notice ? (
                <p className="border-b border-line-4 bg-[rgba(245,158,11,0.08)] px-3 py-1.5 text-[11px] text-warning">
                  {notice}
                </p>
              ) : null}
              <DiffView diff={active.diff} truncated={active.truncated} />
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
              {loading ? (
                <>
                  <Spinner size={20} className="text-brand" />
                  <p className="text-[12px] text-ink-55">正在加载变更…</p>
                </>
              ) : error ? (
                <>
                  <AlertTriangle size={22} className="text-warning" />
                  <p className="max-w-[320px] text-[12px] leading-[18px] text-danger">
                    {error}
                  </p>
                  {onRetry ? (
                    <button
                      type="button"
                      onClick={onRetry}
                      className="mt-1 inline-flex h-7 items-center gap-1 rounded-md border border-line-6 px-2.5 text-[11px] text-ink-80 transition hover:bg-line-4"
                    >
                      <Refresh size={12} /> 重试
                    </button>
                  ) : null}
                </>
              ) : notice ? (
                <>
                  <AlertTriangle size={22} className="text-warning" />
                  <p className="max-w-[320px] text-[12px] leading-[18px] text-ink-55">
                    {notice}
                  </p>
                </>
              ) : (
                <>
                  <FileText size={22} className="text-ink-30" />
                  <p className="max-w-[320px] text-[12px] leading-[18px] text-ink-55">
                    {emptyLabel}
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export default function CodePanel({
  projectId,
  artifacts,
  activeFile,
  onSelect,
  streamingFile,
  streamingBuffer,
  view,
  onViewChange,
  changes,
  changesLoading,
  changesError,
  onRefreshChanges,
  stepDiff,
  stepDiffLoading,
  stepDiffError,
  onCloseStepDiff,
  hasChanges,
}: Props) {
  const changeCount = changes?.files.length ?? null;
  const aggregateNote = !changes
    ? null
    : !changes.has_published
      ? "项目尚未发布，以下为当前全部文件；发布后会以发布快照为基线计算 diff。"
      : !changes.baseline_ok
        ? "发布基线尚未建立。下一次发布成功后会启用未发布改动 diff。"
        : null;
  const stepNote = stepDiff?.changes.some((change) => change.rolled_back)
    ? "本轮改动已回滚；下面是回滚前的 diff 记录。"
    : null;

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex h-10 flex-none items-center justify-between gap-2 px-2 pb-1">
        {stepDiff ? (
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={onCloseStepDiff}
              className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[12px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
            >
              <ChevronLeft size={14} /> 返回代码
            </button>
            <span className="min-w-0 truncate text-[12px] text-ink-55">
              步骤 diff · {stepDiff.title}
            </span>
          </div>
        ) : (
          <div className="flex items-center rounded-full bg-line-4 p-0.5">
            <button
              type="button"
              onClick={() => onViewChange("files")}
              className={`flex h-[26px] items-center gap-1.5 rounded-full px-2.5 text-[12px] transition ${
                view === "files"
                  ? "bg-white font-medium text-ink-95 shadow-[0_1px_3px_rgba(12,12,12,0.10)]"
                  : "text-ink-55 hover:text-ink-80"
              }`}
            >
              <FileText size={13} />
              文件
            </button>
            <button
              type="button"
              onClick={() => onViewChange("changes")}
              className={`flex h-[26px] items-center gap-1.5 rounded-full px-2.5 text-[12px] transition ${
                view === "changes"
                  ? "bg-white font-medium text-ink-95 shadow-[0_1px_3px_rgba(12,12,12,0.10)]"
                  : "text-ink-55 hover:text-ink-80"
              }`}
            >
              <Code size={13} />
              未发布改动              {changeCount != null && changeCount > 0 ? (
                <span className="rounded-full bg-brand-50 px-1.5 text-[10px] font-medium text-brand-text">
                  {changeCount}
                </span>
              ) : changeCount == null && hasChanges ? (
                <span className="h-1.5 w-1.5 rounded-full bg-brand" />
              ) : null}
            </button>
          </div>
        )}

        {!stepDiff && view === "changes" ? (
          <button
            type="button"
            onClick={onRefreshChanges}
            disabled={changesLoading}
            className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
          >
            <Refresh size={13} />
            刷新
          </button>
        ) : null}
      </div>

      {stepDiff ? (
        <DiffBrowser
          files={stepDiff.changes.map(toChangeFile)}
          title="本次工具改动"
          subtitle={`${stepDiff.changes.length} 个文件`}
          loading={stepDiffLoading}
          error={stepDiffError}
          notice={stepNote}
          emptyLabel="这次步骤没有记录到文件改动。"
        />
      ) : view === "files" ? (
        <FilePanel
          projectId={projectId}
          artifacts={artifacts}
          activeFile={activeFile}
          onSelect={onSelect}
          streamingFile={streamingFile}
          streamingBuffer={streamingBuffer}
        />
      ) : (
        <DiffBrowser
          files={changes?.files ?? []}
          title="未发布改动"
          subtitle={
            changes
              ? changes.has_published
                ? `v${changes.published_version ?? "—"} → v${changes.current_version}`
                : "尚未发布"
              : undefined
          }
          loading={changesLoading}
          error={changesError}
          notice={aggregateNote}
          emptyLabel={
            changes?.has_published
              ? "线上版本与当前代码一致，没有未发布改动。"
              : "项目还没有可对比的发布版本。"
          }
          onRetry={onRefreshChanges}
        />
      )}
    </section>
  );
}
