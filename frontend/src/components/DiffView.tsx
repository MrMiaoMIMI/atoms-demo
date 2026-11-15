import { useEffect, useMemo, useRef, type ReactNode } from "react";

type LineKind = "hunk" | "add" | "del" | "context" | "meta" | "header";

interface DiffLine {
  kind: LineKind;
  text: string;
  oldLine: number | null;
  newLine: number | null;
}

export interface DiffMatch {
  lineIndex: number;
  start: number;
  end: number;
}

const HUNK_RE = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/;

export function parseDiff(input: string): DiffLine[] {
  const lines: DiffLine[] = [];
  let oldLine: number | null = null;
  let newLine: number | null = null;

  for (const raw of input.split("\n")) {
    if (!raw) continue;
    if (raw.startsWith("--- ") || raw.startsWith("+++ ")) {
      lines.push({ kind: "header", text: raw, oldLine: null, newLine: null });
      continue;
    }
    const hunk = HUNK_RE.exec(raw);
    if (hunk) {
      oldLine = Number(hunk[1]);
      newLine = Number(hunk[3]);
      lines.push({ kind: "hunk", text: raw, oldLine: null, newLine: null });
      continue;
    }
    if (raw.startsWith("\\")) {
      lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null });
      continue;
    }

    const prefix = raw[0];
    const text = raw.slice(1);
    if (prefix === "+") {
      lines.push({ kind: "add", text, oldLine: null, newLine });
      if (newLine !== null) newLine += 1;
    } else if (prefix === "-") {
      lines.push({ kind: "del", text, oldLine, newLine: null });
      if (oldLine !== null) oldLine += 1;
    } else if (prefix === " ") {
      lines.push({ kind: "context", text, oldLine, newLine });
      if (oldLine !== null) oldLine += 1;
      if (newLine !== null) newLine += 1;
    } else {
      lines.push({ kind: "meta", text: raw, oldLine: null, newLine: null });
    }
  }
  return lines;
}

const ROW_CLASS: Record<LineKind, string> = {
  add: "bg-[rgba(34,197,94,0.10)]",
  del: "bg-[rgba(239,68,68,0.10)]",
  context: "",
  hunk: "bg-[rgba(66,103,255,0.06)]",
  header: "",
  meta: "",
};

function collectMatches(
  lines: DiffLine[],
  query: string,
  caseSensitive: boolean
): DiffMatch[] {
  if (!query) return [];
  const needle = caseSensitive ? query : query.toLowerCase();
  const matches: DiffMatch[] = [];
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    if (
      line.kind !== "add" &&
      line.kind !== "del" &&
      line.kind !== "context"
    ) {
      continue;
    }
    const haystack = caseSensitive ? line.text : line.text.toLowerCase();
    let from = 0;
    while (from <= haystack.length) {
      const at = haystack.indexOf(needle, from);
      if (at === -1) break;
      matches.push({ lineIndex, start: at, end: at + query.length });
      from = at + Math.max(1, needle.length);
      if (matches.length >= 2000) return matches;
    }
  }
  return matches;
}

export function countDiffMatches(
  diff: string,
  query: string,
  caseSensitive: boolean
): number {
  if (!query) return 0;
  return collectMatches(parseDiff(diff), query, caseSensitive).length;
}

function renderLineText(
  text: string,
  matches: { start: number; end: number; index: number }[],
  activeMatch: number
): ReactNode {
  if (!matches.length) return text || " ";
  const parts: ReactNode[] = [];
  let cursor = 0;
  let key = 0;
  for (const match of matches) {
    if (match.start > cursor) parts.push(text.slice(cursor, match.start));
    parts.push(
      <span
        key={key++}
        className={
          match.index === activeMatch
            ? "rounded-[2px] bg-brand text-white"
            : "rounded-[2px] bg-[rgba(66,103,255,0.20)]"
        }
      >
        {text.slice(match.start, match.end)}
      </span>
    );
    cursor = match.end;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return <>{parts}</>;
}

const TEXT_CLASS: Record<LineKind, string> = {
  add: "text-[#15803d]",
  del: "text-[#b91c1c]",
  context: "text-ink-80",
  hunk: "text-brand-text",
  header: "text-ink-30",
  meta: "text-ink-30",
};

interface Props {
  diff: string;
  truncated?: boolean;
  wrap?: boolean;
  hunkIndex?: number;
  findQuery?: string;
  findCase?: boolean;
  activeMatch?: number;
  fontSize?: number;
}

export default function DiffView({
  diff,
  truncated = false,
  wrap = false,
  hunkIndex = 0,
  findQuery = "",
  findCase = false,
  activeMatch = -1,
  fontSize = 12.5,
}: Props) {
  const lines = useMemo(() => parseDiff(diff), [diff]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lineHeight = Math.round(fontSize * 1.75);
  const matches = useMemo(
    () => collectMatches(lines, findQuery, findCase),
    [lines, findQuery, findCase]
  );
  const matchesByLine = useMemo(() => {
    const byLine = new Map<
      number,
      { start: number; end: number; index: number }[]
    >();
    matches.forEach((match, index) => {
      let list = byLine.get(match.lineIndex);
      if (!list) {
        list = [];
        byLine.set(match.lineIndex, list);
      }
      list.push({ start: match.start, end: match.end, index });
    });
    return byLine;
  }, [matches]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const row = container.querySelector<HTMLElement>(
      `[data-hunk="${hunkIndex}"]`
    );
    if (!row) return;
    const top =
      row.getBoundingClientRect().top -
      container.getBoundingClientRect().top +
      container.scrollTop;
    container.scrollTop = Math.max(0, top - 12);
  }, [diff, hunkIndex]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || activeMatch < 0) return;
    const match = matches[activeMatch];
    if (!match) return;
    const row = container.querySelector<HTMLElement>(
      `[data-diff-line="${match.lineIndex}"]`
    );
    if (!row) return;
    const top =
      row.getBoundingClientRect().top -
      container.getBoundingClientRect().top +
      container.scrollTop;
    container.scrollTop = Math.max(0, top - container.clientHeight / 2);
  }, [activeMatch, diff, matches]);

  if (!diff.trim()) {
    return (
      <div className="flex h-full items-center justify-center text-[12px] text-ink-30">
        没有可展示的差异
      </div>
    );
  }

  let hunkOrdinal = -1;

  return (
    <div
      ref={scrollRef}
      className="min-h-0 flex-1 overflow-auto bg-white"
    >
      <table
        className={`border-collapse font-mono ${
          wrap ? "w-full table-fixed" : "min-w-full"
        }`}
        style={{
          fontSize: `${fontSize}px`,
          lineHeight: `${lineHeight}px`,
        }}
      >
        <colgroup>
          <col style={{ width: 46 }} />
          <col style={{ width: 46 }} />
          <col />
        </colgroup>
        <tbody>
          {lines.map((line, index) => {
            if (
              line.kind === "hunk" ||
              line.kind === "header" ||
              line.kind === "meta"
            ) {
              if (line.kind === "hunk") hunkOrdinal += 1;
              return (
                <tr
                  key={index}
                  className={ROW_CLASS[line.kind]}
                  data-hunk={line.kind === "hunk" ? hunkOrdinal : undefined}
                >
                  <td
                    colSpan={3}
                    className={`whitespace-pre px-3 py-0.5 text-[11.5px] ${TEXT_CLASS[line.kind]}`}
                  >
                    {line.text}
                  </td>
                </tr>
              );
            }
            const sign =
              line.kind === "add" ? "+" : line.kind === "del" ? "-" : " ";
            return (
              <tr key={index} className={ROW_CLASS[line.kind]} data-diff-line={index}>
                <td className="w-[46px] select-none border-r border-line-4 px-2 text-right align-top text-[11px] text-ink-30">
                  {line.oldLine ?? ""}
                </td>
                <td className="w-[46px] select-none border-r border-line-4 px-2 text-right align-top text-[11px] text-ink-30">
                  {line.newLine ?? ""}
                </td>
                <td
                  className={`px-3 align-top ${
                    wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre"
                  } ${TEXT_CLASS[line.kind]}`}
                >
                  {sign}
                  {renderLineText(
                    line.text,
                    matchesByLine.get(index) ?? [],
                    activeMatch
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {truncated ? (
        <p className="border-t border-line-4 px-3 py-2 text-[11px] text-warning">
          diff 内容过长，已截断；完整内容可在文件视图中查看。
        </p>
      ) : null}
    </div>
  );
}
