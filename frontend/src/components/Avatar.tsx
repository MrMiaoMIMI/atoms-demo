import { useEffect, useState } from "react";
import { AGENTS, AGENT_RAIL, agentFor } from "../lib/agents";
import type { AgentKey } from "../types";
import { MoreHorizontal } from "./Icons";

interface AvatarProps {
  agent?: string | null;
  size?: number;
  ringColor?: string;
  className?: string;
  title?: string;
  tooltip?: boolean;
  tooltipSide?: "top" | "bottom";
}

export function AgentAvatar({
  agent,
  size = 32,
  ringColor = "rgba(12,12,12,0.06)",
  className = "",
  title,
  tooltip = false,
  tooltipSide = "top",
}: AvatarProps) {
  const persona = agentFor(agent);
  const label = title ?? `${persona.name} · ${persona.role}`;

  const shell = (
    <span
      role="img"
      aria-label={label}
      className={`inline-grid flex-none place-items-center overflow-hidden rounded-full border-2 ${
        tooltip ? "" : className
      }`}
      style={{
        width: size,
        height: size,
        background: persona.bg,
        borderColor: ringColor,
        lineHeight: 1,
      }}
    >
      <img
        src={persona.avatar}
        alt=""
        draggable={false}
        className="h-full w-full object-cover"
        style={{ transform: "scale(1.08)" }}
      />
    </span>
  );

  if (!tooltip) return shell;

  const below = tooltipSide === "bottom";

  return (
    <span
      tabIndex={0}
      className={`group relative inline-flex flex-none rounded-full outline-none focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:ring-offset-2 focus-visible:ring-offset-base ${className}`}
    >
      {shell}
      <span
        aria-hidden="true"
        className={`pointer-events-none invisible absolute left-1/2 z-40 flex -translate-x-1/2 scale-95 items-center gap-1.5 whitespace-nowrap rounded-lg bg-[#1E1E20] px-2.5 py-1.5 opacity-0 shadow-float transition-[opacity,transform] duration-100 ease-out group-hover:visible group-hover:scale-100 group-hover:opacity-100 group-focus-visible:visible group-focus-visible:scale-100 group-focus-visible:opacity-100 ${
          below
            ? "top-full mt-1.5 origin-top"
            : "bottom-full mb-1.5 origin-bottom"
        }`}
      >
        <span
          className="h-1.5 w-1.5 flex-none rounded-full"
          style={{ background: persona.color }}
        />
        <span className="text-[12px] font-medium leading-none text-white">
          {persona.name}
        </span>
        <span
          className="text-[11px] font-medium leading-none"
          style={{ color: persona.color }}
        >
          {persona.role}
        </span>
        <span
          className={`absolute left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 rounded-[1px] bg-[#1E1E20] ${
            below ? "bottom-full translate-y-1/2" : "top-full -translate-y-1/2"
          }`}
        />
      </span>
    </span>
  );
}

export function AgentRail({
  size = 46,
  ringColor = "#F6F6F6",
  className = "",
}: {
  size?: number;
  ringColor?: string;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      {AGENT_RAIL.map((persona, index) => (
        <span
          key={persona.key}
          className="relative inline-flex rounded-full hover:z-30 focus-within:z-30"
          style={{ marginLeft: index === 0 ? 0 : -Math.round(size * 0.22) }}
        >
          <AgentAvatar
            agent={persona.key}
            size={size}
            ringColor={ringColor}
            tooltip
          />
        </span>
      ))}
    </div>
  );
}

export function PresenceAvatars({
  agents = ["mike", "bob", "alex"],
  size = 30,
  ringColor = "#F6F6F6",
}: {
  agents?: string[];
  size?: number;
  ringColor?: string;
}) {
  return (
    <div className="flex items-center">
      {agents.map((agent, index) => (
        <span
          key={`${agent}-${index}`}
          className="inline-flex rounded-full"
          style={{ marginLeft: index === 0 ? 0 : -8 }}
        >
          <AgentAvatar agent={agent} size={size} ringColor={ringColor} />
        </span>
      ))}
    </div>
  );
}

/**
 * Top-bar presence row: the local user, then the agents that have actually
 * replied in this project. Agents that have never chatted are listed behind
 * the "..." button as offline members.
 */
export function PresenceBar({
  activeAgents,
  size = 28,
  ringColor = "#F6F6F6",
}: {
  activeAgents: AgentKey[];
  size?: number;
  ringColor?: string;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const active = AGENTS.filter((persona) => activeAgents.includes(persona.key));
  const offline = AGENTS.filter(
    (persona) => !activeAgents.includes(persona.key)
  );
  const overlap = Math.round(size * 0.3);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <div className="flex items-center">
      <span
        className="inline-flex flex-none rounded-full"
        title="你 · 项目所有者"
      >
        <InitialAvatar size={size} label="你" />
      </span>

      {active.map((persona, index) => (
        <span
          key={persona.key}
          className="relative inline-flex rounded-full hover:z-30 focus-within:z-30"
          style={{ marginLeft: index === 0 ? -overlap : -8 }}
        >
          <AgentAvatar
            agent={persona.key}
            size={size}
            ringColor={ringColor}
            tooltip
            tooltipSide="bottom"
          />
        </span>
      ))}

      {offline.length ? (
        <div className="relative inline-flex">
          <button
            type="button"
            onClick={() => setMenuOpen((value) => !value)}
            title={`离线智能体（${offline.length}）`}
            aria-expanded={menuOpen}
            aria-haspopup="true"
            className="grid flex-none place-items-center rounded-full border-2 bg-white text-ink-55 transition hover:text-ink-95"
            style={{
              width: size,
              height: size,
              marginLeft: active.length ? -8 : -overlap,
              borderColor: ringColor,
            }}
          >
            <MoreHorizontal size={Math.round(size * 0.5)} />
          </button>

          {menuOpen ? (
            <>
              <button
                type="button"
                aria-hidden="true"
                tabIndex={-1}
                className="fixed inset-0 z-30 cursor-default"
                onClick={() => setMenuOpen(false)}
              />
              <div className="absolute right-0 top-full z-40 mt-2 w-[220px] rounded-xl border border-line-6 bg-white p-2 shadow-float">
                <p className="px-2 py-1 text-[11px] text-ink-55">
                  离线智能体
                </p>
                {offline.map((persona) => (
                  <div
                    key={persona.key}
                    className="flex items-center gap-2 rounded-lg px-2 py-1.5"
                  >
                    <AgentAvatar
                      agent={persona.key}
                      size={24}
                      ringColor="#FFFFFF"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] font-medium text-ink-95">
                        {persona.name}
                      </p>
                      <p className="truncate text-[11px] text-ink-30">
                        {persona.role}
                      </p>
                    </div>
                    <span className="flex-none rounded-full bg-line-4 px-1.5 py-0.5 text-[10px] text-ink-55">
                      离线
                    </span>
                  </div>
                ))}
                <p className="mt-1 border-t border-line-4 px-2 pt-2 text-[11px] leading-[16px] text-ink-30">
                  这些智能体还没有参与本项目聊天，输入 @ 可以邀请他们。
                </p>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function InitialAvatar({
  size = 30,
  label = "A",
  className = "",
}: {
  size?: number;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={`inline-grid flex-none place-items-center rounded-full bg-brand text-white ${className}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.42), fontWeight: 500 }}
    >
      {label}
    </span>
  );
}
