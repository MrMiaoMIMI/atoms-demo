import { useMemo, useState } from "react";
import type { Artifact } from "../types";
import { formatSize } from "../lib/format";
import { Code, Copy, Folder } from "./Icons";

interface Props {
  artifacts: Record<string, Artifact>;
  activeFile: string | null;
  onSelect: (filename: string) => void;
  streamingFile: string | null;
  streamingBuffer: string;
}

const GROUP_ORDER = ["frontend", "backend", "root"];
const GROUP_LABEL: Record<string, string> = {
  frontend: "frontend",
  backend: "backend",
  root: "根目录",
};

export default function FilePanel({
  artifacts,
  activeFile,
  onSelect,
  streamingFile,
  streamingBuffer,
}: Props) {
  const [copied, setCopied] = useState(false);

  const groups = useMemo(() => {
    const names = new Set(Object.keys(artifacts));
    if (streamingFile) names.add(streamingFile);
    const buckets = new Map<string, string[]>();
    for (const name of names) {
      const index = name.indexOf("/");
      const group = index === -1 ? "root" : name.slice(0, index);
      const list = buckets.get(group) ?? [];
      list.push(name);
      buckets.set(group, list);
    }
    return Array.from(buckets.entries())
      .sort((a, b) => {
        const ai = GROUP_ORDER.indexOf(a[0]);
        const bi = GROUP_ORDER.indexOf(b[0]);
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi) || a[0].localeCompare(b[0]);
      })
      .map(([group, files]) => ({
        group,
        files: files.sort((a, b) => {
          const [aName, bName] = [a.split("/").pop() ?? a, b.split("/").pop() ?? b];
          if (aName === "App.tsx") return -1;
          if (bName === "App.tsx") return 1;
          if (aName === "main.py") return -1;
          if (bName === "main.py") return 1;
          return a.localeCompare(b);
        }),
      }));
  }, [artifacts, streamingFile]);

  const fileCount = groups.reduce((sum, item) => sum + item.files.length, 0);
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
        <span className="text-[10px] text-slate-600">{fileCount} files</span>
      </div>

      <div className="max-h-44 flex-none overflow-y-auto border-b border-white/5 px-2 py-2">
        {fileCount === 0 ? (
          <span className="block px-2 py-1 text-[11px] text-slate-600">
            等待 Coder 生成文件…
          </span>
        ) : null}
        {groups.map(({ group, files }) => (
          <div key={group} className="mb-1 last:mb-0">
            <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              <Folder className="h-3 w-3" />
              {GROUP_LABEL[group] ?? group}
              <span className="font-normal text-slate-600">{files.length}</span>
            </div>
            {files.map((name) => {
              const streaming = name === streamingFile;
              const artifact = artifacts[name];
              const short = group === "root" ? name : name.slice(group.length + 1);
              return (
                <button
                  key={name}
                  type="button"
                  title={name}
                  onClick={() => onSelect(name)}
                  className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left font-mono text-[11px] transition ${
                    name === activeFile
                      ? "bg-accent/15 text-slate-100"
                      : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                  }`}
                >
                  <Code className="h-3 w-3 flex-none opacity-60" />
                  <span className="truncate">{short}</span>
                  {streaming ? (
                    <span className="ml-auto h-1.5 w-1.5 flex-none animate-pulse rounded-full bg-accent" />
                  ) : artifact ? (
                    <span className="ml-auto flex-none text-[9px] text-slate-600">
                      v{artifact.version}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        ))}
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
