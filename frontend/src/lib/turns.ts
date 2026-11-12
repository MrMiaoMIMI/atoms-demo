import type { Conversation, Execution } from "../types";

export interface Turn {
  id: string;
  user: Conversation | null;
  assistant: Conversation | null;
  executions: Execution[];
  live?: boolean;
}

function inWindow(createdAt: string | undefined, start: string, end: string): boolean {
  if (!start && !end) return false;
  const time = createdAt ?? "";
  if (start && time && time < start) return false;
  if (end && time && time > end) return false;
  return true;
}

/**
 * Executions are persisted before the assistant message, so we attach each
 * batch to the assistant message that follows the same user message. ISO
 * timestamps are used because conversation/execution ids live in different
 * tables and cannot be compared directly.
 */
export function buildTurns(conversations: Conversation[], executions: Execution[]): Turn[] {
  const messages = [...conversations].sort((a, b) => a.id - b.id);
  const steps = [...executions].sort((a, b) => a.id - b.id);
  const turns: Turn[] = [];
  const used = new Set<number>();
  let pendingUser: Conversation | null = null;
  let cursor = "";

  for (const message of messages) {
    if (message.role === "user") {
      pendingUser = message;
      continue;
    }

    const start = pendingUser?.created_at ?? cursor;
    const end = message.created_at ?? "";
    const matched = steps.filter((step) => {
      if (used.has(step.id)) return false;
      return inWindow(step.created_at, start, end);
    });
    matched.forEach((step) => used.add(step.id));

    turns.push({
      id: `turn-${message.id}`,
      user: pendingUser,
      assistant: message,
      executions: matched,
    });

    cursor = message.created_at ?? cursor;
    pendingUser = null;
  }

  const leftovers = steps.filter((step) => !used.has(step.id));

  if (pendingUser) {
    turns.push({
      id: `turn-pending-${pendingUser.id}`,
      user: pendingUser,
      assistant: null,
      executions: leftovers,
      live: true,
    });
  } else if (leftovers.length) {
    if (turns.length) {
      turns[turns.length - 1].executions.push(...leftovers);
    } else {
      turns.push({
        id: "turn-orphan",
        user: null,
        assistant: null,
        executions: leftovers,
      });
    }
  }

  return turns;
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
