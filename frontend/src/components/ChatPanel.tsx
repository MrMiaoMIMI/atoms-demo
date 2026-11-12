import { useEffect, useRef, useState } from "react";
import type { Conversation } from "../types";
import { Send, Sparkle, Stop } from "./Icons";

interface Props {
  messages: Conversation[];
  running: boolean;
  error: string | null;
  onSend: (text: string) => void;
  onStop: () => void;
}

export default function ChatPanel({ messages, running, error, onSend, onStop }: Props) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, running]);

  function submit() {
    const text = input.trim();
    if (!text || running) return;
    setInput("");
    onSend(text);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
        {messages.length === 0 ? (
          <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
            <div className="mb-3 grid h-9 w-9 place-items-center rounded-xl bg-accent/15 text-accent-soft">
              <Sparkle />
            </div>
            <p className="text-sm font-medium text-slate-200">描述你想构建的应用</p>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
              Planner 会拆解需求，Coder 逐文件生成代码，Reviewer 检查后由 Deployer 发布。生成完成后还能继续对话修改。
            </p>
          </div>
        ) : null}

        {messages.map((message) => {
          const isUser = message.role === "user";
          return (
            <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
              {!isUser ? (
                <div className="mr-2 mt-0.5 grid h-7 w-7 flex-none place-items-center rounded-lg bg-gradient-to-br from-accent to-mint text-ink-950">
                  <Sparkle className="h-3.5 w-3.5" />
                </div>
              ) : null}
              <div
                className={`max-w-[86%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
                  isUser
                    ? "rounded-br-md border border-accent/25 bg-accent/15 text-slate-100"
                    : "rounded-bl-md border border-white/10 bg-white/[0.035] text-slate-300"
                }`}
              >
                {message.content}
              </div>
            </div>
          );
        })}

        {running ? (
          <div className="flex justify-start">
            <div className="mr-2 mt-0.5 grid h-7 w-7 flex-none place-items-center rounded-lg bg-gradient-to-br from-accent to-mint text-ink-950">
              <Sparkle className="h-3.5 w-3.5" />
            </div>
            <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.035] px-4 py-3">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-soft [animation-delay:-0.2s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-soft [animation-delay:-0.1s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-soft" />
            </div>
          </div>
        ) : null}
      </div>

      <div className="flex-none border-t border-white/5 p-3">
        {error ? (
          <div className="mb-2 rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-[11px] leading-relaxed text-rose-200">
            {error}
          </div>
        ) : null}
        <div className="rounded-2xl border border-white/10 bg-ink-950/70 p-2 transition focus-within:border-accent/50">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            rows={2}
            placeholder={running ? "Agent 正在生成，稍候…" : "继续描述修改需求，例如：把主色调换成暖色…"}
            className="w-full resize-none bg-transparent px-2 py-1.5 text-[13px] leading-relaxed text-slate-200 outline-none placeholder:text-slate-600"
          />
          <div className="flex items-center justify-between gap-2 px-1">
            <span className="text-[10px] text-slate-600">Enter 发送 · Shift+Enter 换行</span>
            {running ? (
              <button
                type="button"
                onClick={onStop}
                className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/25 bg-rose-400/10 px-3 py-1.5 text-[11px] font-medium text-rose-200 transition hover:bg-rose-400/20"
              >
                <Stop className="h-3 w-3" />
                停止
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={!input.trim()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-[11px] font-semibold text-white transition hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-35"
              >
                <Send className="h-3 w-3" />
                发送
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
