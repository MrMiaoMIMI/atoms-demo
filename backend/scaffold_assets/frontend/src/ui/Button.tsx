import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";
import { Icon, type IconName } from "./Icon";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "soft"
  | "ghost"
  | "danger";

export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
  block?: boolean;
  children?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "primary",
      size = "md",
      icon,
      iconRight,
      loading = false,
      block = false,
      className,
      children,
      disabled,
      type = "button",
      ...rest
    },
    ref
  ) {
    const iconSize = size === "sm" ? 15 : size === "lg" ? 18 : 16;
    return (
      <button
        ref={ref}
        type={type}
        className={clsx(
          "ds-btn",
          `ds-btn--${variant}`,
          `ds-btn--${size}`,
          block && "ds-btn--block",
          className
        )}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading ? (
          <span className="ds-spinner" aria-hidden="true" />
        ) : icon ? (
          <Icon name={icon} size={iconSize} />
        ) : null}
        {children}
        {iconRight ? <Icon name={iconRight} size={iconSize} /> : null}
      </button>
    );
  }
);

export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> {
  icon: IconName;
  label: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton(
    {
      icon,
      label,
      variant = "ghost",
      size = "md",
      loading = false,
      className,
      disabled,
      type = "button",
      ...rest
    },
    ref
  ) {
    const iconSize = size === "sm" ? 16 : size === "lg" ? 20 : 18;
    return (
      <button
        ref={ref}
        type={type}
        aria-label={label}
        title={label}
        className={clsx(
          "ds-btn",
          "ds-btn--icon",
          `ds-btn--${variant}`,
          `ds-btn--${size}`,
          className
        )}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading ? (
          <span className="ds-spinner" aria-hidden="true" />
        ) : (
          <Icon name={icon} size={iconSize} />
        )}
      </button>
    );
  }
);
