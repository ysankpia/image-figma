import sharp from "sharp";
import { pageExportDirectory } from "../shared/manifest";
import type { BBox, CutMode, ProjectDetail } from "../shared/types";
import { normalizeDefaultSliceNames } from "../shared/slice-names";
import { cropSliceToPng } from "./shape-cutout";
import type { TextReconstruction } from "./text-reconstruction";

export type PencilPageTextManifest = {
  ocr: TextReconstruction["ocr"];
  textLayerCount: number;
  textLayers: Array<{
    id: string;
    text: string;
    placement: BBox;
    originalBBox: BBox;
    fontSize: number;
    fontFamily: string;
    fontWeight: string;
    color: string;
    confidence: number;
  }>;
};

type Rgb = { r: number; g: number; b: number };

type RemainderSlice = {
  bbox: BBox;
  cutMode?: CutMode;
  png?: Buffer;
};

export async function createRemainderPng(originalBuffer: Buffer, slices: RemainderSlice[], textKnockouts: BBox[] = []): Promise<Buffer> {
  const original = await sharp(originalBuffer)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  const data = Buffer.from(original.data);
  for (const bbox of textKnockouts) paintBackgroundRect(data, original.info.width, original.info.height, bbox);
  for (const slice of slices) {
    if (slice.cutMode === "subject" || slice.cutMode === "card") {
      await clearAlphaBySliceMask(data, original.info.width, original.info.height, originalBuffer, slice);
    } else {
      clearAlphaRect(data, original.info.width, original.info.height, slice.bbox);
    }
  }
  return sharp(data, { raw: { width: original.info.width, height: original.info.height, channels: 4 } })
    .png()
    .toBuffer();
}

export function buildPencilManifest(
  detail: ProjectDetail,
  exportedAt: string,
  textByPageId: Map<string, PencilPageTextManifest> = new Map()
) {
  return {
    schema: "slice_studio_pencil_project_manifest.v1",
    exportedAt,
    project: detail.project,
    pencil: {
      designPen: "design.pen",
      visibleAssetRoot: "assets/visible"
    },
    pages: detail.pages.map((page, pageIndex) => {
      const pageDirectory = pageExportDirectory(page.pageIndex || pageIndex + 1, page.displayName);
      return {
        pageId: page.id,
        pageIndex: page.pageIndex || pageIndex + 1,
        originalName: page.originalName,
        displayName: page.displayName,
        pageDirectory,
        original: `assets/originals/${pageDirectory}.png`,
        remainder: `assets/visible/remainders/${pageDirectory}/remainder.png`,
        width: page.width,
        height: page.height,
        slices: normalizeDefaultSliceNames(page.slices).map((slice, sliceIndex) => ({
          id: slice.id,
          name: slice.name,
          kind: slice.kind,
          cutMode: slice.cutMode,
          filename: `assets/visible/slices/${pageDirectory}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
          placement: { ...slice.bbox },
          selected: true
        })),
        ocr: textByPageId.get(page.id)?.ocr || {
          provider: "baidu_ppocrv5",
          status: "skipped",
          language: "zh+en",
          reason: "not_run",
          bboxProvider: "ocr",
          bboxProviderStatus: "skipped",
          bboxProviderReason: "not_run",
          sourceLineCount: 0,
          textLayerCount: 0
        },
        textLayerCount: textByPageId.get(page.id)?.textLayerCount || 0,
        textLayers: textByPageId.get(page.id)?.textLayers || []
      };
    })
  };
}

async function clearAlphaBySliceMask(data: Buffer, width: number, height: number, originalBuffer: Buffer, slice: RemainderSlice): Promise<void> {
  const box = roundedBox(slice.bbox, width, height);
  if (box.width <= 0 || box.height <= 0) return;

  const maskSource = slice.png || await cropSliceToPng(originalBuffer, {
    bbox: slice.bbox,
    cutMode: slice.cutMode || "rect"
  });
  const mask = await sharp(maskSource).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const maskWidth = Math.min(box.width, mask.info.width);
  const maskHeight = Math.min(box.height, mask.info.height);
  for (let y = 0; y < maskHeight; y += 1) {
    const targetRow = (box.top + y) * width;
    const maskRow = y * mask.info.width;
    for (let x = 0; x < maskWidth; x += 1) {
      if (mask.data[(maskRow + x) * 4 + 3] < 10) continue;
      data[(targetRow + box.left + x) * 4 + 3] = 0;
    }
  }
}

function clearAlphaRect(data: Buffer, width: number, height: number, bbox: BBox): void {
  const box = roundedBox(bbox, width, height);
  for (let y = box.top; y < box.top + box.height; y += 1) {
    const row = y * width;
    for (let x = box.left; x < box.left + box.width; x += 1) {
      data[(row + x) * 4 + 3] = 0;
    }
  }
}

function roundedBox(bbox: BBox, width: number, height: number): { left: number; top: number; width: number; height: number } {
  const left = clamp(Math.round(bbox.x), 0, width);
  const top = clamp(Math.round(bbox.y), 0, height);
  const right = clamp(Math.round(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.round(bbox.y + bbox.height), top, height);
  return { left, top, width: right - left, height: bottom - top };
}

function paintBackgroundRect(data: Buffer, width: number, height: number, bbox: BBox): void {
  const fill = sampleBackgroundColor(data, width, height, bbox);
  const pad = clamp(Math.round(bbox.height * 0.08), 1, 4);
  const left = clamp(Math.floor(bbox.x - pad), 0, width);
  const top = clamp(Math.floor(bbox.y - pad), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width + pad), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height + pad), top, height);
  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      const offset = (row + x) * 4;
      data[offset] = fill.r;
      data[offset + 1] = fill.g;
      data[offset + 2] = fill.b;
      data[offset + 3] = 255;
    }
  }
}

function sampleBackgroundColor(data: Buffer, width: number, height: number, bbox: BBox): Rgb {
  const ring = clamp(Math.round(bbox.height * 0.5), 4, 18);
  const innerLeft = clamp(Math.floor(bbox.x), 0, width);
  const innerTop = clamp(Math.floor(bbox.y), 0, height);
  const innerRight = clamp(Math.ceil(bbox.x + bbox.width), innerLeft, width);
  const innerBottom = clamp(Math.ceil(bbox.y + bbox.height), innerTop, height);
  const outerLeft = clamp(innerLeft - ring, 0, width);
  const outerTop = clamp(innerTop - ring, 0, height);
  const outerRight = clamp(innerRight + ring, outerLeft, width);
  const outerBottom = clamp(innerBottom + ring, outerTop, height);
  const samples: Rgb[] = [];
  for (let y = outerTop; y < outerBottom; y += 1) {
    const row = y * width;
    for (let x = outerLeft; x < outerRight; x += 1) {
      const insideText = x >= innerLeft && x < innerRight && y >= innerTop && y < innerBottom;
      if (insideText) continue;
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      samples.push({ r: data[offset], g: data[offset + 1], b: data[offset + 2] });
    }
  }
  if (!samples.length) return { r: 255, g: 255, b: 255 };
  return medianRgb(samples);
}

function medianRgb(samples: Rgb[]): Rgb {
  const rs = samples.map((sample) => sample.r).sort((a, b) => a - b);
  const gs = samples.map((sample) => sample.g).sort((a, b) => a - b);
  const bs = samples.map((sample) => sample.b).sort((a, b) => a - b);
  const middle = Math.floor(samples.length / 2);
  return { r: rs[middle], g: gs[middle], b: bs[middle] };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
