import { AGENT_RAIL, agentFor } from "../lib/agents";

interface AvatarProps {
  agent?: string | null;
  size?: number;
  ringColor?: string;
  className?: string;
  title?: string;
  tooltip?: boolean;
}

export function AgentAvatar({
  agent,
  size = 32,
  ringColor = "rgba(12,12,12,0.06)",
  className = "",
  title,
  tooltip = false,
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

  return (
    <span
      tabIndex={0}
      className={`group relative inline-flex flex-none rounded-full outline-none focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:ring-offset-2 focus-visible:ring-offset-base ${className}`}
    >
      {shell}
      <span
        aria-hidden="true"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-40 mb-1.5 flex origin-bottom -translate-x-1/2 scale-95 items-center gap-1.5 whitespace-nowrap rounded-lg bg-[#1E1E20] px-2.5 py-1.5 opacity-0 shadow-float transition-[opacity,transform] duration-100 ease-out group-hover:visible group-hover:scale-100 group-hover:opacity-100 group-focus-visible:visible group-focus-visible:scale-100 group-focus-visible:opacity-100"
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
        <span className="absolute left-1/2 top-full h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[1px] bg-[#1E1E20]" />
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
