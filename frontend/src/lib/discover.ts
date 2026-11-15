// Keep this list aligned with backend/categories.py. These are the tags used
// by the public Atoms discover page, plus the no-match bucket.
export const DISCOVER_CATEGORIES = [
  "网站",
  "电商",
  "游戏",
  "效率",
  "原型",
  "数据分析",
  "博客",
  "名片",
  "深度研究",
  "其他",
] as const;

export type DiscoverCategory = (typeof DISCOVER_CATEGORIES)[number];

export const DEFAULT_DISCOVER_CATEGORY: DiscoverCategory = "其他";

export function isDiscoverCategory(value: string): value is DiscoverCategory {
  return (DISCOVER_CATEGORIES as readonly string[]).includes(value);
}

/** Compact view counts: 734, 1.2K, 12.3K. */
export function formatCount(value: number): string {
  const count = Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0;
  if (count >= 10_000) {
    const text = (count / 1000).toFixed(1).replace(/\.0$/, "");
    return `${text}K`;
  }
  return String(count);
}

export function formatPublishedDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}
