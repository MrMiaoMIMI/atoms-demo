import type { ReactNode } from "react";
import clsx from "clsx";
import { Icon, type IconName } from "./Icon";
import { IconButton } from "./Button";

export interface TabItem {
  key: string;
  label: ReactNode;
  icon?: IconName;
  badge?: ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (key: string) => void;
  variant?: "line" | "pill";
  className?: string;
}

export function Tabs({
  items,
  value,
  onChange,
  variant = "line",
  className,
}: TabsProps) {
  return (
    <div
      className={clsx(
        "ds-tabs",
        variant === "pill" && "ds-tabs--pill",
        className
      )}
      role="tablist"
    >
      {items.map((item) => {
        const selected = item.key === value;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            className="ds-tab"
            onClick={() => onChange(item.key)}
          >
            {item.icon ? <Icon name={item.icon} size={16} /> : null}
            {item.label}
            {item.badge ? (
              <span className="ds-badge ds-badge--neutral">{item.badge}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export interface PageHeaderProps {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  back?: ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  back,
  className,
}: PageHeaderProps) {
  return (
    <header className={clsx("ds-page-header", className)}>
      <div className="ds-page-header__copy">
        {back ? <div>{back}</div> : null}
        {eyebrow ? <p className="ds-eyebrow">{eyebrow}</p> : null}
        <h1 className="ds-h1">{title}</h1>
        {description ? <p className="ds-lead">{description}</p> : null}
      </div>
      {actions ? (
        <div className="ds-page-header__actions">{actions}</div>
      ) : null}
    </header>
  );
}

export interface BreadcrumbItem {
  label: ReactNode;
  href?: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="ds-breadcrumb" aria-label="面包屑">
      {items.map((item, index) => (
        <span className="ds-breadcrumb__item" key={index}>
          {item.href ? <a href={item.href}>{item.label}</a> : item.label}
        </span>
      ))}
    </nav>
  );
}

export interface SidebarNavItem {
  key: string;
  label: string;
  icon?: IconName;
  badge?: ReactNode;
}

export interface SidebarNavProps {
  items: SidebarNavItem[];
  active: string;
  onChange: (key: string) => void;
  title?: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function SidebarNav({
  items,
  active,
  onChange,
  title,
  footer,
  className,
}: SidebarNavProps) {
  return (
    <nav className={clsx("ds-sidebar-nav", className)} aria-label="主导航">
      {title ? <div className="ds-sidebar-nav__title">{title}</div> : null}
      <div className="ds-sidebar-nav__items">
        {items.map((item) => {
          const selected = item.key === active;
          return (
            <button
              key={item.key}
              type="button"
              className={clsx(
                "ds-sidebar-nav__item",
                selected && "is-active"
              )}
              aria-current={selected ? "page" : undefined}
              onClick={() => onChange(item.key)}
            >
              {item.icon ? <Icon name={item.icon} size={18} /> : null}
              <span>{item.label}</span>
              {item.badge ? (
                <span className="ds-sidebar-nav__badge">{item.badge}</span>
              ) : null}
            </button>
          );
        })}
      </div>
      {footer ? <div className="ds-sidebar-nav__footer">{footer}</div> : null}
    </nav>
  );
}

export function AppShell({
  sidebar,
  header,
  children,
  className,
}: {
  sidebar?: ReactNode;
  header?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("ds-shell", !sidebar && "ds-shell--plain", className)}>
      {sidebar ? <aside className="ds-shell__sidebar">{sidebar}</aside> : null}
      <div className="ds-shell__main">
        {header ? <header className="ds-shell__header">{header}</header> : null}
        <main className="ds-shell__content">{children}</main>
      </div>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  onChange,
  className,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
  className?: string;
}) {
  if (totalPages <= 1) return null;

  const pages: Array<number | "dots"> = [];
  const push = (value: number | "dots") => {
    if (pages[pages.length - 1] !== value) pages.push(value);
  };
  for (let index = 1; index <= totalPages; index += 1) {
    if (
      index === 1 ||
      index === totalPages ||
      Math.abs(index - page) <= 1
    ) {
      push(index);
    } else if (Math.abs(index - page) === 2) {
      push("dots");
    }
  }

  return (
    <nav className={clsx("ds-pagination", className)} aria-label="分页">
      <IconButton
        icon="chevronLeft"
        label="上一页"
        size="sm"
        variant="secondary"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      />
      {pages.map((item, index) =>
        item === "dots" ? (
          <span key={`dots-${index}`} className="ds-pagination__dots">
            …
          </span>
        ) : (
          <button
            key={item}
            type="button"
            className="ds-pagination__page"
            aria-current={item === page ? "page" : undefined}
            onClick={() => onChange(item)}
          >
            {item}
          </button>
        )
      )}
      <IconButton
        icon="chevronRight"
        label="下一页"
        size="sm"
        variant="secondary"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
      />
    </nav>
  );
}
