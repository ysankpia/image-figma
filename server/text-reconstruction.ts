import sharp from "sharp";
import type { BBox, SliceRecord } from "../shared/types";
import { locateTextLinesWithM29, type LocatedTextLine, type TextLocationResult } from "./m29-text-locator";
import type { OcrLine, OcrResult } from "./text-ocr";

export type TextLayer = {
  id: string;
  text: string;
  bbox: BBox;
  safeBBox: BBox;
  originalBBox: BBox;
  fontSize: number;
  fontFamily: string;
  fontWeight: string;
  lineHeight: number;
  color: string;
  confidence: number;
  metadata: Record<string, unknown>;
};

export type TextOwnershipDecision = "editable_text" | "raster_preserve" | "skipped";

export type TextReconstruction = {
  ocr: {
    provider: OcrResult["provider"];
    status: OcrResult["status"];
    language: string;
    reason?: string;
    bboxProvider?: TextLocationResult["source"];
    bboxProviderStatus?: TextLocationResult["status"];
    bboxProviderReason?: string;
    sourceLineCount: number;
    textLayerCount: number;
    rasterPreservedTextCount: number;
    skippedTextCount: number;
    ownershipPolicy: "slice_studio_text_ownership.v1";
  };
  layers: TextLayer[];
};

type ReconstructOptions = {
  pageId: string;
  width: number;
  height: number;
  imageBuffer: Buffer;
  slices: SliceRecord[];
  ocr: OcrResult;
  locator?: (input: { imageBuffer: Buffer; width: number; height: number; ocr: OcrResult }) => TextLocationResult | Promise<TextLocationResult>;
};

const fontFamily = "PingFang SC";
const minTextHeight = 5;
const minLineConfidence = 70;
const minRemainingRatio = 0.55;
const minCoverageOverlapRatio = 0.25;

export async function reconstructTextLayers(options: ReconstructOptions): Promise<TextReconstruction> {
  const layers: TextLayer[] = [];
  const decisions: Array<{ decision: TextOwnershipDecision; reason: string }> = [];
  let textLocation: TextLocationResult | null = null;
  if (options.ocr.status === "ok") {
    const raw = await sharp(options.imageBuffer).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    textLocation = await (options.locator || locateTextLinesWithM29)({
      imageBuffer: options.imageBuffer,
      width: options.width,
      height: options.height,
      ocr: options.ocr
    });
    const blockers = options.slices.map((slice) => slice.bbox);
    const canUseLocalForeground = textLocation.source === "m29_ocr_hybrid" && textLocation.status === "ok";
    const locatedLines = textLocation.lines.map((located) => canUseLocalForeground
      ? refineWithLocalForeground(raw.data, raw.info.width, raw.info.height, located)
      : located);
    for (const located of locatedLines) {
      const ownership = classifyTextOwnership(located, options.width, blockers);
      decisions.push(ownership);
      if (ownership.decision !== "editable_text") continue;
      layers.push(makeTextLayer({
        index: layers.length,
        located,
        pageId: options.pageId,
        pageWidth: options.width,
        pageHeight: options.height,
        color: sampleTextColor(raw.data, raw.info.width, raw.info.height, located.bbox),
        ownershipReason: ownership.reason
      }));
    }
  }
  return {
    ocr: {
      provider: options.ocr.provider,
      status: options.ocr.status,
      language: options.ocr.language,
      reason: options.ocr.reason,
      bboxProvider: textLocation?.source,
      bboxProviderStatus: textLocation?.status,
      bboxProviderReason: textLocation?.reason,
      sourceLineCount: options.ocr.lines.length,
      textLayerCount: layers.length,
      rasterPreservedTextCount: decisions.filter((decision) => decision.decision === "raster_preserve").length,
      skippedTextCount: decisions.filter((decision) => decision.decision === "skipped").length,
      ownershipPolicy: "slice_studio_text_ownership.v1"
    },
    layers
  };
}

export function classifyTextOwnership(
  located: LocatedTextLine,
  pageWidth: number,
  blockers: BBox[]
): { decision: TextOwnershipDecision; reason: string } {
  const text = located.line.text.trim();
  if (!text) return { decision: "skipped", reason: "empty_text" };
  if (located.line.confidence < minLineConfidence) return { decision: "skipped", reason: "low_confidence" };
  if (located.bbox.width <= 0 || located.bbox.height < minTextHeight) return { decision: "skipped", reason: "invalid_or_too_small_bbox" };
  if (looksLikeGeneratedMarkerLabel(text)) return { decision: "raster_preserve", reason: "generated_asset_marker_label" };
  if (!textGeometryLooksEditable({ ...located.line, bbox: located.bbox }, pageWidth)) return { decision: "raster_preserve", reason: "geometry_not_editable" };
  if (remainingRatio(located.line.bbox, blockers) < minRemainingRatio) return { decision: "raster_preserve", reason: "ocr_text_inside_confirmed_slice" };
  if (remainingRatio(located.bbox, blockers) < minRemainingRatio) return { decision: "raster_preserve", reason: "physical_text_inside_confirmed_slice" };
  return { decision: "editable_text", reason: "normal_ocr_text" };
}

export function remainingRatio(bbox: BBox, blockers: BBox[]): number {
  const area = bbox.width * bbox.height;
  if (area <= 0) return 0;
  const covered = blockers.reduce((sum, blocker) => {
    const overlap = intersectionArea(bbox, blocker);
    const overlapRatio = overlap / area;
    return sum + (overlapRatio >= minCoverageOverlapRatio ? overlap : 0);
  }, 0);
  return Math.max(0, 1 - Math.min(1, covered / area));
}

function makeTextLayer(input: {
  index: number;
  located: LocatedTextLine;
  pageId: string;
  pageWidth: number;
  pageHeight: number;
  color: string;
  ownershipReason: string;
}): TextLayer {
  const line = input.located.line;
  const script = scriptForText(line.text);
  const fontSize = fitFontSize(line.text, input.located.bbox, input.located.bboxSource);
  const safeBBox = expandedTextBounds(input.located.bbox, input.pageWidth, input.pageHeight, fontSize, script);
  const fontWeight = inferFontWeight(line.text, input.located.bbox, input.located.bboxSource);
  return {
    id: `${input.pageId}__text_${String(input.index + 1).padStart(4, "0")}`,
    text: line.text.trim(),
    bbox: { ...input.located.bbox },
    safeBBox,
    originalBBox: { ...input.located.bbox },
    fontSize,
    fontFamily,
    fontWeight,
    lineHeight: 1,
    color: input.color,
    confidence: line.confidence,
    metadata: {
      type: "slice_studio_editable_text",
      editableMode: "ocr_text_remainder",
      source: "ocr_provider",
      sourceText: line.text.trim(),
      originalBBox: { ...input.located.bbox },
      ocrBBox: { ...line.bbox },
      physicalBBox: input.located.physicalBBox ? { ...input.located.physicalBBox } : undefined,
      bboxSource: input.located.bboxSource,
      bboxMatchScore: input.located.bboxMatchScore,
      bboxFallbackReason: input.located.bboxFallbackReason,
      m29PrimitiveId: input.located.m29PrimitiveId,
      safeBBox,
      safeBoundsPolicy: "slice_studio_text_safe_bounds.v1",
      script,
      confidence: line.confidence,
      wordCount: line.wordCount,
      textOwnershipPolicy: "slice_studio_text_ownership.v1",
      textOwnershipDecision: "editable_text",
      textOwnershipReason: input.ownershipReason,
      zRole: "editable_text"
    }
  };
}

function refineWithLocalForeground(data: Buffer, width: number, height: number, located: LocatedTextLine): LocatedTextLine {
  if (located.bboxSource !== "ocr") return located;
  const physicalBBox = localTextForegroundBBox(data, width, height, located.line.bbox);
  if (!physicalBBox) return located;
  if (textBoxIsTooBroadForLine(located.line.bbox, physicalBBox)) return located;
  return {
    ...located,
    bbox: physicalBBox,
    bboxSource: "local_foreground",
    physicalBBox,
    bboxMatchScore: 1
  };
}

function textBoxIsTooBroadForLine(ocrBBox: BBox, physicalBBox: BBox): boolean {
  const ocrArea = ocrBBox.width * ocrBBox.height;
  const physicalArea = physicalBBox.width * physicalBBox.height;
  if (ocrArea <= 0 || physicalArea <= 0) return true;

  const widthRatio = physicalBBox.width / Math.max(1, ocrBBox.width);
  const heightRatio = physicalBBox.height / Math.max(1, ocrBBox.height);
  const areaRatio = physicalArea / ocrArea;

  if (heightRatio >= 1.32 && areaRatio >= 1.85) return true;
  if (widthRatio >= 1.85 && heightRatio >= 1.12) return true;
  if (widthRatio >= 2.4) return true;
  return false;
}

export function textGeometryLooksEditable(line: OcrLine, pageWidth: number): boolean {
  const text = line.text.trim();
  if (!text) return false;
  const widthRatio = line.bbox.width / Math.max(1, pageWidth);
  if (widthRatio > 0.72 && text.length < 12) return false;
  if (widthRatio > 0.92) return false;
  if (line.bbox.height > 90 && text.length < 8) return false;
  if (hasCjk(text) && text.length <= 4 && line.bbox.height > line.bbox.width * 1.25) return false;
  return true;
}

function fitFontSize(text: string, bbox: BBox, bboxSource: LocatedTextLine["bboxSource"] = "ocr"): number {
  const script = scriptForText(text);
  const units = textVisualUnits(text);
  const isPhysicalBBox = bboxSource === "m29_foreground" || bboxSource === "local_foreground";
  const widthLimit = bbox.width * (isPhysicalBBox ? 1.02 : 0.94) / Math.max(1, units);
  const physicalHeightRatio = script === "latin" ? 0.7 : script === "mixed" ? 0.76 : text.length <= 4 ? 0.82 : 0.86;
  const heightLimit = bbox.height * (isPhysicalBBox ? physicalHeightRatio : script === "latin" ? 0.7 : 0.74);
  const raw = clamp(Math.min(widthLimit, heightLimit), 8, 56);
  return Math.round(raw * 10) / 10;
}

export function looksLikeGeneratedMarkerLabel(text: string): boolean {
  const compact = text.trim().replace(/[()［］\[\]{}]/g, "");
  if (/^(?:img|lmg|ing)[-_]?\d{1,4}$/iu.test(compact)) return true;
  if (/^[gm][-_]?\d{1,4}$/iu.test(compact)) return true;
  if (/^m[-_]\d{1,4}$/iu.test(compact)) return true;
  return false;
}

function expandedTextBounds(bbox: BBox, pageWidth: number, pageHeight: number, fontSize: number, script: string): BBox {
  const rightPad = Math.max(4, Math.round(fontSize * (script === "latin" ? 0.32 : 0.42)));
  const verticalPad = Math.max(2, Math.round(fontSize * 0.2));
  const left = clamp(Math.round(bbox.x), 0, pageWidth);
  const top = clamp(Math.round(bbox.y - verticalPad), 0, pageHeight);
  const right = clamp(Math.round(bbox.x + bbox.width + rightPad), left, pageWidth);
  const bottom = clamp(Math.round(bbox.y + bbox.height + verticalPad), top, pageHeight);
  return { x: left, y: top, width: Math.max(1, right - left), height: Math.max(1, bottom - top) };
}

function sampleTextColor(data: Buffer, width: number, height: number, bbox: BBox): string {
  const background = sampleBackgroundColor(data, width, height, bbox);
  const left = clamp(Math.floor(bbox.x), 0, width);
  const top = clamp(Math.floor(bbox.y), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height), top, height);
  const samples: Array<{ r: number; g: number; b: number; score: number }> = [];
  for (let y = top; y < bottom; y += 1) {
    for (let x = left; x < right; x += 1) {
      const offset = (y * width + x) * 4;
      const alpha = data[offset + 3];
      if (alpha < 200) continue;
      const r = data[offset];
      const g = data[offset + 1];
      const b = data[offset + 2];
      samples.push({ r, g, b, score: colorDistance({ r, g, b }, background) });
    }
  }
  if (!samples.length) return "#111111";
  samples.sort((a, b) => b.score - a.score);
  const chosen = samples.slice(0, Math.max(1, Math.min(samples.length, Math.round(samples.length * 0.15))));
  const average = chosen.reduce((sum, item) => ({
    r: sum.r + item.r,
    g: sum.g + item.g,
    b: sum.b + item.b
  }), { r: 0, g: 0, b: 0 });
  return toHex(
    Math.round(average.r / chosen.length),
    Math.round(average.g / chosen.length),
    Math.round(average.b / chosen.length)
  );
}

function localTextForegroundBBox(data: Buffer, width: number, height: number, bbox: BBox): BBox | null {
  const padX = Math.max(4, Math.round(bbox.height * 0.45));
  const padY = Math.max(2, Math.round(bbox.height * 0.25));
  const search = clampBox({
    x: bbox.x - padX,
    y: bbox.y - padY,
    width: bbox.width + padX * 2,
    height: bbox.height + padY * 2
  }, width, height);
  if (search.width <= 0 || search.height <= 0) return null;

  const background = sampleBackgroundColor(data, width, height, bbox);
  const distances: number[] = [];
  for (let y = search.y; y < search.y + search.height; y += 1) {
    const row = y * width;
    for (let x = search.x; x < search.x + search.width; x += 1) {
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      distances.push(colorDistance({ r: data[offset], g: data[offset + 1], b: data[offset + 2] }, background));
    }
  }
  if (distances.length < 8) return null;
  const threshold = Math.max(30, percentile(distances, 0.72) + 10);
  let left = width;
  let top = height;
  let right = 0;
  let bottom = 0;
  let count = 0;
  for (let y = search.y; y < search.y + search.height; y += 1) {
    const row = y * width;
    for (let x = search.x; x < search.x + search.width; x += 1) {
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      const distance = colorDistance({ r: data[offset], g: data[offset + 1], b: data[offset + 2] }, background);
      if (distance < threshold) continue;
      left = Math.min(left, x);
      top = Math.min(top, y);
      right = Math.max(right, x + 1);
      bottom = Math.max(bottom, y + 1);
      count += 1;
    }
  }
  const minPixels = Math.max(3, Math.round((bbox.width * bbox.height) * 0.012));
  if (count < minPixels || right <= left || bottom <= top) return null;
  const result = { x: left, y: top, width: right - left, height: bottom - top };
  if (result.width > bbox.width * 1.6 || result.height > bbox.height * 1.8) return null;
  return result;
}

function inferFontWeight(text: string, bbox: BBox, bboxSource: LocatedTextLine["bboxSource"] = "ocr"): string {
  const isPhysicalBBox = bboxSource === "m29_foreground" || bboxSource === "local_foreground";
  const height = isPhysicalBBox ? bbox.height * 1.25 : bbox.height;
  if (height >= 34 && text.length <= 8) return "600";
  if (height >= 24 && text.length <= 4) return "500";
  return "400";
}

function textVisualUnits(text: string): number {
  let units = 0;
  for (const char of text.trim()) {
    if (/\s/u.test(char)) units += 0.32;
    else if (/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(char)) units += 1;
    else if (/[0-9]/u.test(char)) units += 0.58;
    else if (/[A-Z]/u.test(char)) units += 0.66;
    else if (/[a-z]/u.test(char)) units += 0.56;
    else if (/[￥¥$%]/u.test(char)) units += 0.62;
    else units += 0.42;
  }
  return Math.max(1, units);
}

function sampleBackgroundColor(data: Buffer, width: number, height: number, bbox: BBox): { r: number; g: number; b: number } {
  const ring = clamp(Math.round(bbox.height * 0.5), 4, 18);
  const innerLeft = clamp(Math.floor(bbox.x), 0, width);
  const innerTop = clamp(Math.floor(bbox.y), 0, height);
  const innerRight = clamp(Math.ceil(bbox.x + bbox.width), innerLeft, width);
  const innerBottom = clamp(Math.ceil(bbox.y + bbox.height), innerTop, height);
  const outerLeft = clamp(innerLeft - ring, 0, width);
  const outerTop = clamp(innerTop - ring, 0, height);
  const outerRight = clamp(innerRight + ring, outerLeft, width);
  const outerBottom = clamp(innerBottom + ring, outerTop, height);
  const samples: Array<{ r: number; g: number; b: number }> = [];
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

function clampBox(bbox: BBox, width: number, height: number): BBox {
  const left = clamp(Math.floor(bbox.x), 0, width);
  const top = clamp(Math.floor(bbox.y), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height), top, height);
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function percentile(values: number[], ratio: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = clamp(Math.floor((sorted.length - 1) * ratio), 0, sorted.length - 1);
  return sorted[index];
}

function medianRgb(samples: Array<{ r: number; g: number; b: number }>): { r: number; g: number; b: number } {
  const rs = samples.map((sample) => sample.r).sort((a, b) => a - b);
  const gs = samples.map((sample) => sample.g).sort((a, b) => a - b);
  const bs = samples.map((sample) => sample.b).sort((a, b) => a - b);
  const middle = Math.floor(samples.length / 2);
  return { r: rs[middle], g: gs[middle], b: bs[middle] };
}

function colorDistance(a: { r: number; g: number; b: number }, b: { r: number; g: number; b: number }): number {
  const dr = a.r - b.r;
  const dg = a.g - b.g;
  const db = a.b - b.b;
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

function scriptForText(text: string): string {
  const cjk = hasCjk(text);
  const latin = /[A-Za-z0-9]/.test(text);
  if (cjk && latin) return "mixed";
  if (cjk) return "cjk";
  return "latin";
}

function hasCjk(text: string): boolean {
  return /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(text);
}

function intersectionArea(a: BBox, b: BBox): number {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  return Math.max(0, right - left) * Math.max(0, bottom - top);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function toHex(r: number, g: number, b: number): string {
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}

function hex(value: number): string {
  return clamp(value, 0, 255).toString(16).padStart(2, "0");
}
