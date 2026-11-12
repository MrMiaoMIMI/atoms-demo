import type { AgentKey } from "../types";

export interface AgentPersona {
  key: AgentKey;
  name: string;
  role: string;
  avatar: string;
  bg: string;
  ring: string;
}

export const AGENTS: AgentPersona[] = [
  {
    key: "mike",
    name: "Mike",
    role: "团队领导",
    avatar: "/agents/mike.webp",
    bg: "#F7DFC4",
    ring: "#F1D3B3",
  },
  {
    key: "bob",
    name: "Bob",
    role: "架构师",
    avatar: "/agents/bob.webp",
    bg: "#E9E4DE",
    ring: "#DCD4CB",
  },
  {
    key: "alex",
    name: "Alex",
    role: "工程师",
    avatar: "/agents/alex.webp",
    bg: "#DCEBFB",
    ring: "#C9DFF7",
  },
];

const BY_KEY = new Map(AGENTS.map((agent) => [agent.key, agent]));

export const AGENT_KEYS = AGENTS.map((agent) => agent.key);

export function agentFor(raw: string | null | undefined): AgentPersona {
  const value = (raw ?? "").toLowerCase();
  if (BY_KEY.has(value as AgentKey)) return BY_KEY.get(value as AgentKey)!;
  for (const persona of BY_KEY.values()) {
    if (value === persona.name.toLowerCase()) return persona;
  }
  if (value.includes("bob") || value.includes("architect")) return BY_KEY.get("bob")!;
  if (value.includes("alex") || value.includes("engineer")) return BY_KEY.get("alex")!;
  return BY_KEY.get("mike")!;
}

export function agentKeyFromName(name: string | null | undefined): AgentKey {
  return agentFor(name).key;
}

export function isAgentKey(value: string | null | undefined): value is AgentKey {
  return value === "mike" || value === "bob" || value === "alex";
}

export const AGENT_RAIL = AGENTS;
