import type { AgentKey, Conversation, Execution } from "../types";
import { agentFor } from "./agents";

export interface ChatGroup {
  id: string;
  kind: "user" | "agent";
  user?: Conversation;
  agent?: AgentKey;
  runId?: string;
  executions: Execution[];
  messages: string[];
  createdAt?: string;
  live?: boolean;
  status?: "running" | "success" | "warning" | "error";
  index?: number;
}

function inWindow(createdAt: string | undefined, start: string, end: string): boolean {
  if (!start && !end) return false;
  const time = createdAt ?? "";
  if (start && time && time < start) return false;
  if (end && time && time > end) return false;
  return true;
}

function groupCreatedAt(
  executions: Execution[],
  messages: { created_at?: string }[]
): string | undefined {
  return (
    executions[0]?.created_at ??
    messages[0]?.created_at ??
    undefined
  );
}

/**
 * Group persisted conversations into Atoms-style agent groups.
 *
 * New rows carry agent + run_id. Legacy rows have neither: consecutive
 * assistant messages are merged under Mike and executions are attached by
 * their timestamp window (the behaviour of the old turn view).
 */
function orderMessages(conversations: Conversation[]): Conversation[] {
  const sorted = [...conversations].sort((a, b) => a.id - b.id);
  const ordered: Conversation[] = [];
  let block: Conversation[] = [];
  const flush = () => {
    block.sort(
      (a, b) =>
        (a.run_index ?? Number.MAX_SAFE_INTEGER) -
          (b.run_index ?? Number.MAX_SAFE_INTEGER) || a.id - b.id
    );
    ordered.push(...block);
    block = [];
  };
  for (const message of sorted) {
    if (message.role === "user") {
      flush();
      ordered.push(message);
    } else {
      block.push(message);
    }
  }
  flush();
  return ordered;
}

export function buildGroups(
  conversations: Conversation[],
  executions: Execution[]
): ChatGroup[] {
  const messages = orderMessages(conversations);
  const steps = [...executions].sort((a, b) => a.id - b.id);
  const byRun = new Map<string, Execution[]>();
  const legacySteps: Execution[] = [];

  for (const step of steps) {
    if (step.run_id) {
      const list = byRun.get(step.run_id) ?? [];
      list.push(step);
      byRun.set(step.run_id, list);
    } else {
      legacySteps.push(step);
    }
  }

  const groups: ChatGroup[] = [];
  const used = new Set<number>();
  const runsWithMessages = new Set<string>();
  let current: ChatGroup | null = null;
  let cursor = "";

  for (const message of messages) {
    if (message.role === "user") {
      groups.push({
        id: `user-${message.id}`,
        kind: "user",
        user: message,
        executions: [],
        messages: [],
        createdAt: message.created_at,
      });
      current = null;
      cursor = message.created_at ?? cursor;
      continue;
    }

    const agent = agentFor(message.agent).key;
    const runId = message.run_id || undefined;
    let matched: Execution[] = [];
    if (runId) {
      matched = byRun.get(runId) ?? [];
      runsWithMessages.add(runId);
    } else {
      matched = legacySteps.filter(
        (step) => !used.has(step.id) && inWindow(step.created_at, cursor, message.created_at ?? "")
      );
      matched.forEach((step) => used.add(step.id));
    }

    const mergeLegacy =
      current?.kind === "agent" &&
      current.agent === agent &&
      !runId &&
      !current.runId;

    if (mergeLegacy && current) {
      current.messages.push(message.content);
      current.executions.push(...matched);
      current.createdAt = current.createdAt ?? message.created_at;
    } else {
      const group: ChatGroup = {
        id: `run-${runId ?? `legacy-${message.id}`}`,
        kind: "agent",
        agent,
        runId,
        executions: matched,
        messages: [message.content],
        createdAt: groupCreatedAt(matched, [message]),
      };
      groups.push(group);
      current = group;
    }
    cursor = message.created_at ?? cursor;
  }

  const leftovers = legacySteps.filter((step) => !used.has(step.id));
  if (leftovers.length) {
    const lastAgent = [...groups].reverse().find((group) => group.kind === "agent");
    if (lastAgent) {
      lastAgent.executions.push(...leftovers);
      lastAgent.createdAt = lastAgent.createdAt ?? groupCreatedAt(leftovers, []);
    } else {
      groups.push({
        id: "run-legacy-orphan",
        kind: "agent",
        agent: "mike",
        executions: leftovers,
        messages: [],
        createdAt: groupCreatedAt(leftovers, []),
      });
    }
  }

  // A run that is still in flight has execution rows but no final assistant
  // message yet. Surface it immediately so a re-opened workspace can show who
  // is working right now instead of waiting for the next live event.
  const pendingRuns = [...byRun.entries()]
    .filter(([runId]) => !runsWithMessages.has(runId))
    .sort((a, b) => (a[1][0]?.id ?? 0) - (b[1][0]?.id ?? 0));
  for (const [runId, runSteps] of pendingRuns) {
    const running = runSteps.some((step) => step.status === "running");
    groups.push({
      id: `run-${runId}`,
      kind: "agent",
      agent: agentFor(runSteps[0]?.agent).key,
      runId,
      executions: runSteps,
      messages: [],
      createdAt: groupCreatedAt(runSteps, []),
      live: running,
      status: running ? "running" : undefined,
    });
  }

  return groups;
}

export function versionFromText(text: string | null | undefined): number | null {
  if (!text) return null;
  const match = /(?:^|\s)v(\d+)/i.exec(text) ?? /版本\s*(\d+)/.exec(text);
  return match ? Number(match[1]) : null;
}

export function summaryFromText(text: string | null | undefined): string {
  if (!text) return "";
  const firstLine = text.split("\n")[0]?.trim() ?? "";
  const colon = firstLine.search(/[：:]/);
  const summary = colon >= 0 ? firstLine.slice(colon + 1).trim() : firstLine;
  return summary.length > 90 ? `${summary.slice(0, 90)}…` : summary;
}
