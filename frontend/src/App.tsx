import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import Home from "./components/Home";
import Workspace from "./components/Workspace";
import type { Health } from "./types";

function currentProjectId(): string | null {
  return new URLSearchParams(window.location.search).get("p");
}

export default function App() {
  const [projectId, setProjectId] = useState<string | null>(() => currentProjectId());
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    const onPop = () => setProjectId(currentProjectId());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((pid: string | null) => {
    const url = new URL(window.location.href);
    if (pid) url.searchParams.set("p", pid);
    else url.searchParams.delete("p");
    window.history.pushState({}, "", url);
    setProjectId(pid);
    if (!pid) setPendingPrompt(null);
  }, []);

  const start = useCallback(
    (pid: string, prompt: string) => {
      setPendingPrompt(prompt);
      navigate(pid);
    },
    [navigate]
  );

  if (projectId) {
    return (
      <Workspace
        key={projectId}
        projectId={projectId}
        initialPrompt={pendingPrompt}
        onPromptUsed={() => setPendingPrompt(null)}
        health={health}
        onExit={() => navigate(null)}
      />
    );
  }

  return <Home health={health} onStart={start} onOpen={navigate} />;
}
