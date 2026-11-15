import { useEffect, useMemo, useRef, useState } from "react";
import { agentFor } from "../lib/agents";
import { copyText } from "../lib/clipboard";
import type { ChatGroup } from "../lib/groups";
import { summaryFromText, versionFromText } from "../lib/groups";
import { Markdown } from "../lib/markdown";
import { AgentAvatar } from "./Avatar";
import ExecutionSteps from "./ExecutionSteps";
import MentionComposer from "./MentionComposer";
import MentionText from "./MentionText";
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

function timeLabel(iso?: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

interface Props {
  groups: ChatGroup[];
  running: boolean;
  error: string | null;
  onSend: (text: string) => void;
  onStop: () => void;
  onOpenCode: () => void;
}

export default function ChatPanel({
  groups,
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
      groups.reduce(
        (total, group) =>
          total +
          group.executions.length +
          group.messages.reduce((sum, message) => sum + message.length, 0) +
          (group.user?.content.length ?? 0),
        0
      ),
    [groups]
  );

  useEffect(() => {
    if (!bottomRef.current) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [signal, running]);

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

  async function copyGroup(id: string, content: string) {
    const ok = await copyText(content);
    if (!ok) return;
    setCopied(id);
    window.setTimeout(() => setCopied(null), 1500);
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-base">
      {error ? (
        <div
          role="alert"
          className="mx-3 mt-3 flex-none rounded-xl border border-danger/20 bg-danger/5 px-3 py-2.5 text-[12px] leading-[18px] text-danger"
        >
          <p className="font-medium">本轮生成未完成</p>
          <p className="mt-0.5 whitespace-pre-wrap break-words">{error}</p>
        </div>
      ) : null}
      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="h-full overflow-y-auto px-4 pb-3 pt-5"
        >
          {groups.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center px-6 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-brand shadow-pill">
                <Code size={22} />
              </span>
              <p className="mt-4 text-[15px] font-medium text-ink-95">描述你想构建的应用</p>
              <p className="mt-1.5 max-w-[320px] text-[12px] leading-[19px] text-ink-55">
                Mike 拆解需求，Bob 设计架构，Alex 写代码并启动预览。也可以输入 @
                直接指定某一位智能体。
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
              {groups.map((group, index) => {
                const previous = groups[index - 1];
                const day = dayLabel(group.createdAt ?? group.user?.created_at);
                const previousDay = dayLabel(previous?.createdAt ?? previous?.user?.created_at);
                const showDay = Boolean(day) && day !== previousDay;

                if (group.kind === "user") {
                  return (
                    <div key={group.id} className="space-y-4">
                      {showDay ? (
                        <div className="flex items-center gap-3 py-1 text-[12px] text-ink-30">
                          <span className="h-px flex-1 bg-line-4" />
                          {day}
                          <span className="h-px flex-1 bg-line-4" />
                        </div>
                      ) : null}
                      <div className="flex justify-end">
                        <div className="max-w-[86%] whitespace-pre-wrap break-words rounded-[12px] rounded-tl-none bg-line-4 px-3 py-2.5 text-[16px] leading-[24px] text-ink-80">
                          <MentionText text={group.user?.content ?? ""} />
                        </div>
                      </div>
                    </div>
                  );
                }

                const persona = agentFor(group.agent);
                const content = group.messages.join("\n\n");
                const buildMessage = group.messages.find((message) =>
                  /^已完成\s*v\d+/i.test(message.trim())
                );
                const version = buildMessage ? versionFromText(buildMessage) : null;
                const hasBody = group.messages.length > 0 || group.executions.length > 0;

                return (
                  <div key={group.id} className="space-y-4">
                    {showDay ? (
                      <div className="flex items-center gap-3 py-1 text-[12px] text-ink-30">
                        <span className="h-px flex-1 bg-line-4" />
                        {day}
                        <span className="h-px flex-1 bg-line-4" />
                      </div>
                    ) : null}

                    <div className="group flex items-start gap-3">
                      <AgentAvatar
                        agent={persona.key}
                        size={32}
                        ringColor="#F6F6F6"
                        className="mt-0.5"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex h-[22px] items-center gap-2 text-[14px] leading-[22px]">
                          <span className="font-medium text-ink-95">{persona.name}</span>
                          <span className="h-3 w-px bg-line-8" />
                          <span className="text-[12px] text-ink-55">{persona.role}</span>
                          <span className="hidden text-[12px] text-ink-30 group-hover:inline">
                            {group.live ? "正在处理" : timeLabel(group.createdAt)}
                          </span>
                        </div>

                        <ExecutionSteps executions={group.executions} live={group.live} />

                        {group.messages.map((message, messageIndex) => (
                          <Markdown
                            key={`${group.id}-m-${messageIndex}`}
                            content={message}
                            className={messageIndex === 0 ? "mt-3" : "mt-4"}
                          />
                        ))}

                        {group.live && !group.messages.length ? (
                          <div className="mt-3 flex items-center gap-2 text-[14px] text-ink-55">
                            <span className="flex gap-1">
                              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-30 [animation-delay:-0.2s]" />
                              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-30 [animation-delay:-0.1s]" />
                              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-30" />
                            </span>
                            正在生成…
                          </div>
                        ) : null}

                        {hasBody && version ? (
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
                                {summaryFromText(buildMessage) || "构建完成"}
                              </p>
                            </div>
                            <Code size={16} className="mt-0.5 flex-none text-brand-text" />
                          </button>
                        ) : null}

                        {group.messages.length ? (
                          <div className="mt-3 flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => void copyGroup(group.id, content)}
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
                            {copied === group.id ? (
                              <span className="ml-1 text-[11px] text-ink-30">已复制</span>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {!atBottom && groups.length ? (
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
        <div className="rounded-[24px] border border-line-4 bg-white p-3 shadow-composer transition focus-within:border-line-8">
          <MentionComposer
            value={input}
            onChange={setInput}
            onSubmit={submit}
            textareaRef={textareaRef}
            rows={2}
            maxLength={4000}
            maxHeight={140}
            placeholder={
              running
                ? "Agent 正在处理，可以先描述下一轮修改…"
                : "让智能体团队实现你的想法，输入 @ 指定成员"
            }
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
                  className="grid h-8 w-8 place-items-center rounded-full bg-brand text-white transition hover:bg-brand-600"
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
