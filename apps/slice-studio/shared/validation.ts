import { normalizeBox } from "./bbox";
import type { BBox, CutMode, SliceKind } from "./types";

export function assertSafeId(value: string, label: string): void {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new Error(`${label} is invalid`);
  }
}

export function assertSafeSliceId(value: string): void {
  if (!/^[A-Za-z0-9_-]+(?:__[A-Za-z0-9_-]+)*$/.test(value)) {
    throw new Error("slice id is invalid");
  }
}

export function normalizeSliceKind(value: unknown): SliceKind {
  if (value !== "image") {
    throw new Error("slice kind must be image");
  }
  return value;
}

export function normalizeCutMode(value: unknown): CutMode {
  return value === "shape" ? "shape" : "rect";
}

export function normalizeSliceBox(box: BBox, bounds: { width: number; height: number }): BBox {
  const normalized = normalizeBox(box, bounds);
  if (normalized.width < 1 || normalized.height < 1) {
    throw new Error("slice bbox must be at least 1x1");
  }
  return normalized;
}
