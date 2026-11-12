import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import Home from "./components/Home";
import ProjectsPage from "./components/ProjectsPage";
import Workspace from "./components/Workspace";
import type { Health, ProjectSummary } from "./types";

type Route =
  | { name: "home" }
  | { name: "projects" }
  | { name: "workspace"; projectId: string };

function parseRoute(): Route {
  const path = window.location.pathname.replace(/\/+$/, "");
  const chat = /^\/chat\/([^/]+)$/.exec(path);
  if (chat) {
    let projectId = chat[1];
    try {
      projectId = decodeURIComponent(projectId);
    } catch {
      // Keep the raw segment if it is not valid percent-encoding.
    }
    return { name: "workspace", projectId };
  }
  // Legacy links used /?p={id}; keep them working.
  const legacy = new URLSearchParams(window.location.search).get("p");
  if (legacy) return { name: "workspace", projectId: legacy };
  if (path === "/projects") return { name: "projects" };
  return { name: "home" };
}

/** Canonicalise the address bar and migrate old /?p= links. */
function normalizeRoute(): void {
  const path = window.location.pathname.replace(/\/+$/, "");
  const legacy = new URLSearchParams(window.location.search).get("p");
  if (legacy) {
    window.history.replaceState(
      {},
      "",
      `/chat/${encodeURIComponent(legacy)}`
    );
    return;
  }
  const known =
    path === "/dashboard" ||
    path === "/projects" ||
    /^\/chat\/[^/]+$/.test(path);
  if (!known) window.history.replaceState({}, "", "/dashboard");
}

const SIDEBAR_COLLAPSED_KEY = "atoms.sidebar.collapsed";

function readSidebarCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => {
    normalizeRoute();
    return parseRoute();
  });
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  // Shared project list for the sidebar. Polling keeps "正在处理" spinners in
  // sync on every page, including builds that outlive a page visit.
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  // Home and the projects list share one collapse state; the workspace keeps
  // its own sidebar closed by default.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    readSidebarCollapsed
  );

  useEffect(() => {
    try {
      window.localStorage.setItem(
        SIDEBAR_COLLAPSED_KEY,
        sidebarCollapsed ? "1" : "0"
      );
    } catch {
      // Storage may be unavailable; the state still works for this session.
    }
  }, [sidebarCollapsed]);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (document.hidden) return;
      try {
        const items = await api.listProjects();
        if (!cancelled) setProjects(items);
      } catch {
        // Keep the previous list; the next tick retries.
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const onPop = () => {
      setPendingPrompt(null);
      setRoute(parseRoute());
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    document.title =
      route.name === "projects"
        ? "项目 · Atoms"
        : route.name === "workspace"
          ? "工作台 · Atoms"
          : "Atoms · 让想法变成可运行的应用";
  }, [route]);

  const goHome = useCallback(() => {
    window.history.pushState({}, "", "/dashboard");
    setPendingPrompt(null);
    setRoute({ name: "home" });
  }, []);

  const goProjects = useCallback(() => {
    window.history.pushState({}, "", "/projects");
    setPendingPrompt(null);
    setRoute({ name: "projects" });
  }, []);

  const openProject = useCallback((projectId: string) => {
    window.history.pushState(
      {},
      "",
      `/chat/${encodeURIComponent(projectId)}`
    );
    setPendingPrompt(null);
    setRoute({ name: "workspace", projectId });
  }, []);

  const start = useCallback(
    (projectId: string, prompt: string) => {
      openProject(projectId);
      setPendingPrompt(prompt);
    },
    [openProject]
  );

  if (route.name === "workspace") {
    return (
      <Workspace
        key={route.projectId}
        projectId={route.projectId}
        initialPrompt={pendingPrompt}
        onPromptUsed={() => setPendingPrompt(null)}
        health={health}
        onExit={goHome}
        projects={projects}
        onOpenProject={openProject}
        onOpenProjects={goProjects}
      />
    );
  }

  if (route.name === "projects") {
    return (
      <ProjectsPage
        health={health}
        sidebarProjects={projects}
        sidebarCollapsed={sidebarCollapsed}
        onSidebarCollapsed={setSidebarCollapsed}
        onHome={goHome}
        onNewProject={goHome}
        onOpenProject={openProject}
      />
    );
  }

  return (
    <Home
      health={health}
      sidebarProjects={projects}
      sidebarCollapsed={sidebarCollapsed}
      onSidebarCollapsed={setSidebarCollapsed}
      onStart={start}
      onOpen={openProject}
      onBrowseAllProjects={goProjects}
    />
  );
}
