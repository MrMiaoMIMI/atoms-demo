import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Artifact } from "../types";
import { fileBadge } from "../lib/files";
import { ChevronRight, Search, X } from "./Icons";

interface Props {
  artifacts: Record<string, Artifact>;
  onClose: () => void;
  onOpenFile: (path: string, line?: number) => void;
}

interface Match {
  line: number;
  start: number;
  end: number;
  text: string;
}

interface FileResult {
  filename: string;
  total: number;
  matches: Match[];
}

const MAX_MATCHES = 500;
const MAX_FILES = 200;
const PER_FILE_PREVIEW = 5;
const SNIPPET_RADIUS = 44;

function TypeBadge({ name }: { name: string }) {
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

function Snippet({ text, start, end }: { text: string; start: number; end: number }) {
  const from = Math.max(0, start - SNIPPET_RADIUS);
  const to = Math.min(text.length, end + SNIPPET_RADIUS);
  const before = text.slice(from, start);
  const lead = before.match(/^\s*/)?.[0].length ?? 0;
  const trimmed = before.slice(lead);
  const after = text.slice(end, to);
  return (
    <span className="whitespace-pre">
      {from > 0 || lead > 0 ? <span className="text-ink-30">…</span> : null}
      {trimmed}
      <mark className="rounded bg-brand-50 px-0.5 text-brand-text">
        {text.slice(start, end)}
      </mark>
      {after}
      {to < text.length ? <span className="text-ink-30">…</span> : null}
    </span>
  );
}

export default function ContentSearch({
  artifacts,
  onClose,
  onOpenFile,
}: Props) {
  const [query, setQuery] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const deferred = useDeferredValue(query);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    setCollapsed(new Set());
  }, [deferred, caseSensitive]);

  const search = useMemo(() => {
    const raw = deferred.trim();
    if (!raw) {
      return { files: [] as FileResult[], total: 0, truncated: false };
    }
    const needle = caseSensitive ? raw : raw.toLowerCase();
    const results: FileResult[] = [];
    let total = 0;
    let truncated = false;

    const entries = Object.entries(artifacts).sort(([a], [b]) =>
      a.localeCompare(b)
    );
    for (const [filename, artifact] of entries) {
      if (results.length >= MAX_FILES) {
        truncated = true;
        break;
      }
      const lines = artifact.content.split("\n");
      const matches: Match[] = [];
      let fileTotal = 0;
      for (let index = 0; index < lines.length; index += 1) {
        const text = lines[index];
        const haystack = caseSensitive ? text : text.toLowerCase();
        let from = 0;
        while (from <= haystack.length) {
          const at = haystack.indexOf(needle, from);
          if (at === -1) break;
          fileTotal += 1;
          total += 1;
          if (matches.length < PER_FILE_PREVIEW) {
            matches.push({
              line: index + 1,
              start: at,
              end: at + raw.length,
              text,
            });
          }
          from = at + Math.max(1, needle.length);
          if (total >= MAX_MATCHES) {
            truncated = true;
            break;
          }
        }
        if (total >= MAX_MATCHES) break;
      }
      if (fileTotal) results.push({ filename, total: fileTotal, matches });
      if (total >= MAX_MATCHES) break;
    }
    return { files: results, total, truncated };
  }, [artifacts, caseSensitive, deferred]);

  function toggleFile(filename: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  }

  function openFirst() {
    const file = search.files[0];
    const first = file?.matches[0];
    if (file && first) onOpenFile(file.filename, first.line);
  }

  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[16px] border border-line-4 bg-white">
        <div className="flex h-11 flex-none items-center gap-2 border-b border-line-4 px-3">
          <Search size={15} className="flex-none text-ink-30" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                openFirst();
              } else if (event.key === "Escape") {
                event.preventDefault();
                onClose();
              }
            }}
            placeholder="在项目中搜索…"
            className="h-full min-w-0 flex-1 bg-transparent text-[13px] text-ink-95 outline-none placeholder:text-ink-30"
          />
          {query.trim() ? (
            <span className="flex-none text-[11px] text-ink-30">
              {search.total} 个结果 · {search.files.length} 个文件
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => setCaseSensitive((value) => !value)}
            title="区分大小写"
            className={`grid h-6 w-6 flex-none place-items-center rounded text-[11px] transition ${
              caseSensitive
                ? "bg-brand-50 text-brand-text"
                : "text-ink-55 hover:bg-line-4 hover:text-ink-95"
            }`}
          >
            Aa
          </button>
          <button
            type="button"
            onClick={onClose}
            title="关闭（Esc）"
            className="grid h-6 w-6 flex-none place-items-center rounded text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
          >
            <X size={14} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto bg-white">
          {!query.trim() ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-xl bg-base text-ink-30">
                <Search size={22} />
              </span>
              <p className="text-[13px] text-ink-55">跨文件搜索源码</p>
              <p className="max-w-[320px] text-[11px] leading-[17px] text-ink-30">
                输入关键字搜索前端与后端文件，Enter 打开第一处匹配，点击结果直接定位到行。
              </p>
            </div>
          ) : search.files.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
              <p className="text-[12px] text-ink-55">没有找到匹配内容</p>
              <p className="max-w-[320px] text-[11px] leading-[17px] text-ink-30">
                试试更短的关键字，或关闭「Aa」忽略大小写。
              </p>
            </div>
          ) : (
            <div className="py-1">
              {search.files.map((file) => {
                const isCollapsed = collapsed.has(file.filename);
                return (
                  <div key={file.filename}>
                    <div className="group flex h-8 items-center gap-1.5 px-2.5 hover:bg-line-2">
                      <button
                        type="button"
                        onClick={() => toggleFile(file.filename)}
                        title={isCollapsed ? "展开" : "折叠"}
                        className="grid h-5 w-5 flex-none place-items-center rounded text-ink-30 transition hover:bg-line-4 hover:text-ink-80"
                      >
                        <ChevronRight
                          size={12}
                          className={`transition-transform ${
                            isCollapsed ? "" : "rotate-90"
                          }`}
                        />
                      </button>
                      <TypeBadge name={file.filename} />
                      <button
                        type="button"
                        onClick={() =>
                          onOpenFile(file.filename, file.matches[0]?.line)
                        }
                        title={`打开 ${file.filename}`}
                        className="min-w-0 flex-1 truncate text-left text-[12.5px] text-ink-80 transition hover:text-ink-95"
                      >
                        {file.filename}
                      </button>
                      <span className="flex-none rounded-full bg-line-4 px-1.5 py-0.5 text-[10px] font-medium text-ink-55">
                        {file.total}
                      </span>
                    </div>
                    {isCollapsed ? null : (
                      <div className="pb-1">
                        {file.matches.map((match) => (
                          <button
                            key={`${match.line}-${match.start}`}
                            type="button"
                            onClick={() => onOpenFile(file.filename, match.line)}
                            className="flex w-full items-center gap-2 rounded-md px-2.5 py-1 text-left transition hover:bg-line-4"
                          >
                            <span className="w-10 flex-none text-right font-mono text-[10.5px] text-ink-30">
                              {match.line}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-[11.5px] text-ink-80">
                              <Snippet
                                text={match.text}
                                start={match.start}
                                end={match.end}
                              />
                            </span>
                          </button>
                        ))}
                        {file.total > file.matches.length ? (
                          <p className="px-12 py-1 text-[10.5px] text-ink-30">
                            还有 {file.total - file.matches.length} 处匹配
                          </p>
                        ) : null}
                      </div>
                    )}
                  </div>
                );
              })}
              {search.truncated ? (
                <p className="border-t border-line-4 px-3 py-2 text-[10.5px] text-warning">
                  结果过多，仅展示前 {MAX_MATCHES} 条匹配；请缩小关键字范围。
                </p>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
