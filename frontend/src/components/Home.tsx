import type { FormEvent, MouseEvent as ReactMouseEvent } from 'react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { Health, ProjectSummary } from '../types';
import { AgentRail } from './Avatar';
import HomeSidebar, { CollapsedSidebar } from './HomeSidebar';
import MentionComposer from './MentionComposer';
import ProjectCard from './ProjectCard';
import {
  ApiIcon,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  Code,
  ListTree,
  Plus,
  Sparkle,
  Spinner,
  X,
} from './Icons';

interface Template {
  id: string;
  title: string;
  desc: string;
  prompt: string;
  emoji: string;
  cover: string;
  mode: string;
  icon: 'page' | 'list' | 'api';
}

const TEMPLATES: Template[] = [
  {
    id: 'todo',
    title: '极简待办清单',
    desc: '任务新增、完成与 SQLite 持久化',
    prompt:
      '做一个极简待办清单，任务保存到 SQLite，刷新不丢，支持新增、完成和删除。',
    emoji: '✅',
    cover: 'linear-gradient(135deg,#EEF3FF,#D9E3FF)',
    mode: '全栈',
    icon: 'list',
  },
  {
    id: 'saas',
    title: 'SaaS 产品落地页',
    desc: 'Hero、功能、定价与行动按钮',
    prompt:
      '做一个 SaaS 产品落地页，包含 Hero、功能、价格和行动按钮，风格简洁现代。',
    emoji: '🚀',
    cover: 'linear-gradient(135deg,#FFF4E8,#FFE2C7)',
    mode: '前端',
    icon: 'page',
  },
  {
    id: 'notes',
    title: '个人笔记应用',
    desc: 'Markdown 笔记与全文搜索',
    prompt:
      '做一个个人笔记应用，支持新增、编辑、搜索和删除笔记，数据保存到 SQLite。',
    emoji: '📝',
    cover: 'linear-gradient(135deg,#EAF7EF,#D3EFDF)',
    mode: '全栈',
    icon: 'list',
  },
  {
    id: 'dashboard',
    title: '数据看板',
    desc: '指标卡片、趋势图和筛选器',
    prompt:
      '做一个数据看板，包含指标卡片、趋势图和筛选器，数据从 SQLite 读取。',
    emoji: '📊',
    cover: 'linear-gradient(135deg,#F3EEFF,#E3D6FF)',
    mode: '全栈',
    icon: 'page',
  },
  {
    id: 'ledger',
    title: '记账 API',
    desc: 'REST 接口与 SQLite 数据库',
    prompt:
      '做一个记账 API（只要后端），支持新增、查询、删除账单，数据保存到 SQLite。',
    emoji: '🧾',
    cover: 'linear-gradient(135deg,#FFF0F4,#FFDCE7)',
    mode: 'API',
    icon: 'api',
  },
  {
    id: 'shop',
    title: '电商商品页',
    desc: '商品列表、分类与购物车',
    prompt:
      '做一个电商商品列表页，包含搜索、分类和购物车，数据来自后端 SQLite。',
    emoji: '🛍️',
    cover: 'linear-gradient(135deg,#FFF8DC,#FFEDB5)',
    mode: '全栈',
    icon: 'page',
  },
];

const SHORTCUTS = [
  {
    label: '待办清单',
    prompt: '做一个极简待办清单，任务保存到 SQLite，刷新不丢。',
    icon: <ListTree size={14} />,
  },
  {
    label: 'SaaS 落地页',
    prompt: '做一个 SaaS 产品落地页，包含 Hero、功能、价格和行动按钮。',
    icon: <Sparkle size={14} />,
  },
  {
    label: '记账 API',
    prompt:
      '做一个记账 API（只要后端），支持新增、查询、删除账单，数据保存到 SQLite。',
    icon: <ApiIcon size={14} />,
  },
];

function TemplatePreview({ template }: { template: Template }) {
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
          <div className="flex w-[26%] flex-none flex-col items-center gap-2 border-r border-line-4 py-3">
            <span
              className="grid h-7 w-7 place-items-center rounded-[7px] text-[15px]"
              style={{ background: template.cover }}
            >
              {template.emoji}
            </span>
            <span className="h-1.5 w-8 rounded-full bg-line-8" />
            <span className="h-1.5 w-6 rounded-full bg-line-4" />
            <span className="h-1.5 w-7 rounded-full bg-line-4" />
          </div>
          <div className="flex-1 p-3">
            <div className="flex items-center justify-between">
              <span className="h-2 w-16 rounded-full bg-line-12" />
              <span className="h-4 w-9 rounded-full bg-line-4" />
            </div>
            <div className="mt-3 h-2.5 w-3/4 rounded-full bg-line-12" />
            <div className="mt-1.5 h-1.5 w-1/2 rounded-full bg-line-6" />
            <div className="mt-3 grid grid-cols-3 gap-1.5">
              <span className="h-10 rounded-[5px] bg-line-4" />
              <span className="h-10 rounded-[5px] bg-line-4" />
              <span className="h-10 rounded-[5px] bg-line-2" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface HomeProps {
  health: Health | null;
  sidebarProjects: ProjectSummary[];
  sidebarCollapsed: boolean;
  onSidebarCollapsed: (collapsed: boolean) => void;
  onStart: (projectId: string, prompt: string) => void;
  onOpen: (projectId: string) => void;
  onBrowseAllProjects: () => void;
}

type Tab = 'projects' | 'templates';

const BANNER_KEY = 'atoms.home.banner.dismissed';

function readBannerVisible(): boolean {
  try {
    return window.localStorage.getItem(BANNER_KEY) !== '1';
  } catch {
    return true;
  }
}

export default function Home({
  health,
  sidebarProjects,
  sidebarCollapsed,
  onSidebarCollapsed,
  onStart,
  onOpen,
  onBrowseAllProjects,
}: HomeProps) {
  const [prompt, setPrompt] = useState('');
  const [creating, setCreating] = useState(false);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('projects');
  const [banner, setBanner] = useState(readBannerVisible);
  const [connector, setConnector] = useState(true);
  const [plusOpen, setPlusOpen] = useState(false);
  const [buildOpen, setBuildOpen] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const composerRef = useRef<HTMLDivElement>(null);
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listProjects()
      .then((items) => {
        if (!cancelled) setProjects(items);
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

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setPlusOpen(false);
      setBuildOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function focusComposer(text?: string) {
    if (text !== undefined) setPrompt(text);
    mainRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    window.setTimeout(() => {
      textareaRef.current?.focus();
      composerRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }, 80);
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = prompt.trim();
    if (!text || creating) return;
    setCreating(true);
    setError(null);
    try {
      const project = await api.createProject(text);
      onStart(project.id, text);
    } catch (err) {
      setError((err as Error).message || '创建项目失败');
      setCreating(false);
    }
  }

  async function removeProject(event: ReactMouseEvent, id: string) {
    event.stopPropagation();
    if (!window.confirm('删除这个项目？该操作不可恢复。')) return;
    setDeleting(id);
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      setError((err as Error).message || '删除失败');
    } finally {
      setDeleting(null);
    }
  }

  function goHomeContent() {
    setTab('projects');
    mainRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function dismissBanner() {
    setBanner(false);
    try {
      window.localStorage.setItem(BANNER_KEY, '1');
    } catch {
      // Storage can be unavailable (private mode); closing still works this session.
    }
  }

  const statusText = health
    ? health.ok
      ? health.llm_mode === 'mock'
        ? 'Mock 模式'
        : health.model + ' : $99' || '服务在线'
      : '服务离线'
    : '连接中';

  return (
    <div className="flex h-full overflow-hidden bg-base">
      {sidebarCollapsed ? (
        <CollapsedSidebar
          health={health}
          section="home"
          onHome={goHomeContent}
          onProjects={onBrowseAllProjects}
          onExpand={() => onSidebarCollapsed(false)}
        />
      ) : (
        <HomeSidebar
          projects={sidebarProjects}
          section="home"
          onHome={goHomeContent}
          onProjects={onBrowseAllProjects}
          onOpenProject={onOpen}
          onCollapse={() => onSidebarCollapsed(true)}
        />
      )}

      <main
        ref={mainRef}
        className="relative min-w-0 flex-1 overflow-y-auto bg-base"
      >
        {banner ? (
          <div className="relative flex h-10 flex-none items-center justify-center bg-[#DCE4FF] px-10 text-[14px] text-[#212675]">
            <span className="hidden font-medium sm:inline">
              让 Atoms 把你的想法变成可运行的作品。
            </span>
            <button
              type="button"
              onClick={() => focusComposer()}
              className="ml-0 inline-flex h-6 items-center gap-1 rounded-full bg-brand px-3 text-[12px] font-medium text-white transition hover:bg-brand-600 sm:ml-3"
            >
              立即开始
              <ArrowUp size={12} />
            </button>
            <button
              type="button"
              onClick={dismissBanner}
              title="关闭横幅"
              className="absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-md text-[#212675]/70 transition hover:bg-white/40"
            >
              <X size={15} />
            </button>
          </div>
        ) : null}

        <div className="relative min-h-[calc(100%-40px)]">
          <div className="absolute right-4 top-3 z-10">
            <div className="inline-flex h-8 items-center gap-1.5 rounded-full border border-line-12 bg-base px-4 text-[14px] font-medium text-ink-95">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  health
                    ? health.ok
                      ? 'bg-positive'
                      : 'bg-ink-30'
                    : 'animate-pulse-soft bg-ink-30'
                }`}
              />
              {statusText}
            </div>
          </div>

          <div
            ref={composerRef}
            className="mx-auto flex w-full max-w-[1164px] flex-col items-center px-6 pb-4 pt-4 sm:pb-4 sm:pt-4"
          >
            <span className="inline-flex h-8 items-center gap-2 rounded-full bg-line-4 px-4 text-[14px] text-ink-55">
              本地演示
              <span className="text-ink-30">·</span>
              无需登录
            </span>

            <AgentRail size={46} className="mt-7" />

            <h1 className="mt-4 text-balance text-center font-serif text-[32px] font-medium leading-[42px] tracking-[-0.5px] text-ink-95 sm:text-[36px] sm:leading-[44px]">
              你的下一个产品从这里开始。
            </h1>

            <form onSubmit={submit} className="mt-6 w-full max-w-[720px]">
              <div className="rounded-[24px] border border-line-12 bg-white shadow-composer">
                <div className="px-4 pb-3 pt-4">
                  <MentionComposer
                    value={prompt}
                    onChange={setPrompt}
                    onSubmit={() => void submit()}
                    textareaRef={textareaRef}
                    rows={2}
                    maxLength={4000}
                    maxHeight={180}
                    disabled={creating}
                    placeholder="让智能体团队实现你的想法，输入 @ 指定 Mike / Bob / Alex…"
                    className="max-h-[180px] min-h-[58px] w-full resize-none bg-transparent px-1 text-[15px] leading-[24px] text-ink-95 outline-none placeholder:text-ink-30"
                  />

                  <div className="mt-2 flex items-center justify-between gap-2">
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setPlusOpen((value) => !value)}
                        title="从示例开始"
                        className="relative grid h-8 w-8 place-items-center rounded-full text-ink-80 transition hover:bg-line-4"
                      >
                        <Plus size={20} />
                        <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-[#FF5A5F]" />
                      </button>
                      {plusOpen ? (
                        <>
                          <button
                            type="button"
                            aria-hidden="true"
                            className="fixed inset-0 z-20 cursor-default"
                            onClick={() => setPlusOpen(false)}
                          />
                          <div className="absolute bottom-full left-0 z-30 mb-2 w-[250px] rounded-xl border border-line-6 bg-white p-2 shadow-float">
                            <p className="px-2 py-1 text-[12px] text-ink-55">
                              从示例开始
                            </p>
                            {SHORTCUTS.map((item) => (
                              <button
                                key={item.label}
                                type="button"
                                onClick={() => {
                                  setPlusOpen(false);
                                  focusComposer(item.prompt);
                                }}
                                className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
                              >
                                <span className="text-ink-55">{item.icon}</span>
                                {item.label}
                              </button>
                            ))}
                          </div>
                        </>
                      ) : null}
                    </div>

                    <div className="flex items-center gap-2">
                      <div className="relative">
                        <button
                          type="button"
                          onClick={() => setBuildOpen((value) => !value)}
                          className="inline-flex h-8 items-center gap-1 rounded-full border border-line-6 px-3 text-[14px] text-ink-80 transition hover:border-line-12 hover:text-ink-95"
                        >
                          构建
                          <ChevronDown size={14} />
                        </button>
                        {buildOpen ? (
                          <>
                            <button
                              type="button"
                              aria-hidden="true"
                              className="fixed inset-0 z-20 cursor-default"
                              onClick={() => setBuildOpen(false)}
                            />
                            <div className="absolute bottom-full right-0 z-30 mb-2 w-[270px] rounded-xl border border-line-6 bg-white p-3 shadow-float">
                              <p className="text-[13px] font-medium text-ink-95">
                                自动选择项目形态
                              </p>
                              <p className="mt-1.5 text-[12px] leading-[19px] text-ink-55">
                                Mike 会判断需求复杂度，再交给 Bob 设计架构或由
                                Alex 直接 实现；自动准备 Vite / FastAPI / SQLite
                                脚手架。
                              </p>
                              <div className="mt-2.5 flex flex-wrap gap-1.5">
                                {['前端', '全栈', 'API'].map((mode) => (
                                  <span
                                    key={mode}
                                    className="rounded-full bg-line-4 px-2 py-0.5 text-[11px] text-ink-55"
                                  >
                                    {mode}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </>
                        ) : null}
                      </div>

                      <button
                        type="submit"
                        disabled={!prompt.trim() || creating}
                        title="生成应用"
                        className="grid h-8 w-8 place-items-center rounded-full bg-brand text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-line-12 disabled:text-ink-30"
                      >
                        {creating ? (
                          <Spinner size={16} />
                        ) : (
                          <ArrowUp size={17} />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {connector ? (
                  <div className="flex items-center justify-between gap-3 rounded-b-[23px] border-t border-line-2 bg-[rgba(12,12,12,0.02)] px-4 py-3">
                    <div className="flex min-w-0 items-center gap-2 text-[13px] text-ink-55">
                      <Sparkle size={15} className="flex-none text-brand" />
                      <span className="truncate">
                        自动识别形态 · 项目独立 · iframe 实时预览
                      </span>
                    </div>
                    <div className="flex flex-none items-center gap-2 text-[11px] text-ink-55">
                      <span className="rounded border border-line-6 px-1.5 py-0.5 text-[10px]">
                        Web
                      </span>
                      <span className="rounded border border-line-6 px-1.5 py-0.5 text-[10px]">
                        API
                      </span>
                      <button
                        type="button"
                        onClick={() => setConnector(false)}
                        title="收起"
                        className="grid h-5 w-5 place-items-center rounded text-ink-30 transition hover:bg-line-6 hover:text-ink-55"
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>

              {error ? (
                <p className="mt-3 rounded-xl border border-danger/20 bg-danger/5 px-3 py-2 text-center text-[12px] text-danger">
                  {error}
                </p>
              ) : null}
            </form>
          </div>

          <section className="mx-auto mb-12 w-full max-w-[1100px] rounded-[24px] border border-line-4 bg-white p-6 shadow-panel sm:p-8">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-1">
                {(
                  [
                    ['projects', '项目'],
                    ['templates', '模板'],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setTab(value)}
                    className={`h-8 rounded-full px-4 text-[14px] transition ${
                      tab === value
                        ? 'bg-line-6 text-ink-95'
                        : 'text-ink-55 hover:text-ink-80'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tab === 'projects' ? (
                <button
                  type="button"
                  onClick={onBrowseAllProjects}
                  className="inline-flex items-center gap-0.5 text-[14px] text-ink-55 transition hover:text-ink-95"
                >
                  查看全部
                  <ChevronRight size={15} />
                </button>
              ) : null}
            </div>

            <div className="mt-6">
              {tab === 'projects' ? (
                loading ? (
                  <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {[0, 1, 2].map((index) => (
                      <div key={index} className="animate-pulse">
                        <div className="aspect-[16/10] rounded-xl bg-line-4" />
                        <div className="mt-3 h-3 w-2/3 rounded-full bg-line-4" />
                        <div className="mt-2 h-2 w-1/2 rounded-full bg-line-2" />
                      </div>
                    ))}
                  </div>
                ) : projects.length === 0 ? (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line-8 px-6 py-16 text-center">
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-line-4 text-ink-55">
                      <Code size={20} />
                    </span>
                    <p className="mt-3 text-[14px] font-medium text-ink-95">
                      还没有项目
                    </p>
                    <p className="mt-1 text-[12px] text-ink-55">
                      从上面的输入框开始你的第一个应用。
                    </p>
                    <button
                      type="button"
                      onClick={() => focusComposer()}
                      className="mt-4 inline-flex h-8 items-center gap-1.5 rounded-full bg-brand px-4 text-[13px] font-medium text-white transition hover:bg-brand-600"
                    >
                      <Plus size={15} />
                      开始构建
                    </button>
                  </div>
                ) : (
                  <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {projects.map((project) => (
                      <ProjectCard
                        key={project.id}
                        project={project}
                        onOpen={onOpen}
                        onDelete={removeProject}
                        deleting={deleting === project.id}
                      />
                    ))}
                  </div>
                )
              ) : (
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {TEMPLATES.map((template) => (
                    <button
                      key={template.id}
                      type="button"
                      onClick={() => focusComposer(template.prompt)}
                      className="group text-left"
                    >
                      <div
                        className="relative aspect-[16/10] overflow-hidden rounded-[12px] border border-line-4 transition group-hover:border-line-8"
                        style={{ background: template.cover }}
                      >
                        <TemplatePreview template={template} />
                        <div className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium text-ink-55 backdrop-blur">
                          {template.mode}
                        </div>
                        <div className="absolute bottom-3 right-3 rounded-full bg-white/85 px-2.5 py-1 text-[11px] font-medium text-ink-80 opacity-0 shadow-sm backdrop-blur transition group-hover:opacity-100">
                          使用模板
                        </div>
                      </div>
                      <h3 className="mt-3 text-[14px] font-medium text-ink-95">
                        {template.title}
                      </h3>
                      <p className="mt-1 line-clamp-1 text-[12px] text-ink-55">
                        {template.desc}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
