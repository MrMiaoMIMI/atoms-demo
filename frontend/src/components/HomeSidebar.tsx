import type { ReactNode } from "react";
import type { Health, ProjectSummary } from "../types";
import { InitialAvatar } from "./Avatar";
import {
  AtomsMark,
  Bell,
  Chat,
  ChevronDown,
  Clock,
  Compass,
  Folder,
  Home,
  PanelLeft,
  Plus,
  Settings,
} from "./Icons";

interface Props {
  health: Health | null;
  projects: ProjectSummary[];
  section: "home" | "projects";
  onHome: () => void;
  onProjects: () => void;
  onOpenProject: (id: string) => void;
  onCollapse: () => void;
}

function NavItem({
  icon,
  label,
  active = false,
  placeholder = false,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
  placeholder?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={placeholder}
      className={`flex h-9 w-full items-center gap-2.5 rounded-lg px-2 text-left text-[14px] transition ${
        active
          ? "bg-line-6 text-ink-95"
          : placeholder
            ? "cursor-default text-ink-30"
            : "text-ink-80 hover:bg-line-4 hover:text-ink-95"
      }`}
    >
      <span className="flex h-4 w-4 flex-none items-center justify-center">{icon}</span>
      <span className="truncate">{label}</span>
      {placeholder ? (
        <span className="ml-auto rounded-full border border-line-6 px-1.5 py-0.5 text-[10px] leading-none text-ink-30">
          占位
        </span>
      ) : null}
    </button>
  );
}

export default function HomeSidebar({
  health,
  projects,
  section,
  onHome,
  onProjects,
  onOpenProject,
  onCollapse,
}: Props) {
  const recent = projects.slice(0, 6);
  const statusText = health?.ok
    ? health.llm_mode === "mock"
      ? "Mock Agent"
      : health.model || "LLM 在线"
    : "服务离线";

  return (
    <aside className="flex h-full w-[270px] flex-none flex-col bg-base-sidebar">
      <div className="flex items-center justify-between px-4 pb-1 pt-4">
        <div className="flex items-center gap-2">
          <AtomsMark size={22} className="text-ink-95" />
          <span className="text-[16px] font-medium tracking-[-0.2px] text-ink-95">Atoms</span>
        </div>
        <button
          type="button"
          onClick={onCollapse}
          title="收起侧边栏"
          className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-6 hover:text-ink-80"
        >
          <PanelLeft size={17} />
        </button>
      </div>

      <div className="px-2 pt-3">
        <button
          type="button"
          className="flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left transition hover:bg-line-4"
          title="当前工作区"
        >
          <span className="grid h-[22px] w-[22px] place-items-center rounded-[6px] bg-brand text-[11px] font-semibold text-white">
            A
          </span>
          <span className="min-w-0 flex-1 truncate text-[14px] text-ink-95">Atoms Demo</span>
          <ChevronDown size={14} className="flex-none text-ink-55" />
        </button>
      </div>

      <nav className="mt-3 space-y-0.5 px-2">
        <NavItem icon={<Home size={17} />} label="首页" active={section === "home"} onClick={onHome} />
        <NavItem icon={<Compass size={17} />} label="资源" placeholder />
        <NavItem
          icon={<Folder size={17} />}
          label="项目"
          active={section === "projects"}
          onClick={onProjects}
        />
        <NavItem icon={<Clock size={17} />} label="定时任务" placeholder />
      </nav>

      <div className="mt-5 px-2">
        <div className="flex h-7 items-center justify-between px-2">
          <span className="text-[12px] text-ink-55">文件夹</span>
          <button
            type="button"
            disabled
            title="占位功能"
            className="grid h-6 w-6 place-items-center rounded-md text-ink-30"
          >
            <Plus size={13} />
          </button>
        </div>
        <div className="flex h-9 items-center gap-2 rounded-lg px-2 text-[14px] text-ink-55">
          <Folder size={16} className="flex-none" />
          <span className="truncate">示例项目</span>
          <span className="ml-auto rounded-full border border-line-6 px-1.5 py-0.5 text-[10px] leading-none text-ink-30">
            占位
          </span>
        </div>
      </div>

      <div className="mt-4 flex min-h-0 flex-1 flex-col px-2">
        <div className="flex h-7 items-center px-2 text-[12px] text-ink-55">最近</div>
        <div className="min-h-0 flex-1 overflow-y-auto pb-2">
          {recent.length ? (
            recent.map((project) => (
              <button
                key={project.id}
                type="button"
                onClick={() => onOpenProject(project.id)}
                className="flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left text-[14px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
              >
                <Chat size={15} className="flex-none text-ink-30" />
                <span className="truncate">{project.name}</span>
              </button>
            ))
          ) : (
            <p className="px-2 py-1.5 text-[12px] text-ink-30">尚无聊天记录</p>
          )}
        </div>
      </div>

      <div className="px-2 pb-3">
        <div className="rounded-xl border border-line-6 bg-white p-3">
          <div className="flex items-center gap-2 text-[13px] font-medium text-ink-95">
            <span className="grid h-6 w-6 place-items-center rounded-md bg-line-4">
              <AtomsMark size={15} className="text-brand" />
            </span>
            本地工作区
          </div>
          <p className="mt-2 truncate text-[12px] leading-[18px] text-ink-55">
            SQLite · {statusText}
          </p>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-55">
            <span
              className={`h-1.5 w-1.5 rounded-full ${health?.ok ? "bg-positive" : "bg-ink-30"}`}
            />
            {health?.ok ? "服务在线" : "服务离线"}
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2 px-1">
          <InitialAvatar size={28} label="A" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-ink-95">Atoms Demo</p>
            <p className="truncate text-[11px] text-ink-55">本地演示</p>
          </div>
          <button
            type="button"
            disabled
            title="设置（占位）"
            className="grid h-7 w-7 place-items-center rounded-md text-ink-30"
          >
            <Settings size={16} />
          </button>
          <button
            type="button"
            disabled
            title="通知（占位）"
            className="grid h-7 w-7 place-items-center rounded-md text-ink-30"
          >
            <Bell size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}
