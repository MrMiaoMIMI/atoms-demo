import type { ReactNode } from "react";

interface IconProps {
  className?: string;
}

const BASE = "h-4 w-4";

function Svg({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      className={`${BASE} ${className ?? ""}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function Sparkle({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
      <path d="M19 15l.7 1.8L21.5 17.5l-1.8.7L19 20l-.7-1.8-1.8-.7 1.8-.7L19 15z" />
    </Svg>
  );
}

export function ArrowRight({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M5 12h14" />
      <path d="M13 6l6 6-6 6" />
    </Svg>
  );
}

export function ChevronLeft({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M15 6l-6 6 6 6" />
    </Svg>
  );
}

export function Plus({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function Refresh({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M20 11a8 8 0 1 0-2.3 6.3" />
      <path d="M20 4v7h-7" />
    </Svg>
  );
}

export function ExternalLink({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M14 4h6v6" />
      <path d="M20 4l-9 9" />
      <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </Svg>
  );
}

export function Check({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </Svg>
  );
}

export function AlertTriangle({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 3l9.5 17h-19L12 3z" />
      <path d="M12 9v5M12 17.5v.5" />
    </Svg>
  );
}

export function X({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  );
}

export function Spinner({ className }: IconProps) {
  return (
    <svg
      className={`${BASE} animate-spin ${className ?? ""}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Send({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 12l16-8-5.5 16L12 13l-8-1z" />
    </Svg>
  );
}

export function Stop({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />
    </Svg>
  );
}

export function Folder({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7z" />
    </Svg>
  );
}

export function Code({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M9 8l-4 4 4 4M15 8l4 4-4 4" />
    </Svg>
  );
}

export function Chat({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M21 12a8 8 0 0 1-8 8H8l-5 3 1.5-5A8 8 0 1 1 21 12z" />
    </Svg>
  );
}

export function Trash({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" />
    </Svg>
  );
}

export function Copy({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a1 1 0 0 1 1-1h10" />
    </Svg>
  );
}
