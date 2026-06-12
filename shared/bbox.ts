import type { BBox } from "./types";

export type ImageBounds = {
  width: number;
  height: number;
};

export type ResizeHandle = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";

export function normalizeBox(box: BBox, bounds: ImageBounds, minSize = 1): BBox {
  const x = clamp(Math.round(box.x), 0, Math.max(0, bounds.width - minSize));
  const y = clamp(Math.round(box.y), 0, Math.max(0, bounds.height - minSize));
  const width = clamp(Math.round(box.width), minSize, bounds.width - x);
  const height = clamp(Math.round(box.height), minSize, bounds.height - y);
  return { x, y, width, height };
}

export function moveBox(box: BBox, dx: number, dy: number, bounds: ImageBounds): BBox {
  return {
    x: clamp(Math.round(box.x + dx), 0, Math.max(0, bounds.width - box.width)),
    y: clamp(Math.round(box.y + dy), 0, Math.max(0, bounds.height - box.height)),
    width: box.width,
    height: box.height
  };
}

export function resizeBox(box: BBox, handle: ResizeHandle, dx: number, dy: number, bounds: ImageBounds, minSize = 8): BBox {
  let left = box.x;
  let top = box.y;
  let right = box.x + box.width;
  let bottom = box.y + box.height;

  if (handle.includes("w")) left += dx;
  if (handle.includes("e")) right += dx;
  if (handle.includes("n")) top += dy;
  if (handle.includes("s")) bottom += dy;

  left = clamp(Math.round(left), 0, bounds.width - minSize);
  top = clamp(Math.round(top), 0, bounds.height - minSize);
  right = clamp(Math.round(right), left + minSize, bounds.width);
  bottom = clamp(Math.round(bottom), top + minSize, bounds.height);

  return { x: left, y: top, width: right - left, height: bottom - top };
}

export function draftToBox(start: { x: number; y: number }, current: { x: number; y: number }, bounds: ImageBounds): BBox {
  return normalizeBox({
    x: Math.min(start.x, current.x),
    y: Math.min(start.y, current.y),
    width: Math.abs(current.x - start.x),
    height: Math.abs(current.y - start.y)
  }, bounds);
}

export function clamp(value: number, min: number, max: number): number {
  if (max < min) return min;
  return Math.max(min, Math.min(value, max));
}
