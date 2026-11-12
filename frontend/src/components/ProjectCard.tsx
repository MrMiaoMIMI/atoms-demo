import type { MouseEvent as ReactMouseEvent } from 'react';
import { timeAgo } from '../lib/format';
import { coverFor, modeLabel } from '../lib/projects';
import type { ProjectSummary } from '../types';
import { AtomsMark, Spinner, Trash } from './Icons';

export function ProjectCover({ project }: { project: ProjectSummary }) {
  const badge = (
    <div className="absolute bottom-6 left-6 flex items-center gap-1.5 rounded-full bg-white/85 px-2.5 py-1 text-[11px] font-medium text-ink-80 shadow-sm backdrop-blur">
      <AtomsMark size={12} className="text-brand" />
      {modeLabel(project)} · v{project.latest_version ?? 0}
    </div>
  );

  if (project.mode === 'backend') {
    return (
      <div className="absolute inset-0 p-4 sm:p-5">
        <div className="flex h-full w-full flex-col overflow-hidden rounded-[8px] border border-white/70 bg-[#17171A] shadow-[0_10px_24px_-18px_rgba(12,12,12,0.35)]">
          <div className="flex h-[22px] flex-none items-center gap-1 border-b border-white/10 px-2">
            <span className="h-1.5 w-1.5 rounded-full bg-white/20" />
            <span className="h-1.5 w-1.5 rounded-full bg-white/20" />
            <span className="h-1.5 w-1.5 rounded-full bg-white/20" />
            <span className="ml-1 h-2 w-16 rounded-full bg-white/10" />
          </div>
          <div className="space-y-1.5 p-3 font-mono text-[7.5px] leading-[12px] text-white/55">
            <div>
              <span className="text-[#92E2AC]">GET</span> /api/transactions
            </div>
            <div>
              <span className="text-[#92E2AC]">POST</span> /api/transactions
            </div>
            <div>
              <span className="text-[#FFBA6C]">PUT</span> /api/transactions/:id
            </div>
            <div>
              <span className="text-[#F68987]">DELETE</span>{' '}
              /api/transactions/:id
            </div>
            <div className="mt-2 rounded bg-white/[0.06] p-2 text-[6.5px] text-white/35">
              {'{ "ok": true, "count": 12 }'}
            </div>
          </div>
        </div>
        {badge}
      </div>
    );
  }

  return (
    <div className="absolute inset-0 p-4 sm:p-5">
      <div className="flex h-full w-full flex-col overflow-hidden rounded-[8px] border border-white/70 bg-white/90 shadow-[0_10px_24px_-18px_rgba(12,12,12,0.35)]">
        <div className="flex h-[22px] flex-none items-center gap-1 border-b border-line-4 px-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[#F0A2A2]" />
          <span className="h-1.5 w-1.5 rounded-full bg-[#F2D08C]" />
          <span className="h-1.5 w-1.5 rounded-full bg-[#A7D7B6]" />
          <span className="ml-1 h-2 w-16 rounded-full bg-line-6" />
        </div>
        <div className="flex min-h-0 flex-1">
          <div className="w-[26%] flex-none space-y-1.5 border-r border-line-4 p-2">
            <div className="h-2 w-3/4 rounded-full bg-line-12" />
            <div className="h-2 w-1/2 rounded-full bg-line-6" />
            <div className="h-2 w-2/3 rounded-full bg-line-6" />
            <div className="h-2 w-1/2 rounded-full bg-line-4" />
          </div>
          <div className="flex-1 space-y-2 p-2.5">
            <div className="h-2.5 w-1/2 rounded-full bg-line-12" />
            <div className="h-1.5 w-4/5 rounded-full bg-line-6" />
            <div className="h-1.5 w-3/5 rounded-full bg-line-4" />
            <div className="mt-2 h-[46%] rounded-[6px] bg-gradient-to-br from-white to-line-4" />
          </div>
        </div>
      </div>
      {badge}
    </div>
  );
}

interface ProjectCardProps {
  project: ProjectSummary;
  onOpen: (id: string) => void;
  onDelete?: (event: ReactMouseEvent, id: string) => void;
  deleting?: boolean;
}

export default function ProjectCard({
  project,
  onOpen,
  onDelete,
  deleting = false,
}: ProjectCardProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(project.id)}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') onOpen(project.id);
      }}
      className="group cursor-pointer text-left"
    >
      <div
        className="relative aspect-[16/10] overflow-hidden rounded-[12px] border border-line-4 transition group-hover:border-line-8"
        style={{ background: coverFor(project.id) }}
      >
        <ProjectCover project={project} />
        {onDelete ? (
          <button
            type="button"
            title="删除项目"
            onClick={(event) => onDelete(event, project.id)}
            disabled={deleting}
            className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-lg bg-white/90 text-ink-55 opacity-0 shadow-sm transition hover:bg-white hover:text-danger group-hover:opacity-100 focus-visible:opacity-100 disabled:opacity-40"
          >
            {deleting ? <Spinner size={13} /> : <Trash size={14} />}
          </button>
        ) : null}
      </div>
      <div className="mt-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-[14px] font-medium text-ink-95">
            {project.name}
          </h3>
          <p className="mt-1 truncate text-[12px] text-ink-55">
            {project.message_count} 条对话 · {project.artifact_count} 个文件 ·{' '}
            {timeAgo(project.created_at)}
          </p>
        </div>
        <span className="flex-none rounded-full bg-line-4 px-2 py-0.5 text-[10px] text-ink-55">
          {modeLabel(project)}
        </span>
      </div>
    </div>
  );
}
