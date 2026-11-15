import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { DISCOVER_CATEGORIES } from "../lib/discover";
import { contentMaxWidth } from "../lib/layout";
import type {
  AuthUser,
  DiscoverApp,
  DiscoverSort,
  Health,
  ProjectSummary,
} from "../types";
import CardGrid from "./CardGrid";
import HomeSidebar, { CollapsedSidebar } from "./HomeSidebar";
import { Bookmark, BookmarkFill, Search, Sparkle, X } from "./Icons";
import DiscoverCard from "./DiscoverCard";
import Tabs, { type TabItem } from "./Tabs";

const PAGE_SIZE = 24;

const CATEGORY_TABS: TabItem<string>[] = ["全部", ...DISCOVER_CATEGORIES].map(
  (value) => ({ value, label: value })
);

const SORT_TABS: TabItem<DiscoverSort>[] = [
  { value: "latest", label: "最新" },
  { value: "popular", label: "最热" },
];

interface Props {
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

export default function DiscoverPage({
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
  const [sort, setSort] = useState<DiscoverSort>("latest");
  const [category, setCategory] = useState<string>("全部");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [savedOnly, setSavedOnly] = useState(false);
  const [items, setItems] = useState<DiscoverApp[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const ownIds = useMemo(
    () => new Set(sidebarProjects.map((project) => project.id)),
    [sidebarProjects]
  );
  // The backend already excludes these; this is a defensive filter for a
  // stale project poll racing the discover response.
  const visibleItems = useMemo(
    () => items.filter((app) => !ownIds.has(app.id)),
    [items, ownIds]
  );

  useEffect(() => {
    const timer = window.setTimeout(
      () => setDebouncedQuery(query.trim()),
      300
    );
    return () => window.clearTimeout(timer);
  }, [query]);

  const load = useCallback(
    async (offset: number, append: boolean) => {
      const request = ++requestRef.current;
      if (append) setLoadingMore(true);
      else {
        setLoading(true);
        setItems([]);
        setHasMore(false);
      }
      setError(null);
      try {
        const data = await api.discover({
          sort,
          category: category === "全部" ? undefined : category,
          q: debouncedQuery || undefined,
          saved: savedOnly,
          offset,
          limit: PAGE_SIZE,
        });
        if (request !== requestRef.current) return;
        setItems((prev) => (append ? [...prev, ...data.apps] : data.apps));
        setHasMore(data.has_more);
      } catch (err) {
        if (request === requestRef.current) {
          setError((err as Error).message || "发现列表加载失败");
        }
      } finally {
        if (request === requestRef.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [sort, category, debouncedQuery, savedOnly]
  );

  useEffect(() => {
    void load(0, false);
  }, [load]);

  // Infinite scroll: load the next page when the sentinel approaches the
  // viewport. The button below remains as a keyboard-accessible fallback.
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || loading || loadingMore || !hasMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void load(items.length, true);
      },
      { rootMargin: "400px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMore, items.length, load, loading, loadingMore]);

  const filtering =
    category !== "全部" || query.trim().length > 0 || savedOnly;

  function resetFilters() {
    setCategory("全部");
    setQuery("");
    setSavedOnly(false);
  }

  return (
    <div className="flex h-full overflow-hidden bg-base">
      {sidebarCollapsed ? (
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
      )}

      <main className="min-w-0 flex-1 overflow-y-auto bg-base">
        <div
          className="mx-auto w-full px-6 py-8 sm:px-8"
          style={{ maxWidth: contentMaxWidth(sidebarCollapsed, 1100) }}
        >
          <header className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-[24px] font-medium leading-[32px] tracking-[-0.3px] text-ink-95">
                发现
              </h1>
              <p className="mt-1 text-[13px] text-ink-55">
                看看其他用户用 Atoms 构建并发布的应用。
              </p>
            </div>
          </header>

          <div className="mt-6 space-y-3">
            <Tabs
              items={CATEGORY_TABS}
              value={category}
              onChange={setCategory}
              className="no-scrollbar overflow-x-auto pb-1"
            />

            <div className="flex flex-wrap items-center justify-end gap-2">
              <div className="relative w-full sm:w-[190px]">
                <Search
                  size={15}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-30"
                />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索应用"
                  className="h-9 w-full rounded-full border border-line-8 bg-white pl-9 pr-9 text-[13px] text-ink-95 outline-none transition placeholder:text-ink-30 focus:border-line-12"
                />
                {query ? (
                  <button
                    type="button"
                    onClick={() => setQuery("")}
                    title="清空搜索"
                    className="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full text-ink-30 transition hover:bg-line-4 hover:text-ink-55"
                  >
                    <X size={13} />
                  </button>
                ) : null}
              </div>

              <Tabs items={SORT_TABS} value={sort} onChange={setSort} />

              <button
                type="button"
                onClick={() => setSavedOnly((value) => !value)}
                aria-pressed={savedOnly}
                className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] transition ${
                  savedOnly
                    ? "border-brand bg-brand text-white hover:bg-brand-600"
                    : "border-line-8 bg-white text-ink-80 hover:border-line-12 hover:text-ink-95"
                }`}
              >
                {savedOnly ? (
                  <BookmarkFill size={14} />
                ) : (
                  <Bookmark size={14} />
                )}
                已保存
              </button>
            </div>
          </div>

          {error ? (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-danger/20 bg-danger/5 px-3 py-2 text-[12px] text-danger">
              <span>{error}</span>
              <button
                type="button"
                onClick={() => void load(0, false)}
                className="rounded-full border border-danger/20 bg-white px-2.5 py-1 text-[11px] font-medium text-danger transition hover:border-danger/40"
              >
                重试
              </button>
            </div>
          ) : null}

          <div className="mt-7 pb-10">
            {loading ? (
              <CardGrid collapsed={sidebarCollapsed}>
                {[0, 1, 2, 3, 4, 5].map((index) => (
                  <div key={index} className="animate-pulse">
                    <div className="aspect-[16/10] rounded-xl bg-line-4" />
                    <div className="mt-3 h-3 w-2/3 rounded-full bg-line-4" />
                    <div className="mt-2 h-2 w-1/2 rounded-full bg-line-2" />
                  </div>
                ))}
              </CardGrid>
            ) : error ? null : visibleItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-[20px] border border-dashed border-line-8 bg-white/60 px-6 py-20 text-center">
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-line-4 text-ink-55">
                  {savedOnly ? <Bookmark size={22} /> : <Sparkle size={22} />}
                </span>
                <p className="mt-4 text-[15px] font-medium text-ink-95">
                  {savedOnly
                    ? "还没有收藏的应用"
                    : filtering
                      ? "没有匹配的应用"
                      : "还没有其他用户公开应用"}
                </p>
                <p className="mt-1.5 max-w-[340px] text-[13px] leading-[20px] text-ink-55">
                  {savedOnly
                    ? "在应用详情页点收藏，之后可以在这里快速找到。"
                    : filtering
                      ? "换个关键词或分类，或者清除当前筛选条件。"
                      : "发布你的应用后，其他用户会在这里看到它。"}
                </p>
                {filtering ? (
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="mt-5 inline-flex h-8 items-center rounded-full border border-line-8 bg-white px-4 text-[13px] text-ink-80 transition hover:border-line-12 hover:text-ink-95"
                  >
                    清除筛选
                  </button>
                ) : null}
              </div>
            ) : (
              <>
                <CardGrid collapsed={sidebarCollapsed}>
                  {visibleItems.map((app) => (
                    <DiscoverCard
                      key={app.id}
                      app={app}
                      onOpen={onOpenDiscoverApp}
                    />
                  ))}
                </CardGrid>

                <div ref={sentinelRef} className="h-1" />
                {hasMore ? (
                  <div className="mt-8 flex justify-center">
                    <button
                      type="button"
                      onClick={() => void load(items.length, true)}
                      disabled={loadingMore}
                      className="inline-flex h-9 items-center gap-2 rounded-full border border-line-8 bg-white px-5 text-[13px] text-ink-80 transition hover:border-line-12 hover:text-ink-95 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {loadingMore ? "加载中…" : "加载更多"}
                    </button>
                  </div>
                ) : (
                  <p className="mt-8 text-center text-[12px] text-ink-30">
                    已经看到全部 {visibleItems.length} 个应用
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
