import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import Home from "./components/Home";
import ProjectsPage from "./components/ProjectsPage";
import Workspace from "./components/Workspace";
import type { Health } from "./types";

type Route =
  | { name: "home" }
  | { name: "projects" }
  | { name: "workspace"; projectId: string };

function parseRoute(): Route {
  const projectId = new URLSearchParams(window.location.search).get("p");
  if (projectId) return { name: "workspace", projectId };
  const path = window.location.pathname.replace(/\/+$/, "");
  if (path === "/projects") return { name: "projects" };
  return { name: "home" };
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute());
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
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
    window.history.pushState({}, "", "/");
    setPendingPrompt(null);
    setRoute({ name: "home" });
  }, []);

  const goProjects = useCallback(() => {
    window.history.pushState({}, "", "/projects");
    setPendingPrompt(null);
    setRoute({ name: "projects" });
  }, []);

  const openProject = useCallback((projectId: string) => {
    window.history.pushState({}, "", `/?p=${encodeURIComponent(projectId)}`);
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
      />
    );
  }

  if (route.name === "projects") {
    return (
      <ProjectsPage
        health={health}
        onHome={goHome}
        onNewProject={goHome}
        onOpenProject={openProject}
      />
    );
  }

  return (
    <Home
      health={health}
      onStart={start}
      onOpen={openProject}
      onBrowseAllProjects={goProjects}
    />
  );
}
