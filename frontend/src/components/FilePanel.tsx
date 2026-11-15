import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { api } from "../api";
import type {
  Artifact,
  ChangeFile,
  ChangesResponse,
} from "../types";
import {
  buildFileTree,
  expandDirPath,
  fileBadge,
  flattenFiles,
  formatBytes,
  languageForFile,
  languageLabel,
  type FileNode,
} from "../lib/files";
import { copyText } from "../lib/clipboard";
import {
  clampFontSize,
  readReaderPrefs,
  readTreePrefs,
  writeReaderPrefs,
  writeTreePrefs,
} from "../lib/codePrefs";
import { isEditableTarget } from "../lib/keyboard";
import { useTreeWidth } from "../lib/useTreeWidth";
import { tokenizeLine } from "../lib/highlight";
import ChangeMark from "./ChangeMark";
import FilePathBreadcrumb from "./FilePathBreadcrumb";
import FindBar from "./FindBar";
import {
  ChevronRight,
  Code,
  Collapse,
  Check,
  Copy,
  Download,
  Expand,
  FileText,
  Folder,
  PanelLeft,
  Search,
  Spinner,
} from "./Icons";

export interface FileFocus {
  path: string;
  start: number;
  end: number;
  note?: string;
}

interface Props {
  projectId: string;
  artifacts: Record<string, Artifact>;
  activeFile: string | null;
  onSelect: (filename: string) => void;
  streamingFile: string | null;
  streamingBuffer: string;
  focus?: FileFocus | null;
  changes?: ChangesResponse | null;
  onOpenChange?: (path: string) => void;
}

function TypeBadge({ name, size = 16 }: { name: string; size?: number }) {
  const badge = fileBadge(name);
  return (
    <span
      className="grid flex-none place-items-center rounded-[4px] font-mono font-medium"
      style={{
        width: size,
        height: size,
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

function collectDirs(nodes: FileNode[]): string[] {
  const paths: string[] = [];
  for (const node of nodes) {
    if (node.type !== "dir") continue;
    paths.push(node.path);
    paths.push(...collectDirs(node.children ?? []));
  }
  return paths;
}

function TreeRows({
  nodes,
  depth,
  activeFile,
  streamingFile,
  collapsed,
  onToggle,
  onSelect,
  changeByPath,
  changedDirs,
}: {
  nodes: FileNode[];
  depth: number;
  activeFile: string | null;
  streamingFile: string | null;
  collapsed: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
  changeByPath: Map<string, ChangeFile>;
  changedDirs: Set<string>;
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
                data-tree-path={node.path}
                onClick={() => onToggle(node.path)}
                title={node.path}
                className="flex h-[26px] w-full items-center gap-1.5 rounded-md pr-2 text-left text-[13px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
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
                {changedDirs.has(node.path) ? (
                  <span
                    title="包含未发布改动"
                    className="h-1.5 w-1.5 flex-none rounded-full bg-warning"
                  />
                ) : null}
              </button>
              {isCollapsed ? null : (
                <TreeRows
                  nodes={node.children ?? []}
                  depth={depth + 1}
                  activeFile={activeFile}
                  streamingFile={streamingFile}
                  collapsed={collapsed}
                  onToggle={onToggle}
                  onSelect={onSelect}
                  changeByPath={changeByPath}
                  changedDirs={changedDirs}
                />
              )}
            </div>
          );
        }
        const active = node.path === activeFile;
        const streaming = node.path === streamingFile;
        const change = changeByPath.get(node.path);
        return (
          <button
            key={node.path}
            type="button"
            data-tree-path={node.path}
            title={node.path}
            onClick={() => onSelect(node.path)}
            className={`flex h-[26px] w-full items-center gap-1.5 rounded-md pr-2 text-left text-[13px] transition ${
              active
                ? "bg-line-6 text-ink-95"
                : "text-ink-80 hover:bg-line-4 hover:text-ink-95"
            }`}
            style={{ paddingLeft: pad + 13 }}
          >
            <TypeBadge name={node.name} />
            <span className="min-w-0 flex-1 truncate">{node.name}</span>
            {change ? <ChangeMark change={change} /> : null}
            {streaming ? (
              <span className="h-1.5 w-1.5 flex-none animate-pulse rounded-full bg-brand" />
            ) : null}
          </button>
        );
      })}
    </>
  );
}

export default function FilePanel({
  projectId,
  artifacts,
  activeFile,
  onSelect,
  streamingFile,
  streamingBuffer,
  focus = null,
  changes = null,
  onOpenChange,
}: Props) {
  const [query, setQuery] = useState("");
  const [treeOpen, setTreeOpen] = useState(
    () => readTreePrefs(projectId).open
  );
  const [collapsed, setCollapsed] = useState<Set<string>>(
    () => new Set(readTreePrefs(projectId).collapsed)
  );
  const [reader, setReader] = useState(readReaderPrefs);
  const [copied, setCopied] = useState(false);
  const [pathCopied, setPathCopied] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [findOpen, setFindOpen] = useState(false);
  const [findQuery, setFindQuery] = useState("");
  const [findCase, setFindCase] = useState(false);
  const [findIndex, setFindIndex] = useState(0);
  const [gotoOpen, setGotoOpen] = useState(false);
  const [gotoValue, setGotoValue] = useState("");
  const [gotoError, setGotoError] = useState<string | null>(null);
  const [activeLine, setActiveLine] = useState<number | null>(null);
  const [revealTarget, setRevealTarget] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const treeScrollRef = useRef<HTMLDivElement>(null);
  const findInputRef = useRef<HTMLInputElement>(null);
  const gotoInputRef = useRef<HTMLInputElement>(null);
  const {
    width: treeWidth,
    dragging: treeDragging,
    containerRef: resizeContainerRef,
    startResize,
  } = useTreeWidth("files");

  const names = useMemo(() => {
    const set = new Set(Object.keys(artifacts));
    if (streamingFile) set.add(streamingFile);
    return Array.from(set);
  }, [artifacts, streamingFile]);

  const tree = useMemo(() => buildFileTree(names), [names]);
  const flat = useMemo(() => flattenFiles(tree), [tree]);
  const dirPaths = useMemo(() => collectDirs(tree), [tree]);

  const changeByPath = useMemo(
    () =>
      new Map((changes?.files ?? []).map((file) => [file.filename, file])),
    [changes]
  );
  const changedDirs = useMemo(() => {
    const dirs = new Set<string>();
    for (const file of changes?.files ?? []) {
      const parts = file.filename.split("/").filter(Boolean);
      for (let index = 1; index < parts.length; index += 1) {
        dirs.add(parts.slice(0, index).join("/"));
      }
    }
    return dirs;
  }, [changes]);

  const results = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return [];
    return flat.filter((name) => name.toLowerCase().includes(value));
  }, [flat, query]);

  const active = activeFile ? artifacts[activeFile] : undefined;
  const isStreaming = Boolean(activeFile && activeFile === streamingFile);
  const focusActive = Boolean(focus && activeFile && focus.path === activeFile);
  const content = isStreaming ? streamingBuffer : active?.content ?? "";
  const lang = languageForFile(activeFile ?? "");
  const lines = useMemo(() => content.split("\n"), [content]);
  const simple = lines.length > 1800;
  const fontSize = reader.fontSize;
  const lineHeight = Math.round(fontSize * 1.75);
  const focusRange =
    focusActive && focus
      ? {
          start: Math.max(1, focus.start),
          end: Math.max(focus.start, focus.end),
        }
      : null;
  const lineInFocus = (index: number) =>
    Boolean(
      focusRange &&
        index + 1 >= focusRange.start &&
        index + 1 <= focusRange.end
    );

  const findMatches = useMemo(() => {
    if (!findOpen || !findQuery) return [];
    const needle = findCase ? findQuery : findQuery.toLowerCase();
    const matches: { line: number; start: number; end: number }[] = [];
    for (let index = 0; index < lines.length; index += 1) {
      const text = lines[index];
      const haystack = findCase ? text : text.toLowerCase();
      let from = 0;
      while (from <= haystack.length) {
        const at = haystack.indexOf(needle, from);
        if (at === -1) break;
        matches.push({
          line: index + 1,
          start: at,
          end: at + findQuery.length,
        });
        from = at + Math.max(1, needle.length);
        if (matches.length >= 2000) break;
      }
      if (matches.length >= 2000) break;
    }
    return matches;
  }, [findCase, findOpen, findQuery, lines]);

  const matchesByLine = useMemo(() => {
    const byLine = new Map<
      number,
      { start: number; end: number; index: number }[]
    >();
    findMatches.forEach((match, index) => {
      let list = byLine.get(match.line);
      if (!list) {
        list = [];
        byLine.set(match.line, list);
      }
      list.push({ start: match.start, end: match.end, index });
    });
    return byLine;
  }, [findMatches]);

  const activeMatch = findMatches.length
    ? Math.min(findIndex, findMatches.length - 1)
    : -1;

  useEffect(() => {
    writeTreePrefs(projectId, {
      open: treeOpen,
      collapsed: Array.from(collapsed),
    });
  }, [projectId, treeOpen, collapsed]);

  useEffect(() => {
    writeReaderPrefs(reader);
  }, [reader]);

  useEffect(() => {
    const target = streamingFile ?? activeFile;
    if (!target) return;
    setCollapsed((current) => expandDirPath(current, target) ?? current);
    setRevealTarget(target);
  }, [activeFile, streamingFile]);

  useEffect(() => {
    if (!revealTarget) return;
    if (!treeOpen) {
      setRevealTarget(null);
      return;
    }
    const container = treeScrollRef.current;
    if (container) {
      const node = Array.from(
        container.querySelectorAll<HTMLElement>("[data-tree-path]")
      ).find((element) => element.dataset.treePath === revealTarget);
      node?.scrollIntoView({ block: "nearest" });
    }
    setRevealTarget(null);
  }, [revealTarget, treeOpen, collapsed]);

  useEffect(() => {
    setCopied(false);
    setPathCopied(false);
    setActiveLine(null);
    setFindIndex(0);
    const el = scrollRef.current;
    if (el) el.scrollTop = 0;
  }, [activeFile]);

  useEffect(() => {
    if (!focusActive || !focus) return;
    const el = scrollRef.current;
    if (!el) return;
    const top = Math.max(0, (Math.max(1, focus.start) - 1) * lineHeight - 66);
    el.scrollTop = top;
  }, [focusActive, focus, activeFile, content, lineHeight]);

  useEffect(() => {
    if (!isStreaming) return;
    if (findOpen && findQuery) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [streamingBuffer, isStreaming, findOpen, findQuery]);

  useEffect(() => {
    setFindIndex(0);
  }, [findQuery, findCase]);

  useEffect(() => {
    if (!findOpen) return;
    const timer = window.setTimeout(() => findInputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [findOpen]);

  useEffect(() => {
    if (!gotoOpen) return;
    setGotoError(null);
    gotoInputRef.current?.focus();
  }, [gotoOpen]);

  useEffect(() => {
    if (!findOpen || !findQuery || !findMatches.length) return;
    const match = findMatches[Math.min(findIndex, findMatches.length - 1)];
    if (!match) return;
    setActiveLine(match.line);
    scrollToLine(match.line, true);
  }, [findOpen, findQuery, findIndex, findMatches]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key !== "f" && key !== "g") return;
      const ownInput =
        event.target === findInputRef.current ||
        event.target === gotoInputRef.current;
      if (isEditableTarget(event.target) && !ownInput) return;
      event.preventDefault();
      if (key === "f") {
        setFindOpen(true);
        window.setTimeout(() => findInputRef.current?.select(), 0);
      } else {
        setGotoOpen(true);
        setGotoValue("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function toggleFolder(path: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
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

  function revealFolder(path: string) {
    setTreeOpen(true);
    // Add a fake child so the clicked directory itself is expanded too.
    setCollapsed((current) => expandDirPath(current, `${path}/_`) ?? current);
    setRevealTarget(path);
  }

  function scrollToLine(line: number, center: boolean) {
    const el = scrollRef.current;
    if (!el) return;
    const top = (line - 1) * lineHeight;
    el.scrollTop = Math.max(0, center ? top - el.clientHeight / 2 : top - 66);
  }

  function stepFind(delta: number) {
    if (!findMatches.length) return;
    setFindIndex(
      (current) =>
        (current + delta + findMatches.length) % findMatches.length
    );
  }

  function jumpToLine(raw: string) {
    const value = Number.parseInt(raw.trim(), 10);
    if (!Number.isFinite(value) || value < 1) {
      setGotoError("请输入有效的行号");
      return;
    }
    const line = Math.min(lines.length, value);
    setActiveLine(line);
    scrollToLine(line, true);
    setGotoOpen(false);
    setGotoValue("");
  }

  async function copy() {
    if (!content) return;
    const ok = await copyText(content);
    setCopied(ok);
    if (ok) window.setTimeout(() => setCopied(false), 1500);
  }

  async function copyPath() {
    if (!activeFile) return;
    const ok = await copyText(activeFile);
    setPathCopied(ok);
    if (ok) window.setTimeout(() => setPathCopied(false), 1500);
  }

  function saveBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadFile() {
    if (!activeFile || !content) return;
    saveBlob(
      new Blob([content], { type: "text/plain;charset=utf-8" }),
      activeFile.split("/").pop() ?? "file.txt"
    );
  }

  async function exportProject() {
    if (exporting) return;
    setExporting(true);
    setExportError(null);
    try {
      const { blob, filename } = await api.exportProject(projectId);
      saveBlob(blob, filename);
    } catch (err) {
      setExportError((err as Error).message || "导出失败，请稍后重试。");
    } finally {
      setExporting(false);
    }
  }

  function lineRowClass(index: number) {
    const activeRow = activeLine === index + 1;
    const inFocus = lineInFocus(index);
    if (inFocus && activeRow) return "bg-[rgba(66,103,255,0.10)]";
    if (inFocus) return "bg-[rgba(66,103,255,0.06)]";
    if (activeRow) return "bg-[rgba(12,12,12,0.035)]";
    return "";
  }

  function renderLineContent(line: string, lineNumber: number) {
    const tokens = simple
      ? [{ text: line || " " }]
      : tokenizeLine(line, lang);
    const hitList =
      findOpen && findQuery ? matchesByLine.get(lineNumber) : undefined;

    if (!hitList || !hitList.length) {
      return tokens.map((token, index) =>
        token.className ? (
          <span key={index} className={token.className}>
            {token.text}
          </span>
        ) : (
          <span key={index}>{token.text}</span>
        )
      );
    }

    const out: ReactNode[] = [];
    let key = 0;
    let offset = 0;
    for (const token of tokens) {
      const tokenStart = offset;
      const tokenEnd = offset + token.text.length;
      let cursor = tokenStart;
      for (const match of hitList) {
        if (match.end <= tokenStart || match.start >= tokenEnd) continue;
        const start = Math.max(match.start, tokenStart);
        const end = Math.min(match.end, tokenEnd);
        if (start > cursor) {
          const text = line.slice(cursor, start);
          out.push(
            token.className ? (
              <span key={key++} className={token.className}>
                {text}
              </span>
            ) : (
              <span key={key++}>{text}</span>
            )
          );
        }
        const matchText = line.slice(start, end);
        out.push(
          match.index === activeMatch ? (
            <span
              key={key++}
              className="rounded-[2px] bg-brand text-white"
            >
              {matchText}
            </span>
          ) : (
            <span
              key={key++}
              className={`${token.className ?? ""} rounded-[2px] bg-[rgba(66,103,255,0.20)]`}
            >
              {matchText}
            </span>
          )
        );
        cursor = end;
      }
      if (cursor < tokenEnd) {
        const text = line.slice(cursor, tokenEnd);
        out.push(
          token.className ? (
            <span key={key++} className={token.className}>
              {text}
            </span>
          ) : (
            <span key={key++}>{text}</span>
          )
        );
      }
      offset = tokenEnd;
    }
    return out;
  }

  const activeChange = activeFile ? changeByPath.get(activeFile) : undefined;

  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div
        ref={resizeContainerRef}
        className="flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-[16px] border border-line-4 bg-white"
        style={{ "--tree-width": `${treeWidth}px` } as CSSProperties}
      >
        {treeOpen ? (
          <>
            <div className="flex w-full flex-none flex-col border-r border-line-6 bg-white md:w-[var(--tree-width)]">
            <div className="flex h-11 flex-none items-center gap-1.5 border-b border-line-4 px-2.5">
              <button
                type="button"
                onClick={() => setTreeOpen(false)}
                title="收起文件树"
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

            <div
              ref={treeScrollRef}
              className="min-h-0 flex-1 overflow-y-auto p-1.5"
            >
              {names.length === 0 ? (
                <p className="px-2 py-2 text-[12px] text-ink-30">
                  等待 Coder 生成文件…
                </p>
              ) : query.trim() ? (
                results.length ? (
                  results.map((name) => {
                    const change = changeByPath.get(name);
                    return (
                      <button
                        key={name}
                        type="button"
                        title={name}
                        onClick={() => onSelect(name)}
                        className={`flex h-[26px] w-full items-center gap-1.5 rounded-md px-2 text-left text-[12px] transition ${
                          name === activeFile
                            ? "bg-line-6 text-ink-95"
                            : "text-ink-80 hover:bg-line-4 hover:text-ink-95"
                        }`}
                      >
                        <TypeBadge name={name} />
                        <span className="min-w-0 flex-1 truncate">{name}</span>
                        {change ? <ChangeMark change={change} /> : null}
                      </button>
                    );
                  })
                ) : (
                  <p className="px-2 py-2 text-[12px] text-ink-30">
                    没有匹配的文件
                  </p>
                )
              ) : (
                <TreeRows
                  nodes={tree}
                  depth={0}
                  activeFile={activeFile}
                  streamingFile={streamingFile}
                  collapsed={collapsed}
                  onToggle={toggleFolder}
                  onSelect={onSelect}
                  changeByPath={changeByPath}
                  changedDirs={changedDirs}
                />
              )}
            </div>

            <div className="flex-none border-t border-line-4 p-2">
              <button
                type="button"
                onClick={() => void exportProject()}
                disabled={!names.length || exporting}
                title="把最新源代码打包为 ZIP 仓库压缩包"
                className="flex h-8 w-full items-center justify-center gap-1.5 rounded-lg border border-line-6 text-[12px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
              >
                {exporting ? <Spinner size={14} /> : <Download size={14} />}
                {exporting ? "正在打包…" : "导出项目"}
              </button>
              {exportError ? (
                <p className="mt-1.5 px-1 text-[11px] leading-[16px] text-danger">
                  {exportError}
                </p>
              ) : null}
            </div>
            </div>
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="调整文件树宽度"
              data-dragging={treeDragging}
              onPointerDown={startResize}
              className="splitter-handle hidden flex-none md:flex"
            />
          </>
        ) : (
          <div className="flex w-10 flex-none flex-col items-center border-r border-line-6 bg-white py-2">
            <button
              type="button"
              onClick={() => setTreeOpen(true)}
              title="展开文件树"
              className="grid h-8 w-8 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
            >
              <PanelLeft size={16} />
            </button>
          </div>
        )}

        <div className="relative flex min-w-0 flex-1 flex-col bg-white">
          {activeFile ? (
            <>
              <div className="flex h-11 flex-none items-center justify-between gap-3 border-b border-line-4 px-3">
                <div className="flex min-w-0 items-center gap-1.5">
                  <TypeBadge name={activeFile} size={18} />
                  <FilePathBreadcrumb
                    path={activeFile}
                    onSelectDir={revealFolder}
                  />
                  {isStreaming ? (
                    <span className="flex-none rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-text">
                      写入中
                    </span>
                  ) : (
                    <span className="flex-none text-[11px] text-ink-30">
                      {formatBytes(content.length)}
                    </span>
                  )}
                  {focusActive ? (
                    <span className="flex-none rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-text">
                      {focus?.note ?? `L${focus?.start}–${focus?.end}`}
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-none items-center gap-1">
                  {activeChange && onOpenChange ? (
                    <button
                      type="button"
                      onClick={() => onOpenChange(activeFile)}
                      title="查看该文件的未发布改动"
                      className="inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-[11px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                    >
                      <Code size={13} />
                      <span className="hidden xl:inline">查看改动</span>
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => {
                      setFindOpen(true);
                      window.setTimeout(
                        () => findInputRef.current?.select(),
                        0
                      );
                    }}
                    title="文件内查找（⌘F / Ctrl+F）"
                    className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                  >
                    <Search size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={() => void copyPath()}
                    title="复制文件路径"
                    className="inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-[11px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                  >
                    {pathCopied ? <Check size={13} /> : <Copy size={13} />}
                    路径
                  </button>
                  <button
                    type="button"
                    onClick={copy}
                    disabled={!content}
                    title="复制文件内容"
                    className="inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-[11px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
                  >
                    {copied ? <Check size={13} /> : <Copy size={13} />}
                    内容
                  </button>
                  <button
                    type="button"
                    onClick={downloadFile}
                    disabled={!content}
                    title="下载当前文件"
                    className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
                  >
                    <Download size={14} />
                  </button>
                </div>
              </div>

              {gotoOpen ? (
                <div
                  className="absolute inset-0 z-30 bg-[rgba(12,12,12,0.06)]"
                  onMouseDown={() => setGotoOpen(false)}
                >
                  <div
                    className="mx-auto mt-10 w-[260px] rounded-lg border border-line-8 bg-white p-2 shadow-float"
                    onMouseDown={(event) => event.stopPropagation()}
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex-none text-[11px] text-ink-55">
                        跳转到行
                      </span>
                      <input
                        ref={gotoInputRef}
                        value={gotoValue}
                        onChange={(event) => {
                          setGotoValue(event.target.value);
                          setGotoError(null);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            jumpToLine(gotoValue);
                          } else if (event.key === "Escape") {
                            event.preventDefault();
                            setGotoOpen(false);
                          }
                        }}
                        placeholder={`1–${lines.length}`}
                        className="h-7 min-w-0 flex-1 rounded border border-line-6 bg-base px-2 font-mono text-[12px] text-ink-95 outline-none focus:border-brand/40"
                      />
                      <button
                        type="button"
                        onClick={() => jumpToLine(gotoValue)}
                        className="h-7 flex-none rounded-md bg-brand px-2.5 text-[11px] font-medium text-white transition hover:bg-brand-600"
                      >
                        跳转
                      </button>
                    </div>
                    {gotoError ? (
                      <p className="mt-1 px-1 text-[10.5px] text-danger">
                        {gotoError}
                      </p>
                    ) : null}
                  </div>
                </div>
              ) : null}

              <div className="relative min-h-0 flex-1">
                {findOpen ? (
                  <FindBar
                    query={findQuery}
                    onQueryChange={setFindQuery}
                    caseSensitive={findCase}
                    onToggleCase={() => setFindCase((value) => !value)}
                    current={activeMatch}
                    total={findMatches.length}
                    onPrev={() => stepFind(-1)}
                    onNext={() => stepFind(1)}
                    onClose={() => setFindOpen(false)}
                    inputRef={findInputRef}
                  />
                ) : null}
                <div
                  ref={scrollRef}
                  className="h-full overflow-auto bg-white"
                >
                {content ? (
                  reader.wrap ? (
                    // Wrapped lines grow vertically, so render one row per
                    // logical line instead of a separate gutter column.
                    <div
                      className="min-w-full py-4 font-mono"
                      style={{
                        fontSize: `${fontSize}px`,
                        lineHeight: `${lineHeight}px`,
                      }}
                    >
                      {lines.map((line, index) => {
                        const rowClass = lineRowClass(index);
                        return (
                          <div
                            key={index}
                            className={`flex min-w-full ${rowClass}`}
                            style={{ minHeight: lineHeight }}
                            onClick={() => setActiveLine(index + 1)}
                          >
                            <div
                              className={`sticky left-0 z-10 w-[54px] flex-none select-none border-r border-line-4 px-3 text-right text-ink-30 ${
                                rowClass || "bg-white"
                              }`}
                            >
                              {index + 1}
                            </div>
                            <div className="min-w-0 flex-1 whitespace-pre-wrap break-words px-4">
                              {renderLineContent(line, index + 1)}
                            </div>
                          </div>
                        );
                      })}
                      {isStreaming ? (
                        <div className="flex min-w-full">
                          <span className="w-[54px] flex-none" />
                          <span className="streaming-caret px-4" />
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div
                      className="flex min-w-full font-mono"
                      style={{
                        fontSize: `${fontSize}px`,
                        lineHeight: `${lineHeight}px`,
                      }}
                    >
                      <div
                        className="sticky left-0 z-10 flex-none select-none border-r border-line-4 bg-white px-3 py-4 text-right text-ink-30"
                        style={{ minWidth: 54 }}
                      >
                        {lines.map((_, index) => (
                          <div key={index} className={lineRowClass(index)}>
                            {index + 1}
                          </div>
                        ))}
                      </div>
                      <pre className="min-w-0 flex-1 whitespace-pre px-4 py-4 text-ink-80">
                        {lines.map((line, index) => (
                          <div
                            key={index}
                            className={lineRowClass(index)}
                            style={{ minHeight: lineHeight }}
                            onClick={() => setActiveLine(index + 1)}
                          >
                            {renderLineContent(line, index + 1)}
                          </div>
                        ))}
                        {isStreaming ? (
                          <span className="streaming-caret" />
                        ) : null}
                      </pre>
                    </div>
                  )
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-2 text-ink-30">
                    <FileText size={24} />
                    <p className="text-[12px]">文件正在写入…</p>
                  </div>
                )}
              </div>
              </div>

              <div className="flex h-7 flex-none items-center justify-between gap-2 border-t border-line-4 px-3 text-[10.5px] text-ink-30">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="truncate">{languageLabel(activeFile)}</span>
                  <span className="flex-none">{lines.length} 行</span>
                  {activeLine ? (
                    <span className="flex-none">行 {activeLine}</span>
                  ) : null}
                </div>
                <div className="flex flex-none items-center gap-1">
                  <button
                    type="button"
                    onClick={() =>
                      setReader((current) => ({
                        ...current,
                        wrap: !current.wrap,
                      }))
                    }
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
                    onClick={() =>
                      setReader((current) => ({
                        ...current,
                        fontSize: clampFontSize(current.fontSize - 0.5),
                      }))
                    }
                    title="缩小字号"
                    className="rounded px-1 py-0.5 transition hover:bg-line-4 hover:text-ink-95"
                  >
                    A−
                  </button>
                  <span className="w-6 text-center font-mono">{fontSize}</span>
                  <button
                    type="button"
                    onClick={() =>
                      setReader((current) => ({
                        ...current,
                        fontSize: clampFontSize(current.fontSize + 0.5),
                      }))
                    }
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
              <span className="grid h-12 w-12 place-items-center rounded-xl bg-base text-ink-30">
                <FileText size={22} />
              </span>
              <p className="text-[13px] text-ink-55">请选择文件查看代码</p>
              <p className="max-w-[280px] text-[11px] leading-[17px] text-ink-30">
                ⌘P / Ctrl+P 快速打开，⌘F / Ctrl+F 文件内查找，⌘G / Ctrl+G 跳转到行；左侧文件树按
                frontend / backend 分组。
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
