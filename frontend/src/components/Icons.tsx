import type { ReactNode, SVGProps } from "react";
import { useId } from "react";

export type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ children, size = 18, className, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...props}
    >
      {children}
    </svg>
  );
}

export function AtomsMark({ size = 22, className, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
      {...props}
    >
      <ellipse cx="8.6" cy="15" rx="4.25" ry="4.6" transform="rotate(-20 8.6 15)" />
      <ellipse cx="15.4" cy="15" rx="4.25" ry="4.6" transform="rotate(20 15.4 15)" />
      <ellipse cx="12" cy="8.5" rx="4.3" ry="4.7" />
    </svg>
  );
}

export function Home(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.5 10.4 12 3.8l8.5 6.6V20a1 1 0 0 1-1 1h-5v-6.4h-5V21h-5a1 1 0 0 1-1-1z" />
    </Icon>
  );
}

export function Compass(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.6" />
      <path d="m15.2 8.8-1.9 4.5-4.5 1.9 1.9-4.5z" />
    </Icon>
  );
}

export function Folder(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.2 7.2a2 2 0 0 1 2-2h3.6l1.9 2h8.1a2 2 0 0 1 2 2v8.6a2 2 0 0 1-2 2H5.2a2 2 0 0 1-2-2z" />
    </Icon>
  );
}

export function FolderOpen(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.2 7.2a2 2 0 0 1 2-2h3.6l1.9 2h8.1a2 2 0 0 1 2 2v1.2h-15z" />
      <path d="M4.4 10.4h16.1l-2.2 8.4a1.6 1.6 0 0 1-1.5 1.2H5.1a1.6 1.6 0 0 1-1.6-1.8z" />
    </Icon>
  );
}

export function Clock(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.6" />
      <path d="M12 7.2V12l3.2 2" />
    </Icon>
  );
}

export function History(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.8 12a8.2 8.2 0 1 0 2.4-5.8" />
      <path d="M3.6 4.8v4.1h4.1" />
      <path d="M12 7.6V12l2.8 1.8" />
    </Icon>
  );
}

export function ChevronDown(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m6 9 6 6 6-6" />
    </Icon>
  );
}

export function ChevronUp(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m6 15 6-6 6 6" />
    </Icon>
  );
}

export function ChevronRight(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m9 6 6 6-6 6" />
    </Icon>
  );
}

export function ChevronLeft(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m15 6-6 6 6 6" />
    </Icon>
  );
}

export function PanelLeft(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.4" y="4.2" width="17.2" height="15.6" rx="2.2" />
      <path d="M9.2 4.2v15.6" />
    </Icon>
  );
}

export function Search(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="10.8" cy="10.8" r="6.6" />
      <path d="m15.8 15.8 4.2 4.2" />
    </Icon>
  );
}

export function Plus(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 5v14M5 12h14" />
    </Icon>
  );
}

export function Sparkle(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3.2 13.9 9l5.8 1.9-5.8 1.9L12 18.6l-1.9-5.8L4.3 10.9 10.1 9z" />
      <path d="M18.7 16.8l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
    </Icon>
  );
}

export function Grid(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="4" y="4" width="6.4" height="6.4" rx="1.6" />
      <rect x="13.6" y="4" width="6.4" height="6.4" rx="1.6" />
      <rect x="4" y="13.6" width="6.4" height="6.4" rx="1.6" />
      <rect x="13.6" y="13.6" width="6.4" height="6.4" rx="1.6" />
    </Icon>
  );
}

export function Code(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m8.2 7.6-4.6 4.4 4.6 4.4" />
      <path d="m15.8 7.6 4.6 4.4-4.6 4.4" />
      <path d="m13.6 4.8-3.2 14.4" />
    </Icon>
  );
}

export function ImageIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="4.4" width="17" height="15.2" rx="2.2" />
      <circle cx="8.6" cy="9.4" r="1.6" />
      <path d="m4.4 17.2 4.8-4.6 3.1 2.9 3.3-3.4 4 4.1" />
    </Icon>
  );
}

export function MoreHorizontal(props: IconProps) {
  return (
    <Icon {...props} stroke="none" fill="currentColor">
      <circle cx="5.2" cy="12" r="1.55" />
      <circle cx="12" cy="12" r="1.55" />
      <circle cx="18.8" cy="12" r="1.55" />
    </Icon>
  );
}

export function Eye(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M2.8 12S6 5.9 12 5.9 21.2 12 21.2 12 18 18.1 12 18.1 2.8 12 2.8 12Z" />
      <circle cx="12" cy="12" r="2.8" />
    </Icon>
  );
}

export function EyeOff(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.2 3.2 20.8 20.8" />
      <path d="M10.6 6.2A9.9 9.9 0 0 1 12 6.1c6 0 9.2 5.9 9.2 5.9a15.4 15.4 0 0 1-3.1 3.6" />
      <path d="M6.6 6.8C4.2 8.3 2.8 12 2.8 12s3.2 6.1 9.2 6.1c1.5 0 2.9-.35 4.1-.95" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </Icon>
  );
}

export function LogOut(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9 4H5.8A1.8 1.8 0 0 0 4 5.8v12.4A1.8 1.8 0 0 0 5.8 20H9" />
      <path d="M15 8l4 4-4 4" />
      <path d="M19 12H9" />
    </Icon>
  );
}

export function Mail(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 6.5 8.5 6 8.5-6" />
    </Icon>
  );
}

export function Monitor(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3" y="4.4" width="18" height="12.4" rx="1.8" />
      <path d="M9 20.4h6M12 16.8v3.6" />
    </Icon>
  );
}

export function Smartphone(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="7" y="3" width="10" height="18" rx="2.4" />
      <path d="M10.8 17.6h2.4" />
    </Icon>
  );
}

export function Refresh(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M20 7.4v4.4h-4.4" />
      <path d="M19.1 11.4A7.4 7.4 0 1 0 20 7.4" />
    </Icon>
  );
}

export function ExternalLink(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M14.2 4.4h5.4v5.4" />
      <path d="M19.2 4.8 11.4 12.6" />
      <path d="M18.4 13.4v4.6a1.8 1.8 0 0 1-1.8 1.8H5.4a1.8 1.8 0 0 1-1.8-1.8V6.8A1.8 1.8 0 0 1 5.4 5h4.7" />
    </Icon>
  );
}

export function Share(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="17.4" cy="5.8" r="2.6" />
      <circle cx="6.2" cy="12" r="2.6" />
      <circle cx="17.4" cy="18.2" r="2.6" />
      <path d="m8.5 10.7 6.6-3.5M8.5 13.3l6.6 3.5" />
    </Icon>
  );
}

export function Settings(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="3.1" />
      <path d="M19.2 13.6a7.7 7.7 0 0 0 0-3.2l1.8-1.4-1.9-3.3-2.2.9a7.6 7.6 0 0 0-2.8-1.6L13.8 2h-3.6l-.3 2.9a7.6 7.6 0 0 0-2.8 1.7l-2.2-.9-1.9 3.3 1.8 1.4a7.7 7.7 0 0 0 0 3.2l-1.8 1.4 1.9 3.3 2.2-.9a7.6 7.6 0 0 0 2.8 1.7l.3 2.9h3.6l.3-2.9a7.6 7.6 0 0 0 2.8-1.7l2.2.9 1.9-3.3z" />
    </Icon>
  );
}

export function Bell(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M18.2 15.6V11a6.2 6.2 0 0 0-12.4 0v4.6L4 17.6h16z" />
      <path d="M9.8 20.4a2.6 2.6 0 0 0 4.4 0" />
    </Icon>
  );
}

export function ArrowUp(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 19V5" />
      <path d="m6 11 6-6 6 6" />
    </Icon>
  );
}

export function ArrowRight(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 12h16" />
      <path d="m14 6 6 6-6 6" />
    </Icon>
  );
}

export function Waveform(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 10.5v3M7.5 8v8M11 5.5v13M14.5 8v8M18 10.5v3M21 11.5v1" />
    </Icon>
  );
}

export function Check(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m5 12.6 4.2 4.2L19 6.6" />
    </Icon>
  );
}

export function CheckCircle(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.6" />
      <path d="m8.2 12.2 2.6 2.6 5-5.2" />
    </Icon>
  );
}

export function CheckCircleFill({ size = 18, className, ...props }: IconProps) {
  const maskId = useId().replace(/:/g, '');
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
      {...props}
    >
      <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">
        <circle cx="12" cy="12" r="10" fill="#fff" />
        <path
          d="m7.3 12.3 3.1 3.1 6.3-6.5"
          stroke="#000"
          strokeWidth="2.1"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </mask>
      <circle
        cx="12"
        cy="12"
        r="10"
        fill="currentColor"
        mask={`url(#${maskId})`}
      />
    </svg>
  );
}

export function AlertTriangle(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3.8 21 19.4H3z" />
      <path d="M12 9.4v4.2M12 16.8h.01" />
    </Icon>
  );
}

export function X(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Icon>
  );
}

export function Copy(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="8.4" y="8.4" width="11.2" height="11.2" rx="2" />
      <path d="M5.4 15.6H4.8a1.8 1.8 0 0 1-1.8-1.8V4.8A1.8 1.8 0 0 1 4.8 3h9a1.8 1.8 0 0 1 1.8 1.8v.6" />
    </Icon>
  );
}

export function ThumbsUp(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M7.4 10.4 11.6 3a2.2 2.2 0 0 1 2.2 2.2v3.4h4.4a2 2 0 0 1 1.9 2.5l-1.5 6.2a2 2 0 0 1-2 1.5H7.4" />
      <path d="M3.4 10.4h4v9h-4z" />
    </Icon>
  );
}

export function ThumbsDown(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M16.6 13.6 12.4 21a2.2 2.2 0 0 1-2.2-2.2v-3.4H5.8a2 2 0 0 1-1.9-2.5l1.5-6.2a2 2 0 0 1 2-1.5h9.2" />
      <path d="M20.6 4.6h-4v9h4z" />
    </Icon>
  );
}

export function Shuffle(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.6 6.8h3.1c4.8 0 5.8 10.4 10.6 10.4h2.9" />
      <path d="m17.4 14.4 3 2.8-3 2.8" />
      <path d="M3.6 17.2h3.1c1.5 0 2.7-1 3.8-2.4M13.3 8.7c1-1 2.1-1.9 4-1.9h2.9" />
      <path d="m17.4 3.9 3 2.8-3 2.8" />
    </Icon>
  );
}

export function Download(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 4v10.4" />
      <path d="m7.6 10.4 4.4 4.4 4.4-4.4" />
      <path d="M4.4 18.8h15.2" />
    </Icon>
  );
}

export function FileText(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M6 3.4h8l4 4v13.2H6z" />
      <path d="M14 3.4v4h4M9 12h6M9 15.6h6" />
    </Icon>
  );
}

export function Chat(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M20.4 12a8.4 8.4 0 0 1-8.4 8.4 8.8 8.8 0 0 1-3.3-.6L4 21l1.3-4.4a8.4 8.4 0 1 1 15.1-4.6Z" />
    </Icon>
  );
}

export function Stop(props: IconProps) {
  return (
    <Icon {...props} stroke="none" fill="currentColor">
      <rect x="6.8" y="6.8" width="10.4" height="10.4" rx="2" />
    </Icon>
  );
}

export function Trash(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4.4 6.8h15.2M9.4 3.8h5.2M6.4 6.8l.9 13.4h9.4l.9-13.4" />
      <path d="M10 10.4v6.4M14 10.4v6.4" />
    </Icon>
  );
}

export function Spinner(props: IconProps) {
  return (
    <Icon {...props} className={`animate-spin ${props.className ?? ""}`}>
      <circle cx="12" cy="12" r="8.4" opacity="0.22" />
      <path d="M20.4 12a8.4 8.4 0 0 0-8.4-8.4" />
    </Icon>
  );
}

export function Diamond(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3.4 20.2 12 12 20.6 3.8 12z" />
    </Icon>
  );
}

export function Users(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="9.4" cy="8.6" r="3.2" />
      <path d="M3.4 19.4c.5-3.3 3-5.2 6-5.2s5.5 1.9 6 5.2" />
      <path d="M15.4 5.7a3.2 3.2 0 0 1 0 5.9M17.4 14.5c1.9.5 3.1 2.2 3.4 4.5" />
    </Icon>
  );
}

export function Sliders(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7.4h9M17 7.4h3M4 16.6h3M11 16.6h9" />
      <circle cx="15" cy="7.4" r="2" />
      <circle cx="9" cy="16.6" r="2" />
    </Icon>
  );
}

export function ListTree(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9 6h11M9 12h11M9 18h11" />
      <path d="M4 4v16" />
      <path d="M4 6h2M4 12h2M4 18h2" />
    </Icon>
  );
}

export function Expand(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5" />
    </Icon>
  );
}

export function ApiIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.4" y="4.4" width="17.2" height="15.2" rx="3" />
      <path d="M8.2 9.4 6 12l2.2 2.6M15.8 9.4 18 12l-2.2 2.6M13.2 8.4l-2.4 7.2" />
    </Icon>
  );
}

export function DropdownChevron(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m7.5 9.8 4.5 4.4 4.5-4.4" />
    </Icon>
  );
}
