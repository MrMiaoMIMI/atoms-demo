import type { MouseEvent as ReactMouseEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { contentMaxWidth } from '../lib/layout';
import { PROJECT_MODES, MODE_LABEL, projectMode } from '../lib/projects';
import type { AuthUser, Health, ProjectMode, ProjectSummary } from '../types';
import CardGrid from './CardGrid';
import HomeSidebar, { CollapsedSidebar } from './HomeSidebar';
import { Code, Plus, Search, X } from './Icons';
import ProjectCard from './ProjectCard';
import Tabs, { type TabItem } from './Tabs';

type ModeFilter = ProjectMode | 'all';

const MODE_TABS: TabItem<ModeFilter>[] = [
  { value: 'all', label: '全部' },
  ...PROJECT_MODES.map((value) => ({ value, label: MODE_LABEL[value] })),
];

interface Props {
  health: Health | null;
  sidebarProjects: ProjectSummary[];
  sidebarCollapsed: boolean;
  user: AuthUser;
  onSidebarCollapsed: (collapsed: boolean) => void;
  onHome: () => void;
  onDiscover: () => void;
  onNewProject: () => void;
  onOpenProject: (id: string) => void;
  onLogout: () => void;
}

export default function ProjectsPage({
  health,
  sidebarProjects,
  sidebarCollapsed,
  user,
  onSidebarCollapsed,
  onHome,
  onDiscover,
  onNewProject,
  onOpenProject,
  onLogout,
}: Props) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<ModeFilter>('all');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listProjects()
      .then((items) => {
        if (!cancelled) {
          setProjects(items);
          setError(null);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || '项目列表加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Keep counts, cover thumbnails and generating state in sync with the shell
  // poll while the page is open.
  useEffect(() => {
    if (sidebarProjects.length) setProjects(sidebarProjects);
  }, [sidebarProjects]);

  const counts = useMemo(() => {
    const next: Record<ModeFilter, number> = {
      all: projects.length,
      frontend: 0,
      fullstack: 0,
      backend: 0,
    };
    for (const project of projects) next[projectMode(project)] += 1;
    return next;
  }, [projects]);

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return projects.filter((project) => {
      if (mode !== 'all' && projectMode(project) !== mode) return false;
      if (!keyword) return true;
      return project.name.toLowerCase().includes(keyword);
    });
  }, [projects, mode, query]);

  async function removeProject(event: ReactMouseEvent, id: string) {
    event.stopPropagation();
    if (!window.confirm('删除这个项目？该操作不可恢复。')) return;
    setDeleting(id);
    setError(null);
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setError((err as Error).message || '删除失败');
    } finally {
      setDeleting(null);
    }
  }

  function resetFilters() {
    setQuery('');
    setMode('all');
  }

  const filtering = mode !== 'all' || query.trim().length > 0;

  return (
    <div className="flex h-full overflow-hidden bg-base">
      {sidebarCollapsed ? (
        <CollapsedSidebar
          health={health}
          section="projects"
          user={user}
          onHome={onHome}
          onDiscover={onDiscover}
          onProjects={() => undefined}
          onExpand={() => onSidebarCollapsed(false)}
        />
      ) : (
        <HomeSidebar
          projects={sidebarProjects}
          section="projects"
          user={user}
          onHome={onHome}
          onDiscover={onDiscover}
          onProjects={() => undefined}
          onOpenProject={onOpenProject}
          onCollapse={() => onSidebarCollapsed(true)}
          onLogout={onLogout}
        />
      )}

      <main className="min-w-0 flex-1 overflow-y-auto bg-base">
        <div
          className="mx-auto w-full px-6 py-8 sm:px-8"
          style={{ maxWidth: contentMaxWidth(sidebarCollapsed, 1100) }}
        >
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-[24px] font-medium leading-[32px] tracking-[-0.3px] text-ink-95">
                项目
              </h1>
              <p className="mt-1 text-[13px] text-ink-55">
                所有生成的应用都会自动保存在这里，刷新或重启都不会丢失。
              </p>
            </div>
            <button
              type="button"
              onClick={onNewProject}
              className="inline-flex h-9 flex-none items-center gap-1.5 rounded-full bg-brand px-4 text-[13px] font-medium text-white transition hover:bg-brand-600"
            >
              <Plus size={16} />
              新建项目
            </button>
          </header>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <Tabs
              items={MODE_TABS.map((item) => ({
                ...item,
                count: counts[item.value],
              }))}
              value={mode}
              onChange={setMode}
              className="flex-wrap"
            />

            <div className="relative w-full sm:w-[240px]">
              <Search
                size={15}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-30"
              />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索项目"
                className="h-9 w-full rounded-full border border-line-8 bg-white pl-9 pr-9 text-[13px] text-ink-95 outline-none transition placeholder:text-ink-30 focus:border-line-12"
              />
              {query ? (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  title="清空搜索"
                  className="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full text-ink-30 transition hover:bg-line-4 hover:text-ink-55"
                >
                  <X size={13} />
                </button>
              ) : null}
            </div>
          </div>

          {error ? (
            <p className="mt-4 rounded-xl border border-danger/20 bg-danger/5 px-3 py-2 text-[12px] text-danger">
              {error}
            </p>
          ) : null}

          <div className="mt-7 flex items-center justify-between gap-3">
            <h2 className="text-[14px] font-medium text-ink-95">
              {filtering ? '筛选结果' : '全部项目'}
            </h2>
            <span className="text-[12px] text-ink-55">
              共 {filtered.length} 个
            </span>
          </div>

          <div className="mt-4 pb-10">
            {loading ? (
              <CardGrid collapsed={sidebarCollapsed}>
                {[0, 1, 2, 3, 4, 5, 6, 7].map((index) => (
                  <div key={index} className="animate-pulse">
                    <div className="aspect-[16/10] rounded-xl bg-line-4" />
                    <div className="mt-3 h-3 w-2/3 rounded-full bg-line-4" />
                    <div className="mt-2 h-2 w-1/2 rounded-full bg-line-2" />
                  </div>
                ))}
              </CardGrid>
            ) : projects.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-[20px] border border-dashed border-line-8 bg-white/60 px-6 py-20 text-center">
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-line-4 text-ink-55">
                  <Code size={22} />
                </span>
                <p className="mt-4 text-[15px] font-medium text-ink-95">
                  还没有项目
                </p>
                <p className="mt-1.5 max-w-[320px] text-[13px] leading-[20px] text-ink-55">
                  用一句话描述你的想法，Mike、Bob 和 Alex 会把它变成一个可运行的应用。
                </p>
                <button
                  type="button"
                  onClick={onNewProject}
                  className="mt-5 inline-flex h-9 items-center gap-1.5 rounded-full bg-brand px-4 text-[13px] font-medium text-white transition hover:bg-brand-600"
                >
                  <Plus size={15} />
                  开始构建
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-[20px] border border-dashed border-line-8 px-6 py-16 text-center">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-line-4 text-ink-55">
                  <Search size={20} />
                </span>
                <p className="mt-3 text-[14px] font-medium text-ink-95">
                  没有匹配的项目
                </p>
                <p className="mt-1 text-[12px] text-ink-55">
                  换个关键词，或者清除当前筛选条件。
                </p>
                <button
                  type="button"
                  onClick={resetFilters}
                  className="mt-4 inline-flex h-8 items-center rounded-full border border-line-8 bg-white px-4 text-[13px] text-ink-80 transition hover:border-line-12 hover:text-ink-95"
                >
                  清除筛选
                </button>
              </div>
            ) : (
              <CardGrid collapsed={sidebarCollapsed}>
                {filtered.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    onOpen={onOpenProject}
                    onDelete={removeProject}
                    deleting={deleting === project.id}
                  />
                ))}
              </CardGrid>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
