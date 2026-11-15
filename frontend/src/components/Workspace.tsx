import type { PointerEvent as ReactPointerEvent } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, generate, resumeGeneration } from '../api';
import { AGENT_KEYS, agentFor, isAgentKey } from '../lib/agents';
import { copyText } from '../lib/clipboard';
import {
  captureBuildCover,
  capturePublishedCover,
} from '../lib/cover';
import { buildGroups, type ChatGroup } from '../lib/groups';
import { projectStatus } from '../lib/projects';
import type {
  AgentKey,
  Artifact,
  AuthUser,
  ChangesResponse,
  Conversation,
  Execution,
  FileChange,
  Health,
  Project,
  ProjectMode,
  ProjectState,
  ProjectSummary,
} from '../types';
import { PresenceBar } from './Avatar';
import ChatPanel from './ChatPanel';
import CodePanel from './CodePanel';
import HomeSidebar from './HomeSidebar';
import {
  AtomsMark,
  ChevronDown,
  Code,
  Eye,
  ExternalLink,
  Grid,
  Home,
  PanelLeft,
  Spinner,
} from './Icons';
import OverviewPane from './OverviewPane';
import PreviewPane from './PreviewPane';
import PublishDialog from './PublishDialog';
import type { StepView, StepViewKind } from './StepViewPanel';
import type { FileFocus } from './FilePanel';

interface Props {
  projectId: string;
  initialPrompt: string | null;
  onPromptUsed: () => void;
  health: Health | null;
  onExit: () => void;
  projects: ProjectSummary[];
  user: AuthUser;
  onDiscover: () => void;
  onOpenProject: (id: string) => void;
  onOpenProjects: () => void;
  onLogout: () => void;
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

const VIEW_KINDS: StepViewKind[] = [
  "diff",
  "terminal",
  "file",
  "files",
  "search",
  "http",
  "json",
];

function normalizeViewKind(value: string): StepViewKind {
  return VIEW_KINDS.includes(value as StepViewKind)
    ? (value as StepViewKind)
    : "json";
}

function numberField(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function readFocusNote(payload: Record<string, unknown>): string {
  const start = Math.max(1, numberField(payload.start_line, 1));
  const end =
    payload.end_line == null
      ? null
      : Math.max(start, numberField(payload.end_line, start));
  return end == null ? `读取 L${start}` : `读取 L${start}–${end}`;
}

export default function Workspace({
  projectId,
  initialPrompt,
  onPromptUsed,
  health,
  onExit,
  projects,
  user,
  onDiscover,
  onOpenProject,
  onOpenProjects,
  onLogout,
}: Props) {
  const [project, setProject] = useState<Project | null>(null);
  const [mode, setMode] = useState<ProjectMode>('frontend');
  const [groups, setGroups] = useState<ChatGroup[]>([]);
  const [artifacts, setArtifacts] = useState<Record<string, Artifact>>({});
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [codeView, setCodeView] = useState<'files' | 'changes'>('files');
  const [changes, setChanges] = useState<ChangesResponse | null>(null);
  const [changesLoading, setChangesLoading] = useState(false);
  const [changesError, setChangesError] = useState<string | null>(null);
  const [stepView, setStepView] = useState<StepView | null>(null);
  const [stepViewLoading, setStepViewLoading] = useState(false);
  const [stepViewError, setStepViewError] = useState<string | null>(null);
  const [fileFocus, setFileFocus] = useState<FileFocus | null>(null);
  const [runChanges, setRunChanges] = useState<Record<number, FileChange>>({});
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [streamingFile, setStreamingFile] = useState<string | null>(null);
  const [streamingBuffer, setStreamingBuffer] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [pane, setPane] = useState<'preview' | 'overview' | 'code'>('preview');
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishBusy, setPublishBusy] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishDescription, setPublishDescription] = useState('');
  const [publishCategory, setPublishCategory] = useState('其他');
  const [suggestingCategory, setSuggestingCategory] = useState(false);
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
  // True when a build that outlived a previous page visit is still running on
  // the server; we re-attach to its live event stream below.
  const [watching, setWatching] = useState(false);
  // The home sidebar is the workspace's optional third column, hidden until
  // the top-left toggle is clicked.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);
  const resumeStartedRef = useRef(false);
  const dragCleanupRef = useRef<(() => void) | null>(null);
  const buildCoverAttempt = useRef<string | null>(null);
  const changesTimerRef = useRef<number | null>(null);
  const changesRequestRef = useRef(0);
  const stepViewRequestRef = useRef(0);
  const codeViewRef = useRef<'files' | 'changes'>('files');

  const maybeCaptureBuildCover = useCallback(
    (version: number) => {
      const key = `${projectId}:${version}`;
      if (buildCoverAttempt.current === key) return;
      buildCoverAttempt.current = key;
      void captureBuildCover(projectId, version).then((ok) => {
        if (!ok && buildCoverAttempt.current === key) {
          buildCoverAttempt.current = null;
        }
      });
    },
    [projectId]
  );

  const latestVersion = useMemo(
    () =>
      Object.values(artifacts).reduce(
        (max, artifact) => Math.max(max, artifact.version),
        0,
      ),
    [artifacts],
  );

  const status = project ? projectStatus(project) : 'draft';
  const hasOverview = status !== 'draft';
  const building = running || watching;
  const publicUrl = project?.published_url ?? null;
  const hasChanges = Boolean(
    project?.has_changes ??
      (project?.published_version != null &&
        project?.built_version != null &&
        project.built_version > project.published_version),
  );
  const publishLabel = building
    ? '构建中…'
    : status === 'online'
      ? hasChanges
        ? '更新'
        : '已发布'
      : status === 'paused'
        ? hasChanges
          ? '更新'
          : '已暂停'
        : '发布';

  const chattedAgents = useMemo<AgentKey[]>(() => {
    const seen = new Set<string>();
    for (const group of groups) {
      if (group.kind === 'agent' && group.agent) seen.add(group.agent);
    }
    return AGENT_KEYS.filter((key) => seen.has(key));
  }, [groups]);

  // Reflect a local run in the sidebar immediately, without waiting for the
  // shared 2s project poll in App.
  const sidebarProjects = useMemo(
    () =>
      running || watching
        ? projects.map((item) =>
            item.id === projectId ? { ...item, generating: true } : item,
          )
        : projects,
    [projects, projectId, running, watching],
  );

  useEffect(() => {
    if (project?.name) document.title = `${project.name} · Atoms`;
  }, [project?.name]);

  const applyState = useCallback((state: ProjectState) => {
    setProject(state.project);
    setMode(state.mode ?? 'frontend');
    const map: Record<string, Artifact> = {};
    for (const artifact of state.artifacts) map[artifact.filename] = artifact;
    setArtifacts(map);
    setActiveFile((current) =>
      current && map[current] ? current : pickDefaultFile(state.artifacts),
    );
    // The backend only exposes preview_url once .preview/index.html exists, so
    // an in-flight build cannot point the iframe at a missing file.
    setPreviewUrl(state.preview_url ?? null);
    setGroups(buildGroups(state.conversations, state.executions));
  }, []);

  const refreshChanges = useCallback(async () => {
    // Publishing changes the diff baseline, so a slow pre-publish response
    // must not overwrite a newer one when both are in flight.
    const request = ++changesRequestRef.current;
    setChangesLoading(true);
    setChangesError(null);
    try {
      const next = await api.projectChanges(projectId);
      if (changesRequestRef.current === request) setChanges(next);
    } catch (err) {
      if (changesRequestRef.current === request) {
        setChangesError((err as Error).message || '未发布变更加载失败');
      }
    } finally {
      if (changesRequestRef.current === request) setChangesLoading(false);
    }
  }, [projectId]);

  const scheduleChangesRefresh = useCallback(() => {
    if (changesTimerRef.current) window.clearTimeout(changesTimerRef.current);
    changesTimerRef.current = window.setTimeout(() => {
      changesTimerRef.current = null;
      void refreshChanges();
    }, 500);
  }, [refreshChanges]);

  useEffect(() => {
    codeViewRef.current = codeView;
  }, [codeView]);

  useEffect(() => {
    if (codeView === 'changes' && !stepView) void refreshChanges();
  }, [codeView, stepView, refreshChanges]);

  useEffect(
    () => () => {
      if (changesTimerRef.current) window.clearTimeout(changesTimerRef.current);
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setLoadError(null);
    setPreviewUrl(null);
    setActiveFile(null);
    setPublishOpen(false);
    setPublishError(null);
    setCodeView('files');
    setChanges(null);
    setChangesError(null);
    setChangesLoading(false);
    setStepView(null);
    setStepViewError(null);
    setStepViewLoading(false);
    setFileFocus(null);
    setRunChanges({});
    api
      .getProject(projectId)
      .then((state) => {
        if (cancelled) return;
        applyState(state);
        const built = state.project.built_version;
        const buildCover = state.project.build_cover_version;
        const hasPublishedCover =
          state.project.cover_version != null &&
          state.project.cover_version === state.project.published_version;
        // Backfill a working-build thumbnail for projects built before this
        // feature existed. A published cover already wins on the project card,
        // so it is not worth another capture in that case.
        if (built != null && buildCover !== built && !hasPublishedCover) {
          maybeCaptureBuildCover(built);
        }
        if (state.generating) {
          // A build kept running after the previous page was closed.
          setRunning(true);
          setWatching(true);
        }
        setLoaded(true);
        // Prefetch the aggregate diff so the changes tab shows its file count
        // (and any baseline notice) right after a page refresh, instead of
        // only after the tab is first opened.
        void refreshChanges();
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setLoadError(err.message || '项目加载失败');
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, applyState, maybeCaptureBuildCover, refreshChanges]);

  // The overview only exists after the first successful build; never leave the
  // right pane pointing at a hidden mode.
  useEffect(() => {
    if (pane === 'overview' && !hasOverview) setPane('preview');
  }, [pane, hasOverview]);

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

  const normalizeAgent = useCallback((raw: unknown) => {
    const value = typeof raw === 'string' ? raw : 'mike';
    return isAgentKey(value) ? value : agentFor(value).key;
  }, []);

  const handleEvent = useCallback(
    (event: string, data: Record<string, unknown>) => {
      if (event === 'snapshot') {
        const state = data.state as ProjectState | undefined;
        if (!state) return;
        applyState(state);
        setGroups((prev) =>
          prev.map((group) =>
            group.executions.some((execution) => execution.status === 'running')
              ? { ...group, live: true, status: 'running' as const }
              : group,
          ),
        );
        const stream = data.stream as
          | { filename?: unknown; content?: unknown }
          | undefined;
        if (typeof stream?.filename === 'string') {
          setStreamingFile(stream.filename);
          setActiveFile(stream.filename);
        }
        if (typeof stream?.content === 'string') {
          setStreamingBuffer(stream.content);
        }
        return;
      }
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
      if (event === 'file_change') {
        const change = data as unknown as FileChange;
        if (typeof change.id !== 'number' || !change.filename) return;
        setRunChanges((prev) => ({ ...prev, [change.id]: change }));
        if (change.change_type === 'deleted') {
          setArtifacts((prev) => {
            if (!(change.filename in prev)) return prev;
            const next = { ...prev };
            delete next[change.filename];
            return next;
          });
          setActiveFile((prev) =>
            prev === change.filename ? null : prev,
          );
        }
        if (codeViewRef.current === 'changes') scheduleChangesRefresh();
        return;
      }
      if (event === 'changes_reset') {
        setChanges(null);
        setRunChanges({});
        stepViewRequestRef.current += 1;
        setStepView(null);
        setStepViewError(null);
        setStepViewLoading(false);
        setFileFocus(null);
        if (codeViewRef.current === 'changes') scheduleChangesRefresh();
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
        if (typeof data.version === 'number') {
          maybeCaptureBuildCover(data.version);
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
    [applyState, normalizeAgent, maybeCaptureBuildCover, scheduleChangesRefresh],
  );

  const openStepView = useCallback(
    async (execution: Execution) => {
      const changeCount =
        execution.change_count ?? (execution.change_id ? 1 : 0);
      const request = ++stepViewRequestRef.current;
      setPane('code');
      setStepViewError(null);
      setStepViewLoading(false);
      setFileFocus(null);

      if (changeCount > 0) {
        const live = Object.values(runChanges).filter(
          (change) => change.execution_id === execution.id,
        );
        if (live.length) {
          setStepView({
            title: execution.step,
            kind: 'diff',
            changes: live,
          });
          return;
        }
        setStepView({ title: execution.step, kind: 'diff', changes: [] });
        setStepViewLoading(true);
        try {
          const data = await api.executionChanges(projectId, execution.id);
          if (stepViewRequestRef.current !== request) return;
          setStepView({
            title: execution.step,
            kind: 'diff',
            changes: data.changes,
          });
        } catch (err) {
          if (stepViewRequestRef.current !== request) return;
          setStepViewError(
            (err as Error).message || '步骤 diff 加载失败',
          );
        } finally {
          if (stepViewRequestRef.current === request) {
            setStepViewLoading(false);
          }
        }
        return;
      }

      const viewType = execution.view_type;
      if (!viewType || execution.status === 'running') return;
      const kind = normalizeViewKind(viewType);
      setStepView({ title: execution.step, kind, status: execution.status });
      setStepViewLoading(true);
      try {
        const data = await api.executionView(projectId, execution.id);
        if (stepViewRequestRef.current !== request) return;
        const payload = data.payload ?? {};
        const nextKind = normalizeViewKind(data.view_type || viewType);
        if (nextKind === 'file') {
          const path =
            typeof payload.path === 'string' ? payload.path : '';
          if (path && (path in artifacts)) {
            // The file still exists: open it at the range the agent read,
            // rather than showing a duplicate read-only snapshot.
            setStepView(null);
            setCodeView('files');
            setActiveFile(path);
            setFileFocus({
              path,
              start: Math.max(1, numberField(payload.start_line, 1)),
              end: Math.max(
                1,
                numberField(
                  payload.end_line,
                  numberField(payload.start_line, 1),
                ),
              ),
              note: readFocusNote(payload),
            });
            return;
          }
        }
        setStepView({
          title: execution.step,
          kind: nextKind,
          payload,
          truncated: data.truncated,
          status: execution.status,
        });
      } catch (err) {
        if (stepViewRequestRef.current !== request) return;
        setStepViewError(
          (err as Error).message || '步骤视图加载失败',
        );
      } finally {
        if (stepViewRequestRef.current === request) {
          setStepViewLoading(false);
        }
      }
    },
    [projectId, runChanges, artifacts],
  );

  const closeStepView = useCallback(() => {
    stepViewRequestRef.current += 1;
    setStepView(null);
    setStepViewError(null);
    setStepViewLoading(false);
  }, []);

  const selectFile = useCallback((path: string) => {
    setActiveFile(path);
    setFileFocus((current) =>
      current && current.path !== path ? null : current
    );
  }, []);

  const openFileAt = useCallback(
    (path: string, line?: number) => {
      if (!path) return;
      if (!(path in artifacts)) {
        setStepViewError('该文件已不在当前项目中，无法打开。');
        return;
      }
      stepViewRequestRef.current += 1;
      setPane('code');
      setStepView(null);
      setStepViewError(null);
      setStepViewLoading(false);
      setCodeView('files');
      setActiveFile(path);
      setFileFocus(
        line
          ? { path, start: line, end: line, note: `定位第 ${line} 行` }
          : null
      );
    },
    [artifacts],
  );

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
      setFileFocus(null);
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
      let aborted = false;

      try {
        await generate(projectId, message, handleEvent, controller.signal);
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          aborted = true;
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
        if (!aborted) {
          // A failed round rolls the project back on the server; reload so the
          // file tree and preview match what is actually on disk.
          try {
            applyState(await api.getProject(projectId));
          } catch {
            // Ignore; the next user action will refresh the workspace.
          }
          void refreshChanges();
        }
      }
    },
    [projectId, handleEvent, applyState, refreshChanges],
  );

  const resume = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setError(null);
    let aborted = false;
    try {
      await resumeGeneration(projectId, handleEvent, controller.signal);
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        aborted = true;
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
        setError((err as Error).message || '恢复生成失败，请重试。');
      }
    } finally {
      setRunning(false);
      setStreamingFile(null);
      setStreamingBuffer('');
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
      if (!aborted) {
        // The build may have finished just before the stream attached.
        try {
          applyState(await api.getProject(projectId));
        } catch {
          // Ignore; the next user action will refresh the workspace.
        }
        void refreshChanges();
      }
    }
  }, [projectId, handleEvent, applyState, refreshChanges]);

  useEffect(() => {
    if (!watching || resumeStartedRef.current) return;
    resumeStartedRef.current = true;
    void resume().finally(() => setWatching(false));
  }, [watching, resume]);

  useEffect(() => {
    if (!loaded || !initialPrompt || startedRef.current || watching) return;
    startedRef.current = true;
    onPromptUsed();
    if (groups.length === 0) void run(initialPrompt);
  }, [loaded, initialPrompt, groups.length, onPromptUsed, run, watching]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    // Aborting the fetch only detaches this page; tell the server to stop too.
    void api.cancelGeneration(projectId).catch(() => undefined);
  }, [projectId]);

  function refreshPreview() {
    setRefreshKey((value) => value + 1);
  }

  const copyToClipboard = useCallback(async (value: string | null) => {
    if (!value) return;
    const ok = await copyText(value);
    if (!ok) return;
    setShareCopied(true);
    window.setTimeout(() => setShareCopied(false), 1500);
  }, []);

  async function share() {
    // Once published, sharing should hand out the public site rather than the
    // login-gated workspace preview.
    const target =
      publicUrl && (status === 'online' || status === 'paused')
        ? new URL(publicUrl, window.location.origin).toString()
        : previewUrl
          ? new URL(previewUrl, window.location.origin).toString()
          : window.location.href;
    await copyToClipboard(target);
  }

  const reloadProject = useCallback(async () => {
    try {
      applyState(await api.getProject(projectId));
    } catch {
      // Keep the dialog error visible; the next action refreshes state.
    }
  }, [projectId, applyState]);

  const openPublish = useCallback(() => {
    setPublishDescription(project?.description ?? '');
    setPublishCategory(project?.category ?? '其他');
    setPublishError(null);
    setPublishOpen(true);
  }, [project?.description, project?.category]);

  const closePublish = useCallback(() => {
    setPublishOpen(false);
    setPublishError(null);
  }, []);

  const suggestPublishCategory = useCallback(async () => {
    setSuggestingCategory(true);
    setPublishError(null);
    try {
      const result = await api.suggestCategory(
        projectId,
        publishDescription
      );
      setPublishCategory(result.category);
    } catch (err) {
      setPublishError((err as Error).message || '自动识别失败');
    } finally {
      setSuggestingCategory(false);
    }
  }, [projectId, publishDescription]);

  const doPublish = useCallback(async () => {
    setPublishBusy(true);
    setPublishError(null);
    try {
      const result = await api.publishProject(projectId, {
        description: publishDescription,
        category: publishCategory,
      });
      await reloadProject();
      // Publishing moves the diff baseline to the current build, so the
      // unpublished-changes badge and list must be recomputed right away
      // instead of staying on the pre-publish snapshot until the tab is
      // opened again.
      void refreshChanges();
      setPublishOpen(false);
      // The cover is captured from the just-published workspace build. It is
      // best-effort: a failure leaves the discover card on its CSS cover.
      const version = result.project.published_version;
      if (version != null) {
        void capturePublishedCover(projectId, version);
      }
    } catch (err) {
      setPublishError((err as Error).message || '发布失败');
    } finally {
      setPublishBusy(false);
    }
  }, [
    projectId,
    publishDescription,
    publishCategory,
    reloadProject,
    refreshChanges,
  ]);

  const doPause = useCallback(async () => {
    setStatusBusy(true);
    setPublishError(null);
    try {
      await api.pauseProject(projectId);
      await reloadProject();
      setPublishOpen(false);
    } catch (err) {
      setPublishError((err as Error).message || '暂停失败');
    } finally {
      setStatusBusy(false);
    }
  }, [projectId, reloadProject]);

  const doResume = useCallback(async () => {
    setStatusBusy(true);
    setPublishError(null);
    try {
      await api.resumeProject(projectId);
      await reloadProject();
      setPublishOpen(false);
    } catch (err) {
      setPublishError((err as Error).message || '恢复失败');
    } finally {
      setStatusBusy(false);
    }
  }, [projectId, reloadProject]);

  const openSite = useCallback(() => {
    if (!publicUrl) return;
    window.open(
      new URL(publicUrl, window.location.origin).toString(),
      '_blank',
      'noopener,noreferrer',
    );
  }, [publicUrl]);

  const copyPublicUrl = useCallback(() => {
    if (!publicUrl) return;
    void copyToClipboard(new URL(publicUrl, window.location.origin).toString());
  }, [copyToClipboard, publicUrl]);

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
    <div className="flex h-full overflow-hidden bg-base">
      {sidebarOpen ? (
        <HomeSidebar
          projects={sidebarProjects}
          section="workspace"
          user={user}
          onHome={onExit}
          onDiscover={onDiscover}
          onProjects={onOpenProjects}
          onOpenProject={onOpenProject}
          onCollapse={() => setSidebarOpen(false)}
          onLogout={onLogout}
        />
      ) : null}

      <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-base">
      <header className="flex h-11 flex-none items-center bg-base">
        <div
          style={{ width: chatWidth }}
          className="flex h-full min-w-0 flex-none items-center gap-2 border-r border-transparent px-4"
        >
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            title={sidebarOpen ? '收起侧边栏' : '展开侧边栏'}
            aria-label={sidebarOpen ? '收起侧边栏' : '展开侧边栏'}
            aria-pressed={sidebarOpen}
            className="group grid h-7 w-7 flex-none place-items-center rounded-md text-ink-95 transition hover:bg-line-6"
          >
            <AtomsMark size={20} className={sidebarOpen ? 'hidden' : 'group-hover:hidden'} />
            <PanelLeft
              size={18}
              className={
                sidebarOpen
                  ? 'block text-ink-80'
                  : 'hidden text-ink-80 group-hover:block'
              }
            />
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
                        ? 'Mock 演示模式'
                        : health?.model || 'LLM'}
                    </p>
                  </div>
                  <div className="my-1 h-px bg-line-4" />

                  <button
                    type="button"
                    onClick={() => {
                      setProjectMenu(false);
                      onOpenProjects();
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
              onClick={() => {
                closeStepView();
                setPane('preview');
              }}
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
            {hasOverview ? (
              <button
                type="button"
                onClick={() => {
                  closeStepView();
                  setPane('overview');
                }}
                title="概览"
                aria-label="概览"
                className={`flex h-[30px] items-center gap-1.5 rounded-full text-[14px] transition ${
                  pane === 'overview'
                    ? 'bg-white px-2.5 font-medium text-brand-text shadow-[0_1px_3px_rgba(12,12,12,0.10)]'
                    : 'w-[34px] justify-center text-ink-55 hover:text-ink-80'
                }`}
              >
                <Grid size={17} />
                {pane === 'overview' ? '概览' : null}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => {
                closeStepView();
                setPane('code');
              }}
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
              onClick={openPublish}
              disabled={building || publishBusy || statusBusy}
              title={publishLabel}
              className="flex h-[30px] items-center gap-1.5 rounded-full bg-brand px-3 text-[13px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {building ? <Spinner size={13} /> : null}
              {publishLabel}
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
            onStop={stop}
            onOpenCode={() => {
              closeStepView();
              setPane('code');
            }}
            onOpenStep={(execution) => void openStepView(execution)}
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

        {pane === 'overview' && project ? (
          <OverviewPane
            project={project}
            status={status}
            mode={mode}
            latestVersion={latestVersion}
            building={building}
            busy={statusBusy}
            copied={shareCopied}
            error={publishError}
            onOpenPublish={openPublish}
            onPause={() => void doPause()}
            onResume={() => void doResume()}
            onCopyUrl={copyPublicUrl}
            onOpenSite={openSite}
          />
        ) : pane === 'code' ? (
          <CodePanel
            projectId={projectId}
            artifacts={artifacts}
            activeFile={activeFile}
            onSelect={selectFile}
            streamingFile={streamingFile}
            streamingBuffer={streamingBuffer}
            view={codeView}
            onViewChange={(view) => {
              closeStepView();
              setCodeView(view);
            }}
            changes={changes}
            changesLoading={changesLoading}
            changesError={changesError}
            onRefreshChanges={() => void refreshChanges()}
            stepView={stepView}
            stepViewLoading={stepViewLoading}
            stepViewError={stepViewError}
            onCloseStepView={closeStepView}
            onOpenFile={openFileAt}
            fileFocus={fileFocus}
            hasChanges={hasChanges}
          />
        ) : (
          <PreviewPane
            url={previewUrl}
            running={running}
            version={latestVersion}
            mode={mode}
            refreshKey={refreshKey}
          />
        )}
      </div>
      </div>

      {project ? (
        <PublishDialog
          open={publishOpen}
          project={project}
          status={status}
          building={building}
          busy={publishBusy || statusBusy}
          error={publishError}
          copied={shareCopied}
          description={publishDescription}
          category={publishCategory}
          suggestingCategory={suggestingCategory}
          onDescriptionChange={setPublishDescription}
          onCategoryChange={setPublishCategory}
          onSuggestCategory={() => void suggestPublishCategory()}
          onClose={closePublish}
          onPublish={() => void doPublish()}
          onPause={() => void doPause()}
          onResume={() => void doResume()}
          onOpenSite={openSite}
          onCopyUrl={copyPublicUrl}
        />
      ) : null}
    </div>
  );
}
