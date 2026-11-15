interface Props {
  path: string;
  /** When provided, directory segments become buttons that reveal the folder. */
  onSelectDir?: (dir: string) => void;
}

export default function FilePathBreadcrumb({ path, onSelectDir }: Props) {
  const segments = path.split("/").filter(Boolean);

  return (
    <div
      className="flex min-w-0 flex-1 items-center gap-0.5 overflow-hidden text-[12px]"
      title={path}
    >
      {segments.map((part, index) => {
        const sub = segments.slice(0, index + 1).join("/");
        const last = index === segments.length - 1;
        return (
          <span key={sub} className="flex min-w-0 items-center gap-0.5">
            {index > 0 ? (
              <span className="flex-none text-ink-30">/</span>
            ) : null}
            {last ? (
              <span className="truncate px-1 font-medium text-ink-95">
                {part}
              </span>
            ) : onSelectDir ? (
              <button
                type="button"
                onClick={() => onSelectDir(sub)}
                title={`定位到 ${sub}`}
                className="truncate rounded px-1 py-0.5 text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
              >
                {part}
              </button>
            ) : (
              <span className="truncate px-1 py-0.5 text-ink-55">
                {part}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}
