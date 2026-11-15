import { clsx } from "clsx";
import type { ClassValue } from "clsx";

export * from "./Button";
export * from "./Field";
export * from "./Icon";
export * from "./Navigation";
export * from "./Overlay";
export * from "./Surface";

/** Merge conditional class names without writing string concatenation. */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}
