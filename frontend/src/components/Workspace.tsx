import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, generate } from "../api";
import type {
  Artifact,
  Conversation,
  Execution,
  Health,
  Project,
  ProjectMode,
} from "../types";
import ChatPanel from "./ChatPanel";
import FilePanel from "./FilePanel";
import HealthPill from "./HealthPill";
import { Chat, ChevronLeft, Code, Plus } from "./Icons";
import PreviewPane from "./PreviewPane";
import Timeline from "./Timeline";

interface Props {
  projectId: string;
  initialPrompt: string | null;
  onPromptUsed: () => void;
  health: Health | null;
  onExit: () => void;
}

export default function Workspace({
  projectId,
  initialPrompt,
  onPromptUsed,
  health,
  onExit,
}: Props) {
  const [project, setProject] = useState<Project | null>(null);
  const [mode, setMode] = useState<ProjectMode>("frontend");
  const [messages, setMessages] = useState<Conversation[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [artifacts, setArtifacts] = useState<Record<string, Artifact>>({});
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [streamingFile, setStreamingFile] = useState<string | null>(null);
  const [streamingBuffer, setStreamingBuffer] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [tab, setTab] = useState<"chat" | "files">("chat");

  const abortRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);

  const latestVersion = useMemo(
    () => Object.values(artifacts).reduce((max, artifact) => Math.max(max, artifact.version), 0),
    [artifacts]
  );

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setLoadError(null);
    api
      .getProject(projectId)
      .then((state) => {
        if (cancelled) return;
        setProject(state.project);
        setMode(state.mode ?? "frontend");
        setMessages(state.conversations);
        setExecutions(state.executions);
        const map: Record<string, Artifact> = {};
        for (const artifact of state.artifacts) map[artifact.filename] = artifact;
        setArtifacts(map);
        setActiveFile(
          state.artifacts.find((artifact) => artifact.filename === "frontend/src/App.tsx")
            ?.filename ??
            state.artifacts.find((artifact) => artifact.filename === "backend/main.py")
              ?.filename ??
            state.artifacts.find((artifact) => artifact.filename === "index.html")?.filename ??
            state.artifacts[0]?.filename ??
            null
        );
        const version = state.artifacts.reduce((max, artifact) => Math.max(max, artifact.version), 0);
        if (state.artifacts.length > 0) {
          setPreviewUrl(state.preview_url ?? `/apps/${projectId}/?v=${version || 1}`);
        }
        setLoaded(true);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setLoadError(err.message || "项目加载失败");
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const run = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message) return;

      setTab("chat");
      setError(null);
      setStreamingFile(null);
      setStreamingBuffer("");
      setRunning(true);
      setMessages((prev) => [
        ...prev,
        { id: -Date.now(), role: "user", content: message, created_at: new Date().toISOString() },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await generate(
          projectId,
          message,
          (event, data) => {
            if (event === "execution") {
              const exec = data as unknown as Execution;
              if (typeof exec.id !== "number") return;
              setExecutions((prev) => {
                const index = prev.findIndex((item) => item.id === exec.id);
                if (index === -1) return [...prev, exec];
                const next = [...prev];
                next[index] = { ...next[index], ...exec };
                return next;
              });
              return;
            }
            if (event === "token") {
              const delta = typeof data.delta === "string" ? data.delta : "";
              if (delta) setStreamingBuffer((prev) => prev + delta);
              return;
            }
            if (event === "token_reset") {
              setStreamingBuffer("");
              return;
            }
            if (event === "file_start") {
              const filename = typeof data.filename === "string" ? data.filename : null;
              setStreamingFile(filename);
              setStreamingBuffer("");
              if (filename) setActiveFile(filename);
              return;
            }
            if (event === "artifact") {
              const artifact = data as unknown as Artifact;
              if (!artifact.filename) return;
              setArtifacts((prev) => ({ ...prev, [artifact.filename]: artifact }));
              setActiveFile((prev) => prev ?? artifact.filename);
              setStreamingFile(null);
              return;
            }
            if (event === "preview") {
              if (typeof data.url === "string") setPreviewUrl(data.url);
              if (
                data.mode === "frontend" ||
                data.mode === "fullstack" ||
                data.mode === "backend"
              ) {
                setMode(data.mode);
              }
              return;
            }
            if (event === "message") {
              if (typeof data.content !== "string") return;
              const role = data.role === "user" ? "user" : "assistant";
              setMessages((prev) => [
                ...prev,
                { id: -Date.now() - Math.random(), role, content: data.content as string },
              ]);
              return;
            }
            if (event === "error") {
              setError(typeof data.message === "string" ? data.message : "生成失败");
            }
          },
          controller.signal
        );
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          setError("已停止本轮生成。");
        } else {
          setError((err as Error).message || "生成失败，请重试。");
        }
      } finally {
        setRunning(false);
        setStreamingFile(null);
        abortRef.current = null;
      }
    },
    [projectId]
  );

  useEffect(() => {
    if (!loaded || !initialPrompt || startedRef.current) return;
    startedRef.current = true;
    onPromptUsed();
    if (messages.length === 0) void run(initialPrompt);
  }, [loaded, initialPrompt, messages.length, onPromptUsed, run]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    []
  );

  if (!loaded) {
    return (
      <div className="grid h-full place-items-center">
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          正在加载项目…
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="grid h-full place-items-center px-6">
        <div className="glass max-w-sm rounded-2xl p-6 text-center">
          <p className="text-sm font-medium text-slate-200">项目加载失败</p>
          <p className="mt-2 text-xs text-slate-500">{loadError}</p>
          <button
            type="button"
            onClick={onExit}
            className="mt-5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white transition hover:bg-accent-soft"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex h-14 flex-none items-center justify-between gap-3 border-b border-white/5 bg-ink-950/70 px-3 backdrop-blur sm:px-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <button
            type="button"
            onClick={onExit}
            title="返回项目列表"
            className="grid h-8 w-8 flex-none place-items-center rounded-lg text-slate-400 transition hover:bg-white/[0.06] hover:text-slate-200"
          >
            <ChevronLeft />
          </button>
          <div className="grid h-8 w-8 flex-none place-items-center rounded-xl bg-gradient-to-br from-accent to-mint text-sm font-black text-ink-950">
            A
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-100">
              {project?.name ?? "未命名项目"}
            </p>
            <p className="text-[10px] text-slate-500">
              Atoms 工作台 · v{latestVersion || 1} ·{" "}
              {mode === "fullstack" ? "全栈" : mode === "backend" ? "API" : "前端"}
            </p>
          </div>
        </div>
        <div className="flex flex-none items-center gap-2">
          <HealthPill health={health} />
          <button
            type="button"
            onClick={onExit}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-white/20 hover:text-white"
          >
            <Plus className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">新项目</span>
          </button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 overflow-y-auto xl:grid-cols-[260px_400px_minmax(0,1fr)] xl:overflow-hidden">
        <Timeline executions={executions} running={running} />

        <section className="flex min-h-[70vh] min-w-0 flex-col border-r border-white/5 bg-ink-900/30 xl:min-h-0">
          <div className="flex h-12 flex-none items-center justify-between border-b border-white/5 px-3">
            <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.02] p-1">
              <button
                type="button"
                onClick={() => setTab("chat")}
                className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition ${
                  tab === "chat"
                    ? "bg-white/[0.08] text-slate-100"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                <Chat className="h-3 w-3" />
                对话
              </button>
              <button
                type="button"
                onClick={() => setTab("files")}
                className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition ${
                  tab === "files"
                    ? "bg-white/[0.08] text-slate-100"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                <Code className="h-3 w-3" />
                文件
                {Object.keys(artifacts).length > 0 ? (
                  <span className="rounded bg-white/10 px-1 text-[9px] text-slate-400">
                    {Object.keys(artifacts).length}
                  </span>
                ) : null}
              </button>
            </div>
            {running ? (
              <span className="inline-flex items-center gap-1.5 text-[10px] text-accent-soft">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                生成中
              </span>
            ) : (
              <span className="text-[10px] text-slate-600">
                {messages.filter((m) => m.role === "user").length} 轮对话
              </span>
            )}
          </div>

          {tab === "chat" ? (
            <ChatPanel
              messages={messages}
              running={running}
              error={error}
              onSend={(text) => void run(text)}
              onStop={() => abortRef.current?.abort()}
            />
          ) : (
            <FilePanel
              artifacts={artifacts}
              activeFile={activeFile}
              onSelect={setActiveFile}
              streamingFile={streamingFile}
              streamingBuffer={streamingBuffer}
            />
          )}
        </section>

        <PreviewPane url={previewUrl} running={running} version={latestVersion} mode={mode} />
      </div>
    </div>
  );
}
