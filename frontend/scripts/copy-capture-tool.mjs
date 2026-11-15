// Serve the DOM-to-image library as a plain same-origin script for the
// cover-capture iframe. The workspace injects it into a sandboxed preview
// document and screenshots the app after publish.
//
// html-to-image is used instead of html2canvas because html2canvas clones the
// document through a nested iframe, which a sandboxed (opaque-origin) preview
// cannot access. html-to-image serializes the DOM into an SVG foreignObject and
// therefore stays inside the preview document.
import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, "node_modules/html-to-image/dist/html-to-image.js");
const target = resolve(root, "public/preview-assets/html-to-image.js");

await mkdir(dirname(target), { recursive: true });
await copyFile(source, target);
