import type {
  AuthProviders,
  AuthUser,
  ChangesResponse,
  DiscoverApp,
  DiscoverDetail,
  DiscoverSort,
  ExecutionView,
  FileChange,
  Health,
  Project,
  ProjectState,
  ProjectSummary,
  QuickLoginResult,
} from "./types";

/** Fired when a protected endpoint answers 401 so the shell can show login. */
export const AUTH_EVENT = "atoms:unauthorized";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (
      data.detail &&
      typeof data.detail === "object" &&
      "message" in data.detail
    ) {
      return String((data.detail as { message: unknown }).message);
    }
    return res.statusText;
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

async function request(
  url: string,
  init?: RequestInit,
  options?: { silent401?: boolean }
): Promise<Response> {
  const res = await fetch(url, init);
  if (res.status === 401 && !options?.silent401) {
    window.dispatchEvent(new Event(AUTH_EVENT));
  }
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res;
}

async function getJson<T>(
  url: string,
  options?: { silent401?: boolean }
): Promise<T> {
  const res = await request(url, undefined, options);
  return (await res.json()) as T;
}

async function postJson<T>(
  url: string,
  body: unknown,
  options?: { silent401?: boolean }
): Promise<T> {
  const res = await request(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    options
  );
  return (await res.json()) as T;
}

export const api = {
  health: () => getJson<Health>("/api/health"),

  // ---- auth ---------------------------------------------------------------

  providers: () => getJson<AuthProviders>("/api/auth/providers"),

  me: () =>
    getJson<{ user: AuthUser }>("/api/auth/me", { silent401: true }).then(
      (data) => data.user
    ),

  checkEmail: (email: string) =>
    postJson<{ registered: boolean; provider: string | null; verified: boolean }>(
      "/api/auth/check-email",
      { email },
      { silent401: true }
    ),

  register: (email: string, password: string, redirect = "/dashboard") =>
    postJson<{
      email: string;
      verification_sent: boolean;
      already_registered: boolean;
      dev_verify_url?: string | null;
      warning?: string | null;
    }>(
      "/api/auth/register",
      { email, password, redirect },
      { silent401: true }
    ),

  verifyEmail: (token: string) =>
    postJson<{
      ok: boolean;
      email: string;
      user: AuthUser;
      redirect: string;
    }>("/api/auth/verify-email", { token }, { silent401: true }),

  resendVerification: (email: string, redirect = "/dashboard") =>
    postJson<{ sent: boolean; dev_verify_url?: string | null }>(
      "/api/auth/resend-verification",
      { email, redirect },
      { silent401: true }
    ),

  login: (email: string, password: string) =>
    postJson<{ user: AuthUser }>(
      "/api/auth/login",
      { email, password },
      { silent401: true }
    ).then((data) => data.user),

  quickLogin: (email: string) =>
    postJson<QuickLoginResult>(
      "/api/auth/quick",
      { email },
      { silent401: true }
    ),

  logout: () => postJson<{ ok: boolean }>("/api/auth/logout", {}),

  forgotPassword: (email: string) =>
    postJson<{
      sent: boolean;
      delivered?: boolean | null;
      dev_reset_url?: string | null;
    }>("/api/auth/password/forgot", { email }, { silent401: true }),

  resetPassword: (token: string, password: string) =>
    postJson<{ ok: boolean }>(
      "/api/auth/password/reset",
      { token, password },
      { silent401: true }
    ),

  googleStartUrl: (redirect: string) =>
    `/api/auth/google/start?redirect=${encodeURIComponent(redirect)}`,

  // ---- projects -----------------------------------------------------------

  listProjects: async (): Promise<ProjectSummary[]> => {
    const data = await getJson<{ projects: ProjectSummary[] }>("/api/projects");
    return data.projects;
  },

  createProject: async (prompt: string): Promise<Project> => {
    // The backend derives a short title from the full prompt (LLM-assisted,
    // with a heuristic fallback) instead of truncating the first line here.
    return postJson<Project>("/api/projects", { prompt });
  },

  getProject: (pid: string) => getJson<ProjectState>(`/api/projects/${pid}`),

  projectChanges: (pid: string) =>
    getJson<ChangesResponse>(`/api/projects/${pid}/changes`),

  projectChange: (pid: string, changeId: number) =>
    getJson<FileChange>(`/api/projects/${pid}/changes/${changeId}`),

  executionChanges: (pid: string, executionId: number) =>
    getJson<{ changes: FileChange[] }>(
      `/api/projects/${pid}/executions/${executionId}/changes`
    ),

  executionView: (pid: string, executionId: number) =>
    getJson<ExecutionView>(
      `/api/projects/${pid}/executions/${executionId}/view`
    ),

  // Generation outlives the SSE connection; stopping it needs an explicit call.
  cancelGeneration: async (pid: string): Promise<void> => {
    await request(`/api/projects/${pid}/cancel`, { method: "POST" });
  },

  deleteProject: async (pid: string): Promise<void> => {
    await request(`/api/projects/${pid}`, { method: "DELETE" });
  },

  publishProject: (
    pid: string,
    meta?: { description?: string; category?: string }
  ) =>
    postJson<{
      ok: boolean;
      project: Project;
      published_url: string;
      manifest?: Record<string, unknown>;
    }>(`/api/projects/${pid}/publish`, meta ?? {}),

  suggestCategory: (pid: string, description: string) =>
    postJson<{ category: string }>(
      `/api/projects/${pid}/category/suggest`,
      { description }
    ),

  uploadCover: (pid: string, version: number, image: string) =>
    postJson<{ ok: boolean }>(`/api/projects/${pid}/cover`, {
      version,
      image,
    }),

  uploadBuildCover: (pid: string, version: number, image: string) =>
    postJson<{ ok: boolean }>(`/api/projects/${pid}/build-cover`, {
      version,
      image,
    }),

  pauseProject: (pid: string) =>
    postJson<{ ok: boolean; project: Project }>(
      `/api/projects/${pid}/pause`,
      {}
    ),

  resumeProject: (pid: string) =>
    postJson<{ ok: boolean; project: Project }>(
      `/api/projects/${pid}/resume`,
      {}
    ),

  exportProject: async (
    pid: string
  ): Promise<{ blob: Blob; filename: string }> => {
    const res = await request(`/api/projects/${encodeURIComponent(pid)}/export`);

    const disposition = res.headers.get("content-disposition") ?? "";
    const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
    const plain = /filename="?([^";]+)"?/i.exec(disposition);
    let filename = `atoms-${pid}.zip`;
    if (encoded?.[1]) {
      try {
        filename = decodeURIComponent(encoded[1]);
      } catch {
        // Keep the default name if the header is malformed.
      }
    } else if (plain?.[1]) {
      filename = plain[1];
    }
    return { blob: await res.blob(), filename };
  },

  // ---- discover -----------------------------------------------------------

  discover: async (params: {
    sort?: DiscoverSort;
    category?: string;
    q?: string;
    saved?: boolean;
    offset?: number;
    limit?: number;
  }): Promise<{ apps: DiscoverApp[]; has_more: boolean }> => {
    const query = new URLSearchParams();
    if (params.sort) query.set("sort", params.sort);
    if (params.category) query.set("category", params.category);
    if (params.q) query.set("q", params.q);
    if (params.saved) query.set("saved", "1");
    if (params.offset != null) query.set("offset", String(params.offset));
    if (params.limit != null) query.set("limit", String(params.limit));
    const suffix = query.toString();
    return getJson<{ apps: DiscoverApp[]; has_more: boolean }>(
      `/api/discover${suffix ? `?${suffix}` : ""}`
    );
  },

  discoverDetail: async (pid: string): Promise<DiscoverDetail> => {
    const data = await getJson<{ app: DiscoverDetail }>(
      `/api/discover/${encodeURIComponent(pid)}`
    );
    return data.app;
  },

  recordDiscoverView: (pid: string) =>
    postJson<{ ok: boolean; view_count: number }>(
      `/api/discover/${encodeURIComponent(pid)}/view`,
      {}
    ),

  saveDiscover: (pid: string) =>
    postJson<{ ok: boolean; saved: boolean }>(
      `/api/discover/${encodeURIComponent(pid)}/save`,
      {}
    ),

  unsaveDiscover: async (pid: string): Promise<{ saved: boolean }> => {
    const res = await request(
      `/api/discover/${encodeURIComponent(pid)}/save`,
      { method: "DELETE" }
    );
    return (await res.json()) as { saved: boolean };
  },
};

export type StreamHandler = (event: string, data: Record<string, unknown>) => void;

function parseBlock(block: string, onEvent: StreamHandler): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return;
  try {
    onEvent(event, JSON.parse(dataLines.join("\n")) as Record<string, unknown>);
  } catch {
    // Ignore malformed frames; the stream keeps going.
  }
}

async function readEventStream(
  url: string,
  init: RequestInit,
  onEvent: StreamHandler
): Promise<void> {
  const res = await request(url, init);
  if (!res.body) throw new Error("浏览器不支持流式响应");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      parseBlock(block, onEvent);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) parseBlock(buffer, onEvent);
}

export async function generate(
  projectId: string,
  message: string,
  onEvent: StreamHandler,
  signal?: AbortSignal
): Promise<void> {
  return readEventStream(
    `/api/projects/${projectId}/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal,
    },
    onEvent
  );
}

/** Re-attach to a build that is still running after a page reload. */
export async function resumeGeneration(
  projectId: string,
  onEvent: StreamHandler,
  signal?: AbortSignal
): Promise<void> {
  return readEventStream(
    `/api/projects/${projectId}/events`,
    { signal },
    onEvent
  );
}
