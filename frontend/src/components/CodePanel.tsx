import { useEffect, useMemo, useState } from "react";
import type {
  Artifact,
  ChangeFile,
  ChangeType,
  ChangesResponse,
  FileChange,
} from "../types";
import { buildFileTree, fileBadge, flattenFiles, type FileNode } from "../lib/files";
import DiffView from "./DiffView";
import FilePanel from "./FilePanel";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Code,
  FileText,
  Folder,
  PanelLeft,
  Refresh,
  Search,
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

interface ChangeTreeNode {
  type: "dir" | "file";
  name: string;
  path: string;
  additions: number;
  deletions: number;
  file?: ChangeFile;
  children?: ChangeTreeNode[];
}

/** Reuse the file tab's tree shape so both lists nest and order files alike. */
function buildChangeTree(files: ChangeFile[]): ChangeTreeNode[] {
  const byPath = new Map(files.map((file) => [file.filename, file]));
  const convert = (nodes: FileNode[]): ChangeTreeNode[] =>
    nodes.map((node) => {
      if (node.type === "file") {
        const file = byPath.get(node.path);
        return {
          type: "file" as const,
          name: node.name,
          path: node.path,
          additions: file?.additions ?? 0,
          deletions: file?.deletions ?? 0,
          file,
        };
      }
      const children = convert(node.children ?? []);
      return {
        type: "dir" as const,
        name: node.name,
        path: node.path,
        additions: children.reduce((sum, child) => sum + child.additions, 0),
        deletions: children.reduce((sum, child) => sum + child.deletions, 0),
        children,
      };
    });
  return convert(buildFileTree(files.map((file) => file.filename)));
}

function ChangeFileRow({
  file,
  label,
  active,
  paddingLeft,
  onSelect,
}: {
  file: ChangeFile;
  label: string;
  active: boolean;
  paddingLeft: number;
  onSelect: (path: string) => void;
}) {
  return (
    <button
      type="button"
      title={file.filename}
      onClick={() => onSelect(file.filename)}
      className={`flex h-[26px] w-full items-center gap-1.5 rounded-md pr-2 text-left text-[12px] transition ${
        active
          ? "bg-line-6 text-ink-95"
          : "text-ink-80 hover:bg-line-4 hover:text-ink-95"
      }`}
      style={{ paddingLeft }}
    >
      <FileBadge name={file.filename} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
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
}

function ChangeTreeRows({
  nodes,
  depth,
  activePath,
  collapsed,
  onToggle,
  onSelect,
}: {
  nodes: ChangeTreeNode[];
  depth: number;
  activePath: string | null;
  collapsed: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
}) {
  return (
    <>
      {nodes.map((node) => {
        const pad = 8 + depth * 12;
        if (node.type === "dir") {
          const isCollapsed = collapsed.has(node.path);
          return (
            <div key={node.path}>
              <button
                type="button"
                onClick={() => onToggle(node.path)}
                title={node.path}
                className="flex h-[26px] w-full items-center gap-1.5 rounded-md pr-2 text-left text-[12px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
                style={{ paddingLeft: pad }}
              >
                <ChevronRight
                  size={12}
                  className={`flex-none text-ink-30 transition-transform ${
                    isCollapsed ? "" : "rotate-90"
                  }`}
                />
                <Folder size={14} className="flex-none text-ink-30" />
                <span className="min-w-0 flex-1 truncate">{node.name}</span>
                <span className="flex flex-none items-center gap-1 font-mono text-[10px]">
                  <span className="text-[#15803d]">+{node.additions}</span>
                  <span className="text-[#b91c1c]">−{node.deletions}</span>
                </span>
              </button>
              {isCollapsed ? null : (
                <ChangeTreeRows
                  nodes={node.children ?? []}
                  depth={depth + 1}
                  activePath={activePath}
                  collapsed={collapsed}
                  onToggle={onToggle}
                  onSelect={onSelect}
                />
              )}
            </div>
          );
        }
        const file = node.file;
        if (!file) return null;
        return (
          <ChangeFileRow
            key={node.path}
            file={file}
            label={node.name}
            active={node.path === activePath}
            paddingLeft={pad + 13}
            onSelect={onSelect}
          />
        );
      })}
    </>
  );
}

function DiffBrowser({
  files,
  loading,
  error,
  notice,
  emptyLabel,
  onRetry,
}: {
  files: ChangeFile[];
  loading?: boolean;
  error?: string | null;
  notice?: string | null;
  emptyLabel: string;
  onRetry?: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [treeOpen, setTreeOpen] = useState(true);
  const [query, setQuery] = useState("");
  const tree = useMemo(() => buildChangeTree(files), [files]);
  const ordered = useMemo(() => flattenFiles(tree), [tree]);
  const byName = useMemo(
    () => new Map(files.map((file) => [file.filename, file])),
    [files],
  );
  const results = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return [];
    return ordered
      .filter((name) => name.toLowerCase().includes(value))
      .map((name) => byName.get(name))
      .filter((file): file is ChangeFile => Boolean(file));
  }, [ordered, byName, query]);

  useEffect(() => {
    setSelected((current) =>
      current && files.some((file) => file.filename === current)
        ? current
        : files[0]?.filename ?? null
    );
  }, [files]);

  const active = files.find((file) => file.filename === selected) ?? files[0];

  function toggleFolder(path: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[16px] border border-line-4 bg-white md:flex-row">
        <div
          className={`flex flex-none flex-col bg-white ${
            treeOpen
              ? "w-full border-b border-line-6 md:w-[270px] md:border-b-0 md:border-r"
              : "w-10 items-center border-b border-line-6 py-2 md:border-b-0 md:border-r"
          }`}
        >
          {treeOpen ? (
            <>
              <div className="flex h-11 flex-none items-center gap-2 border-b border-line-4 px-2.5">
                <button
                  type="button"
                  onClick={() => setTreeOpen(false)}
                  title="收起变更树"
                  className="grid h-7 w-7 flex-none place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                >
                  <PanelLeft size={16} />
                </button>
                <div className="relative min-w-0 flex-1">
                  <Search
                    size={14}
                    className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-30"
                  />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="搜索"
                    className="h-8 w-full rounded-lg border border-line-6 bg-base px-2.5 pl-7 text-[12px] text-ink-95 outline-none transition placeholder:text-ink-30 focus:border-brand/40"
                  />
                </div>
              </div>
              <div className="max-h-[220px] min-h-0 flex-1 overflow-y-auto p-1.5 md:max-h-none">
                {files.length === 0 && loading ? (
                  <p className="px-2 py-2 text-[12px] text-ink-30">
                    正在加载变更…
                  </p>
                ) : query.trim() ? (
                  results.length ? (
                    results.map((file) => (
                      <ChangeFileRow
                        key={file.filename}
                        file={file}
                        label={file.filename}
                        active={file.filename === active?.filename}
                        paddingLeft={8}
                        onSelect={setSelected}
                      />
                    ))
                  ) : (
                    <p className="px-2 py-2 text-[12px] text-ink-30">
                      没有匹配的文件
                    </p>
                  )
                ) : (
                  <ChangeTreeRows
                    nodes={tree}
                    depth={0}
                    activePath={active?.filename ?? null}
                    collapsed={collapsed}
                    onToggle={toggleFolder}
                    onSelect={setSelected}
                  />
                )}
              </div>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setTreeOpen(true)}
              title="展开变更树"
              className="grid h-8 w-8 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
            >
              <PanelLeft size={16} />
            </button>
          )}
        </div>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {notice ? (
            <p className="flex flex-none items-start gap-1.5 border-b border-line-4 bg-[rgba(245,158,11,0.08)] px-3 py-1.5 text-[11px] leading-[16px] text-warning">
              <AlertTriangle size={12} className="mt-[2px] flex-none" />
              <span className="min-w-0">{notice}</span>
            </p>
          ) : null}
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
      ? "项目尚未发布，暂时没有线上基线，全部文件按新增展示；发布后会按发布快照计算 diff。"
      : !changes.baseline_ok
        ? "发布基线尚未建立，暂时无法计算未发布改动；下一次发布成功后会启用。"
        : null;
  const stepNote = stepDiff?.changes.some((change) => change.rolled_back)
    ? "本轮改动已回滚，以下为回滚前的 diff 记录。"
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
                <span className="rounded-full bg-[rgba(216,122,22,0.12)] px-1.5 text-[10px] font-medium text-warning">
                  {changeCount}
                </span>
              ) : changeCount == null && hasChanges ? (
                <span className="h-1.5 w-1.5 rounded-full bg-warning" />
              ) : null}
            </button>
          </div>
        )}
      </div>

      {stepDiff ? (
        <DiffBrowser
          files={stepDiff.changes.map(toChangeFile)}
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
