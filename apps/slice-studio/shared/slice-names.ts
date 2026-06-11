import type { SliceRecord } from "./types";

const defaultSliceNamePattern = /^slice_(\d+)$/i;

export function defaultSliceName(index: number): string {
  return `slice_${String(index).padStart(2, "0")}`;
}

export function isDefaultSliceName(name: string): boolean {
  return defaultSliceNamePattern.test(name.trim());
}

export function normalizeDefaultSliceNames<T extends Pick<SliceRecord, "sliceIndex" | "name">>(slices: T[]): T[] {
  return slices.map((slice, index) => ({
    ...slice,
    sliceIndex: index + 1,
    name: isDefaultSliceName(slice.name) ? defaultSliceName(index + 1) : slice.name
  }));
}

