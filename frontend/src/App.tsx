import { useCallback, useEffect, useState } from "react";
import { AUTH_EVENT, api } from "./api";
import CheckEmailPage from "./components/auth/CheckEmailPage";
import ForgotPasswordPage from "./components/auth/ForgotPasswordPage";
import LoginPage from "./components/auth/LoginPage";
import RegisterPage from "./components/auth/RegisterPage";
import ResetPasswordPage from "./components/auth/ResetPasswordPage";
import VerifyEmailPage from "./components/auth/VerifyEmailPage";
import Home from "./components/Home";
import { AtomsMark } from "./components/Icons";
import ProjectsPage from "./components/ProjectsPage";
import Workspace from "./components/Workspace";
import { safeRedirect } from "./lib/auth";
import type { AuthUser, Health, ProjectSummary } from "./types";

type Route =
  | { name: "home" }
  | { name: "projects" }
  | { name: "workspace"; projectId: string }
  | { name: "login" }
  | { name: "register"; email: string; redirect: string }
  | { name: "check-email"; email: string }
  | {
      name: "verify-email";
      token: string;
      email: string;
      redirect: string;
    }
  | { name: "forgot-password"; email: string }
  | { name: "reset-password"; token: string; email: string };

const AUTH_PATH_PREFIXES = [
  "/login",
  "/register",
  "/register/verify",
  "/verify-email",
  "/password/forgot",
  "/password/reset",
];

const AUTH_ROUTE_NAMES = new Set<Route["name"]>([
  "login",
  "register",
  "check-email",
  "verify-email",
  "forgot-password",
  "reset-password",
]);

// These pages still do useful work when a session already exists (an email
// link opened in a logged-in browser, or a password reset).
const ALLOW_WHEN_LOGGED_IN = new Set<Route["name"]>([
  "verify-email",
  "reset-password",
]);

function isAuthPath(pathname: string): boolean {
  return AUTH_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

function parseRoute(): Route {
  const url = new URL(window.location.href);
  const path = url.pathname.replace(/\/+$/, "");
  const query = url.searchParams;

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
  const legacy = query.get("p");
  if (legacy) return { name: "workspace", projectId: legacy };

  switch (path) {
    case "/login":
      return { name: "login" };
    case "/register":
      return {
        name: "register",
        email: query.get("email") ?? "",
        redirect: safeRedirect(query.get("redirect")),
      };
    case "/register/verify":
      return { name: "check-email", email: query.get("email") ?? "" };
    case "/verify-email":
      return {
        name: "verify-email",
        token: query.get("token") ?? "",
        email: query.get("email") ?? "",
        redirect: safeRedirect(query.get("redirect")),
      };
    case "/password/forgot":
      return { name: "forgot-password", email: query.get("email") ?? "" };
    case "/password/reset":
      return {
        name: "reset-password",
        token: query.get("token") ?? "",
        email: query.get("email") ?? "",
      };
    case "/projects":
      return { name: "projects" };
    default:
      return { name: "home" };
  }
}

/** Canonicalise the address bar and migrate old /?p= links. */
function normalizeRoute(): void {
  const url = new URL(window.location.href);
  const path = url.pathname.replace(/\/+$/, "");
  const legacy = url.searchParams.get("p");
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
    /^\/chat\/[^/]+$/.test(path) ||
    isAuthPath(path);
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

function Splash() {
  return (
    <div className="grid min-h-screen place-items-center bg-white">
      <div className="flex items-center gap-2 text-ink-55">
        <AtomsMark size={22} className="text-brand" />
        <span className="text-[13px]">正在加载…</span>
      </div>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => {
    normalizeRoute();
    return parseRoute();
  });
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authStatus, setAuthStatus] = useState<
    "loading" | "anon" | "user"
  >("loading");

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

  // Resolve the session once on boot. The login page is rendered while the
  // answer is pending, so there is no flash of protected content.
  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((current) => {
        if (cancelled) return;
        setUser(current);
        setAuthStatus("user");
      })
      .catch(() => {
        if (cancelled) return;
        setUser(null);
        setAuthStatus("anon");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setAuthStatus("anon");
      setProjects([]);
      const current = `${window.location.pathname}${window.location.search}`;
      if (!isAuthPath(window.location.pathname)) {
        window.history.replaceState(
          {},
          "",
          `/login?redirect=${encodeURIComponent(current)}`
        );
        setRoute(parseRoute());
      }
    };
    window.addEventListener(AUTH_EVENT, onUnauthorized);
    return () => window.removeEventListener(AUTH_EVENT, onUnauthorized);
  }, []);

  useEffect(() => {
    if (authStatus === "anon" && !AUTH_ROUTE_NAMES.has(route.name)) {
      const current = `${window.location.pathname}${window.location.search}`;
      window.history.replaceState(
        {},
        "",
        `/login?redirect=${encodeURIComponent(current)}`
      );
      setRoute({ name: "login" });
      return;
    }
    if (
      authStatus === "user" &&
      AUTH_ROUTE_NAMES.has(route.name) &&
      !ALLOW_WHEN_LOGGED_IN.has(route.name)
    ) {
      const params = new URLSearchParams(window.location.search);
      const target = safeRedirect(params.get("redirect"));
      window.history.replaceState({}, "", target);
      setRoute(parseRoute());
    }
  }, [authStatus, route]);

  useEffect(() => {
    if (authStatus !== "user") {
      setProjects([]);
      return;
    }
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
  }, [authStatus, user?.id]);

  useEffect(() => {
    const onPop = () => {
      setPendingPrompt(null);
      setRoute(parseRoute());
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    const authTitles: Partial<Record<Route["name"], string>> = {
      login: "登录 · Atoms",
      register: "创建账户 · Atoms",
      "check-email": "查收邮件 · Atoms",
      "verify-email": "验证邮箱 · Atoms",
      "forgot-password": "忘记密码 · Atoms",
      "reset-password": "重置密码 · Atoms",
    };
    document.title =
      authTitles[route.name] ??
      (route.name === "projects"
        ? "项目 · Atoms"
        : route.name === "workspace"
          ? "工作台 · Atoms"
          : "Atoms · 让想法变成可运行的应用");
  }, [route]);

  const navigate = useCallback((path: string) => {
    window.history.pushState({}, "", path);
    setPendingPrompt(null);
    setRoute(parseRoute());
  }, []);

  const goHome = useCallback(() => {
    navigate("/dashboard");
  }, [navigate]);

  const goProjects = useCallback(() => {
    navigate("/projects");
  }, [navigate]);

  const openProject = useCallback(
    (projectId: string) => {
      navigate(`/chat/${encodeURIComponent(projectId)}`);
    },
    [navigate]
  );

  const start = useCallback(
    (projectId: string, prompt: string) => {
      openProject(projectId);
      setPendingPrompt(prompt);
    },
    [openProject]
  );

  const onAuthenticated = useCallback(
    (nextUser: AuthUser, redirect: string) => {
      setUser(nextUser);
      setAuthStatus("user");
      const target = safeRedirect(redirect);
      window.history.replaceState({}, "", target);
      setRoute(parseRoute());
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // The cookie is cleared client-side even if the request fails.
    }
    setUser(null);
    setAuthStatus("anon");
    setProjects([]);
    window.history.replaceState({}, "", "/login");
    setRoute({ name: "login" });
  }, []);

  if (authStatus === "loading") return <Splash />;

  if (authStatus === "anon") {
    switch (route.name) {
      case "login":
        return (
          <LoginPage onNavigate={navigate} onAuthenticated={onAuthenticated} />
        );
      case "register":
        return (
          <RegisterPage
            email={route.email}
            redirect={route.redirect}
            onNavigate={navigate}
          />
        );
      case "check-email":
        return (
          <CheckEmailPage email={route.email} onNavigate={navigate} />
        );
      case "verify-email":
        return (
          <VerifyEmailPage
            token={route.token}
            email={route.email}
            redirect={route.redirect}
            onAuthenticated={onAuthenticated}
            onNavigate={navigate}
          />
        );
      case "forgot-password":
        return (
          <ForgotPasswordPage
            initialEmail={route.email}
            onNavigate={navigate}
          />
        );
      case "reset-password":
        return (
          <ResetPasswordPage
            token={route.token}
            email={route.email}
            onNavigate={navigate}
          />
        );
      default:
        return <Splash />;
    }
  }

  if (route.name === "verify-email") {
    return (
      <VerifyEmailPage
        token={route.token}
        email={route.email}
        redirect={route.redirect}
        onAuthenticated={onAuthenticated}
        onNavigate={navigate}
      />
    );
  }
  if (route.name === "reset-password") {
    return (
      <ResetPasswordPage
        token={route.token}
        email={route.email}
        onNavigate={navigate}
      />
    );
  }
  if (AUTH_ROUTE_NAMES.has(route.name)) return <Splash />;

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
        user={user!}
        onLogout={logout}
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
        user={user!}
        onLogout={logout}
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
      user={user!}
      onLogout={logout}
    />
  );
}
