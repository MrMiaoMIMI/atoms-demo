import type { Health, Project, ProjectState, ProjectSummary } from "./types";

async function readError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string };
    return data.detail || res.statusText;
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as T;
}

export const api = {
  health: () => getJson<Health>("/api/health"),

  listProjects: async (): Promise<ProjectSummary[]> => {
    const data = await getJson<{ projects: ProjectSummary[] }>("/api/projects");
    return data.projects;
  },

  createProject: async (prompt: string): Promise<Project> => {
    const cleaned = prompt.replace(/@(?:mike|bob|alex)(?![A-Za-z0-9])/gi, "").trim();
    const firstLine =
      cleaned
        .split(/\r?\n/)
        .map((line) => line.trim())
        .find(Boolean) ?? cleaned;
    const name = firstLine.replace(/^[\s,，。.;；:：]+/, "").trim().slice(0, 24);
    const res = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, name: name || prompt.slice(0, 24) }),
    });
    if (!res.ok) throw new Error(await readError(res));
    return (await res.json()) as Project;
  },

  getProject: (pid: string) => getJson<ProjectState>(`/api/projects/${pid}`),

  deleteProject: async (pid: string): Promise<void> => {
    const res = await fetch(`/api/projects/${pid}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await readError(res));
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

export async function generate(
  projectId: string,
  message: string,
  onEvent: StreamHandler,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`/api/projects/${projectId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!res.ok) throw new Error(await readError(res));
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
