import { useEffect, useId } from "react";
import type { ComponentProps, ReactNode } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { Toaster as SonnerToaster, toast } from "sonner";
import { Button, IconButton } from "./Button";

export { toast };

export function Toaster(props: ComponentProps<typeof SonnerToaster>) {
  return (
    <SonnerToaster
      position="top-right"
      closeButton
      richColors
      {...props}
    />
  );
}

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg";
  closeOnBackdrop?: boolean;
  className?: string;
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  closeOnBackdrop = true,
  className,
}: DialogProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="ds-overlay"
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className={clsx(
          "ds-dialog",
          size === "lg" && "ds-dialog--lg",
          className
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="ds-dialog__header">
          <div>
            <h2 className="ds-dialog__title" id={titleId}>
              {title}
            </h2>
            {description ? (
              <p className="ds-dialog__description">{description}</p>
            ) : null}
          </div>
          <IconButton
            icon="close"
            label="关闭"
            size="sm"
            onClick={onClose}
          />
        </div>
        {children ? <div className="ds-dialog__body">{children}</div> : null}
        {footer ? <div className="ds-dialog__footer">{footer}</div> : null}
      </div>
    </div>,
    document.body
  );
}

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: ReactNode;
  description?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  tone?: "primary" | "danger";
  loading?: boolean;
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmText = "确认",
  cancelText = "取消",
  tone = "primary",
  loading = false,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            {cancelText}
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmText}
          </Button>
        </>
      }
    />
  );
}

export type DrawerSide = "left" | "right" | "bottom";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  side?: DrawerSide;
  children?: ReactNode;
  footer?: ReactNode;
}

export function Drawer({
  open,
  onClose,
  title,
  description,
  side = "right",
  children,
  footer,
}: DrawerProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className={clsx("ds-drawer", `ds-drawer--${side}`)}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="ds-drawer__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="ds-drawer__header">
          <div>
            <h2 className="ds-dialog__title" id={titleId}>
              {title}
            </h2>
            {description ? (
              <p className="ds-dialog__description">{description}</p>
            ) : null}
          </div>
          <IconButton icon="close" label="关闭" size="sm" onClick={onClose} />
        </div>
        <div className="ds-drawer__body">{children}</div>
        {footer ? <div className="ds-drawer__footer">{footer}</div> : null}
      </div>
    </div>,
    document.body
  );
}

export function InlineNotice({
  tone = "info",
  icon,
  children,
  className,
}: {
  tone?: "info" | "success" | "warning" | "danger";
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx("ds-inline-notice", `ds-inline-notice--${tone}`, className)}
      role={tone === "danger" ? "alert" : "status"}
    >
      {icon ? <span className="ds-inline-notice__icon">{icon}</span> : null}
      <div>{children}</div>
    </div>
  );
}
