import { forwardRef } from "react";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import clsx from "clsx";

export interface FieldProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}

export function Field({
  label,
  hint,
  error,
  required,
  htmlFor,
  className,
  children,
}: FieldProps) {
  return (
    <div className={clsx("ds-field", className)}>
      {label ? (
        <label className="ds-field__label" htmlFor={htmlFor}>
          {label}
          {required ? (
            <span className="ds-field__required" aria-hidden="true">
              {" "}
              *
            </span>
          ) : null}
        </label>
      ) : null}
      {children}
      {error ? (
        <p className="ds-field__error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="ds-field__hint">{hint}</p>
      ) : null}
    </div>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid = false, className, ...rest },
  ref
) {
  return (
    <input
      ref={ref}
      className={clsx("ds-input", invalid && "ds-input--invalid", className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
});

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ invalid = false, className, ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        className={clsx(
          "ds-textarea",
          invalid && "ds-textarea--invalid",
          className
        )}
        aria-invalid={invalid || undefined}
        {...rest}
      />
    );
  }
);

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps
  extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
  options?: SelectOption[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select({ invalid = false, options, className, children, ...rest }, ref) {
    return (
      <select
        ref={ref}
        className={clsx(
          "ds-select",
          invalid && "ds-select--invalid",
          className
        )}
        aria-invalid={invalid || undefined}
        {...rest}
      >
        {options
          ? options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))
          : children}
      </select>
    );
  }
);

export interface CheckboxProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: ReactNode;
  description?: ReactNode;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  function Checkbox({ label, description, className, ...rest }, ref) {
    return (
      <label className={clsx("ds-checkbox", className)}>
        <input ref={ref} type="checkbox" {...rest} />
        {label || description ? (
          <span>
            {label}
            {description ? (
              <span className="ds-field__hint" style={{ display: "block" }}>
                {description}
              </span>
            ) : null}
          </span>
        ) : null}
      </label>
    );
  }
);

export function FormGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={clsx("ds-grid ds-grid--2", className)}>{children}</div>;
}
