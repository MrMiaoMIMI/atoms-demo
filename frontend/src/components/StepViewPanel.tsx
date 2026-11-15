import { useMemo, useState, type ReactNode } from "react";
import type { FileChange } from "../types";
import { copyText } from "../lib/clipboard";
import { fileBadge, formatBytes } from "../lib/files";
import {
  AlertTriangle,
  CheckCircle,
  Code,
  Copy,
  FileText,
  Folder,
  Globe,
  Search,
  Spinner,
  Terminal,
  X,
} from "./Icons";

export type StepViewKind =
  | "diff"
  | "terminal"
  | "file"
  | "files"
  | "search"
  | "http"
  | "json";

export interface StepView {
  title: string;
  kind: StepViewKind;
  payload?: Record<string, unknown> | null;
  changes?: FileChange[];
  truncated?: boolean;
  status?: string;
}

interface Props {
  view: StepView;
  loading: boolean;
  error: string | null;
  onOpenFile: (path: string, line?: number) => void;
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function KindIcon({ kind, size = 14 }: { kind: StepViewKind; size?: number }) {
  if (kind === "terminal") return <Terminal size={size} />;
  if (kind === "files") return <Folder size={size} />;
  if (kind === "search") return <Search size={size} />;
  if (kind === "http") return <Globe size={size} />;
  if (kind === "json") return <Code size={size} />;
  return <FileText size={size} />;
}

function TypeBadge({ name }: { name: string }) {
  const badge = fileBadge(name);
  return (
    <span
      className="grid h-4 w-4 flex-none place-items-center rounded-[4px] font-mono font-medium"
      style={{ background: badge.bg, color: badge.color, fontSize: 8, lineHeight: 1 }}
    >
      {badge.label}
    </span>
  );
}

function CopyButton({ value, label = "复制" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    if (!value) return;
    const ok = await copyText(value);
    if (!ok) return;
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }
  return (
    <button
      type="button"
      onClick={() => void copy()}
      disabled={!value}
      className="inline-flex h-7 flex-none items-center gap-1 rounded-md px-2 text-[11px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
    >
      <Copy size={13} />
      {copied ? "已复制" : label}
    </button>
  );
}

function ViewHeader({
  kind,
  title,
  subtitle,
  truncated,
  copyValue,
  actions,
}: {
  kind: StepViewKind;
  title: string;
  subtitle?: string | null;
  truncated?: boolean;
  copyValue?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex min-h-11 flex-none items-center justify-between gap-3 border-b border-line-4 px-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        <span className="grid h-6 w-6 flex-none place-items-center rounded-md bg-line-4 text-ink-55">
          <KindIcon kind={kind} />
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium text-ink-95">{title}</p>
          {subtitle ? (
            <p className="truncate text-[11px] text-ink-30">{subtitle}</p>
          ) : null}
        </div>
        {truncated ? (
          <span className="flex-none rounded-full bg-[rgba(245,158,11,0.12)] px-1.5 py-0.5 text-[10px] font-medium text-warning">
            已截断
          </span>
        ) : null}
      </div>
      <div className="flex flex-none items-center gap-1">
        {actions}
        {copyValue ? <CopyButton value={copyValue} /> : null}
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <FileText size={22} className="text-ink-30" />
      <p className="max-w-[320px] text-[12px] leading-[18px] text-ink-55">{text}</p>
    </div>
  );
}

function ShellMessage({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col items-center justify-center gap-2 overflow-hidden rounded-[16px] border border-line-4 bg-white px-6 text-center">
        {error ? (
          <AlertTriangle size={22} className="text-warning" />
        ) : (
          <Spinner size={20} className="text-brand" />
        )}
        <p
          className={`max-w-[360px] text-[12px] leading-[18px] ${
            error ? "text-danger" : "text-ink-55"
          }`}
        >
          {children}
        </p>
      </div>
    </section>
  );
}

function ErrorBanner({ text }: { text: string }) {
  return (
    <p className="flex flex-none items-start gap-1.5 border-b border-line-4 bg-[rgba(239,68,68,0.06)] px-3 py-1.5 text-[11px] leading-[16px] text-danger">
      <AlertTriangle size={12} className="mt-[2px] flex-none" />
      <span className="min-w-0">{text}</span>
    </p>
  );
}

function TerminalBody({ payload }: { payload: Record<string, unknown> }) {
  const command = str(payload.command);
  const raw = str(payload.output);
  const lines = asArray(payload.lines).map((line) => String(line));
  const output = raw || lines.join("\n");
  const ok = payload.ok !== false;
  const exitCode = num(payload.exit_code);
  const duration = num(payload.duration_ms);
  const port = num(payload.port);
  const truncated = Boolean(payload.truncated);

  function lineClass(line: string): string {
    if (/traceback|error|exception|failed|错误|失败/i.test(line)) {
      return "text-[#b91c1c]";
    }
    if (/warn|warning|警告/i.test(line)) return "text-warning";
    if (/^(✓|INFO: Application startup|构建成功|服务已启动)/.test(line)) {
      return "text-[#15803d]";
    }
    return "text-ink-80";
  }

  return (
    <>
      <ViewHeader
        kind="terminal"
        title={command || "运行时日志"}
        subtitle={
          [
            port != null ? `端口 ${port}` : null,
            duration != null ? `${duration} ms` : null,
            exitCode != null ? `exit ${exitCode}` : null,
          ]
            .filter(Boolean)
            .join(" · ") || null
        }
        truncated={truncated}
        copyValue={output}
        actions={
          <span
            className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
              ok
                ? "bg-[rgba(34,197,94,0.12)] text-[#15803d]"
                : "bg-[rgba(239,68,68,0.12)] text-[#b91c1c]"
            }`}
          >
            {ok ? <CheckCircle size={11} /> : <X size={11} />}
            {ok ? "成功" : "失败"}
          </span>
        }
      />
      <div className="min-h-0 flex-1 overflow-auto bg-[#FBFBFA]">
        {command ? (
          <div className="border-b border-line-4 px-3 py-2 font-mono text-[11.5px] text-ink-55">
            <span className="mr-1.5 select-none text-ink-30">$</span>
            {command}
          </div>
        ) : null}
        {output ? (
          <div className="px-3 py-3 font-mono text-[12px] leading-[20px]">
            {output.split("\n").map((line, index) => (
              <div
                key={index}
                className={`whitespace-pre-wrap break-words ${lineClass(line)}`}
              >
                {line || " "}
              </div>
            ))}
          </div>
        ) : (
          <p className="px-3 py-3 text-[12px] text-ink-30">（无输出）</p>
        )}
      </div>
    </>
  );
}

function HttpBody({ payload }: { payload: Record<string, unknown> }) {
  const method = str(payload.method) || "GET";
  const url = str(payload.url) || "/api/health";
  const status = num(payload.status);
  const duration = num(payload.duration_ms);
  const body = str(payload.body);
  const ok = payload.ok !== false;
  const truncated = Boolean(payload.truncated);

  let pretty = body;
  try {
    pretty = JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    // Keep the raw body when it is not JSON.
  }

  return (
    <>
      <ViewHeader
        kind="http"
        title={`${method} ${url}`}
        subtitle={duration != null ? `${duration} ms` : null}
        truncated={truncated}
        copyValue={pretty}
        actions={
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
              ok
                ? "bg-[rgba(34,197,94,0.12)] text-[#15803d]"
                : "bg-[rgba(239,68,68,0.12)] text-[#b91c1c]"
            }`}
          >
            {status != null ? `HTTP ${status}` : ok ? "成功" : "失败"}
          </span>
        }
      />
      <div className="min-h-0 flex-1 overflow-auto bg-[#FBFBFA]">
        <pre className="min-w-full px-3 py-3 font-mono text-[12px] leading-[20px] text-ink-80 whitespace-pre-wrap break-words">
          {pretty || "（空响应）"}
        </pre>
      </div>
    </>
  );
}

function FileListBody({
  payload,
  onOpenFile,
}: {
  payload: Record<string, unknown>;
  onOpenFile: (path: string, line?: number) => void;
}) {
  const [query, setQuery] = useState("");
  const pattern = str(payload.pattern);
  const files = useMemo(
    () =>
      asArray(payload.files)
        .map(asRecord)
        .filter((item) => str(item.path)),
    [payload.files]
  );
  const total = num(payload.total) ?? files.length;
  const visible = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return files;
    return files.filter((item) =>
      str(item.path).toLowerCase().includes(value)
    );
  }, [files, query]);

  return (
    <>
      <ViewHeader
        kind="files"
        title={pattern ? `文件 · ${pattern}` : "文件列表"}
        subtitle={`${total} 个文件`}
        truncated={Boolean(payload.truncated)}
        actions={
          <div className="relative">
            <Search
              size={13}
              className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-ink-30"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="过滤"
              className="h-7 w-[150px] rounded-md border border-line-6 bg-white pl-6 pr-2 text-[11px] text-ink-95 outline-none transition placeholder:text-ink-30 focus:border-brand/40"
            />
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-auto p-1.5">
        {visible.length ? (
          visible.map((item) => {
            const path = str(item.path);
            return (
              <button
                key={path}
                type="button"
                onClick={() => onOpenFile(path)}
                title={path}
                className="flex h-[30px] w-full items-center gap-2 rounded-md px-2 text-left text-[12px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
              >
                <TypeBadge name={path} />
                <span className="min-w-0 flex-1 truncate">{path}</span>
                <span className="flex-none font-mono text-[10px] text-ink-30">
                  {formatBytes(num(item.bytes) ?? 0)} · {num(item.lines) ?? 0} 行
                </span>
              </button>
            );
          })
        ) : (
          <p className="px-2 py-3 text-[12px] text-ink-30">
            {query.trim() ? "没有匹配的文件" : "没有可展示的文件"}
          </p>
        )}
      </div>
    </>
  );
}

function Highlighted({ text, pattern }: { text: string; pattern: string }) {
  if (!pattern) return <>{text}</>;
  try {
    const re = new RegExp(pattern, "gi");
    const parts: ReactNode[] = [];
    let last = 0;
    let match = re.exec(text);
    let guard = 0;
    while (match && match[0] && guard < 50) {
      guard += 1;
      parts.push(text.slice(last, match.index));
      parts.push(
        <mark
          key={`${match.index}-${guard}`}
          className="rounded bg-brand-50 px-0.5 text-brand-text"
        >
          {match[0]}
        </mark>
      );
      last = match.index + match[0].length;
      match = re.exec(text);
    }
    parts.push(text.slice(last));
    return <>{parts}</>;
  } catch {
    return <>{text}</>;
  }
}

function SearchBody({
  payload,
  onOpenFile,
}: {
  payload: Record<string, unknown>;
  onOpenFile: (path: string, line?: number) => void;
}) {
  const pattern = str(payload.pattern);
  const glob = str(payload.glob);
  const total = num(payload.total) ?? 0;
  const groups = useMemo(() => {
    const map = new Map<string, { line: number; text: string }[]>();
    for (const raw of asArray(payload.matches)) {
      const item = asRecord(raw);
      const path = str(item.path);
      if (!path) continue;
      const entry = map.get(path) ?? [];
      entry.push({ line: num(item.line) ?? 0, text: str(item.text) });
      map.set(path, entry);
    }
    return Array.from(map.entries());
  }, [payload.matches]);

  return (
    <>
      <ViewHeader
        kind="search"
        title={pattern ? `搜索 · ${pattern}` : "搜索结果"}
        subtitle={[glob, `${total} 处命中`].filter(Boolean).join(" · ")}
        truncated={Boolean(payload.truncated)}
      />
      <div className="min-h-0 flex-1 overflow-auto">
        {groups.length ? (
          <div className="divide-y divide-line-4">
            {groups.map(([path, matches]) => (
              <div key={path} className="py-1.5">
                <div className="flex items-center gap-1.5 px-3 py-1 text-[11px] text-ink-55">
                  <TypeBadge name={path} />
                  <span className="truncate">{path}</span>
                  <span className="flex-none text-ink-30">{matches.length}</span>
                </div>
                {matches.map((match, index) => (
                  <button
                    key={`${path}-${match.line}-${index}`}
                    type="button"
                    onClick={() => onOpenFile(path, match.line)}
                    title={`打开 ${path}:${match.line}`}
                    className="flex w-full items-start gap-2 px-3 py-0.5 text-left font-mono text-[11.5px] leading-[18px] transition hover:bg-line-4"
                  >
                    <span className="w-[42px] flex-none select-none text-right text-ink-30">
                      {match.line}
                    </span>
                    <span className="min-w-0 flex-1 whitespace-pre-wrap break-words text-ink-80">
                      <Highlighted text={match.text} pattern={pattern} />
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="没有命中结果。" />
        )}
      </div>
    </>
  );
}

function FileSnapshotBody({ payload }: { payload: Record<string, unknown> }) {
  const path = str(payload.path);
  const content = str(payload.content);
  const start = num(payload.start_line) ?? 1;
  const end = num(payload.end_line);
  const total = num(payload.total_lines);
  const lines = content.endsWith("\n")
    ? content.slice(0, -1).split("\n")
    : content.split("\n");
  return (
    <>
      <ViewHeader
        kind="file"
        title={path || "文件读取快照"}
        subtitle={[
          end != null ? `读取第 ${start}–${end} 行` : `从第 ${start} 行开始`,
          total != null ? `共 ${total} 行` : null,
          "文件已不在当前项目中，以下为读取时的快照",
        ]
          .filter(Boolean)
          .join(" · ")}
        truncated={Boolean(payload.truncated)}
        copyValue={content}
      />
      <div className="min-h-0 flex-1 overflow-auto bg-white">
        <div className="flex min-w-full font-mono text-[12.5px] leading-[22px]">
          <div
            className="sticky left-0 z-10 flex-none select-none border-r border-line-4 bg-white px-3 py-4 text-right text-ink-30"
            style={{ minWidth: 54 }}
          >
            {lines.map((_, index) => (
              <div key={index}>{start + index}</div>
            ))}
          </div>
          <pre className="min-w-0 flex-1 px-4 py-4 text-ink-80">
            {lines.map((line, index) => (
              <div key={index} className="min-h-[22px] whitespace-pre">
                {line || " "}
              </div>
            ))}
          </pre>
        </div>
      </div>
    </>
  );
}

function JsonBody({ payload }: { payload: Record<string, unknown> }) {
  const valid = payload.valid;
  const hasValid = typeof valid === "boolean";
  const plan = payload.plan;
  const value = hasValid ? plan ?? {} : payload;
  let pretty = "";
  try {
    pretty = JSON.stringify(value, null, 2);
  } catch {
    pretty = String(value);
  }
  return (
    <>
      <ViewHeader
        kind="json"
        title={hasValid ? "方案校验" : "步骤详情"}
        subtitle={hasValid ? undefined : str(payload.tool) || "JSON"}
        copyValue={pretty}
        actions={
          hasValid ? (
            <span
              className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                valid
                  ? "bg-[rgba(34,197,94,0.12)] text-[#15803d]"
                  : "bg-[rgba(239,68,68,0.12)] text-[#b91c1c]"
              }`}
            >
              {valid ? <CheckCircle size={11} /> : <X size={11} />}
              {valid ? "方案有效" : "方案无效"}
            </span>
          ) : null
        }
      />
      {!hasValid && str(asRecord(payload.error).message) ? (
        <ErrorBanner text={str(asRecord(payload.error).message)} />
      ) : null}
      <div className="min-h-0 flex-1 overflow-auto bg-[#FBFBFA]">
        <pre className="min-w-full px-3 py-3 font-mono text-[12px] leading-[20px] text-ink-80 whitespace-pre-wrap break-words">
          {pretty || "（空）"}
        </pre>
      </div>
    </>
  );
}

export default function StepViewPanel({
  view,
  loading,
  error,
  onOpenFile,
}: Props) {
  const payload = view.payload ?? {};

  if (loading && !view.payload) {
    return <ShellMessage>正在加载步骤详情…</ShellMessage>;
  }
  if (error && !view.payload) {
    return <ShellMessage error>{error}</ShellMessage>;
  }

  let body: ReactNode;
  switch (view.kind) {
    case "terminal":
      body = <TerminalBody payload={payload} />;
      break;
    case "http":
      body = <HttpBody payload={payload} />;
      break;
    case "files":
      body = <FileListBody payload={payload} onOpenFile={onOpenFile} />;
      break;
    case "search":
      body = <SearchBody payload={payload} onOpenFile={onOpenFile} />;
      break;
    case "file":
      body = <FileSnapshotBody payload={payload} />;
      break;
    case "json":
      body = <JsonBody payload={payload} />;
      break;
    default:
      body = (
        <>
          <ViewHeader
            kind="json"
            title={view.title}
            subtitle="未知的步骤视图"
          />
          <EmptyState text="该步骤没有可展示的内容。" />
        </>
      );
  }

  return (
    <section className="flex min-h-0 min-w-0 flex-1 bg-white pb-2 pr-2">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[16px] border border-line-4 bg-white">
        {error ? <ErrorBanner text={error} /> : null}
        {body}
      </div>
    </section>
  );
}
