import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { copyText } from "../lib/clipboard";
import {
  formatCount,
  formatPublishedDate,
} from "../lib/discover";
import { contentMaxWidth } from "../lib/layout";
import { MODE_LABEL } from "../lib/projects";
import type {
  AuthUser,
  DiscoverDetail,
  Health,
  ProjectSummary,
} from "../types";
import { InitialAvatar } from "./Avatar";
import CardGrid from "./CardGrid";
import DiscoverCard from "./DiscoverCard";
import HomeSidebar, { CollapsedSidebar } from "./HomeSidebar";
import {
  Bookmark,
  BookmarkFill,
  Check,
  ChevronRight,
  Copy,
  ExternalLink,
  Eye,
  Spinner,
} from "./Icons";

interface Props {
  projectId: string;
  health: Health | null;
  sidebarProjects: ProjectSummary[];
  sidebarCollapsed: boolean;
  user: AuthUser;
  onSidebarCollapsed: (collapsed: boolean) => void;
  onHome: () => void;
  onDiscover: () => void;
  onProjects: () => void;
  onOpenProject: (id: string) => void;
  onOpenDiscoverApp: (id: string) => void;
  onLogout: () => void;
}

export default function DiscoverDetailPage({
  projectId,
  health,
  sidebarProjects,
  sidebarCollapsed,
  user,
  onSidebarCollapsed,
  onHome,
  onDiscover,
  onProjects,
  onOpenProject,
  onOpenDiscoverApp,
  onLogout,
}: Props) {
  const [app, setApp] = useState<DiscoverDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [frameLoaded, setFrameLoaded] = useState(false);
  const viewSent = useRef(false);

  const own = sidebarProjects.some((project) => project.id === projectId);

  // A user's own app belongs in the workspace, not in discover. Redirect
  // before the detail request so the discover page never renders it.
  useEffect(() => {
    if (own) onOpenProject(projectId);
  }, [own, projectId, onOpenProject]);

  useEffect(() => {
    if (own) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setApp(null);
    setSaved(false);
    setFrameLoaded(false);
    viewSent.current = false;
    api
      .discoverDetail(projectId)
      .then((detail) => {
        if (cancelled) return;
        setApp(detail);
        setSaved(detail.saved);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || "应用加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, own]);

  // Count each visit. The ref only suppresses React StrictMode's double effect
  // on the same mount; navigating away and back remounts the page and counts
  // again.
  useEffect(() => {
    const id = app?.id;
    if (!id || viewSent.current) return;
    viewSent.current = true;
    api
      .recordDiscoverView(id)
      .then((result) => {
        setApp((current) =>
          current ? { ...current, view_count: result.view_count } : current
        );
      })
      .catch(() => {
        // A failed analytics call should never surface to the viewer.
      });
  }, [app?.id]);

  useEffect(() => {
    if (app) document.title = `${app.name} · 发现 · Atoms`;
  }, [app?.name]);

  const publicUrl = app
    ? new URL(app.published_url, window.location.origin).toString()
    : "";
  const ownIds = new Set(sidebarProjects.map((project) => project.id));
  const relatedApps = app
    ? app.related.filter((item) => !ownIds.has(item.id))
    : [];

  async function copyLink() {
    if (!publicUrl) return;
    if (await copyText(publicUrl)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }

  function openApp() {
    if (!publicUrl) return;
    window.open(publicUrl, "_blank", "noopener,noreferrer");
  }

  async function toggleSave() {
    if (!app || saving) return;
    setSaving(true);
    setActionError(null);
    try {
      if (saved) {
        await api.unsaveDiscover(app.id);
        setSaved(false);
      } else {
        await api.saveDiscover(app.id);
        setSaved(true);
      }
    } catch (err) {
      setActionError((err as Error).message || "收藏操作失败");
    } finally {
      setSaving(false);
    }
  }

  const sidebar = sidebarCollapsed ? (
    <CollapsedSidebar
      health={health}
      section="discover"
      user={user}
      onHome={onHome}
      onDiscover={onDiscover}
      onProjects={onProjects}
      onExpand={() => onSidebarCollapsed(false)}
    />
  ) : (
    <HomeSidebar
      projects={sidebarProjects}
      section="discover"
      user={user}
      onHome={onHome}
      onDiscover={onDiscover}
      onProjects={onProjects}
      onOpenProject={onOpenProject}
      onCollapse={() => onSidebarCollapsed(true)}
      onLogout={onLogout}
    />
  );

  if (own) {
    return (
      <div className="flex h-full overflow-hidden bg-base">
        {sidebar}
        <main className="grid min-w-0 flex-1 place-items-center bg-base">
          <div className="flex items-center gap-2 text-[13px] text-ink-55">
            <Spinner size={16} className="text-brand" />
            正在打开你的项目…
          </div>
        </main>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full overflow-hidden bg-base">
        {sidebar}
        <main className="min-w-0 flex-1 overflow-y-auto bg-base">
          <div
            className="mx-auto w-full animate-pulse px-6 py-8 sm:px-8"
            style={{ maxWidth: contentMaxWidth(sidebarCollapsed, 1100) }}
          >
            <div className="h-3 w-40 rounded-full bg-line-4" />
            <div className="mt-5 h-8 w-2/3 rounded-lg bg-line-4" />
            <div className="mt-6 aspect-[16/9] rounded-[12px] bg-line-4" />
            <div className="mt-6 h-3 w-1/2 rounded-full bg-line-2" />
          </div>
        </main>
      </div>
    );
  }

  if (error || !app) {
    return (
      <div className="flex h-full overflow-hidden bg-base">
        {sidebar}
        <main className="grid min-w-0 flex-1 place-items-center bg-base px-6">
          <div className="w-full max-w-sm rounded-2xl border border-line-6 bg-white p-6 text-center shadow-composer">
            <p className="text-[14px] font-medium text-ink-95">
              应用不存在或已下线
            </p>
            <p className="mt-2 text-[12px] leading-[19px] text-ink-55">
              {error || "作者可能暂停了访问，或者删除了这个应用。"}
            </p>
            <button
              type="button"
              onClick={onDiscover}
              className="mt-5 inline-flex h-9 items-center rounded-full bg-brand px-4 text-[13px] font-medium text-white transition hover:bg-brand-600"
            >
              返回发现
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden bg-base">
      {sidebar}

      <main className="min-w-0 flex-1 overflow-y-auto bg-base">
        <div
          className="mx-auto w-full px-6 py-8 sm:px-8"
          style={{ maxWidth: contentMaxWidth(sidebarCollapsed, 1100) }}
        >
          <nav
            aria-label="面包屑"
            className="flex min-w-0 items-center gap-1.5 text-[12px] text-ink-55"
          >
            <button
              type="button"
              onClick={onDiscover}
              className="transition hover:text-ink-95"
            >
              发现
            </button>
            <ChevronRight size={12} className="flex-none text-ink-30" />
            <span className="flex-none">{app.category}</span>
            <ChevronRight size={12} className="flex-none text-ink-30" />
            <span className="truncate text-ink-80">{app.name}</span>
          </nav>

          <header className="mt-4 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h1 className="text-[28px] font-semibold leading-[38px] tracking-[-0.4px] text-ink-95">
                {app.name}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-4 text-[12px] text-ink-55">
                <span className="inline-flex items-center gap-1.5">
                  <Eye size={14} />
                  {formatCount(app.view_count)} 次浏览
                </span>
                <span>发布于 {formatPublishedDate(app.published_at)}</span>
                <span className="rounded-full bg-line-4 px-2 py-0.5 text-[11px] text-ink-55">
                  {MODE_LABEL[app.mode] ?? "前端"}
                </span>
              </div>
            </div>

            <div className="flex flex-none flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={openApp}
                className="inline-flex h-9 items-center gap-1.5 rounded-full bg-brand px-4 text-[13px] font-medium text-white transition hover:bg-brand-600"
              >
                <ExternalLink size={14} />
                打开应用
              </button>
              <button
                type="button"
                onClick={() => void copyLink()}
                className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line-8 bg-white px-4 text-[13px] text-ink-80 transition hover:border-line-12 hover:text-ink-95"
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "已复制" : "复制链接"}
              </button>
              <button
                type="button"
                onClick={() => void toggleSave()}
                disabled={saving}
                aria-pressed={saved}
                className={`inline-flex h-9 items-center gap-1.5 rounded-full border px-4 text-[13px] transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  saved
                    ? "border-brand bg-brand text-white hover:bg-brand-600"
                    : "border-line-8 bg-white text-ink-80 hover:border-line-12 hover:text-ink-95"
                }`}
              >
                {saved ? (
                  <BookmarkFill size={14} />
                ) : (
                  <Bookmark size={14} />
                )}
                {saved ? "已收藏" : "收藏"}
              </button>
            </div>
          </header>

          {actionError ? (
            <p className="mt-3 rounded-lg bg-danger/10 px-3 py-2 text-[12px] text-danger">
              {actionError}
            </p>
          ) : null}

          <div className="relative mt-5 aspect-[16/9] overflow-hidden rounded-[12px] border border-line-4 bg-white">
            {!frameLoaded ? (
              <div className="absolute inset-0 grid place-items-center bg-line-2">
                <div className="flex items-center gap-2 text-[12px] text-ink-55">
                  <Spinner size={14} className="text-brand" />
                  正在加载应用…
                </div>
              </div>
            ) : null}
            <iframe
              src={app.published_url}
              title={`${app.name} 预览`}
              sandbox="allow-scripts allow-forms allow-popups allow-modals"
              onLoad={() => setFrameLoaded(true)}
              className="h-full w-full border-0 bg-white"
            />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
            <section className="min-w-0">
              <h2 className="text-[14px] font-medium text-ink-95">关于</h2>
              <p className="mt-2 whitespace-pre-wrap text-[13px] leading-[22px] text-ink-80">
                {app.description || "作者还没有填写简介。"}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-line-4 px-2.5 py-1 text-[11px] text-ink-55">
                  {app.category}
                </span>
                <span className="rounded-full bg-line-4 px-2.5 py-1 text-[11px] text-ink-55">
                  {MODE_LABEL[app.mode] ?? "前端"}
                </span>
              </div>
            </section>

            <aside className="rounded-2xl border border-line-4 bg-white p-5">
              <h2 className="text-[12px] text-ink-55">创作者</h2>
              <div className="mt-3 flex items-center gap-3">
                <InitialAvatar
                  size={36}
                  label={app.author_initial || "A"}
                />
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-medium text-ink-95">
                    {app.author_name}
                  </p>
                  <p className="mt-0.5 text-[11px] text-ink-55">
                    发布于 {formatPublishedDate(app.published_at)}
                  </p>
                </div>
              </div>
            </aside>
          </div>

          {relatedApps.length ? (
            <section className="mt-10 pb-10">
              <div className="flex items-center justify-between">
                <h2 className="text-[16px] font-medium text-ink-95">
                  相关应用
                </h2>
                <button
                  type="button"
                  onClick={onDiscover}
                  className="text-[12px] text-ink-55 transition hover:text-ink-95"
                >
                  查看更多
                </button>
              </div>
              <CardGrid collapsed={sidebarCollapsed} className="mt-4">
                {relatedApps.map((item) => (
                  <DiscoverCard
                    key={item.id}
                    app={item}
                    onOpen={onOpenDiscoverApp}
                  />
                ))}
              </CardGrid>
            </section>
          ) : null}
        </div>
      </main>
    </div>
  );
}
