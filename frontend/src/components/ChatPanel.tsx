import type { KeyboardEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { agentFor } from "../lib/agents";
import { copyText } from "../lib/clipboard";
import { Markdown } from "../lib/markdown";
import type { Turn } from "../lib/turns";
import { summaryFromText, versionFromText } from "../lib/turns";
import { AgentAvatar } from "./Avatar";
import ExecutionSteps from "./ExecutionSteps";
import {
  ArrowUp,
  ChevronDown,
  Code,
  Copy,
  Plus,
  Stop,
} from "./Icons";

const QUICK_EDITS = [
  "把整体配色调整为更克制的黑白灰风格。",
  "增加一个搜索框，并按关键词过滤列表。",
  "把数据保存到 SQLite，刷新页面后仍然保留。",
];

function dayLabel(iso?: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return "今天";
  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" });
}

interface Props {
  turns: Turn[];
  running: boolean;
  error: string | null;
  onSend: (text: string) => void;
  onStop: () => void;
  onOpenCode: () => void;
}

export default function ChatPanel({
  turns,
  running,
  error,
  onSend,
  onStop,
  onOpenCode,
}: Props) {
  const [input, setInput] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [quickOpen, setQuickOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const signal = useMemo(
    () =>
      turns.reduce(
        (total, turn) =>
          total +
          (turn.assistant?.content.length ?? 0) +
          (turn.user?.content.length ?? 0) +
          turn.executions.length,
        0
      ),
    [turns]
  );

  useEffect(() => {
    if (!bottomRef.current) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [signal, running]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [input]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const next = distance < 90;
    bottomRef.current = next;
    setAtBottom(next);
  }

  function scrollToBottom() {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }

  function submit() {
    const text = input.trim();
    if (!text || running) return;
    setInput("");
    setQuickOpen(false);
    bottomRef.current = true;
    onSend(text);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  async function copyTurn(id: string, content: string) {
    const ok = await copyText(content);
    if (!ok) return;
    setCopied(id);
    window.setTimeout(() => setCopied(null), 1500);
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-base">
      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="h-full overflow-y-auto px-4 pb-3 pt-5"
        >
        {turns.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-brand shadow-pill">
              <Code size={22} />
            </span>
            <p className="mt-4 text-[15px] font-medium text-ink-95">描述你想构建的应用</p>
            <p className="mt-1.5 max-w-[300px] text-[12px] leading-[19px] text-ink-55">
              Planner 判断形态，Coder 生成代码，Deployer 启动预览。生成后继续对话即可修改。
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {QUICK_EDITS.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setInput(item);
                    textareaRef.current?.focus();
                  }}
                  className="rounded-full border border-line-6 bg-white px-3 py-1.5 text-[12px] text-ink-55 transition hover:border-line-12 hover:text-ink-80"
                >
                  {item.length > 18 ? `${item.slice(0, 18)}…` : item}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {turns.map((turn, index) => {
              const previousTurn = turns[index - 1];
              const day = dayLabel(turn.user?.created_at ?? turn.assistant?.created_at);
              const previousDay = dayLabel(
                previousTurn?.user?.created_at ?? previousTurn?.assistant?.created_at
              );
              const showDay = Boolean(day) && day !== previousDay;
              const assistantContent = turn.assistant?.content ?? "";
              const version = versionFromText(assistantContent);
              const persona = agentFor("orchestrator");
              const hasAssistant =
                Boolean(turn.assistant) || turn.live || turn.executions.length > 0;

              return (
                <div key={turn.id} className="space-y-4">
                  {showDay ? (
                    <div className="flex items-center gap-3 py-1 text-[12px] text-ink-30">
                      <span className="h-px flex-1 bg-line-4" />
                      {day}
                      <span className="h-px flex-1 bg-line-4" />
                    </div>
                  ) : null}

                  {turn.user ? (
                    <div className="flex justify-end">
                      <div className="max-w-[86%] whitespace-pre-wrap break-words rounded-[12px] rounded-tl-none bg-line-4 px-3 py-2.5 text-[16px] leading-[24px] text-ink-80">
                        {turn.user.content}
                      </div>
                    </div>
                  ) : null}

                  {hasAssistant ? (
                    <div className="flex items-start gap-3">
                      <AgentAvatar
                        agent="orchestrator"
                        size={32}
                        ringColor="#F6F6F6"
                        className="mt-0.5"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 text-[14px] leading-[22px]">
                          <span className="font-medium text-ink-95">{persona.name}</span>
                          <span className="text-ink-30">|</span>
                          <span className="text-ink-55">{persona.role}</span>
                        </div>

                        <ExecutionSteps executions={turn.executions} live={turn.live} />

                        {assistantContent ? (
                          <Markdown content={assistantContent} className="mt-3" />
                        ) : turn.live ? (
                          <div className="mt-3 flex items-center gap-2 text-[14px] text-ink-55">
                            <span className="flex gap-1">
                              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-30 [animation-delay:-0.2s]" />
                              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-30 [animation-delay:-0.1s]" />
                              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-30" />
                            </span>
                            {turn.executions.some((execution) => execution.status === "running")
                              ? "正在生成…"
                              : "等待智能体响应…"}
                          </div>
                        ) : null}

                        {turn.assistant && version ? (
                          <button
                            type="button"
                            onClick={onOpenCode}
                            title="查看代码"
                            className="mt-3 flex w-full max-w-[380px] items-start justify-between gap-3 rounded-[12px] border border-brand bg-[rgba(61,99,255,0.12)] px-3 py-2.5 text-left transition hover:bg-[rgba(61,99,255,0.16)]"
                          >
                            <div className="min-w-0">
                              <p className="text-[14px] font-medium leading-[22px] text-ink-95">
                                版本 {version}
                              </p>
                              <p className="mt-0.5 line-clamp-2 text-[13px] leading-[20px] text-ink-80">
                                {summaryFromText(assistantContent) || "构建完成"}
                              </p>
                            </div>
                            <Code size={16} className="mt-0.5 flex-none text-brand-text" />
                          </button>
                        ) : null}

                        {turn.assistant ? (
                          <div className="mt-3 flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => void copyTurn(turn.id, assistantContent)}
                              title="复制"
                              className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                            >
                              <Copy size={15} />
                            </button>
                            <button
                              type="button"
                              onClick={onOpenCode}
                              title="查看代码"
                              className="grid h-7 w-7 place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
                            >
                              <Code size={15} />
                            </button>
                            {copied === turn.id ? (
                              <span className="ml-1 text-[11px] text-ink-30">已复制</span>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                </div>
              );
            })}
          </div>
        )}

        </div>

        {!atBottom && turns.length ? (
          <button
            type="button"
            onClick={scrollToBottom}
            title="滚动到底部"
            className="absolute bottom-3 left-1/2 z-10 grid h-8 w-8 -translate-x-1/2 place-items-center rounded-full border border-line-6 bg-white text-ink-55 shadow-float transition hover:text-ink-95"
          >
            <ChevronDown size={16} />
          </button>
        ) : null}
      </div>

      <div className="flex-none px-2 pb-2">
        {error ? (
          <p className="mb-2 rounded-xl border border-danger/20 bg-danger/5 px-3 py-2 text-[12px] leading-[18px] text-danger">
            {error}
          </p>
        ) : null}

        <div className="rounded-[24px] border border-line-4 bg-white p-3 shadow-composer transition focus-within:border-line-8">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            maxLength={4000}
            placeholder={running ? "Agent 正在生成，可以先描述下一轮修改…" : "让智能体团队实现你的想法"}
            className="max-h-[140px] min-h-[48px] w-full resize-none bg-transparent px-1 text-[14px] leading-[22px] text-ink-95 outline-none placeholder:text-ink-30"
          />

          <div className="mt-1 flex items-center justify-between gap-2">
            <div className="relative flex items-center gap-1">
              <button
                type="button"
                onClick={() => setQuickOpen((value) => !value)}
                title="快捷修改"
                className="grid h-8 w-8 place-items-center rounded-full text-ink-80 transition hover:bg-line-4"
              >
                <Plus size={19} />
              </button>

              {quickOpen ? (
                <>
                  <button
                    type="button"
                    aria-hidden="true"
                    className="fixed inset-0 z-20 cursor-default"
                    onClick={() => setQuickOpen(false)}
                  />
                  <div className="absolute bottom-full left-0 z-30 mb-2 w-[280px] rounded-xl border border-line-6 bg-white p-2 shadow-float">
                    <p className="px-2 py-1 text-[12px] text-ink-55">快捷修改</p>
                    {QUICK_EDITS.map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => {
                          setQuickOpen(false);
                          setInput(item);
                          textareaRef.current?.focus();
                        }}
                        className="block w-full rounded-lg px-2 py-2 text-left text-[12px] leading-[18px] text-ink-80 transition hover:bg-line-4 hover:text-ink-95"
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </>
              ) : null}
            </div>

            <div className="flex items-center gap-1.5">
              {running ? (
                <button
                  type="button"
                  onClick={onStop}
                  title="停止生成"
                  className="grid h-8 w-8 place-items-center rounded-full bg-ink-95 text-white transition hover:bg-ink-80"
                >
                  <Stop size={14} />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={submit}
                  disabled={!input.trim()}
                  title="发送"
                  className="grid h-8 w-8 place-items-center rounded-full bg-brand text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-line-12 disabled:text-ink-30"
                >
                  <ArrowUp size={17} />
                </button>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
