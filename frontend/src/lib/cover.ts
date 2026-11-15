import { api } from "../api";

/**
 * Capture the app in the owner's browser and upload it as a project thumbnail.
 *
 * Two destinations share this flow:
 * - published cover: the discover card and the owner's project card (published
 *   version wins over a working-build thumbnail);
 * - build cover: the owner's project card for builds that have not been
 *   published yet.
 *
 * The server injects a small script into the *workspace* preview document
 * (`/apps/{id}/?atoms_capture=1`). That script loads html-to-image inside the
 * sandboxed iframe, screenshots its own DOM, and posts a JPEG back here. The
 * sandbox keeps its opaque origin: the preview never gains access to the demo
 * session or the parent document.
 *
 * Any failure is non-fatal; callers fall back to the CSS cover.
 */
type CoverUploader = (
  projectId: string,
  version: number,
  image: string
) => Promise<unknown>;

async function captureCover(
  projectId: string,
  version: number,
  upload: CoverUploader
): Promise<boolean> {
  if (typeof window === "undefined" || !document.body) return false;

  const captureId = `cover_${Date.now().toString(36)}_${Math.random()
    .toString(36)
    .slice(2, 10)}`;
  const target = new URL(
    `/apps/${encodeURIComponent(projectId)}/`,
    window.location.origin
  );
  target.searchParams.set("atoms_capture", "1");
  target.searchParams.set("capture_id", captureId);

  const frame = document.createElement("iframe");
  frame.setAttribute(
    "sandbox",
    "allow-scripts allow-forms allow-popups allow-modals"
  );
  frame.setAttribute("aria-hidden", "true");
  frame.setAttribute("tabindex", "-1");
  frame.style.cssText =
    "position:fixed;left:-10000px;top:0;width:1280px;height:720px;" +
    "border:0;opacity:0;pointer-events:none;";

  return new Promise<boolean>((resolve) => {
    let settled = false;
    let readyTimer: number | undefined;
    let timeout: number | undefined;

    function cleanup() {
      if (readyTimer !== undefined) window.clearTimeout(readyTimer);
      if (timeout !== undefined) window.clearTimeout(timeout);
      window.removeEventListener("message", onMessage);
      frame.remove();
    }

    function finish(ok: boolean) {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(ok);
    }

    async function onMessage(event: MessageEvent) {
      if (event.source !== frame.contentWindow) return;
      const data = event.data as
        | { type?: string; id?: string; dataUrl?: string; message?: string }
        | null;
      if (!data || data.id !== captureId) return;

      if (data.type === "atoms-cover-ready") {
        // Give the app a beat to finish data fetches and entry animations.
        window.clearTimeout(readyTimer);
        readyTimer = window.setTimeout(() => {
          frame.contentWindow?.postMessage(
            { type: "atoms-capture", id: captureId },
            "*"
          );
        }, 1500);
        return;
      }

      if (data.type === "atoms-cover-error") {
        console.warn("[cover] capture failed:", data.message);
        finish(false);
        return;
      }

      if (data.type !== "atoms-cover") return;
      const dataUrl = data.dataUrl;
      // Keep the upload below nginx's 2m body limit, and let the backend
      // validate the actual image bytes.
      if (
        typeof dataUrl !== "string" ||
        !dataUrl.startsWith("data:image/") ||
        dataUrl.length < 5000 ||
        dataUrl.length > 1_590_000
      ) {
        finish(false);
        return;
      }
      try {
        await upload(projectId, version, dataUrl);
        finish(true);
      } catch (error) {
        console.warn("[cover] upload failed:", error);
        finish(false);
      }
    }

    timeout = window.setTimeout(() => finish(false), 18_000);
    window.addEventListener("message", onMessage);
    frame.src = target.toString();
    document.body.appendChild(frame);
  });
}

/** Published snapshot cover: used by discover and as the owner's top priority. */
export function capturePublishedCover(
  projectId: string,
  version: number
): Promise<boolean> {
  return captureCover(projectId, version, api.uploadCover);
}

/** Working-build cover: used by the owner's project cards before publishing. */
export function captureBuildCover(
  projectId: string,
  version: number
): Promise<boolean> {
  return captureCover(projectId, version, api.uploadBuildCover);
}
