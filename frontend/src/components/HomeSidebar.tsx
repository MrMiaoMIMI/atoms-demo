import type { ReactNode } from 'react';
import type { AuthUser, Health, ProjectSummary } from '../types';
import { InitialAvatar } from './Avatar';
import {
  AtomsMark,
  Chat,
  Clock,
  Compass,
  Folder,
  Home,
  LogOut,
  PanelLeft,
  Plus,
  Spinner,
} from './Icons';

interface Props {
  projects: ProjectSummary[];
  section: 'home' | 'projects' | 'workspace';
  user: AuthUser;
  onHome: () => void;
  onProjects: () => void;
  onOpenProject: (id: string) => void;
  onCollapse: () => void;
  onLogout: () => void;
}

function userInitial(user: AuthUser): string {
  const source = user.name?.trim() || user.email || 'A';
  return source.slice(0, 1).toUpperCase();
}

function displayName(user: AuthUser): string {
  return user.name?.trim() || user.email.split('@')[0] || '用户';
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
          ? 'bg-line-6 text-ink-95'
          : placeholder
            ? 'cursor-default text-ink-30'
            : 'text-ink-80 hover:bg-line-4 hover:text-ink-95'
      }`}
    >
      <span className="flex h-4 w-4 flex-none items-center justify-center">
        {icon}
      </span>
      <span className="truncate">{label}</span>
      {placeholder ? (
        <span className="ml-auto rounded-full border border-line-6 px-1.5 py-0.5 text-[10px] leading-none text-ink-30">
          占位
        </span>
      ) : null}
    </button>
  );
}

export function CollapsedSidebar({
  health,
  section,
  user,
  onHome,
  onProjects,
  onExpand,
}: {
  health: Health | null;
  section: 'home' | 'projects';
  user: AuthUser;
  onHome: () => void;
  onProjects: () => void;
  onExpand: () => void;
}) {
  const navItems = [
    {
      key: 'home' as const,
      label: '首页',
      icon: <Home size={18} />,
      onClick: onHome,
    },
    {
      key: 'projects' as const,
      label: '项目',
      icon: <Folder size={18} />,
      onClick: onProjects,
    },
  ];

  return (
    <div className="flex h-full w-[56px] flex-none flex-col items-center bg-base-sidebar py-3">
      <button
        type="button"
        onClick={onExpand}
        title="展开侧边栏"
        className="grid h-9 w-9 place-items-center rounded-lg text-ink-95 transition hover:bg-line-6"
      >
        <AtomsMark size={20} />
      </button>

      <nav className="mt-3 flex flex-col items-center gap-1">
        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={item.onClick}
            title={item.label}
            aria-label={item.label}
            aria-current={section === item.key ? 'page' : undefined}
            className={`grid h-9 w-9 place-items-center rounded-lg transition ${
              section === item.key
                ? 'bg-line-6 text-ink-95'
                : 'text-ink-80 hover:bg-line-4 hover:text-ink-95'
            }`}
          >
            {item.icon}
          </button>
        ))}
      </nav>

      <div className="mt-auto flex flex-col items-center gap-3 pb-1">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            health?.ok ? 'bg-positive' : 'bg-ink-30'
          }`}
          title={health?.ok ? '服务在线' : '服务离线'}
        />
        <span title={`${user.email} · 展开侧边栏`}>
          <InitialAvatar size={24} label={userInitial(user)} />
        </span>
      </div>
    </div>
  );
}

export default function HomeSidebar({
  projects,
  section,
  user,
  onHome,
  onProjects,
  onOpenProject,
  onCollapse,
  onLogout,
}: Props) {
  const recent = projects.slice(0, 6);

  return (
    <aside className="flex h-full w-[270px] flex-none flex-col bg-base-sidebar">
      <div className="flex items-center justify-between px-4 pb-1 pt-4">
        <button
          type="button"
          onClick={onHome}
          title="回到首页"
          className="flex items-center gap-2 rounded-lg text-left transition hover:opacity-70"
        >
          <AtomsMark size={22} className="text-ink-95" />
          <span className="text-[16px] font-medium tracking-[-0.2px] text-ink-95">
            Atoms
          </span>
        </button>
        <button
          type="button"
          onClick={onCollapse}
          title="收起侧边栏"
          className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-6 hover:text-ink-80"
        >
          <PanelLeft size={17} />
        </button>
      </div>

      <nav className="mt-3 space-y-0.5 px-2">
        <NavItem
          icon={<Home size={17} />}
          label="首页"
          active={section === 'home'}
          onClick={onHome}
        />
        <NavItem icon={<Compass size={17} />} label="资源" placeholder />
        <NavItem
          icon={<Folder size={17} />}
          label="项目"
          active={section === 'projects'}
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
        <div className="flex h-7 items-center px-2 text-[12px] text-ink-55">
          最近
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto pb-2">
          {recent.length ? (
            recent.map((project) => (
              <button
                key={project.id}
                type="button"
                onClick={() => onOpenProject(project.id)}
                title={project.generating ? '正在处理' : undefined}
                className="flex h-9 w-full items-center gap-2 rounded-lg px-2 text-left text-[14px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
              >
                {project.generating ? (
                  <Spinner size={15} className="flex-none text-brand" />
                ) : (
                  <Chat size={15} className="flex-none text-ink-30" />
                )}
                <span className="truncate">{project.name}</span>
              </button>
            ))
          ) : (
            <p className="px-2 py-1.5 text-[12px] text-ink-30">尚无聊天记录</p>
          )}
        </div>
      </div>

      <div className="px-2 pb-3">
        <div className="mt-3 flex items-center gap-2 px-1">
          <InitialAvatar size={28} label={userInitial(user)} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-ink-95">
              {displayName(user)}
            </p>
            <p className="truncate text-[11px] text-ink-55" title={user.email}>
              {user.email}
            </p>
          </div>
          <button
            type="button"
            onClick={onLogout}
            title="退出登录"
            aria-label="退出登录"
            className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-6 hover:text-ink-95"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}
