import { useMemo, useState } from "react";
import type { Artifact } from "../types";
import { formatSize } from "../lib/format";
import { Code, Copy } from "./Icons";

interface Props {
  artifacts: Record<string, Artifact>;
  activeFile: string | null;
  onSelect: (filename: string) => void;
  streamingFile: string | null;
  streamingBuffer: string;
}

const ORDER: Record<string, number> = { "index.html": 0, "styles.css": 1, "app.js": 2 };

export default function FilePanel({
  artifacts,
  activeFile,
  onSelect,
  streamingFile,
  streamingBuffer,
}: Props) {
  const [copied, setCopied] = useState(false);

  const files = useMemo(() => {
    const names = new Set(Object.keys(artifacts));
    if (streamingFile) names.add(streamingFile);
    return Array.from(names).sort((a, b) => (ORDER[a] ?? 9) - (ORDER[b] ?? 9) || a.localeCompare(b));
  }, [artifacts, streamingFile]);

  const active = activeFile ? artifacts[activeFile] : undefined;
  const isStreaming = activeFile !== null && activeFile === streamingFile;
  const content = isStreaming ? streamingBuffer : active?.content ?? "";

  async function copy() {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-none items-center justify-between border-b border-white/5 px-4 py-2">
        <span className="text-[11px] font-medium text-slate-400">项目文件</span>
        <span className="text-[10px] text-slate-600">{files.length} files</span>
      </div>

      <div className="flex flex-none gap-1.5 overflow-x-auto border-b border-white/5 px-3 py-2">
        {files.length === 0 ? (
          <span className="px-1 py-1 text-[11px] text-slate-600">等待 Coder 生成文件…</span>
        ) : null}
        {files.map((name) => {
          const streaming = name === streamingFile;
          const artifact = artifacts[name];
          return (
            <button
              key={name}
              type="button"
              onClick={() => onSelect(name)}
              className={`inline-flex flex-none items-center gap-1.5 rounded-lg border px-2.5 py-1.5 font-mono text-[11px] transition ${
                name === activeFile
                  ? "border-accent/40 bg-accent/15 text-slate-100"
                  : "border-white/10 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200"
              }`}
            >
              <Code className="h-3 w-3" />
              {name}
              {streaming ? (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              ) : artifact ? (
                <span className="text-[9px] text-slate-600">v{artifact.version}</span>
              ) : null}
            </button>
          );
        })}
      </div>

      {activeFile ? (
        <>
          <div className="flex flex-none items-center justify-between gap-2 border-b border-white/5 px-4 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className="truncate font-mono text-[11px] text-slate-300">{activeFile}</span>
              {isStreaming ? (
                <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[9px] font-medium text-accent-soft">
                  写入中
                </span>
              ) : (
                <span className="text-[10px] text-slate-600">{formatSize(content.length)}</span>
              )}
            </div>
            <button
              type="button"
              onClick={copy}
              disabled={!content}
              className="inline-flex items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-[10px] text-slate-400 transition hover:border-white/20 hover:text-slate-200 disabled:opacity-40"
            >
              <Copy className="h-3 w-3" />
              {copied ? "已复制" : "复制"}
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto bg-ink-950/60">
            <pre className="p-4 font-mono text-[11.5px] leading-[1.75] text-slate-300">
              <code>
                {content}
                {isStreaming ? <span className="streaming-caret" /> : null}
              </code>
            </pre>
          </div>
        </>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-slate-600">
          <Code className="h-7 w-7" />
          <p className="text-xs">选择文件查看代码</p>
        </div>
      )}
    </div>
  );
}
