import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  MAX_TREE_WIDTH,
  MIN_TREE_WIDTH,
  readTreeWidth,
  writeTreeWidth,
  type CodeView,
} from "./codePrefs";

/** Keep enough room for the code/diff column next to the tree. */
const MIN_CONTENT_WIDTH = 320;

export function useTreeWidth(view: CodeView) {
  const [width, setWidth] = useState(() => readTreeWidth(view));
  const [dragging, setDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const widthRef = useRef(width);
  const cleanupRef = useRef<(() => void) | null>(null);

  const clamp = useCallback((value: number) => {
    const container = containerRef.current;
    if (!container || container.clientWidth <= 0) {
      return Math.max(MIN_TREE_WIDTH, Math.min(MAX_TREE_WIDTH, value));
    }
    const max = Math.max(
      MIN_TREE_WIDTH,
      Math.min(MAX_TREE_WIDTH, container.clientWidth - MIN_CONTENT_WIDTH)
    );
    return Math.max(MIN_TREE_WIDTH, Math.min(max, value));
  }, []);

  useEffect(() => {
    widthRef.current = width;
  }, [width]);

  // The workbench pane itself is resizable, so re-clamp whenever it changes.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => {
      setWidth((current) => clamp(current));
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [clamp]);

  useEffect(
    () => () => {
      cleanupRef.current?.();
    },
    []
  );

  const startResize = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = widthRef.current;

      const onMove = (moveEvent: PointerEvent) => {
        const next = clamp(startWidth + moveEvent.clientX - startX);
        widthRef.current = next;
        setWidth(next);
      };

      const finish = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", finish);
        window.removeEventListener("pointercancel", finish);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        cleanupRef.current = null;
        setDragging(false);
        writeTreeWidth(view, widthRef.current);
      };

      cleanupRef.current = finish;
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", finish);
      window.addEventListener("pointercancel", finish);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      setDragging(true);
    },
    [clamp, view]
  );

  return { width, dragging, containerRef, startResize };
}
