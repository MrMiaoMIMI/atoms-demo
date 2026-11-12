export interface AgentPersona {
  key: string;
  name: string;
  role: string;
  emoji: string;
  bg: string;
}

export const AGENTS: AgentPersona[] = [
  { key: "orchestrator", name: "Mike", role: "团队领导", emoji: "🐶", bg: "#F7DFC4" },
  { key: "planner", name: "Emma", role: "产品规划", emoji: "🐱", bg: "#FBE7B3" },
  { key: "coder", name: "Alex", role: "工程师", emoji: "🐻", bg: "#E9E4DE" },
  { key: "reviewer", name: "Iris", role: "质量审查", emoji: "🐰", bg: "#F9DCE8" },
  { key: "deployer", name: "Bob", role: "发布工程师", emoji: "🐼", bg: "#E6E8EF" },
  { key: "researcher", name: "Sophie", role: "研究员", emoji: "🦊", bg: "#DCEBFB" },
  { key: "designer", name: "Leo", role: "设计师", emoji: "🐸", bg: "#DFF0D8" },
  { key: "data", name: "Nina", role: "数据分析", emoji: "🐯", bg: "#E8DDF7" },
];

const BY_KEY = new Map(AGENTS.map((agent) => [agent.key, agent]));

export function agentFor(raw: string | null | undefined): AgentPersona {
  const value = (raw ?? "").toLowerCase();
  if (BY_KEY.has(value)) return BY_KEY.get(value)!;
  if (value.includes("plan")) return BY_KEY.get("planner")!;
  if (value.includes("cod") || value.includes("engineer")) return BY_KEY.get("coder")!;
  if (value.includes("review") || value.includes("qa")) return BY_KEY.get("reviewer")!;
  if (value.includes("deploy") || value.includes("publish")) return BY_KEY.get("deployer")!;
  if (value.includes("research")) return BY_KEY.get("researcher")!;
  if (value.includes("design")) return BY_KEY.get("designer")!;
  if (value.includes("data")) return BY_KEY.get("data")!;
  return BY_KEY.get("orchestrator")!;
}

export function agentKeyFromName(name: string | null | undefined): string {
  return agentFor(name).key;
}

export const AGENT_RAIL = AGENTS;
