import { AGENT_RAIL, agentFor } from "../lib/agents";

interface AvatarProps {
  agent?: string | null;
  size?: number;
  ringColor?: string;
  className?: string;
  title?: string;
}

export function AgentAvatar({
  agent,
  size = 32,
  ringColor = "rgba(12,12,12,0.06)",
  className = "",
  title,
}: AvatarProps) {
  const persona = agentFor(agent);
  return (
    <span
      title={title ?? `${persona.name} · ${persona.role}`}
      className={`inline-grid flex-none place-items-center overflow-hidden rounded-full border-2 ${className}`}
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
          className="inline-flex rounded-full"
          style={{ marginLeft: index === 0 ? 0 : -Math.round(size * 0.22) }}
        >
          <AgentAvatar
            agent={persona.key}
            size={size}
            ringColor={ringColor}
            title={`${persona.name} · ${persona.role}`}
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
