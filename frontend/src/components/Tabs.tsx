import type { ReactNode } from 'react';

export interface TabItem<T extends string> {
  value: T;
  label: ReactNode;
  count?: number;
}

interface Props<T extends string> {
  items: readonly TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

/**
 * Shared pill tabs used on home, projects and discover. The visual reference is
 * the home page: a soft grey pill for the active tab, plain text otherwise.
 */
export default function Tabs<T extends string>({
  items,
  value,
  onChange,
  className = '',
}: Props<T>) {
  return (
    <div role="tablist" className={`flex items-center gap-1 ${className}`}>
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={`inline-flex h-8 flex-none items-center rounded-full px-4 text-[14px] transition ${
              active
                ? 'bg-line-6 text-ink-95'
                : 'text-ink-55 hover:text-ink-80'
            }`}
          >
            {item.label}
            {item.count !== undefined ? (
              <span
                className={`ml-1.5 text-[11px] ${
                  active ? 'text-ink-55' : 'text-ink-30'
                }`}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
