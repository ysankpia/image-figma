import { normalizeBox } from "./bbox";
import type { AiSliceBox, BBox, CutMode, PageRecord, SliceRecord } from "./types";

const existingIouThreshold = 0.6;

export type AiSliceMergePage = PageRecord & {
  slices: SliceRecord[];
};

export type AiSliceMergeResult = {
  slices: SliceRecord[];
  addedCount: number;
  skippedCount: number;
  lastAddedSliceId: string | null;
};

export function mergeAiBoxesIntoSlices(input: {
  projectId: string;
  page: AiSliceMergePage;
  boxes: AiSliceBox[];
  cutMode?: CutMode;
  idSeed?: string;
}): AiSliceMergeResult {
  const nextSlices = [...input.page.slices];
  let addedCount = 0;
  let skippedCount = 0;
  let lastAddedSliceId: string | null = null;
  const idSeed = input.idSeed || Date.now().toString(36);

  for (const box of input.boxes) {
    const bbox = normalizeBox(box.bbox, input.page, 1);
    if (nextSlices.some((slice) => iou(bbox, slice.bbox) >= existingIouThreshold)) {
      skippedCount += 1;
      continue;
    }
    const index = nextSlices.length + 1;
    const slice: SliceRecord = {
      id: `${input.page.id}__slice_ai_${idSeed}_${String(addedCount + 1).padStart(3, "0")}`,
      projectId: input.projectId,
      pageId: input.page.id,
      sliceIndex: index,
      name: defaultAiSliceName(index, box.name),
      kind: "image",
      cutMode: input.cutMode || "rect",
      bbox,
      selected: true
    };
    nextSlices.push(slice);
    addedCount += 1;
    lastAddedSliceId = slice.id;
  }

  return {
    slices: nextSlices,
    addedCount,
    skippedCount,
    lastAddedSliceId
  };
}

export function iou(a: BBox, b: BBox): number {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  const intersection = Math.max(0, right - left) * Math.max(0, bottom - top);
  if (intersection <= 0) return 0;
  return intersection / (a.width * a.height + b.width * b.height - intersection);
}

function defaultAiSliceName(index: number, name: string | undefined): string {
  if (name && !/^asset$/i.test(name.trim())) return name.trim().slice(0, 80);
  return `slice_${String(index).padStart(2, "0")}`;
}
