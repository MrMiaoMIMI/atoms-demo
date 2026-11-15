export type CodeView = "files" | "changes";

export interface CodeLayout {
  file: string | null;
  view: CodeView;
}

export interface ReaderPrefs {
  wrap: boolean;
  fontSize: number;
}

export interface TreePrefs {
  open: boolean;
  collapsed: string[];
}

export const MIN_FONT_SIZE = 11;
export const MAX_FONT_SIZE = 16;
export const DEFAULT_FONT_SIZE = 12.5;

export const MIN_TREE_WIDTH = 180;
export const MAX_TREE_WIDTH = 420;

export const DEFAULT_READER: ReaderPrefs = {
  wrap: false,
  fontSize: DEFAULT_FONT_SIZE,
};

const LAYOUT_PREFIX = "atoms-code-layout:";
const TREE_PREFIX = "atoms-code-tree:";
const TREE_WIDTH_PREFIX = "atoms-code-tree-width:";
const READER_KEY = "atoms-code-reader";

const DEFAULT_TREE_WIDTH: Record<CodeView, number> = {
  files: 250,
  changes: 270,
};

function readJson(key: string): unknown {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Private mode or a full quota: preferences are best effort.
  }
}

export function clampFontSize(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_FONT_SIZE;
  return Math.min(
    MAX_FONT_SIZE,
    Math.max(MIN_FONT_SIZE, Math.round(value * 2) / 2)
  );
}

export function readLayout(projectId: string): CodeLayout {
  const raw = readJson(LAYOUT_PREFIX + projectId) as
    | { file?: unknown; view?: unknown }
    | null;
  return {
    file: typeof raw?.file === "string" ? raw.file : null,
    view: raw?.view === "changes" ? "changes" : "files",
  };
}

export function writeLayout(projectId: string, layout: CodeLayout): void {
  writeJson(LAYOUT_PREFIX + projectId, layout);
}

export function readTreePrefs(projectId: string): TreePrefs {
  const raw = readJson(TREE_PREFIX + projectId) as
    | { open?: unknown; collapsed?: unknown }
    | null;
  return {
    open: raw?.open !== false,
    collapsed: Array.isArray(raw?.collapsed)
      ? raw.collapsed.filter((item): item is string => typeof item === "string")
      : [],
  };
}

export function writeTreePrefs(projectId: string, prefs: TreePrefs): void {
  writeJson(TREE_PREFIX + projectId, prefs);
}

export function readTreeWidth(view: CodeView): number {
  const raw = readJson(TREE_WIDTH_PREFIX + view);
  const value =
    typeof raw === "number" && Number.isFinite(raw)
      ? raw
      : DEFAULT_TREE_WIDTH[view];
  return Math.min(MAX_TREE_WIDTH, Math.max(MIN_TREE_WIDTH, value));
}

export function writeTreeWidth(view: CodeView, width: number): void {
  writeJson(TREE_WIDTH_PREFIX + view, Math.round(width));
}

export function readReaderPrefs(): ReaderPrefs {
  const raw = readJson(READER_KEY) as
    | { wrap?: unknown; fontSize?: unknown }
    | null;
  return {
    wrap: raw?.wrap === true,
    fontSize: clampFontSize(
      typeof raw?.fontSize === "number" ? raw.fontSize : DEFAULT_FONT_SIZE
    ),
  };
}

export function writeReaderPrefs(prefs: ReaderPrefs): void {
  writeJson(READER_KEY, {
    wrap: prefs.wrap,
    fontSize: clampFontSize(prefs.fontSize),
  });
}
