import { useMemo } from "react";

type LineKind = "hunk" | "add" | "del" | "context" | "meta" | "header";

interface DiffLine {
  kind: LineKind;
  text: string;
  oldLine: number | null;
  newLine: number | null;
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
}

export default function DiffView({ diff, truncated = false }: Props) {
  const lines = useMemo(() => parseDiff(diff), [diff]);

  if (!diff.trim()) {
    return (
      <div className="flex h-full items-center justify-center text-[12px] text-ink-30">
        没有可展示的差异
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-white">
      <table className="min-w-full border-collapse font-mono text-[12.5px] leading-[22px]">
        <tbody>
          {lines.map((line, index) => {
            if (
              line.kind === "hunk" ||
              line.kind === "header" ||
              line.kind === "meta"
            ) {
              return (
                <tr key={index} className={ROW_CLASS[line.kind]}>
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
              <tr key={index} className={ROW_CLASS[line.kind]}>
                <td className="w-[46px] select-none border-r border-line-4 px-2 text-right align-top text-[11px] text-ink-30">
                  {line.oldLine ?? ""}
                </td>
                <td className="w-[46px] select-none border-r border-line-4 px-2 text-right align-top text-[11px] text-ink-30">
                  {line.newLine ?? ""}
                </td>
                <td
                  className={`whitespace-pre px-3 align-top ${TEXT_CLASS[line.kind]}`}
                >
                  {sign}
                  {line.text || " "}
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
