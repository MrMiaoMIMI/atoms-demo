import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fileBadge } from "../lib/files";
import { fuzzyMatch } from "../lib/fuzzy";
import { Search } from "./Icons";

interface Props {
  open: boolean;
  names: string[];
  recent: string[];
  onClose: () => void;
  onOpen: (path: string) => void;
}

interface Result {
  path: string;
  score: number;
  indices: number[];
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

function splitPath(path: string) {
  const slash = path.lastIndexOf("/");
  return slash === -1
    ? { dir: "", base: path, baseStart: 0 }
    : {
        dir: path.slice(0, slash),
        base: path.slice(slash + 1),
        baseStart: slash + 1,
      };
}

function HighlightedName({
  path,
  indices,
}: {
  path: string;
  indices: number[];
}) {
  const { base, baseStart } = splitPath(path);
  if (!indices.length) return <>{base}</>;
  const hits = new Set(
    indices.filter((index) => index >= baseStart && index < baseStart + base.length)
  );
  const parts: ReactNode[] = [];
  for (let index = 0; index < base.length; index += 1) {
    const char = base[index];
    parts.push(
      hits.has(baseStart + index) ? (
        <span key={index} className="font-medium text-brand-text">
          {char}
        </span>
      ) : (
        char
      )
    );
  }
  return <>{parts}</>;
}

export default function QuickOpen({
  open,
  names,
  recent,
  onClose,
  onOpen,
}: Props) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const available = useMemo(() => new Set(names), [names]);

  const results = useMemo<Result[]>(() => {
    if (!query.trim()) {
      const seen = new Set<string>();
      return [
        ...recent.filter((path) => available.has(path)),
        ...[...available].sort((a, b) => a.localeCompare(b)),
      ]
        .filter((path) => {
          if (seen.has(path)) return false;
          seen.add(path);
          return true;
        })
        .slice(0, 50)
        .map((path) => ({ path, score: 0, indices: [] }));
    }

    const matches: Result[] = [];
    for (const path of names) {
      const match = fuzzyMatch(query, path);
      if (match) matches.push({ path, score: match.score, indices: match.indices });
    }
    matches.sort(
      (a, b) =>
        b.score - a.score ||
        a.path.length - b.path.length ||
        a.path.localeCompare(b.path)
    );
    return matches.slice(0, 50);
  }, [available, names, query, recent]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setCursor(0);
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    setCursor(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector<HTMLElement>(
      `[data-index="${cursor}"]`
    );
    node?.scrollIntoView({ block: "nearest" });
  }, [cursor, open, results.length]);

  if (!open) return null;

  function choose(path: string | undefined) {
    if (!path) return;
    onOpen(path);
  }

  return (
    <div
      className="absolute inset-0 z-30 bg-[rgba(12,12,12,0.12)] px-3 pt-3"
      onMouseDown={onClose}
    >
      <div
        className="mx-auto w-full max-w-[560px] overflow-hidden rounded-xl border border-line-8 bg-white shadow-float"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex h-11 items-center gap-2 border-b border-line-4 px-3">
          <Search size={15} className="flex-none text-ink-30" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setCursor((current) =>
                  Math.max(
                    0,
                    Math.min(results.length - 1, current + 1)
                  )
                );
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setCursor((current) => Math.max(0, current - 1));
              } else if (event.key === "Enter") {
                event.preventDefault();
                choose(results[cursor]?.path);
              } else if (event.key === "Escape") {
                event.preventDefault();
                onClose();
              }
            }}
            placeholder="搜索文件名…"
            className="h-full min-w-0 flex-1 bg-transparent text-[13px] text-ink-95 outline-none placeholder:text-ink-30"
          />
          <kbd className="flex-none rounded border border-line-6 bg-base px-1.5 py-0.5 font-sans text-[10px] text-ink-30">
            Esc
          </kbd>
        </div>

        <div
          ref={listRef}
          className="max-h-[340px] overflow-y-auto p-1.5"
        >
          {results.length ? (
            results.map((item, index) => {
              const { dir } = splitPath(item.path);
              const active = index === cursor;
              return (
                <button
                  key={item.path}
                  type="button"
                  data-index={index}
                  onMouseEnter={() => setCursor(index)}
                  onClick={() => choose(item.path)}
                  className={`flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left transition ${
                    active ? "bg-brand-50" : "hover:bg-line-4"
                  }`}
                >
                  <FileBadge name={item.path} />
                  <span
                    className={`min-w-0 flex-1 truncate text-[12.5px] ${
                      active ? "text-ink-95" : "text-ink-80"
                    }`}
                  >
                    <HighlightedName path={item.path} indices={item.indices} />
                  </span>
                  {dir ? (
                    <span className="hidden max-w-[45%] flex-none truncate text-right text-[11px] text-ink-30 sm:block">
                      {dir}
                    </span>
                  ) : null}
                </button>
              );
            })
          ) : (
            <p className="px-2 py-4 text-center text-[12px] text-ink-30">
              没有匹配的文件
            </p>
          )}
        </div>

        <div className="flex h-8 items-center justify-between border-t border-line-4 px-3 text-[10.5px] text-ink-30">
          <span>↑↓ 选择 · Enter 打开</span>
          <span>{results.length} 个文件</span>
        </div>
      </div>
    </div>
  );
}
