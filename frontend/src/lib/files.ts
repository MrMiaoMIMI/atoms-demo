export interface FileNode {
  type: "dir" | "file";
  name: string;
  path: string;
  children?: FileNode[];
}

const DIR_PRIORITY = ["frontend", "backend", "src", "app", "api", "components", "pages"];
const FILE_PRIORITY = [
  "App.tsx",
  "main.tsx",
  "index.html",
  "main.py",
  "package.json",
  "vite.config.ts",
  "tailwind.config.ts",
  "main.css",
  "index.css",
  "README.md",
];

function dirRank(name: string): number {
  const index = DIR_PRIORITY.indexOf(name);
  return index === -1 ? 50 : index;
}

function fileRank(name: string): number {
  const index = FILE_PRIORITY.indexOf(name);
  return index === -1 ? 50 : index;
}

export function buildFileTree(names: string[]): FileNode[] {
  const root: FileNode[] = [];

  for (const fullPath of [...names].sort()) {
    const parts = fullPath.split("/").filter(Boolean);
    let level = root;
    let current = "";

    parts.forEach((part, index) => {
      current = current ? `${current}/${part}` : part;
      const isFile = index === parts.length - 1;
      let node = level.find((item) => item.name === part && item.path === current);
      if (!node) {
        node = isFile
          ? { type: "file", name: part, path: current }
          : { type: "dir", name: part, path: current, children: [] };
        level.push(node);
      }
      if (!isFile) level = node.children!;
    });
  }

  const sortLevel = (nodes: FileNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
      if (a.type === "dir") {
        return dirRank(a.name) - dirRank(b.name) || a.name.localeCompare(b.name);
      }
      return fileRank(a.name) - fileRank(b.name) || a.name.localeCompare(b.name);
    });
    for (const node of nodes) if (node.children) sortLevel(node.children);
  };
  sortLevel(root);
  return root;
}

export function flattenFiles(nodes: FileNode[]): string[] {
  const out: string[] = [];
  for (const node of nodes) {
    if (node.type === "file") out.push(node.path);
    else if (node.children) out.push(...flattenFiles(node.children));
  }
  return out;
}

/**
 * Remove every directory on `path` from a collapsed-path set so the tree can
 * reveal it. Pass a fake child (`dir/_`) to expand `dir` itself.
 */
export function expandDirPath(
  current: Set<string>,
  path: string
): Set<string> | null {
  const parts = path.split("/").filter(Boolean);
  let next: Set<string> | null = null;
  let prefix = "";
  for (let index = 0; index < parts.length - 1; index += 1) {
    prefix = prefix ? `${prefix}/${parts[index]}` : parts[index];
    if (!current.has(prefix)) continue;
    if (!next) next = new Set(current);
    next.delete(prefix);
  }
  return next;
}

export type CodeLanguage =
  | "ts"
  | "js"
  | "py"
  | "json"
  | "css"
  | "html"
  | "md"
  | "sh"
  | "sql"
  | "txt";

const LANGUAGE_LABEL: Record<CodeLanguage, string> = {
  ts: "TypeScript",
  js: "JavaScript",
  py: "Python",
  json: "JSON",
  css: "CSS",
  html: "HTML",
  md: "Markdown",
  sh: "Shell",
  sql: "SQL",
  txt: "纯文本",
};

export function languageLabel(filename: string): string {
  return LANGUAGE_LABEL[languageForFile(filename)];
}

export function languageForFile(filename: string): CodeLanguage {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "ts" || ext === "tsx") return "ts";
  if (ext === "js" || ext === "jsx" || ext === "mjs" || ext === "cjs") return "js";
  if (ext === "py") return "py";
  if (ext === "json") return "json";
  if (ext === "css" || ext === "scss") return "css";
  if (ext === "html" || ext === "htm" || ext === "vue") return "html";
  if (ext === "md" || ext === "mdx") return "md";
  if (ext === "sh" || ext === "bash" || ext === "zsh") return "sh";
  if (ext === "sql") return "sql";
  return "txt";
}

const BADGES: Record<string, { label: string; bg: string; color: string }> = {
  ts: { label: "TS", bg: "#E8EEFF", color: "#425CE1" },
  js: { label: "JS", bg: "#FFF3CE", color: "#8A6A00" },
  py: { label: "PY", bg: "#E3F1E7", color: "#25813C" },
  json: { label: "{}", bg: "#F0F0EF", color: "#58585A" },
  css: { label: "CSS", bg: "#F0E9FF", color: "#7341CC" },
  html: { label: "<>", bg: "#FFE9E4", color: "#B72027" },
  md: { label: "MD", bg: "#F0F0EF", color: "#58585A" },
  sh: { label: "SH", bg: "#F0F0EF", color: "#58585A" },
  sql: { label: "SQL", bg: "#E8EEFF", color: "#425CE1" },
  img: { label: "IMG", bg: "#F0F0EF", color: "#58585A" },
  txt: { label: "TXT", bg: "#F0F0EF", color: "#58585A" },
};

export function fileBadge(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (["png", "jpg", "jpeg", "gif", "svg", "webp", "ico"].includes(ext)) return BADGES.img;
  return BADGES[languageForFile(filename)] ?? BADGES.txt;
}

export function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
