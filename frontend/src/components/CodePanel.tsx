import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type {
  Artifact,
  ChangeFile,
  ChangeType,
  ChangesResponse,
  FileChange,
} from "../types";
import { buildFileTree, expandDirPath, fileBadge, flattenFiles, languageLabel, type FileNode } from "../lib/files";
import { clampFontSize, readReaderPrefs, writeReaderPrefs } from "../lib/codePrefs";
import { isEditableTarget } from "../lib/keyboard";
import { useTreeWidth } from "../lib/useTreeWidth";
import ChangeMark, {
  CHANGE_LABEL,
  CHANGE_SHORT,
  CHANGE_TEXT_CLASS,
} from "./ChangeMark";
import ContentSearch from "./ContentSearch";
import DiffView, { countDiffMatches, parseDiff } from "./DiffView";
import FilePanel, { type FileFocus } from "./FilePanel";
import FilePathBreadcrumb from "./FilePathBreadcrumb";
import FindBar from "./FindBar";
import QuickOpen from "./QuickOpen";
import ShortcutHelp from "./ShortcutHelp";
import StepViewPanel, { type StepView } from "./StepViewPanel";
import {
  AlertTriangle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Code,
  Collapse,
  Expand,
  FileText,
  Folder,
  Keyboard,
  ListTree,
  PanelLeft,
  Refresh,
  Search,
  Spinner,
} from "./Icons";

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
  stepView: StepView | null;
  stepViewLoading: boolean;
  stepViewError: string | null;
  onCloseStepView: () => void;
  onOpenFile: (path: string, line?: number) => void;
  fileFocus?: FileFocus | null;
  hasChanges: boolean;
  canGoBack: boolean;
  canGoForward: boolean;
  onBack: () => void;
  onForward: () => void;
}

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

function collectChangeDirs(nodes: ChangeTreeNode[]): string[] {
  const paths: string[] = [];
  for (const node of nodes) {
    if (node.type !== "dir") continue;
    paths.push(node.path);
    paths.push(...collectChangeDirs(node.children ?? []));
  }
  return paths;
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
      data-change-path={file.filename}
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
      <span className="flex flex-none items-center gap-1 font-mono text-[10px]">
        <span className="text-[#15803d]">+{file.additions}</span>
        <span className="text-[#b91c1c]">−{file.deletions}</span>
      </span>
      <ChangeMark change={file} />
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
                data-change-path={node.path}
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

function firstHunkLine(diff: string): number | null {
  const match = /^@@ -\d+(?:,\d+)? \+(\d+)/m.exec(diff);
  if (!match) return null;
  const line = Number(match[1]);
  return Number.isFinite(line) && line > 0 ? line : null;
}

const FILTERS: { key: "all" | ChangeType; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "created", label: CHANGE_SHORT.created },
  { key: "modified", label: CHANGE_SHORT.modified },
  { key: "deleted", label: CHANGE_SHORT.deleted },
];

function DiffBrowser({
  files,
  loading,
  error,
  notice,
  emptyLabel,
  onRetry,
  onOpenFile,
  focusRequest,
  onFocusApplied,
}: {
  files: ChangeFile[];
  loading?: boolean;
  error?: string | null;
  notice?: string | null;
  emptyLabel: string;
  onRetry?: () => void;
  onOpenFile?: (path: string, line?: number) => void;
  focusRequest?: { path: string } | null;
  onFocusApplied?: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [treeOpen, setTreeOpen] = useState(true);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | ChangeType>("all");
  const [reader, setReader] = useState(readReaderPrefs);
  const [hunkIndex, setHunkIndex] = useState(0);
  const [revealTarget, setRevealTarget] = useState<string | null>(null);
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findCase, setFindCase] = useState(false);
  const [findIndex, setFindIndex] = useState(0);
  const appliedFocus = useRef<object | null>(null);
  const treeScrollRef = useRef<HTMLDivElement>(null);
  const findInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    writeReaderPrefs(reader);
  }, [reader]);
  const {
    width: treeWidth,
    dragging: treeDragging,
    containerRef: resizeContainerRef,
    startResize,
  } = useTreeWidth("changes");

  const counts = useMemo(() => {
    const next: Record<ChangeType, number> = {
      created: 0,
      modified: 0,
      deleted: 0,
    };
    for (const file of files) next[file.change_type] += 1;
    return next;
  }, [files]);

  const visibleFiles = useMemo(
    () =>
      filter === "all"
        ? files
        : files.filter((file) => file.change_type === filter),
    [files, filter]
  );

  const tree = useMemo(() => buildChangeTree(visibleFiles), [visibleFiles]);
  const ordered = useMemo(() => flattenFiles(tree), [tree]);
  const dirPaths = useMemo(() => collectChangeDirs(tree), [tree]);
  const byName = useMemo(
    () => new Map(visibleFiles.map((file) => [file.filename, file])),
    [visibleFiles]
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
      current && visibleFiles.some((file) => file.filename === current)
        ? current
        : visibleFiles[0]?.filename ?? null
    );
  }, [visibleFiles]);

  useEffect(() => {
    if (!focusRequest || appliedFocus.current === focusRequest) return;
    if (files.some((file) => file.filename === focusRequest.path)) {
      setFilter("all");
      setSelected(focusRequest.path);
      appliedFocus.current = focusRequest;
      onFocusApplied?.();
      return;
    }
    if (!loading) {
      // The requested file has no change record (any more): stop retrying.
      appliedFocus.current = focusRequest;
      onFocusApplied?.();
    }
  }, [files, focusRequest, loading, onFocusApplied]);

  useEffect(() => {
    if (!revealTarget) return;
    if (!treeOpen) {
      setRevealTarget(null);
      return;
    }
    const container = treeScrollRef.current;
    if (container) {
      const node = Array.from(
        container.querySelectorAll<HTMLElement>("[data-change-path]")
      ).find((element) => element.dataset.changePath === revealTarget);
      node?.scrollIntoView({ block: "nearest" });
    }
    setRevealTarget(null);
  }, [revealTarget, treeOpen, collapsed]);

  const active =
    visibleFiles.find((file) => file.filename === selected) ??
    visibleFiles[0];

  const diffLineCount = useMemo(() => {
    if (!active) return 0;
    return parseDiff(active.diff).filter(
      (line) =>
        line.kind === "add" ||
        line.kind === "del" ||
        line.kind === "context"
    ).length;
  }, [active]);

  const hunkCount = useMemo(() => {
    if (!active) return 0;
    let count = 0;
    for (const line of active.diff.split("\n")) {
      if (line.startsWith("@@")) count += 1;
    }
    return count;
  }, [active]);

  useEffect(() => {
    setHunkIndex(0);
  }, [active?.filename, active?.diff]);

  const findTotal = useMemo(
    () =>
      findOpen
        ? countDiffMatches(active?.diff ?? "", findQuery, findCase)
        : 0,
    [active?.diff, findCase, findOpen, findQuery]
  );
  const activeMatch = findTotal ? Math.min(findIndex, findTotal - 1) : -1;

  useEffect(() => {
    setFindIndex(0);
  }, [findQuery, findCase, active?.filename]);

  useEffect(() => {
    if (!findOpen) return;
    const timer = window.setTimeout(() => findInputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [findOpen]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        !(event.metaKey || event.ctrlKey) ||
        event.altKey ||
        event.shiftKey
      ) {
        return;
      }
      if (event.key.toLowerCase() !== "f") return;
      if (
        isEditableTarget(event.target) &&
        event.target !== findInputRef.current
      ) {
        return;
      }
      event.preventDefault();
      setFindOpen(true);
      window.setTimeout(() => findInputRef.current?.select(), 0);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function stepFind(delta: number) {
    if (!findTotal) return;
    setFindIndex(
      (current) => (current + delta + findTotal) % findTotal
    );
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "F3") return;
      if (isEditableTarget(event.target)) return;
      event.preventDefault();
      if (!hunkCount) return;
      setHunkIndex(
        (current) =>
          (current + (event.shiftKey ? -1 : 1) + hunkCount) % hunkCount
      );
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hunkCount]);

  function stepHunk(delta: number) {
    if (!hunkCount) return;
    setHunkIndex((current) => (current + delta + hunkCount) % hunkCount);
  }

  function toggleWrap() {
    setReader((current) => ({ ...current, wrap: !current.wrap }));
  }

  function stepFont(delta: number) {
    setReader((current) => ({
      ...current,
      fontSize: clampFontSize(current.fontSize + delta),
    }));
  }

  function openInFiles() {
    if (!active || active.change_type === "deleted") return;
    onOpenFile?.(active.filename, firstHunkLine(active.diff) ?? undefined);
  }

  function toggleFolder(path: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function collapseAll() {
    setCollapsed(new Set(dirPaths));
  }

  function expandAll() {
    setCollapsed(new Set());
  }

  function revealChangeDir(dir: string) {
    setTreeOpen(true);
    setCollapsed((current) => expandDirPath(current, `${dir}/_`) ?? current);
    setRevealTarget(dir);
  }

  const emptyText =
    filter !== "all" ? "当前筛选下没有改动的文件。" : emptyLabel;

  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div
        ref={resizeContainerRef}
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[16px] border border-line-4 bg-white md:flex-row"
        style={{ "--tree-width": `${treeWidth}px` } as CSSProperties}
      >
        <div
          className={`flex flex-none flex-col bg-white ${
            treeOpen
              ? "w-full border-b border-line-6 md:w-[var(--tree-width)] md:border-b-0 md:border-r"
              : "w-10 items-center border-b border-line-6 py-2 md:border-b-0 md:border-r"
          }`}
        >
          {treeOpen ? (
            <>
              <div className="flex h-11 flex-none items-center gap-1.5 border-b border-line-4 px-2.5">
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
                <button
                  type="button"
                  onClick={collapseAll}
                  title="全部折叠"
                  className="grid h-7 w-7 flex-none place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                >
                  <Collapse size={14} />
                </button>
                <button
                  type="button"
                  onClick={expandAll}
                  title="全部展开"
                  className="grid h-7 w-7 flex-none place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                >
                  <Expand size={14} />
                </button>
              </div>
              {files.length ? (
                <div className="flex flex-wrap items-center gap-1 border-b border-line-4 px-2.5 pb-2">
                  {FILTERS.map((option) => {
                    const count =
                      option.key === "all" ? files.length : counts[option.key];
                    const activeChip = filter === option.key;
                    const colorClass = count
                      ? option.key === "all"
                        ? activeChip
                          ? "text-ink-95"
                          : "text-ink-55 hover:text-ink-95"
                        : CHANGE_TEXT_CLASS[option.key]
                      : "text-ink-30";
                    const bgClass = activeChip
                      ? "bg-line-6 font-medium"
                      : count
                        ? "hover:bg-line-4"
                        : "cursor-default";
                    return (
                      <button
                        key={option.key}
                        type="button"
                        onClick={() => setFilter(option.key)}
                        disabled={!count}
                        title={
                          option.key === "all"
                            ? "全部改动"
                            : CHANGE_LABEL[option.key]
                        }
                        className={`inline-flex h-6 items-center gap-1 rounded-full px-2 text-[10.5px] transition ${bgClass} ${colorClass}`}
                      >
                        {option.label}
                        <span className="font-mono">{count}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}
              <div
                ref={treeScrollRef}
                className="max-h-[220px] min-h-0 flex-1 overflow-y-auto p-1.5 md:max-h-none"
              >
                {visibleFiles.length === 0 && loading ? (
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

        {treeOpen ? (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="调整变更树宽度"
            data-dragging={treeDragging}
            onPointerDown={startResize}
            className="splitter-handle hidden flex-none md:flex"
          />
        ) : null}

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
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <FileBadge name={active.filename} />
                  <FilePathBreadcrumb
                    path={active.filename}
                    onSelectDir={revealChangeDir}
                  />
                </div>
                <div className="flex flex-none items-center gap-1.5">
                  <span className="flex items-center gap-1 font-mono text-[11px]">
                    <span className="text-[#15803d]">+{active.additions}</span>
                    <span className="text-[#b91c1c]">−{active.deletions}</span>
                  </span>
                  <div className="flex items-center rounded-md bg-line-4 p-0.5">
                    <button
                      type="button"
                      onClick={() => stepHunk(-1)}
                      disabled={!hunkCount}
                      title="上一处改动（Shift+F3）"
                      className="grid h-6 w-6 place-items-center rounded text-ink-55 transition hover:bg-white hover:text-ink-95 disabled:opacity-30"
                    >
                      <ChevronUp size={13} />
                    </button>
                    <span className="min-w-[34px] px-0.5 text-center font-mono text-[10.5px] text-ink-55">
                      {hunkCount ? `${hunkIndex + 1}/${hunkCount}` : "0/0"}
                    </span>
                    <button
                      type="button"
                      onClick={() => stepHunk(1)}
                      disabled={!hunkCount}
                      title="下一处改动（F3）"
                      className="grid h-6 w-6 place-items-center rounded text-ink-55 transition hover:bg-white hover:text-ink-95 disabled:opacity-30"
                    >
                      <ChevronDown size={13} />
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setFindOpen(true);
                      window.setTimeout(
                        () => findInputRef.current?.select(),
                        0
                      );
                    }}
                    title="在改动中查找（⌘F / Ctrl+F）"
                    className={`grid h-7 w-7 place-items-center rounded-md transition hover:bg-line-4 hover:text-ink-95 ${
                      findOpen ? "bg-line-4 text-ink-95" : "text-ink-55"
                    }`}
                  >
                    <Search size={14} />
                  </button>
                  {onOpenFile ? (
                    <button
                      type="button"
                      onClick={openInFiles}
                      disabled={active.change_type === "deleted"}
                      title={
                        active.change_type === "deleted"
                          ? "文件已删除，只能查看 diff"
                          : "在文件中打开"
                      }
                      className="inline-flex h-7 items-center rounded-md px-1.5 text-[11px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-30"
                    >
                      打开文件
                    </button>
                  ) : null}
                </div>
              </div>
              {error ? (
                <p className="border-b border-line-4 bg-[rgba(239,68,68,0.06)] px-3 py-1.5 text-[11px] text-danger">
                  {error}
                </p>
              ) : null}
              <div className="relative flex min-h-0 flex-1 flex-col">
                {findOpen ? (
                  <FindBar
                    query={findQuery}
                    onQueryChange={setFindQuery}
                    caseSensitive={findCase}
                    onToggleCase={() => setFindCase((value) => !value)}
                    current={activeMatch}
                    total={findTotal}
                    onPrev={() => stepFind(-1)}
                    onNext={() => stepFind(1)}
                    onClose={() => setFindOpen(false)}
                    inputRef={findInputRef}
                    placeholder="在改动中查找"
                  />
                ) : null}
                <DiffView
                  diff={active.diff}
                  truncated={active.truncated}
                  wrap={reader.wrap}
                  hunkIndex={hunkIndex}
                  findQuery={findOpen ? findQuery : ""}
                  findCase={findCase}
                  activeMatch={activeMatch}
                  fontSize={reader.fontSize}
                />
              </div>
              <div className="flex h-7 flex-none items-center justify-between gap-2 border-t border-line-4 px-3 text-[10.5px] text-ink-30">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="truncate">
                    {languageLabel(active.filename)}
                  </span>
                  <span className="flex-none" title="当前 diff 内容行数">
                    {diffLineCount} 行
                  </span>
                </div>
                <div className="flex flex-none items-center gap-1">
                  <button
                    type="button"
                    onClick={toggleWrap}
                    title="自动换行"
                    className={`rounded px-1.5 py-0.5 transition hover:bg-line-4 hover:text-ink-95 ${
                      reader.wrap ? "text-brand-text" : ""
                    }`}
                  >
                    自动换行{reader.wrap ? "：开" : "：关"}
                  </button>
                  <span className="text-line-12">|</span>
                  <button
                    type="button"
                    onClick={() => stepFont(-0.5)}
                    title="缩小字号"
                    className="rounded px-1 py-0.5 transition hover:bg-line-4 hover:text-ink-95"
                  >
                    A−
                  </button>
                  <span className="w-6 text-center font-mono">
                    {reader.fontSize}
                  </span>
                  <button
                    type="button"
                    onClick={() => stepFont(0.5)}
                    title="放大字号"
                    className="rounded px-1 py-0.5 transition hover:bg-line-4 hover:text-ink-95"
                  >
                    A+
                  </button>
                </div>
              </div>
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
                    {emptyText}
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
  stepView,
  stepViewLoading,
  stepViewError,
  onCloseStepView,
  onOpenFile,
  fileFocus = null,
  hasChanges,
  canGoBack,
  canGoForward,
  onBack,
  onForward,
}: Props) {
  const [quickOpen, setQuickOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutOpen, setShortcutOpen] = useState(false);
  const [changeFocus, setChangeFocus] = useState<{ path: string } | null>(
    null
  );
  const [recent, setRecent] = useState<string[]>([]);
  const names = useMemo(() => Object.keys(artifacts), [artifacts]);

  useEffect(() => {
    if (!activeFile) return;
    setRecent((current) =>
      current[0] === activeFile
        ? current
        : [activeFile, ...current.filter((path) => path !== activeFile)].slice(
            0,
            8
          )
    );
  }, [activeFile]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key !== "p" && key !== "f") return;
      if (isEditableTarget(event.target)) return;
      if (key === "p" && !event.shiftKey) {
        event.preventDefault();
        setSearchOpen(false);
        setQuickOpen((open) => !open);
        return;
      }
      if (key === "f" && event.shiftKey) {
        event.preventDefault();
        setQuickOpen(false);
        setSearchOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.altKey || event.metaKey || event.ctrlKey || event.shiftKey) {
        return;
      }
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      if (isEditableTarget(event.target)) return;
      event.preventDefault();
      if (event.key === "ArrowLeft") historyBack();
      else historyForward();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onBack, onForward]);

  useEffect(() => {
    if (stepView) setSearchOpen(false);
  }, [stepView]);

  function historyBack() {
    setSearchOpen(false);
    setQuickOpen(false);
    onBack();
  }

  function historyForward() {
    setSearchOpen(false);
    setQuickOpen(false);
    onForward();
  }

  const changeCount = changes?.files.length ?? null;
  const aggregateNote = !changes
    ? null
    : !changes.has_published
      ? "项目尚未发布，暂时没有线上基线，全部文件按新增展示；发布后会按发布快照计算 diff。"
      : !changes.baseline_ok
        ? "发布基线尚未建立，暂时无法计算未发布改动；下一次发布成功后会启用。"
        : null;
  const stepNote = stepView?.changes?.some((change) => change.rolled_back)
    ? "本轮改动已回滚，以下为回滚前的 diff 记录。"
    : null;

  return (
    <section className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="flex h-10 flex-none items-center justify-between gap-2 px-2 pb-1">
        <div className="flex min-w-0 items-center gap-2">
          {stepView ? (
            <>
              <button
                type="button"
                onClick={onCloseStepView}
                className="inline-flex h-7 flex-none items-center gap-1 rounded-md px-2 text-[12px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
              >
                <ChevronLeft size={14} /> 返回代码
              </button>
              <span className="min-w-0 truncate text-[12px] text-ink-55">
                步骤 · {stepView.title}
              </span>
            </>
          ) : (
            <div className="flex items-center rounded-full bg-line-4 p-0.5">
              <button
                type="button"
                onClick={() => {
                  setSearchOpen(false);
                  onViewChange("files");
                }}
                className={`flex h-[26px] items-center gap-1.5 rounded-full px-2.5 text-[12px] transition ${
                  view === "files" && !searchOpen
                    ? "bg-white font-medium text-ink-95 shadow-[0_1px_3px_rgba(12,12,12,0.10)]"
                    : "text-ink-55 hover:text-ink-80"
                }`}
              >
                <FileText size={13} />
                文件
              </button>
              <button
                type="button"
                onClick={() => {
                  setSearchOpen(false);
                  onViewChange("changes");
                }}
                className={`flex h-[26px] items-center gap-1.5 rounded-full px-2.5 text-[12px] transition ${
                  view === "changes" && !searchOpen
                    ? "bg-white font-medium text-ink-95 shadow-[0_1px_3px_rgba(12,12,12,0.10)]"
                    : "text-ink-55 hover:text-ink-80"
                }`}
              >
                <Code size={13} />
                未发布改动
                {changeCount != null && changeCount > 0 ? (
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
        <div className="flex flex-none items-center gap-0.5">
          {!stepView && view === "files" ? (
            <>
              <button
                type="button"
                onClick={historyBack}
                disabled={!canGoBack}
                title="后退（Alt+←）"
                className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-30"
              >
                <ChevronLeft size={15} />
              </button>
              <button
                type="button"
                onClick={historyForward}
                disabled={!canGoForward}
                title="前进（Alt+→）"
                className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-30"
              >
                <ChevronRight size={15} />
              </button>
              <button
                type="button"
                onClick={() => {
                  setSearchOpen(false);
                  setQuickOpen(true);
                }}
                title="快速打开文件（⌘P / Ctrl+P）"
                className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[12px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
              >
                <Search size={14} />
                <span className="hidden lg:inline">快速打开</span>
              </button>
            </>
          ) : null}
          {!stepView ? (
            <button
              type="button"
              onClick={() => {
                setQuickOpen(false);
                setSearchOpen((open) => !open);
              }}
              title="全文搜索（⌘⇧F / Ctrl+Shift+F）"
              className={`inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[12px] transition hover:bg-line-4 hover:text-ink-95 ${
                searchOpen ? "bg-line-4 text-ink-95" : "text-ink-55"
              }`}
            >
              <ListTree size={14} />
              <span className="hidden lg:inline">全文搜索</span>
            </button>
          ) : null}
          {!stepView ? (
            <button
              type="button"
              onClick={() => setShortcutOpen(true)}
              title="快捷键"
              className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
            >
              <Keyboard size={15} />
            </button>
          ) : null}
        </div>
      </div>

      {stepView ? (
        stepView.kind === "diff" ? (
          <DiffBrowser
            files={(stepView.changes ?? []).map(toChangeFile)}
            loading={stepViewLoading}
            error={stepViewError}
            notice={stepNote}
            emptyLabel="这次步骤没有记录到文件改动。"
            onOpenFile={onOpenFile}
          />
        ) : (
          <StepViewPanel
            view={stepView}
            loading={stepViewLoading}
            error={stepViewError}
            onOpenFile={onOpenFile}
          />
        )
      ) : searchOpen ? (
        <ContentSearch
          artifacts={artifacts}
          onClose={() => setSearchOpen(false)}
          onOpenFile={(path, line) => {
            setSearchOpen(false);
            onOpenFile(path, line);
          }}
        />
      ) : view === "files" ? (
        <FilePanel
          projectId={projectId}
          artifacts={artifacts}
          activeFile={activeFile}
          onSelect={onSelect}
          streamingFile={streamingFile}
          streamingBuffer={streamingBuffer}
          focus={fileFocus}
          changes={changes}
          onOpenChange={(path) => {
            setChangeFocus({ path });
            onViewChange("changes");
          }}
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
          onOpenFile={onOpenFile}
          focusRequest={changeFocus}
          onFocusApplied={() => setChangeFocus(null)}
        />
      )}

      <QuickOpen
        open={quickOpen}
        names={names}
        recent={recent}
        onClose={() => setQuickOpen(false)}
        onOpen={(path) => {
          setQuickOpen(false);
          onOpenFile(path);
        }}
      />

      {shortcutOpen ? (
        <ShortcutHelp
          activeView={view}
          onClose={() => setShortcutOpen(false)}
        />
      ) : null}
    </section>
  );
}
