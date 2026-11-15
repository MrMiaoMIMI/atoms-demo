import { useState } from "react";
import { formatCount } from "../lib/discover";
import { MODE_LABEL, coverFor } from "../lib/projects";
import type { DiscoverApp, ProjectSummary } from "../types";
import { InitialAvatar } from "./Avatar";
import { Eye } from "./Icons";
import { ProjectCover } from "./ProjectCard";

interface Props {
  app: DiscoverApp;
  onOpen: (id: string) => void;
}

/**
 * Discover cards are links so cmd/ctrl-click opens a new tab; a plain click
 * stays inside the SPA.
 */
export default function DiscoverCard({ app, onOpen }: Props) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = Boolean(app.cover_url) && !imageFailed;
  const fallbackProject: ProjectSummary = {
    id: app.id,
    name: app.name,
    created_at: app.published_at ?? "",
    message_count: 0,
    artifact_count: 0,
    latest_version: null,
    mode: app.mode,
  };

  return (
    <a
      href={`/discover/${encodeURIComponent(app.id)}`}
      onClick={(event) => {
        if (
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey ||
          event.button !== 0
        ) {
          return;
        }
        event.preventDefault();
        onOpen(app.id);
      }}
      className="group block min-w-0 text-left"
    >
      <div
        className="relative aspect-[16/10] overflow-hidden rounded-[12px] border border-line-4 transition group-hover:border-line-8"
        style={{ background: coverFor(app.id) }}
      >
        <ProjectCover
          project={fallbackProject}
          label={MODE_LABEL[app.mode] ?? "前端"}
        />
        {showImage ? (
          <img
            src={app.cover_url ?? ""}
            alt=""
            loading="lazy"
            onError={() => setImageFailed(true)}
            className="absolute inset-0 h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
          />
        ) : null}

        <span className="absolute left-2 top-2 inline-flex items-center rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-ink-80 shadow-sm backdrop-blur">
          {app.category}
        </span>
      </div>

      <div className="mt-3 min-w-0">
        <h3 className="truncate text-[14px] font-medium text-ink-95">
          {app.name}
        </h3>
        <div className="mt-1 flex items-center gap-2 text-[12px] text-ink-55">
          <InitialAvatar size={18} label={app.author_initial || "A"} />
          <span className="min-w-0 truncate">{app.author_name}</span>
          <span className="ml-auto inline-flex flex-none items-center gap-1 text-ink-55">
            <Eye size={12} />
            {formatCount(app.view_count)}
          </span>
        </div>
      </div>
    </a>
  );
}
