import sharp from "sharp";
import { pageExportDirectory } from "../shared/manifest";
import type { BBox, CutMode, ProjectDetail } from "../shared/types";
import { normalizeDefaultSliceNames } from "../shared/slice-names";
import { cropSliceToPng } from "./shape-cutout";
import type { TextReconstruction } from "./text-reconstruction";

const pageFrameGap = 160;

export type PencilPageTextManifest = {
  ocr: TextReconstruction["ocr"];
  textLayerCount: number;
  textLayers: Array<{
    id: string;
    text: string;
    placement: BBox;
    textRenderBBox: BBox;
    originalBBox: BBox;
    knockoutBBox: BBox;
    fontSize: number;
    fontFamily: string;
    fontWeight: string;
    color: string;
    confidence: number;
    textOwnerSurface?: unknown;
    textLayoutOwnerSurface?: unknown;
  }>;
};

export type PencilSlicePlacementManifest = {
  placement: BBox;
  originalBBox: BBox;
  alphaTrim?: BBox;
};

type Rgb = { r: number; g: number; b: number };
type BackgroundEstimate = { fill: Rgb; tolerance: number };

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
  const sourceData = Buffer.from(original.data);
  for (const bbox of textKnockouts) paintTextForeground(data, sourceData, original.info.width, original.info.height, bbox);
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

export function frameLayoutXPositions(pages: Array<{ width: number }>): number[] {
  const positions: number[] = [];
  let cursor = 0;
  for (const page of pages) {
    positions.push(cursor);
    cursor += Math.round(page.width) + pageFrameGap;
  }
  return positions;
}

export async function preparePencilSliceImage(slicePng: Buffer, sourceBBox: BBox, cutMode: CutMode): Promise<{
  data: Buffer;
  placement: BBox;
  alphaTrim?: BBox;
}> {
  if (cutMode === "rect") {
    return { data: slicePng, placement: roundBBox(sourceBBox) };
  }
  const raw = await sharp(slicePng).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const trim = alphaContentBBox(raw.data, raw.info.width, raw.info.height);
  if (!trim) return { data: slicePng, placement: roundBBox(sourceBBox) };
  const roundedSource = roundBBox(sourceBBox);
  if (trim.x === 0 && trim.y === 0 && trim.width === raw.info.width && trim.height === raw.info.height) {
    return { data: slicePng, placement: roundedSource };
  }
  const data = await sharp(slicePng)
    .extract({ left: trim.x, top: trim.y, width: trim.width, height: trim.height })
    .png()
    .toBuffer();
  return {
    data,
    placement: {
      x: roundedSource.x + trim.x,
      y: roundedSource.y + trim.y,
      width: trim.width,
      height: trim.height
    },
    alphaTrim: trim
  };
}

export function buildPencilManifest(
  detail: ProjectDetail,
  exportedAt: string,
  textByPageId: Map<string, PencilPageTextManifest> = new Map(),
  slicePlacements: Map<string, PencilSlicePlacementManifest> = new Map()
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
        slices: normalizeDefaultSliceNames(page.slices).map((slice, sliceIndex) => {
          const placement = slicePlacements.get(slice.id);
          return {
            id: slice.id,
            name: slice.name,
            kind: slice.kind,
            cutMode: slice.cutMode,
            filename: `assets/visible/slices/${pageDirectory}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
            placement: placement ? { ...placement.placement } : { ...slice.bbox },
            originalBBox: placement ? { ...placement.originalBBox } : { ...slice.bbox },
            alphaTrim: placement?.alphaTrim ? { ...placement.alphaTrim } : undefined,
            selected: true
          };
        }),
        ocr: textByPageId.get(page.id)?.ocr || {
          provider: "baidu_ppocrv5",
          status: "skipped",
          language: "zh+en",
          reason: "not_run",
          bboxProvider: "ocr",
          bboxProviderStatus: "skipped",
          bboxProviderReason: "not_run",
          sourceLineCount: 0,
          textLayerCount: 0,
          rasterPreservedTextCount: 0,
          skippedTextCount: 0,
          ownershipPolicy: "slice_studio_text_ownership.v1"
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

function alphaContentBBox(data: Buffer, width: number, height: number): BBox | null {
  let left = width;
  let top = height;
  let right = -1;
  let bottom = -1;
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) {
      if (data[(row + x) * 4 + 3] < 10) continue;
      if (x < left) left = x;
      if (y < top) top = y;
      if (x > right) right = x;
      if (y > bottom) bottom = y;
    }
  }
  if (right < left || bottom < top) return null;
  return { x: left, y: top, width: right - left + 1, height: bottom - top + 1 };
}

function roundBBox(bbox: BBox): BBox {
  return {
    x: Math.round(bbox.x),
    y: Math.round(bbox.y),
    width: Math.round(bbox.width),
    height: Math.round(bbox.height)
  };
}

function paintTextForeground(targetData: Buffer, sourceData: Buffer, width: number, height: number, bbox: BBox): void {
  const background = estimateBackgroundColor(sourceData, width, height, bbox);
  const pad = clamp(Math.round(bbox.height * 0.08), 1, 4);
  const left = clamp(Math.floor(bbox.x - pad), 0, width);
  const top = clamp(Math.floor(bbox.y - pad), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width + pad), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height + pad), top, height);
  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      const offset = (row + x) * 4;
      if (sourceData[offset + 3] < 200) continue;
      const pixel = { r: sourceData[offset], g: sourceData[offset + 1], b: sourceData[offset + 2] };
      if (!isForegroundTextPixel(pixel, background)) continue;
      targetData[offset] = background.fill.r;
      targetData[offset + 1] = background.fill.g;
      targetData[offset + 2] = background.fill.b;
      targetData[offset + 3] = 255;
    }
  }
}

function estimateBackgroundColor(data: Buffer, width: number, height: number, bbox: BBox): BackgroundEstimate {
  const local = sampleDominantInteriorColor(data, width, height, bbox);
  if (local) return local;

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
  if (!samples.length) return { fill: { r: 255, g: 255, b: 255 }, tolerance: 18 };
  return backgroundEstimate(samples);
}

function sampleDominantInteriorColor(data: Buffer, width: number, height: number, bbox: BBox): BackgroundEstimate | null {
  const left = clamp(Math.floor(bbox.x), 0, width);
  const top = clamp(Math.floor(bbox.y), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height), top, height);
  const buckets = new Map<string, { count: number; samples: Rgb[] }>();
  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      const sample = { r: data[offset], g: data[offset + 1], b: data[offset + 2] };
      const key = `${Math.round(sample.r / 32)}:${Math.round(sample.g / 32)}:${Math.round(sample.b / 32)}`;
      const bucket = buckets.get(key) || { count: 0, samples: [] };
      bucket.count += 1;
      bucket.samples.push(sample);
      buckets.set(key, bucket);
    }
  }
  if (buckets.size < 2) return null;
  const candidates = [...buckets.values()].filter((bucket) => bucket.count >= 8);
  if (!candidates.length) return null;
  candidates.sort((a, b) => b.count - a.count);
  return backgroundEstimate(candidates[0].samples);
}

function backgroundEstimate(samples: Rgb[]): BackgroundEstimate {
  const fill = medianRgb(samples);
  const distances = samples
    .map((sample) => colorDistance(sample, fill))
    .sort((a, b) => a - b);
  const p90 = distances[Math.min(distances.length - 1, Math.floor(distances.length * 0.9))] || 0;
  const channels = [fill.r, fill.g, fill.b];
  const chroma = Math.max(...channels) - Math.min(...channels);
  const baseTolerance = chroma >= 48 ? 24 : 18;
  const maxTolerance = chroma >= 48 ? 72 : 54;
  return {
    fill,
    tolerance: clamp(Math.round(p90 + baseTolerance), baseTolerance, maxTolerance)
  };
}

function isForegroundTextPixel(pixel: Rgb, background: BackgroundEstimate): boolean {
  const distance = colorDistance(pixel, background.fill);
  if (distance > background.tolerance) return true;
  const lumaDelta = Math.abs(luma(pixel) - luma(background.fill));
  return lumaDelta > background.tolerance * 0.75;
}

function colorDistance(a: Rgb, b: Rgb): number {
  return Math.sqrt(
    ((a.r - b.r) ** 2)
    + ((a.g - b.g) ** 2)
    + ((a.b - b.b) ** 2)
  );
}

function luma(color: Rgb): number {
  return 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b;
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
