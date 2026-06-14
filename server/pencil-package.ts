import sharp from "sharp";
import { pageExportDirectory } from "../shared/manifest";
import type { BBox, CutMode, ProjectDetail } from "../shared/types";
import { normalizeDefaultSliceNames } from "../shared/slice-names";
import { cropSliceToPng } from "./shape-cutout";
import type { TextReconstruction } from "./text-reconstruction";
import type { SurfaceKnockout, TextKnockout } from "./render-plan";

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
    textStyleSource?: unknown;
    textStyleMeasured?: unknown;
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
type PaintRect = { left: number; top: number; width: number; height: number };

type RemainderSlice = {
  bbox: BBox;
  cutMode?: CutMode;
  png?: Buffer;
};

export async function createRemainderPng(
  originalBuffer: Buffer,
  slices: RemainderSlice[],
  textKnockouts: Array<BBox | TextKnockout> = [],
  surfaceKnockouts: SurfaceKnockout[] = []
): Promise<Buffer> {
  const original = await sharp(originalBuffer)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  const data = Buffer.from(original.data);
  const sourceData = Buffer.from(original.data);
  for (const knockout of textKnockouts) paintTextForeground(data, sourceData, original.info.width, original.info.height, normalizeTextKnockout(knockout));
  for (const knockout of surfaceKnockouts) clearSurfaceOwnership(data, sourceData, original.info.width, original.info.height, knockout);
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

function normalizeTextKnockout(value: BBox | TextKnockout): TextKnockout {
  if ("bbox" in value && "provenance" in value) return value;
  return {
    bbox: value,
    provenance: "ocr_text"
  };
}

function paintTextForeground(targetData: Buffer, sourceData: Buffer, width: number, height: number, knockout: TextKnockout): void {
  const bbox = knockout.bbox;
  const foreground = knockout.foregroundColor ? rgbFromHex(knockout.foregroundColor) : null;
  const background = estimateBackgroundColor(sourceData, width, height, bbox, foreground);
  const pad = knockout.paintPadding ?? clamp(Math.round(bbox.height * 0.08), 1, 4);
  const left = clamp(Math.floor(bbox.x - pad), 0, width);
  const top = clamp(Math.floor(bbox.y - pad), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width + pad), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height + pad), top, height);
  const clip = knockout.clipShape;
  const clipBox = clip ? roundedBox(clip.bbox, width, height) : null;
  const clipRadius = clip && clipBox
    ? clamp(Math.round(clip.cornerRadius), 0, Math.floor(Math.min(clipBox.width, clipBox.height) / 2))
    : 0;
  const rect: PaintRect = { left, top, width: right - left, height: bottom - top };
  if (rect.width <= 0 || rect.height <= 0) return;
  const mask = new Uint8Array(rect.width * rect.height);
  let marked = 0;
  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      if (clip && clipBox && !insideRoundedClip(x, y, clipBox, clipRadius)) continue;
      const offset = (row + x) * 4;
      if (sourceData[offset + 3] < 200) continue;
      const pixel = { r: sourceData[offset], g: sourceData[offset + 1], b: sourceData[offset + 2] };
      if (foreground
        ? !isForegroundTextPixelNearColor(pixel, foreground, background)
        : !isForegroundTextPixel(pixel, background)
      ) continue;
      const localIndex = (y - rect.top) * rect.width + (x - rect.left);
      mask[localIndex] = 1;
      marked += 1;
    }
  }
  if (!marked) return;
  const dilation = clamp(Math.ceil(bbox.height * 0.08), 1, 3);
  const paintMask = dilateTextMask(mask, rect.width, rect.height, dilation);
  if (clip && clipBox) constrainMaskToClip(paintMask, rect, clipBox, clipRadius, width, height);
  inpaintTextMask(targetData, width, height, rect, paintMask, background.fill);
}

function dilateTextMask(mask: Uint8Array, width: number, height: number, radius: number): Uint8Array {
  if (radius <= 0) return mask;
  const result = new Uint8Array(mask);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x;
      if (!mask[index]) continue;
      for (let dy = -radius; dy <= radius; dy += 1) {
        for (let dx = -radius; dx <= radius; dx += 1) {
          const nextX = x + dx;
          const nextY = y + dy;
          if (nextX < 0 || nextY < 0 || nextX >= width || nextY >= height) continue;
          result[nextY * width + nextX] = 1;
        }
      }
    }
  }
  return result;
}

function constrainMaskToClip(
  mask: Uint8Array,
  rect: PaintRect,
  clipBox: { left: number; top: number; width: number; height: number },
  clipRadius: number,
  pageWidth: number,
  pageHeight: number
): void {
  for (let localY = 0; localY < rect.height; localY += 1) {
    const y = rect.top + localY;
    if (y < 0 || y >= pageHeight) continue;
    for (let localX = 0; localX < rect.width; localX += 1) {
      const index = localY * rect.width + localX;
      if (!mask[index]) continue;
      const x = rect.left + localX;
      if (x < 0 || x >= pageWidth || !insideRoundedClip(x, y, clipBox, clipRadius)) mask[index] = 0;
    }
  }
}

function inpaintTextMask(targetData: Buffer, width: number, height: number, rect: PaintRect, mask: Uint8Array, fallback: Rgb): void {
  const resolved = new Uint8Array(mask.length);
  let unresolved = 0;
  for (let index = 0; index < mask.length; index += 1) {
    if (mask[index]) {
      unresolved += 1;
    } else {
      resolved[index] = 1;
    }
  }
  if (!unresolved) return;

  const maxIterations = clamp(Math.ceil(Math.max(rect.width, rect.height) * 0.35), 8, 36);
  for (let iteration = 0; iteration < maxIterations && unresolved > 0; iteration += 1) {
    const updates: Array<{ index: number; r: number; g: number; b: number }> = [];
    for (let localY = 0; localY < rect.height; localY += 1) {
      for (let localX = 0; localX < rect.width; localX += 1) {
        const index = localY * rect.width + localX;
        if (!mask[index] || resolved[index]) continue;
        let sumR = 0;
        let sumG = 0;
        let sumB = 0;
        let count = 0;
        for (let dy = -1; dy <= 1; dy += 1) {
          for (let dx = -1; dx <= 1; dx += 1) {
            if (dx === 0 && dy === 0) continue;
            const nextX = localX + dx;
            const nextY = localY + dy;
            if (nextX < 0 || nextY < 0 || nextX >= rect.width || nextY >= rect.height) continue;
            const nextIndex = nextY * rect.width + nextX;
            if (!resolved[nextIndex]) continue;
            const pageX = rect.left + nextX;
            const pageY = rect.top + nextY;
            if (pageX < 0 || pageY < 0 || pageX >= width || pageY >= height) continue;
            const offset = (pageY * width + pageX) * 4;
            if (targetData[offset + 3] < 200) continue;
            sumR += targetData[offset];
            sumG += targetData[offset + 1];
            sumB += targetData[offset + 2];
            count += 1;
          }
        }
        if (count > 0) updates.push({
          index,
          r: Math.round(sumR / count),
          g: Math.round(sumG / count),
          b: Math.round(sumB / count)
        });
      }
    }
    if (!updates.length) break;
    for (const update of updates) {
      const localX = update.index % rect.width;
      const localY = Math.floor(update.index / rect.width);
      const pageX = rect.left + localX;
      const pageY = rect.top + localY;
      if (pageX < 0 || pageY < 0 || pageX >= width || pageY >= height) continue;
      const offset = (pageY * width + pageX) * 4;
      targetData[offset] = update.r;
      targetData[offset + 1] = update.g;
      targetData[offset + 2] = update.b;
      targetData[offset + 3] = 255;
      resolved[update.index] = 1;
      unresolved -= 1;
    }
  }

  for (let localY = 0; localY < rect.height; localY += 1) {
    for (let localX = 0; localX < rect.width; localX += 1) {
      const index = localY * rect.width + localX;
      if (!mask[index] || resolved[index]) continue;
      const pageX = rect.left + localX;
      const pageY = rect.top + localY;
      if (pageX < 0 || pageY < 0 || pageX >= width || pageY >= height) continue;
      const offset = (pageY * width + pageX) * 4;
      targetData[offset] = fallback.r;
      targetData[offset + 1] = fallback.g;
      targetData[offset + 2] = fallback.b;
      targetData[offset + 3] = 255;
    }
  }
}

function insideRoundedClip(
  x: number,
  y: number,
  box: { left: number; top: number; width: number; height: number },
  radius: number
): boolean {
  if (x < box.left || x >= box.left + box.width || y < box.top || y >= box.top + box.height) return false;
  return pointInsideRoundedRect(x - box.left + 0.5, y - box.top + 0.5, box.width, box.height, radius);
}

function clearSurfaceOwnership(
  targetData: Buffer,
  sourceData: Buffer,
  width: number,
  height: number,
  knockout: SurfaceKnockout
): void {
  const shape = knockout.visibleShape;
  const region = knockout.sourceOwnerRegion;
  const pad = region.pad;
  const cleanupBox = roundedBox({
    x: shape.bbox.x - pad,
    y: shape.bbox.y - pad,
    width: shape.bbox.width + pad * 2,
    height: shape.bbox.height + pad * 2
  }, width, height);
  const visibleBox = roundedBox(shape.bbox, width, height);
  if (cleanupBox.width <= 0 || cleanupBox.height <= 0 || visibleBox.width <= 0 || visibleBox.height <= 0) return;
  const radius = clamp(
    Math.round(shape.cornerRadius),
    0,
    Math.floor(Math.min(visibleBox.width, visibleBox.height) / 2)
  );
  const paddedRadius = clamp(radius + pad, 0, Math.floor(Math.min(cleanupBox.width, cleanupBox.height) / 2));
  const fill = rgbFromHex(region.fill);
  const background = fill
    ? estimateOwnerBandBackground(sourceData, width, height, shape.bbox, pad)
    : null;
  const candidate = new Uint8Array(cleanupBox.width * cleanupBox.height);
  const owned = new Uint8Array(cleanupBox.width * cleanupBox.height);
  const queue: number[] = [];
  for (let y = cleanupBox.top; y < cleanupBox.top + cleanupBox.height; y += 1) {
    const row = y * width;
    for (let x = cleanupBox.left; x < cleanupBox.left + cleanupBox.width; x += 1) {
      const offset = (row + x) * 4;
      if (sourceData[offset + 3] < 10) continue;
      const localIndex = (y - cleanupBox.top) * cleanupBox.width + (x - cleanupBox.left);
      const insideVisibleBox = x >= visibleBox.left
        && x < visibleBox.left + visibleBox.width
        && y >= visibleBox.top
        && y < visibleBox.top + visibleBox.height;
      const insideVisibleSurface = insideVisibleBox && pointInsideRoundedRect(
        x - visibleBox.left + 0.5,
        y - visibleBox.top + 0.5,
        visibleBox.width,
        visibleBox.height,
        radius
      );
      if (insideVisibleSurface) {
        owned[localIndex] = 1;
        queue.push(localIndex);
        targetData[offset + 3] = 0;
        continue;
      }
      if (!fill || !background) continue;
      const insidePaddedSurface = pointInsideRoundedRect(
        x - cleanupBox.left + 0.5,
        y - cleanupBox.top + 0.5,
        cleanupBox.width,
        cleanupBox.height,
        paddedRadius
      );
      if (!insidePaddedSurface) continue;
      const sourcePixel = { r: sourceData[offset], g: sourceData[offset + 1], b: sourceData[offset + 2] };
      if (isOwnerBandPixel(sourcePixel, fill, background)) candidate[localIndex] = 1;
    }
  }

  while (queue.length) {
    const current = queue.shift() as number;
    const localX = current % cleanupBox.width;
    const localY = Math.floor(current / cleanupBox.width);
    for (let dy = -1; dy <= 1; dy += 1) {
      for (let dx = -1; dx <= 1; dx += 1) {
        if (dx === 0 && dy === 0) continue;
        const nextX = localX + dx;
        const nextY = localY + dy;
        if (nextX < 0 || nextY < 0 || nextX >= cleanupBox.width || nextY >= cleanupBox.height) continue;
        const nextIndex = nextY * cleanupBox.width + nextX;
        if (owned[nextIndex] || !candidate[nextIndex]) continue;
        owned[nextIndex] = 1;
        const targetOffset = ((cleanupBox.top + nextY) * width + cleanupBox.left + nextX) * 4;
        targetData[targetOffset + 3] = 0;
        queue.push(nextIndex);
      }
    }
  }
}

function estimateOwnerBandBackground(data: Buffer, width: number, height: number, bbox: BBox, pad: number): Rgb {
  const ring = 8;
  const innerLeft = clamp(Math.floor(bbox.x - pad), 0, width);
  const innerTop = clamp(Math.floor(bbox.y - pad), 0, height);
  const innerRight = clamp(Math.ceil(bbox.x + bbox.width + pad), innerLeft, width);
  const innerBottom = clamp(Math.ceil(bbox.y + bbox.height + pad), innerTop, height);
  const outerLeft = clamp(innerLeft - ring, 0, width);
  const outerTop = clamp(innerTop - ring, 0, height);
  const outerRight = clamp(innerRight + ring, outerLeft, width);
  const outerBottom = clamp(innerBottom + ring, outerTop, height);
  const samples: Rgb[] = [];
  for (let y = outerTop; y < outerBottom; y += 1) {
    const row = y * width;
    for (let x = outerLeft; x < outerRight; x += 1) {
      const insideOwnerSearch = x >= innerLeft && x < innerRight && y >= innerTop && y < innerBottom;
      if (insideOwnerSearch) continue;
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      samples.push({ r: data[offset], g: data[offset + 1], b: data[offset + 2] });
    }
  }
  if (!samples.length) return { r: 255, g: 255, b: 255 };
  return backgroundEstimate(samples).fill;
}

function isOwnerBandPixel(pixel: Rgb, fill: Rgb, background: Rgb): boolean {
  const backgroundDistance = colorDistance(pixel, background);
  if (backgroundDistance <= 6) return false;
  const fillBackgroundDistance = colorDistance(fill, background);
  if (fillBackgroundDistance <= 1) return colorDistance(pixel, fill) <= 18;

  const fillToBackground = {
    r: background.r - fill.r,
    g: background.g - fill.g,
    b: background.b - fill.b
  };
  const fillToPixel = {
    r: pixel.r - fill.r,
    g: pixel.g - fill.g,
    b: pixel.b - fill.b
  };
  const lengthSquared = fillBackgroundDistance * fillBackgroundDistance;
  const t = (
    fillToPixel.r * fillToBackground.r
    + fillToPixel.g * fillToBackground.g
    + fillToPixel.b * fillToBackground.b
  ) / lengthSquared;
  if (t < -0.1 || t > 1.08) return false;
  const projected = {
    r: fill.r + fillToBackground.r * t,
    g: fill.g + fillToBackground.g * t,
    b: fill.b + fillToBackground.b * t
  };
  const blendLineTolerance = clamp(fillBackgroundDistance * 0.08, 10, 34);
  return colorDistance(pixel, projected) <= blendLineTolerance;
}

function pointInsideRoundedRect(localX: number, localY: number, width: number, height: number, radius: number): boolean {
  if (radius <= 0) return true;
  if (localX >= radius && localX <= width - radius) return true;
  if (localY >= radius && localY <= height - radius) return true;
  const centerX = localX < radius ? radius : width - radius;
  const centerY = localY < radius ? radius : height - radius;
  const dx = localX - centerX;
  const dy = localY - centerY;
  return dx * dx + dy * dy <= radius * radius + 0.75;
}

function estimateBackgroundColor(
  data: Buffer,
  width: number,
  height: number,
  bbox: BBox,
  foreground?: Rgb | null
): BackgroundEstimate {
  if (foreground) {
    const local = sampleInteriorColorWithoutForeground(data, width, height, bbox, foreground);
    if (local) return local;
  }
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

function sampleInteriorColorWithoutForeground(
  data: Buffer,
  width: number,
  height: number,
  bbox: BBox,
  foreground: Rgb
): BackgroundEstimate | null {
  const left = clamp(Math.floor(bbox.x), 0, width);
  const top = clamp(Math.floor(bbox.y), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height), top, height);
  const samples: Rgb[] = [];
  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      const sample = { r: data[offset], g: data[offset + 1], b: data[offset + 2] };
      if (colorDistance(sample, foreground) <= 58) continue;
      samples.push(sample);
    }
  }
  if (samples.length < 8) return null;
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
  const channels = [background.fill.r, background.fill.g, background.fill.b];
  const chroma = Math.max(...channels) - Math.min(...channels);
  if (chroma <= 28) {
    const antialiasTolerance = Math.max(8, Math.min(18, background.tolerance * 0.45));
    return distance >= antialiasTolerance && lumaDelta >= antialiasTolerance;
  }
  return lumaDelta > background.tolerance * 0.75;
}

function isForegroundTextPixelNearColor(pixel: Rgb, foreground: Rgb, background: BackgroundEstimate): boolean {
  const foregroundDistance = colorDistance(pixel, foreground);
  const backgroundDistance = colorDistance(pixel, background.fill);
  if (foregroundDistance > 118) return false;
  if (foregroundDistance + 8 < backgroundDistance) return true;
  return foregroundDistance <= 48 && (backgroundDistance > 10 || Math.abs(luma(pixel) - luma(background.fill)) > 10);
}

function colorDistance(a: Rgb, b: Rgb): number {
  return Math.sqrt(
    ((a.r - b.r) ** 2)
    + ((a.g - b.g) ** 2)
    + ((a.b - b.b) ** 2)
  );
}

function rgbFromHex(value: string): Rgb | null {
  if (!value.startsWith("#")) return null;
  const hex = value.slice(1);
  if (!/^[0-9a-f]{6}$/iu.test(hex)) return null;
  return {
    r: Number.parseInt(hex.slice(0, 2), 16),
    g: Number.parseInt(hex.slice(2, 4), 16),
    b: Number.parseInt(hex.slice(4, 6), 16)
  };
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
