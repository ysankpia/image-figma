import type { BBox, Candidate, HandleName, ManualSlice } from './types';

export function area(box: BBox): number {
  return Math.max(0, box.width) * Math.max(0, box.height);
}

export function contains(box: BBox, point: { x: number; y: number }): boolean {
  return point.x >= box.x && point.y >= box.y && point.x <= box.x + box.width && point.y <= box.y + box.height;
}

export function moveBox(box: BBox, dx: number, dy: number, bounds: { width: number; height: number }): BBox {
  const x = clamp(box.x + dx, 0, Math.max(0, bounds.width - box.width));
  const y = clamp(box.y + dy, 0, Math.max(0, bounds.height - box.height));
  return { ...box, x, y };
}

export function resizeBox(box: BBox, handle: HandleName, dx: number, dy: number, bounds: { width: number; height: number }): BBox {
  let left = box.x;
  let top = box.y;
  let right = box.x + box.width;
  let bottom = box.y + box.height;
  if (handle.includes('w')) left += dx;
  if (handle.includes('e')) right += dx;
  if (handle.includes('n')) top += dy;
  if (handle.includes('s')) bottom += dy;
  left = clamp(left, 0, bounds.width);
  right = clamp(right, 0, bounds.width);
  top = clamp(top, 0, bounds.height);
  bottom = clamp(bottom, 0, bounds.height);
  if (right - left < 4) {
    if (handle.includes('w')) left = right - 4;
    else right = left + 4;
  }
  if (bottom - top < 4) {
    if (handle.includes('n')) top = bottom - 4;
    else bottom = top + 4;
  }
  left = clamp(left, 0, bounds.width - 1);
  top = clamp(top, 0, bounds.height - 1);
  right = clamp(right, left + 1, bounds.width);
  bottom = clamp(bottom, top + 1, bounds.height);
  return { x: Math.round(left), y: Math.round(top), width: Math.round(right - left), height: Math.round(bottom - top) };
}

export function handlesFor(box: BBox, size = 8): Array<{ name: HandleName; bbox: BBox }> {
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const right = box.x + box.width;
  const bottom = box.y + box.height;
  const points: Array<[HandleName, number, number]> = [
    ['nw', box.x, box.y],
    ['n', cx, box.y],
    ['ne', right, box.y],
    ['e', right, cy],
    ['se', right, bottom],
    ['s', cx, bottom],
    ['sw', box.x, bottom],
    ['w', box.x, cy],
  ];
  return points.map(([name, x, y]) => ({ name, bbox: { x: x - size / 2, y: y - size / 2, width: size, height: size } }));
}

export function hitHandle(slice: ManualSlice | undefined, point: { x: number; y: number }): HandleName | null {
  if (!slice) return null;
  const hit = handlesFor(slice.bbox, 10).find((handle) => contains(handle.bbox, point));
  return hit?.name ?? null;
}

export function sliceAt(slices: ManualSlice[], point: { x: number; y: number }): ManualSlice | undefined {
  return [...slices].reverse().find((slice) => slice.selected !== false && contains(slice.bbox, point));
}

export function candidateAt(candidates: Candidate[], hiddenIds: Set<string>, point: { x: number; y: number }): Candidate | undefined {
  return candidates
    .filter((candidate) => !hiddenIds.has(candidate.id) && contains(candidate.bbox, point))
    .sort((a, b) => area(a.bbox) - area(b.bbox) || b.confidence - a.confidence || a.id.localeCompare(b.id))[0];
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(value, max));
}
