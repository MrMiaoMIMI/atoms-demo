import type { RefObject } from "react";
import { ChevronDown, ChevronUp, X } from "./Icons";

interface Props {
  query: string;
  onQueryChange: (value: string) => void;
  caseSensitive: boolean;
  onToggleCase: () => void;
  current: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
  inputRef?: RefObject<HTMLInputElement>;
  placeholder?: string;
}

export default function FindBar({
  query,
  onQueryChange,
  caseSensitive,
  onToggleCase,
  current,
  total,
  onPrev,
  onNext,
  onClose,
  inputRef,
  placeholder = "在文件中查找",
}: Props) {
  return (
    <div className="absolute right-3 top-2 z-20 flex h-8 items-center gap-0.5 rounded-lg border border-line-8 bg-white px-1 shadow-float">
      <input
        ref={inputRef}
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            if (event.shiftKey) onPrev();
            else onNext();
          } else if (event.key === "Escape") {
            event.preventDefault();
            onClose();
          }
        }}
        placeholder={placeholder}
        className="h-6 w-[132px] rounded bg-transparent px-1.5 text-[12px] text-ink-95 outline-none placeholder:text-ink-30"
      />
      <span className="min-w-[42px] px-1 text-center font-mono text-[10.5px] text-ink-30">
        {total ? `${Math.min(current, total - 1) + 1}/${total}` : "0/0"}
      </span>
      <button
        type="button"
        onClick={onToggleCase}
        title="区分大小写"
        className={`grid h-6 w-6 place-items-center rounded text-[11px] transition ${
          caseSensitive
            ? "bg-brand-50 text-brand-text"
            : "text-ink-55 hover:bg-line-4 hover:text-ink-95"
        }`}
      >
        Aa
      </button>
      <button
        type="button"
        onClick={onPrev}
        disabled={!total}
        title="上一个（Shift+Enter）"
        className="grid h-6 w-6 place-items-center rounded text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
      >
        <ChevronUp size={13} />
      </button>
      <button
        type="button"
        onClick={onNext}
        disabled={!total}
        title="下一个（Enter）"
        className="grid h-6 w-6 place-items-center rounded text-ink-55 transition hover:bg-line-4 hover:text-ink-95 disabled:opacity-40"
      >
        <ChevronDown size={13} />
      </button>
      <button
        type="button"
        onClick={onClose}
        title="关闭（Esc）"
        className="grid h-6 w-6 place-items-center rounded text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
      >
        <X size={13} />
      </button>
    </div>
  );
}
