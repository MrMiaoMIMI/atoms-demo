import { useEffect, useRef } from "react";
import { Keyboard, X } from "./Icons";

interface Props {
  activeView: "files" | "changes";
  onClose: () => void;
}

const isMac =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad|iPod/.test(
    `${navigator.platform ?? ""} ${navigator.userAgent ?? ""}`
  );

const MOD = isMac ? "⌘" : "Ctrl";
const SHIFT = isMac ? "⇧" : "Shift";
const ALT = isMac ? "⌥" : "Alt";

interface ShortcutRow {
  label: string;
  combos: string[][];
}

interface ShortcutSection {
  title: string;
  note?: string;
  current?: boolean;
  rows: ShortcutRow[];
}

function buildSections(activeView: "files" | "changes"): ShortcutSection[] {
  return [
    {
      title: "文件 tab",
      current: activeView === "files",
      rows: [
        { label: "快速打开文件", combos: [[MOD, "P"]] },
        { label: "全文搜索", combos: [[MOD, SHIFT, "F"]] },
        {
          label: "后退 / 前进",
          combos: [
            [ALT, "←"],
            [ALT, "→"],
          ],
        },
        { label: "文件内查找", combos: [[MOD, "F"]] },
        { label: "跳转到行", combos: [[MOD, "G"]] },
        {
          label: "查找下一个 / 上一个",
          combos: [["Enter"], [SHIFT, "Enter"]],
        },
      ],
    },
    {
      title: "未发布改动 tab",
      current: activeView === "changes",
      note: "顶部「全文搜索」在改动 tab 也可用，结果会定位到文件 tab。",
      rows: [
        { label: "在改动中查找", combos: [[MOD, "F"]] },
        {
          label: "下一处 / 上一处改动",
          combos: [["F3"], [SHIFT, "F3"]],
        },
        {
          label: "查找下一个 / 上一个",
          combos: [["Enter"], [SHIFT, "Enter"]],
        },
      ],
    },
  ];
}

function Keycap({ children }: { children: string }) {
  return (
    <kbd className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-[5px] border border-line-8 bg-base px-1 font-sans text-[10.5px] leading-none text-ink-55 shadow-[0_1px_0_rgba(12,12,12,0.04)]">
      {children}
    </kbd>
  );
}

export default function ShortcutHelp({ activeView, onClose }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);
  const sections = buildSections(activeView);

  useEffect(() => {
    cardRef.current?.focus();
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          onClose();
        }
        // Keep Cmd/Ctrl shortcuts from reaching the code panel behind.
        event.stopPropagation();
      }}
    >
      <button
        type="button"
        aria-label="关闭快捷键弹窗"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-[rgba(12,12,12,0.32)] animate-fade backdrop-blur-[2px]"
      />
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcut-help-title"
        tabIndex={-1}
        onClick={() => cardRef.current?.focus()}
        className="relative max-h-[calc(100vh-40px)] w-full max-w-[540px] overflow-y-auto rounded-2xl border border-line-6 bg-white shadow-float outline-none animate-rise"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line-4 px-5 py-4">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-base text-ink-55">
              <Keyboard size={17} />
            </span>
            <div className="min-w-0">
              <h2
                id="shortcut-help-title"
                className="text-[15px] font-medium text-ink-95"
              >
                快捷键
              </h2>
              <p className="mt-0.5 text-[11px] text-ink-30">
                仅在右侧代码面板内生效，输入框聚焦时不拦截
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="关闭（Esc）"
            className="grid h-7 w-7 flex-none place-items-center rounded-md text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
          >
            <X size={15} />
          </button>
        </div>

        <div>
          {sections.map((section) => (
            <section
              key={section.title}
              className="border-b border-line-4 px-5 py-3.5 last:border-b-0"
            >
              <div className="flex items-center gap-2">
                <h3 className="text-[12px] font-medium text-ink-95">
                  {section.title}
                </h3>
                {section.current ? (
                  <span className="rounded-full bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-text">
                    当前
                  </span>
                ) : null}
              </div>
              {section.note ? (
                <p className="mt-1 text-[10.5px] leading-[16px] text-ink-30">
                  {section.note}
                </p>
              ) : null}
              <div className="mt-1">
                {section.rows.map((row) => (
                  <div
                    key={row.label}
                    className="flex min-h-[30px] items-center justify-between gap-4 py-1"
                  >
                    <span className="min-w-0 truncate text-[12px] text-ink-80">
                      {row.label}
                    </span>
                    <span className="flex flex-none items-center gap-1">
                      {row.combos.map((combo, comboIndex) => (
                        <span
                          key={comboIndex}
                          className="flex items-center gap-1"
                        >
                          {comboIndex > 0 ? (
                            <span className="px-0.5 text-[10px] text-ink-30">
                              /
                            </span>
                          ) : null}
                          {combo.map((key, keyIndex) => (
                            <Keycap key={`${comboIndex}-${keyIndex}`}>
                              {key}
                            </Keycap>
                          ))}
                        </span>
                      ))}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>

        <div className="px-5 py-3 text-[10.5px] leading-[16px] text-ink-30">
          快速打开列表支持 ↑↓ 选择、Enter 打开；任意浮层可用 Esc 关闭。Mac 使用
          ⌘ / ⌥，其他平台使用 Ctrl / Alt。
        </div>
      </div>
    </div>
  );
}
