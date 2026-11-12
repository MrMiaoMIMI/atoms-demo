import type { ProjectMode, ProjectSummary } from '../types';

export const MODE_LABEL: Record<string, string> = {
  frontend: '前端',
  fullstack: '全栈',
  backend: 'API',
};

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
