import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { Artifact } from "../types";
import {
  buildFileTree,
  fileBadge,
  flattenFiles,
  formatBytes,
  languageForFile,
  type FileNode,
} from "../lib/files";
import { copyText } from "../lib/clipboard";
import { highlightLine } from "../lib/highlight";
import {
  ChevronRight,
  Copy,
  Download,
  FileText,
  Folder,
  PanelLeft,
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

function TreeRows({
  nodes,
  depth,
  activeFile,
  streamingFile,
  collapsed,
  onToggle,
  onSelect,
}: {
  nodes: FileNode[];
  depth: number;
  activeFile: string | null;
  streamingFile: string | null;
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
                <span className="truncate">{node.name}</span>
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
                />
              )}
            </div>
          );
        }
        const active = node.path === activeFile;
        const streaming = node.path === streamingFile;
        return (
          <button
            key={node.path}
            type="button"
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
            <span className="truncate">{node.name}</span>
            {streaming ? (
              <span className="ml-auto h-1.5 w-1.5 flex-none animate-pulse rounded-full bg-brand" />
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
}: Props) {
  const [query, setQuery] = useState("");
  const [treeOpen, setTreeOpen] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const names = useMemo(() => {
    const set = new Set(Object.keys(artifacts));
    if (streamingFile) set.add(streamingFile);
    return Array.from(set);
  }, [artifacts, streamingFile]);

  const tree = useMemo(() => buildFileTree(names), [names]);
  const flat = useMemo(() => flattenFiles(tree), [tree]);

  const results = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return [];
    return flat.filter((name) => name.toLowerCase().includes(value));
  }, [flat, query]);

  const active = activeFile ? artifacts[activeFile] : undefined;
  const isStreaming = Boolean(activeFile && activeFile === streamingFile);
  const content = isStreaming ? streamingBuffer : active?.content ?? "";
  const lang = languageForFile(activeFile ?? "");
  const lines = useMemo(() => content.split("\n"), [content]);
  const simple = lines.length > 1800;

  useEffect(() => {
    setCopied(false);
    const el = scrollRef.current;
    if (el) el.scrollTop = 0;
  }, [activeFile]);

  useEffect(() => {
    if (!isStreaming) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [streamingBuffer, isStreaming]);

  function toggleFolder(path: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  async function copy() {
    if (!content) return;
    const ok = await copyText(content);
    setCopied(ok);
    if (ok) window.setTimeout(() => setCopied(false), 1500);
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

  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden rounded-[16px] border border-line-4 bg-white">
        {treeOpen ? (
          <div className="flex w-[250px] flex-none flex-col border-r border-line-6 bg-white">
            <div className="flex h-11 flex-none items-center gap-2 border-b border-line-4 px-2.5">
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
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
              {names.length === 0 ? (
                <p className="px-2 py-2 text-[12px] text-ink-30">等待 Coder 生成文件…</p>
              ) : query.trim() ? (
                results.length ? (
                  results.map((name) => (
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
                      <span className="truncate">{name}</span>
                    </button>
                  ))
                ) : (
                  <p className="px-2 py-2 text-[12px] text-ink-30">没有匹配的文件</p>
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

        <div className="flex min-w-0 flex-1 flex-col bg-white">
          {activeFile ? (
            <>
              <div className="flex h-11 flex-none items-center justify-between gap-3 border-b border-line-4 px-3">
                <div className="flex min-w-0 items-center gap-2">
                  <TypeBadge name={activeFile} size={18} />
                  <span className="truncate text-[13px] font-medium text-ink-95">
                    {activeFile.split("/").pop()}
                  </span>
                  <span className="hidden truncate text-[11px] text-ink-30 sm:inline">
                    {activeFile}
                  </span>
                  {isStreaming ? (
                    <span className="flex-none rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-text">
                      写入中
                    </span>
                  ) : (
                    <span className="flex-none text-[11px] text-ink-30">
                      {formatBytes(content.length)}
                    </span>
                  )}
                </div>
                <div className="flex flex-none items-center gap-1">
                  <button
                    type="button"
                    onClick={copy}
                    disabled={!content}
                    title="复制代码"
                    className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
                  >
                    <Copy size={13} />
                    {copied ? "已复制" : "复制"}
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

              <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto bg-white">
                {content ? (
                  <div className="flex min-w-full font-mono text-[12.5px] leading-[22px]">
                    <div
                      className="sticky left-0 z-10 flex-none select-none border-r border-line-4 bg-white px-3 py-4 text-right text-ink-30"
                      style={{ minWidth: 54 }}
                    >
                      {lines.map((_, index) => (
                        <div key={index}>{index + 1}</div>
                      ))}
                    </div>
                    <pre className="min-w-0 flex-1 px-4 py-4 text-ink-80">
                      {lines.map((line, index) => (
                        <div key={index} className="min-h-[22px] whitespace-pre">
                          {simple ? line || " " : highlightLine(line, lang)}
                        </div>
                      ))}
                      {isStreaming ? <span className="streaming-caret" /> : null}
                    </pre>
                  </div>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-2 text-ink-30">
                    <FileText size={24} />
                    <p className="text-[12px]">文件正在写入…</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-xl bg-base text-ink-30">
                <FileText size={22} />
              </span>
              <p className="text-[13px] text-ink-55">请选择文件查看代码</p>
              <p className="max-w-[260px] text-[11px] leading-[17px] text-ink-30">
                左侧文件树按 frontend / backend 分组；生成过程中会自动定位到正在写入的文件。
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
