export type Role = "user" | "assistant";
export type ExecutionStatus = "running" | "success" | "warning" | "error";

export interface Conversation {
  id: number;
  role: Role;
  content: string;
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
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
  message_count: number;
  artifact_count: number;
  latest_version: number | null;
}

export interface Health {
  ok: boolean;
  llm_mode: "mock" | "deepseek";
  model: string;
  version: string;
}
