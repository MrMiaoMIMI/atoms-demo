import type { ProjectMode, ProjectStatus, ProjectSummary } from '../types';

export const MODE_LABEL: Record<string, string> = {
  frontend: '前端',
  fullstack: '全栈',
  backend: 'API',
};

interface StatusFields {
  status?: ProjectStatus;
  built_version?: number | null;
  published_version?: number | null;
  paused?: boolean;
}

export const STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: '未构建',
  unpublished: '未发布',
  online: '在线',
  paused: '暂停',
};

export const STATUS_TONE: Record<
  ProjectStatus,
  { badge: string; dot: string; text: string }
> = {
  draft: {
    badge: 'bg-line-4 text-ink-55',
    dot: 'bg-ink-30',
    text: 'text-ink-55',
  },
  unpublished: {
    badge: 'bg-line-4 text-ink-55',
    dot: 'bg-ink-30',
    text: 'text-ink-55',
  },
  online: {
    badge: 'bg-positive/10 text-positive',
    dot: 'bg-positive',
    text: 'text-positive',
  },
  paused: {
    badge: 'bg-warning/10 text-warning',
    dot: 'bg-warning',
    text: 'text-warning',
  },
};

/** 暂停 / 恢复按钮共用状态色，避免概览与发布弹窗各写一套。 */
export const PAUSE_ACTION_CLASS =
  'border-warning/30 bg-white text-warning hover:border-warning/60 hover:bg-warning/10';

export const RESUME_ACTION_CLASS =
  'border-positive bg-positive text-white hover:bg-positive/90';

export const RESUME_OUTLINE_CLASS =
  'border-positive/30 bg-white text-positive hover:border-positive/60 hover:bg-positive/10';

/** Fall back to the persisted versions if an older response omits status. */
export function projectStatus(project: StatusFields): ProjectStatus {
  if (project.status) return project.status;
  if (project.built_version == null) return 'draft';
  if (project.published_version == null) return 'unpublished';
  return project.paused ? 'paused' : 'online';
}

export function statusLabel(project: StatusFields): string {
  return STATUS_LABEL[projectStatus(project)];
}

export function absoluteUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  try {
    return new URL(path, window.location.origin).toString();
  } catch {
    return null;
  }
}

export const PROJECT_MODES: ProjectMode[] = ['frontend', 'fullstack', 'backend'];

const COVERS = [
  'linear-gradient(135deg,#EEF3FF,#D9E3FF)',
  'linear-gradient(135deg,#FFF4E8,#FFE2C7)',
  'linear-gradient(135deg,#EAF7EF,#D3EFDF)',
  'linear-gradient(135deg,#F3EEFF,#E3D6FF)',
  'linear-gradient(135deg,#FFF0F4,#FFDCE7)',
  'linear-gradient(135deg,#FFF8DC,#FFEDB5)',
];

export function coverFor(id: string): string {
  let hash = 0;
  for (let index = 0; index < id.length; index += 1)
    hash = (hash * 31 + id.charCodeAt(index)) >>> 0;
  return COVERS[hash % COVERS.length];
}

export function projectMode(project: ProjectSummary): ProjectMode {
  return project.mode ?? 'frontend';
}

export function modeLabel(project: ProjectSummary): string {
  return MODE_LABEL[projectMode(project)] ?? '前端';
}
