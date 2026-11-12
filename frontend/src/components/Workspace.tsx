import type { PointerEvent as ReactPointerEvent } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, generate } from '../api';
import { AGENT_KEYS, agentFor, isAgentKey } from '../lib/agents';
import { copyText } from '../lib/clipboard';
import { buildGroups, type ChatGroup } from '../lib/groups';
import type {
  AgentKey,
  Artifact,
  Conversation,
  Execution,
  Health,
  Project,
  ProjectMode,
} from '../types';
import { PresenceBar } from './Avatar';
import ChatPanel from './ChatPanel';
import FilePanel from './FilePanel';
import {
  AtomsMark,
  ChevronDown,
  Code,
  Eye,
  ExternalLink,
  Home,
  Spinner,
} from './Icons';
import PreviewPane from './PreviewPane';

interface Props {
  projectId: string;
  initialPrompt: string | null;
  onPromptUsed: () => void;
  health: Health | null;
  onExit: () => void;
}

const MIN_CHAT = 340;
const DEFAULT_CHAT = 500;
const MAX_CHAT = 760;

const MODE_LABEL: Record<ProjectMode, string> = {
  frontend: '前端',
  fullstack: '全栈',
  backend: 'API',
};

function pickDefaultFile(artifacts: Artifact[]): string | null {
  const priorities = [
    'frontend/src/App.tsx',
    'frontend/src/main.tsx',
    'backend/main.py',
    'index.html',
  ];
  for (const path of priorities) {
    if (artifacts.some((artifact) => artifact.filename === path)) return path;
  }
  return artifacts[0]?.filename ?? null;
}

function upsertExecution(list: Execution[], execution: Execution): Execution[] {
  const index = list.findIndex((item) => item.id === execution.id);
  if (index === -1) return [...list, execution];
  const next = [...list];
  next[index] = { ...next[index], ...execution };
  return next;
}

export default function Workspace({
  projectId,
  initialPrompt,
  onPromptUsed,
  health,
  onExit,
}: Props) {
  const [project, setProject] = useState<Project | null>(null);
  const [mode, setMode] = useState<ProjectMode>('frontend');
  const [groups, setGroups] = useState<ChatGroup[]>([]);
  const [artifacts, setArtifacts] = useState<Record<string, Artifact>>({});
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [streamingFile, setStreamingFile] = useState<string | null>(null);
  const [streamingBuffer, setStreamingBuffer] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [pane, setPane] = useState<'preview' | 'code'>('preview');
  const [chatOpen, setChatOpen] = useState(
    () => window.localStorage.getItem('atoms-chat-open') !== '0'
  );
  const [refreshKey, setRefreshKey] = useState(0);
  const [chatWidth, setChatWidth] = useState(() => {
    const saved = Number(window.localStorage.getItem('atoms-chat-width'));
    return Number.isFinite(saved) && saved >= MIN_CHAT && saved <= MAX_CHAT
      ? saved
      : DEFAULT_CHAT;
  });
  const [dragging, setDragging] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [projectMenu, setProjectMenu] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);
  const dragCleanupRef = useRef<(() => void) | null>(null);

  const latestVersion = useMemo(
    () =>
      Object.values(artifacts).reduce(
        (max, artifact) => Math.max(max, artifact.version),
        0,
      ),
    [artifacts],
  );

  const chattedAgents = useMemo<AgentKey[]>(() => {
    const seen = new Set<string>();
    for (const group of groups) {
      if (group.kind === 'agent' && group.agent) seen.add(group.agent);
    }
    return AGENT_KEYS.filter((key) => seen.has(key));
  }, [groups]);

  useEffect(() => {
    if (project?.name) document.title = `${project.name} · Atoms`;
  }, [project?.name]);

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setLoadError(null);
    api
      .getProject(projectId)
      .then((state) => {
        if (cancelled) return;
        setProject(state.project);
        setMode(state.mode ?? 'frontend');
        const map: Record<string, Artifact> = {};
        for (const artifact of state.artifacts)
          map[artifact.filename] = artifact;
        setArtifacts(map);
        setActiveFile(pickDefaultFile(state.artifacts));
        const version = state.artifacts.reduce(
          (max, artifact) => Math.max(max, artifact.version),
          0,
        );
        if (state.artifacts.length > 0) {
          setPreviewUrl(
            state.preview_url ?? `/apps/${projectId}/?v=${version || 1}`,
          );
        }
        setGroups(buildGroups(state.conversations, state.executions));
        setLoaded(true);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setLoadError(err.message || '项目加载失败');
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    window.localStorage.setItem('atoms-chat-width', String(chatWidth));
  }, [chatWidth]);

  useEffect(() => {
    window.localStorage.setItem('atoms-chat-open', chatOpen ? '1' : '0');
  }, [chatOpen]);

  useEffect(() => {
    const clamp = () => {
      const max = Math.min(
        MAX_CHAT,
        Math.max(MIN_CHAT, window.innerWidth - 460),
      );
      setChatWidth((value) => Math.max(MIN_CHAT, Math.min(max, value)));
    };
    clamp();
    window.addEventListener('resize', clamp);
    return () => window.removeEventListener('resize', clamp);
  }, []);

  useEffect(() => () => dragCleanupRef.current?.(), []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setProjectMenu(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function startDrag(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = chatWidth;

    const onMove = (moveEvent: PointerEvent) => {
      const max = Math.min(
        MAX_CHAT,
        Math.max(MIN_CHAT, window.innerWidth - 460),
      );
      setChatWidth(
        Math.max(
          MIN_CHAT,
          Math.min(max, startWidth + moveEvent.clientX - startX),
        ),
      );
    };

    const finish = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', finish);
      window.removeEventListener('pointercancel', finish);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setDragging(false);
      dragCleanupRef.current = null;
    };

    dragCleanupRef.current = finish;
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', finish);
    window.addEventListener('pointercancel', finish);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    setDragging(true);
  }

  const run = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message) return;

      const now = new Date().toISOString();
      const userMessage: Conversation = {
        id: -Date.now(),
        role: 'user',
        content: message,
        created_at: now,
      };

      setError(null);
      setRunning(true);
      setStreamingFile(null);
      setStreamingBuffer('');
      setGroups((prev) => [
        ...prev,
        {
          id: `live-user-${Date.now()}`,
          kind: 'user',
          user: userMessage,
          executions: [],
          messages: [],
          createdAt: now,
        },
      ]);

      const controller = new AbortController();
      abortRef.current = controller;

      const normalizeAgent = (raw: unknown) => {
        const value = typeof raw === 'string' ? raw : 'mike';
        return isAgentKey(value) ? value : agentFor(value).key;
      };

      try {
        await generate(
          projectId,
          message,
          (event, data) => {
            if (event === 'project') {
              // The backend names the project from the full first prompt in
              // the background; adopt the resolved title when it arrives.
              const name = typeof data.name === 'string' ? data.name.trim() : '';
              if (name) {
                setProject((prev) => (prev ? { ...prev, name } : prev));
              }
              return;
            }
            if (event === 'agent_start') {
              const runId =
                typeof data.run_id === 'string' ? data.run_id : null;
              if (!runId) return;
              const agent = normalizeAgent(data.agent);
              const index =
                typeof data.index === 'number' ? data.index : undefined;
              setGroups((prev) => {
                if (prev.some((group) => group.runId === runId)) return prev;
                return [
                  ...prev,
                  {
                    id: `live-${runId}`,
                    kind: 'agent',
                    agent,
                    runId,
                    executions: [],
                    messages: [],
                    createdAt: new Date().toISOString(),
                    live: true,
                    status: 'running',
                    index,
                  },
                ];
              });
              return;
            }
            if (event === 'execution') {
              const execution = data as unknown as Execution;
              if (typeof execution.id !== 'number') return;
              const runId =
                typeof execution.run_id === 'string' ? execution.run_id : null;
              if (!runId) return;
              setGroups((prev) => {
                let found = false;
                const next = prev.map((group) => {
                  if (group.runId !== runId) return group;
                  found = true;
                  return {
                    ...group,
                    executions: upsertExecution(group.executions, execution),
                  };
                });
                if (found) return next;
                const agent = normalizeAgent(execution.agent);
                return [
                  ...next,
                  {
                    id: `live-${runId}`,
                    kind: 'agent',
                    agent,
                    runId,
                    executions: [execution],
                    messages: [],
                    createdAt: execution.created_at ?? new Date().toISOString(),
                    live: true,
                    status: 'running',
                  },
                ];
              });
              return;
            }
            if (event === 'token') {
              const delta = typeof data.delta === 'string' ? data.delta : '';
              if (delta) setStreamingBuffer((prev) => prev + delta);
              return;
            }
            if (event === 'token_reset') {
              setStreamingBuffer('');
              return;
            }
            if (event === 'file_start') {
              const filename =
                typeof data.filename === 'string' ? data.filename : null;
              setStreamingFile(filename);
              setStreamingBuffer('');
              if (filename) setActiveFile(filename);
              return;
            }
            if (event === 'artifact') {
              const artifact = data as unknown as Artifact;
              if (!artifact.filename) return;
              setArtifacts((prev) => ({
                ...prev,
                [artifact.filename]: artifact,
              }));
              setActiveFile((prev) => prev ?? artifact.filename);
              setStreamingFile(null);
              setStreamingBuffer('');
              return;
            }
            if (event === 'preview') {
              if (typeof data.url === 'string') setPreviewUrl(data.url);
              if (
                data.mode === 'frontend' ||
                data.mode === 'fullstack' ||
                data.mode === 'backend'
              ) {
                setMode(data.mode);
              }
              return;
            }
            if (event === 'message') {
              const runId =
                typeof data.run_id === 'string' ? data.run_id : null;
              const content =
                typeof data.content === 'string' ? data.content : null;
              if (!runId || !content) return;
              setGroups((prev) =>
                prev.map((group) =>
                  group.runId === runId
                    ? { ...group, messages: [...group.messages, content] }
                    : group,
                ),
              );
              return;
            }
            if (event === 'agent_end') {
              const runId =
                typeof data.run_id === 'string' ? data.run_id : null;
              if (!runId) return;
              const status =
                data.status === 'error'
                  ? ('error' as const)
                  : data.status === 'warning'
                    ? ('warning' as const)
                    : ('success' as const);
              setGroups((prev) =>
                prev.map((group) =>
                  group.runId === runId
                    ? { ...group, live: false, status }
                    : group,
                ),
              );
              return;
            }
            if (event === 'error') {
              setError(
                typeof data.message === 'string' ? data.message : '生成失败',
              );
            }
          },
          controller.signal,
        );
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          setError('已停止本轮生成。');
          setGroups((prev) =>
            prev.map((group) =>
              group.live
                ? {
                    ...group,
                    live: false,
                    status: 'warning' as const,
                    executions: group.executions.map((execution) =>
                      execution.status === 'running'
                        ? {
                            ...execution,
                            status: 'warning' as const,
                            log: '已手动停止',
                          }
                        : execution,
                    ),
                  }
                : group,
            ),
          );
        } else {
          setError((err as Error).message || '生成失败，请重试。');
        }
      } finally {
        setRunning(false);
        setStreamingFile(null);
        abortRef.current = null;
        setGroups((prev) =>
          prev.map((group) =>
            group.live
              ? {
                  ...group,
                  live: false,
                  status: group.messages.length
                    ? ('success' as const)
                    : ('warning' as const),
                }
              : group,
          ),
        );
      }
    },
    [projectId],
  );

  useEffect(() => {
    if (!loaded || !initialPrompt || startedRef.current) return;
    startedRef.current = true;
    onPromptUsed();
    if (groups.length === 0) void run(initialPrompt);
  }, [loaded, initialPrompt, groups.length, onPromptUsed, run]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  function refreshPreview() {
    setRefreshKey((value) => value + 1);
  }

  async function share() {
    const url = previewUrl
      ? new URL(previewUrl, window.location.origin).toString()
      : window.location.href;
    const ok = await copyText(url);
    if (!ok) return;
    setShareCopied(true);
    window.setTimeout(() => setShareCopied(false), 1500);
  }

  if (!loaded) {
    return (
      <div className="grid h-full place-items-center bg-base">
        <div className="flex items-center gap-2.5 text-[13px] text-ink-55">
          <Spinner size={16} className="text-brand" />
          正在加载项目…
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="grid h-full place-items-center bg-base px-6">
        <div className="w-full max-w-sm rounded-2xl border border-line-6 bg-white p-6 text-center shadow-composer">
          <p className="text-[14px] font-medium text-ink-95">项目加载失败</p>
          <p className="mt-2 text-[12px] leading-[19px] text-ink-55">
            {loadError}
          </p>
          <button
            type="button"
            onClick={onExit}
            className="mt-5 inline-flex h-8 items-center rounded-full bg-brand px-4 text-[13px] font-medium text-white transition hover:bg-brand-600"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-base">
      <header className="flex h-11 flex-none items-center bg-base">
        <div
          style={{ width: chatWidth }}
          className="flex h-full min-w-0 flex-none items-center gap-2 border-r border-transparent px-4"
        >
          <button
            type="button"
            onClick={onExit}
            title="返回首页"
            className="grid h-7 w-7 flex-none place-items-center rounded-md text-ink-95 transition hover:bg-line-6"
          >
            <AtomsMark size={20} />
          </button>

          <div className="relative min-w-0 flex-1">
            <button
              type="button"
              onClick={() => setProjectMenu((value) => !value)}
              className="flex min-w-0 max-w-full items-center gap-1.5 rounded-md px-1 text-left transition hover:bg-line-4"
            >
              <span className="truncate text-[14px] font-medium text-ink-95">
                {project?.name ?? '未命名项目'}
              </span>
              <ChevronDown size={14} className="flex-none text-ink-55" />
            </button>

            {projectMenu ? (
              <>
                <button
                  type="button"
                  aria-hidden="true"
                  className="fixed inset-0 z-20 cursor-default"
                  onClick={() => setProjectMenu(false)}
                />
                <div className="absolute left-0 top-full z-30 mt-1.5 w-[250px] rounded-xl border border-line-6 bg-white p-2 shadow-float">
                  <div className="px-2 py-1.5">
                    <p className="truncate text-[13px] font-medium text-ink-95">
                      {project?.name ?? '未命名项目'}
                    </p>
                    <p className="mt-0.5 text-[11px] text-ink-55">
                      {MODE_LABEL[mode]} · v{latestVersion || 1} ·{' '}
                      {health?.llm_mode === 'mock'
                        ? 'Mock Agent'
                        : health?.model || 'LLM'}
                    </p>
                  </div>
                  <div className="my-1 h-px bg-line-4" />

                  <button
                    type="button"
                    onClick={() => {
                      setProjectMenu(false);
                      onExit();
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
                  >
                    <Home size={15} />
                    返回项目列表
                  </button>
                </div>
              </>
            ) : null}
          </div>

          <button
            type="button"
            onClick={() => setChatOpen((value) => !value)}
            title={chatOpen ? '关闭聊天框' : '打开聊天框'}
            aria-label={chatOpen ? '关闭聊天框' : '打开聊天框'}
            aria-pressed={!chatOpen}
            className="grid h-6 min-w-[32px] flex-none place-items-center rounded-full bg-line-4 px-2 font-mono text-[12px] font-medium tracking-[-1px] text-ink-55 transition hover:bg-line-6 hover:text-ink-80"
          >
            {chatOpen ? '<<' : '>>'}
          </button>
        </div>

        <div className="flex min-w-0 flex-1 items-center justify-between gap-2 pl-2 pr-3">
          <div className="flex items-center rounded-full bg-line-4 p-0 shadow-[inset_0_0_0_1px_rgba(12,12,12,0.03)]">
            <button
              type="button"
              onClick={() => setPane('preview')}
              title="预览"
              className={`flex h-[30px] items-center gap-1.5 rounded-full text-[14px] transition ${
                pane === 'preview'
                  ? 'bg-white px-2.5 font-medium text-brand-text shadow-[0_1px_3px_rgba(12,12,12,0.10)]'
                  : 'w-[34px] justify-center text-ink-55 hover:text-ink-80'
              }`}
            >
              <Eye size={17} />
              {pane === 'preview' ? '预览' : null}
            </button>
            <button
              type="button"
              onClick={() => setPane('code')}
              title="代码"
              className={`flex h-[30px] items-center gap-1.5 rounded-full text-[14px] transition ${
                pane === 'code'
                  ? 'bg-white px-2.5 font-medium text-brand-text shadow-[0_1px_3px_rgba(12,12,12,0.10)]'
                  : 'w-[34px] justify-center text-ink-55 hover:text-ink-80'
              }`}
            >
              <Code size={17} />
              {pane === 'code' ? '代码' : null}
            </button>
          </div>

          <div className="flex min-w-0 items-center gap-1">
            <a
              href={previewUrl ?? '#'}
              target="_blank"
              rel="noreferrer"
              title="在新标签页打开"
              className={`hidden h-[30px] w-[30px] place-items-center rounded-full text-ink-55 transition hover:bg-line-4 hover:text-ink-95 md:grid ${
                previewUrl ? '' : 'pointer-events-none opacity-30'
              }`}
            >
              <ExternalLink size={15} />
            </a>

            <span className="mx-1 hidden h-4 w-px bg-line-6 lg:block" />
            <span className="hidden lg:block">
              <PresenceBar activeAgents={chattedAgents} size={28} />
            </span>

            <button
              type="button"
              onClick={() => void share()}
              className="ml-1 flex h-[30px] items-center rounded-full border border-line-6 bg-white px-3 text-[13px] font-medium text-ink-95 transition hover:border-line-12"
            >
              {shareCopied ? '已复制' : '分享'}
            </button>
            <button
              type="button"
              onClick={refreshPreview}
              disabled={!previewUrl}
              title="刷新预览"
              className="flex h-[30px] items-center rounded-full bg-brand px-3 text-[13px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              刷新预览
            </button>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div
          style={chatOpen ? { width: chatWidth } : undefined}
          className={`min-h-0 min-w-0 flex-none flex-col ${
            chatOpen ? 'flex' : 'hidden'
          }`}
        >
          <ChatPanel
            groups={groups}
            running={running}
            error={error}
            onSend={(text) => void run(text)}
            onStop={() => abortRef.current?.abort()}
            onOpenCode={() => setPane('code')}
          />
        </div>

        {chatOpen ? (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="调整对话宽度"
            data-dragging={dragging}
            onPointerDown={startDrag}
            className="splitter-handle flex-none"
          />
        ) : null}

        {pane === 'preview' ? (
          <PreviewPane
            url={previewUrl}
            running={running}
            version={latestVersion}
            mode={mode}
            refreshKey={refreshKey}
          />
        ) : (
          <FilePanel
            projectId={projectId}
            artifacts={artifacts}
            activeFile={activeFile}
            onSelect={setActiveFile}
            streamingFile={streamingFile}
            streamingBuffer={streamingBuffer}
          />
        )}
      </div>
    </div>
  );
}
