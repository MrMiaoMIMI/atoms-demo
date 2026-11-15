import type {
  CSSProperties,
  HTMLAttributes,
  ReactNode,
} from "react";
import clsx from "clsx";
import { Icon, type IconName } from "./Icon";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
}

export function Card({ interactive = false, className, ...rest }: CardProps) {
  return (
    <div
      className={clsx("ds-card", interactive && "ds-card--interactive", className)}
      {...rest}
    />
  );
}

export interface CardHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  icon?: IconName;
  className?: string;
}

export function CardHeader({
  title,
  subtitle,
  actions,
  icon,
  className,
}: CardHeaderProps) {
  return (
    <div className={clsx("ds-card__header", className)}>
      <div className="ds-card__heading">
        <div className="ds-row" style={{ gap: 10 }}>
          {icon ? (
            <span className="ds-empty__icon" style={{ width: 32, height: 32, borderRadius: 10 }}>
              <Icon name={icon} size={16} />
            </span>
          ) : null}
          <span className="ds-card__title">{title}</span>
        </div>
        {subtitle ? <p className="ds-card__subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="ds-page-header__actions">{actions}</div> : null}
    </div>
  );
}

export function CardBody({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("ds-card__body", className)} {...rest} />;
}

export function CardFooter({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("ds-card__footer", className)} {...rest} />;
}

export type BadgeTone =
  | "neutral"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "info";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  dot?: boolean;
}

export function Badge({
  tone = "neutral",
  dot = false,
  className,
  children,
  ...rest
}: BadgeProps) {
  return (
    <span className={clsx("ds-badge", `ds-badge--${tone}`, className)} {...rest}>
      {dot ? <span className="ds-badge__dot" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

export type AvatarSize = "sm" | "md" | "lg";

export interface AvatarProps {
  name: string;
  src?: string;
  size?: AvatarSize;
  className?: string;
}

export function Avatar({ name, src, size = "md", className }: AvatarProps) {
  const initials = name.trim().slice(0, 2).toUpperCase();
  return (
    <span
      className={clsx("ds-avatar", `ds-avatar--${size}`, className)}
      title={name}
      aria-label={name}
    >
      {src ? <img src={src} alt={name} /> : initials}
    </span>
  );
}

export interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  className?: string;
  style?: CSSProperties;
}

export function Skeleton({
  width = "100%",
  height = 16,
  radius,
  className,
  style,
}: SkeletonProps) {
  return (
    <span
      className={clsx("ds-skeleton", className)}
      style={{
        width,
        height,
        borderRadius: radius,
        ...style,
      }}
      aria-hidden="true"
    />
  );
}

export function Spinner({
  size = 16,
  label,
  className,
}: {
  size?: number;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={clsx("ds-spinner", className)}
      style={{ width: size, height: size }}
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}

export interface EmptyStateProps {
  icon?: IconName;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon = "sparkles",
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={clsx("ds-empty", className)}>
      <span className="ds-empty__icon">
        <Icon name={icon} size={22} />
      </span>
      <p className="ds-empty__title">{title}</p>
      {description ? (
        <p className="ds-empty__description">{description}</p>
      ) : null}
      {action ? <div style={{ marginTop: 4 }}>{action}</div> : null}
    </div>
  );
}

export interface StatProps {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  trend?: "up" | "down";
  icon?: IconName;
  className?: string;
}

export function Stat({ label, value, hint, trend, icon, className }: StatProps) {
  return (
    <div className={clsx("ds-stat", className)}>
      <span className="ds-stat__label">
        {icon ? <Icon name={icon} size={15} /> : null}
        {label}
      </span>
      <span className="ds-stat__value">{value}</span>
      {hint ? (
        <span
          className={clsx(
            "ds-stat__hint",
            trend === "up" && "ds-stat__trend--up",
            trend === "down" && "ds-stat__trend--down"
          )}
        >
          {hint}
        </span>
      ) : null}
    </div>
  );
}

export interface SectionProps {
  id?: string;
  eyebrow?: ReactNode;
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function Section({
  id,
  eyebrow,
  title,
  description,
  actions,
  children,
  className,
}: SectionProps) {
  const hasHead = eyebrow || title || description || actions;
  return (
    <section id={id} className={clsx("ds-section", className)}>
      {hasHead ? (
        <div className="ds-section__head">
          <div className="ds-section__copy">
            {eyebrow ? <p className="ds-eyebrow">{eyebrow}</p> : null}
            {title ? <h2 className="ds-h2">{title}</h2> : null}
            {description ? <p className="ds-lead">{description}</p> : null}
          </div>
          {actions ? (
            <div className="ds-page-header__actions">{actions}</div>
          ) : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Divider({ className }: { className?: string }) {
  return <hr className={clsx("ds-divider", className)} />;
}

export function Table({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className={clsx("ds-table", className)}>{children}</table>
    </div>
  );
}
