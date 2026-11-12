export type Role = "user" | "assistant";
export type AgentKey = "mike" | "bob" | "alex";
export type ExecutionStatus = "running" | "success" | "warning" | "error";
export type ProjectMode = "frontend" | "fullstack" | "backend";

export interface Conversation {
  id: number;
  role: Role;
  content: string;
  agent?: AgentKey | string | null;
  run_id?: string | null;
  run_index?: number | null;
  created_at?: string;
}

export interface Artifact {
  filename: string;
  content: string;
  version: number;
  created_at?: string;
}

export interface Execution {
  id: number;
  agent: string;
  step: string;
  status: ExecutionStatus;
  log: string;
  run_id?: string | null;
  created_at?: string;
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
}

export interface ProjectState {
  project: Project;
  conversations: Conversation[];
  artifacts: Artifact[];
  executions: Execution[];
  mode: ProjectMode;
  preview_url: string | null;
  generating?: boolean;
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
  message_count: number;
  artifact_count: number;
  latest_version: number | null;
  mode?: ProjectMode;
  has_frontend?: number;
  has_backend?: number;
  generating?: boolean;
}

export interface Health {
  ok: boolean;
  llm_mode: "mock" | "deepseek";
  model: string;
  version: string;
  running_apps?: Record<string, number>;
}
