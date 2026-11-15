export type Role = "user" | "assistant";
export type AgentKey = "mike" | "bob" | "alex";
export type ExecutionStatus = "running" | "success" | "warning" | "error";
export type ProjectMode = "frontend" | "fullstack" | "backend";
export type ProjectStatus = "draft" | "unpublished" | "online" | "paused";

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
  tool?: string | null;
  target?: string | null;
  view_type?: string | null;
  change_id?: number | null;
  change_count?: number | null;
}

/** Read-only payload behind one timeline step. */
export interface ExecutionView {
  execution_id: number;
  view_type: string;
  payload: Record<string, unknown>;
  truncated: boolean;
}

export type ChangeType = "created" | "modified" | "deleted";

export interface FileChange {
  id: number;
  project_id?: string;
  version: number;
  run_id?: string | null;
  agent?: string | null;
  execution_id?: number | null;
  filename: string;
  change_type: ChangeType;
  diff: string;
  additions: number;
  deletions: number;
  rolled_back?: number;
  truncated?: number;
  created_at?: string;
}

export interface ChangeFile {
  filename: string;
  change_type: ChangeType;
  additions: number;
  deletions: number;
  diff: string;
  truncated: boolean;
}

export interface ChangesResponse {
  published_version: number | null;
  current_version: number;
  has_published: boolean;
  baseline_ok: boolean;
  files: ChangeFile[];
  summary: { created: number; modified: number; deleted: number };
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  provider: "email" | "google" | "quick" | string;
  email_verified: number;
  created_at?: string;
  last_login_at?: string | null;
}

export interface AuthProviders {
  google: boolean;
  google_reason?: string | null;
  quick: boolean;
  quick_password?: string | null;
  mail: "smtp" | "dev";
  dev_links: boolean;
}

export interface QuickLoginResult {
  user: AuthUser;
  created: boolean;
  default_password?: string | null;
}

export interface Project {
  id: string;
  name: string;
  user_id?: string | null;
  created_at: string;
  built_version?: number | null;
  built_at?: string | null;
  published_version?: number | null;
  published_at?: string | null;
  paused?: boolean;
  status?: ProjectStatus;
  has_changes?: boolean;
  published_url?: string | null;
  description?: string | null;
  category?: string | null;
  view_count?: number | null;
  cover_version?: number | null;
  cover_at?: string | null;
  build_cover_version?: number | null;
  build_cover_at?: string | null;
}

export interface ProjectState {
  project: Project;
  conversations: Conversation[];
  artifacts: Artifact[];
  executions: Execution[];
  mode: ProjectMode;
  preview_url: string | null;
  generating?: boolean;
  status?: ProjectStatus;
  has_changes?: boolean;
  published_url?: string | null;
  paused?: boolean;
}

export interface ProjectSummary {
  id: string;
  name: string;
  user_id?: string | null;
  created_at: string;
  message_count: number;
  artifact_count: number;
  latest_version: number | null;
  mode?: ProjectMode;
  has_frontend?: number;
  has_backend?: number;
  generating?: boolean;
  built_version?: number | null;
  built_at?: string | null;
  published_version?: number | null;
  published_at?: string | null;
  paused?: boolean;
  status?: ProjectStatus;
  has_changes?: boolean;
  published_url?: string | null;
  description?: string | null;
  category?: string | null;
  view_count?: number | null;
  cover_version?: number | null;
  cover_at?: string | null;
  build_cover_version?: number | null;
  build_cover_at?: string | null;
  cover_url?: string | null;
}

export type DiscoverSort = "latest" | "popular";

/**
 * An app shown on the discover page. The backend excludes the viewer's own
 * projects, so this always describes another user's published snapshot.
 */
export interface DiscoverApp {
  id: string;
  name: string;
  description: string;
  category: string;
  mode: ProjectMode;
  view_count: number;
  published_version?: number | null;
  published_at?: string | null;
  published_url: string;
  cover_url: string | null;
  saved: boolean;
  author_name: string;
  author_initial: string;
}

export interface DiscoverDetail extends DiscoverApp {
  related: DiscoverApp[];
}

export interface Health {
  ok: boolean;
  llm_mode: "mock" | "deepseek";
  model: string;
  version: string;
  running_apps?: Record<string, number>;
  auth?: {
    mail: "smtp" | "dev";
    google: boolean;
    google_reason?: string | null;
    quick: boolean;
  };
}
