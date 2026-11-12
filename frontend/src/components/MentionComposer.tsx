import type { KeyboardEvent, RefObject } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AGENTS } from "../lib/agents";
import { AgentAvatar } from "./Avatar";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  rows?: number;
  maxLength?: number;
  maxHeight?: number;
  disabled?: boolean;
  autoFocus?: boolean;
  className?: string;
  textareaRef?: RefObject<HTMLTextAreaElement>;
}

function mentionQuery(value: string, cursor: number): { start: number; query: string } | null {
  const before = value.slice(0, cursor);
  const at = before.lastIndexOf("@");
  if (at < 0) return null;
  const query = before.slice(at + 1);
  if (query.length > 12 || !/^[A-Za-z]*$/.test(query)) return null;
  const prev = at > 0 ? before[at - 1] : "";
  if (prev && /[A-Za-z0-9]/.test(prev)) return null;
  return { start: at, query };
}

export default function MentionComposer({
  value,
  onChange,
  onSubmit,
  placeholder,
  rows = 2,
  maxLength = 4000,
  maxHeight = 160,
  disabled = false,
  autoFocus = false,
  className = "",
  textareaRef,
}: Props) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const ref = textareaRef ?? internalRef;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [triggerStart, setTriggerStart] = useState<number | null>(null);
  // True while an IME (e.g. Chinese/Japanese input) is composing. Enter there
  // confirms the candidate, it must never submit the message.
  const composingRef = useRef(false);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return AGENTS;
    return AGENTS.filter(
      (agent) =>
        agent.name.toLowerCase().includes(needle) ||
        agent.role.toLowerCase().includes(needle)
    );
  }, [query]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, [value, maxHeight, ref]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  function syncCursor(text: string, cursor: number | null) {
    if (cursor == null || disabled) {
      setOpen(false);
      return;
    }
    const match = mentionQuery(text, cursor);
    if (!match) {
      setOpen(false);
      return;
    }
    setTriggerStart(match.start);
    setQuery(match.query);
    setActive(0);
    setOpen(true);
  }

  function selectAgent(index: number) {
    const persona = filtered[index];
    const el = ref.current;
    if (!persona || triggerStart == null) return;
    const cursor = el?.selectionStart ?? value.length;
    const before = value.slice(0, triggerStart);
    const after = value.slice(cursor);
    const next = `${before}@${persona.name} ${after}`;
    onChange(next);
    setOpen(false);
    requestAnimationFrame(() => {
      el?.focus();
      const position = before.length + persona.name.length + 2;
      el?.setSelectionRange(position, position);
    });
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Safari reports isComposing=false and keyCode=229 when Enter ends a
    // composition, so check the ref and the legacy keyCode as well.
    if (composingRef.current || event.nativeEvent.isComposing || event.keyCode === 229) {
      return;
    }
    if (open) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (filtered.length) setActive((index) => (index + 1) % filtered.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        if (filtered.length) {
          setActive((index) => (index - 1 + filtered.length) % filtered.length);
        }
        return;
      }
      if ((event.key === "Enter" || event.key === "Tab") && filtered.length) {
        event.preventDefault();
        selectAgent(active);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <textarea
        ref={ref}
        value={value}
        rows={rows}
        maxLength={maxLength}
        disabled={disabled}
        autoFocus={autoFocus}
        placeholder={placeholder}
        onChange={(event) => {
          const next = event.target.value;
          onChange(next);
          if (
            !composingRef.current &&
            !(event.nativeEvent as InputEvent).isComposing
          ) {
            syncCursor(next, event.target.selectionStart);
          }
        }}
        onCompositionStart={() => {
          composingRef.current = true;
        }}
        onCompositionEnd={(event) => {
          composingRef.current = false;
          syncCursor(event.currentTarget.value, event.currentTarget.selectionStart);
        }}
        onClick={(event) => syncCursor(value, event.currentTarget.selectionStart)}
        onKeyUp={(event) => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            syncCursor(value, event.currentTarget.selectionStart);
          }
        }}
        onKeyDown={handleKeyDown}
        onBlur={() => {
          // Keep the menu usable with the mouse: selection is handled on
          // mousedown, and the document listener closes it on outside clicks.
        }}
        className={className}
      />

      {open ? (
        <div
          className="absolute bottom-full left-0 z-40 mb-2 max-h-[300px] w-[280px] overflow-y-auto rounded-[14px] border border-line-6 bg-white p-1.5 shadow-float"
          onMouseDown={(event) => event.preventDefault()}
        >
          <p className="px-2.5 py-1.5 text-[12px] font-medium text-ink-55">组成员</p>
          {filtered.length === 0 ? (
            <p className="px-2.5 py-2 text-[12px] text-ink-30">没有匹配的智能体</p>
          ) : (
            filtered.map((persona, index) => (
              <button
                key={persona.key}
                type="button"
                onMouseEnter={() => setActive(index)}
                onClick={() => selectAgent(index)}
                className={`flex w-full items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-left transition ${
                  index === active ? "bg-line-4" : "hover:bg-line-2"
                }`}
              >
                <AgentAvatar agent={persona.key} size={28} ringColor="#F6F6F6" />
                <span className="text-[14px] font-medium text-ink-95">{persona.name}</span>
                <span className="text-[12px] text-ink-55">{persona.role}</span>
                {index === active ? (
                  <span className="ml-auto text-[12px] text-ink-30">↵</span>
                ) : null}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
