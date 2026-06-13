import sharp from "sharp";
import type { BBox, SliceRecord } from "../shared/types";
import { locateTextLinesWithM29, type LocatedTextLine, type TextLocationResult } from "./m29-text-locator";
import type { OcrLine, OcrResult } from "./text-ocr";

export type TextLayer = {
  id: string;
  text: string;
  bbox: BBox;
  textRenderBBox: BBox;
  safeBBox: BBox;
  knockoutBBox: BBox;
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

type TextOwnerSurface = {
  bbox: BBox;
  fill: string;
  cornerRadius: number;
  confidence: number;
  reason: string;
  fillRatio: number;
  edgeCoverage: number;
};

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
    const locatedLines = textLocation.lines.map((located) => refineWithLocalForeground(
      raw.data,
      raw.info.width,
      raw.info.height,
      located,
      blockers,
      { refineOcrFallback: canUseLocalForeground }
    ));
    for (const located of locatedLines) {
      const ownership = classifyTextOwnership(located, options.width, blockers);
      decisions.push(ownership);
      if (ownership.decision !== "editable_text") continue;
      const ownerSurface = detectTextOwnerSurface(raw.data, raw.info.width, raw.info.height, located);
      const layoutOwnerSurface = ownerSurface && located.bboxSource !== "local_foreground" && canUseOwnerSurfaceForLayout(ownerSurface, located.line.bbox)
        ? ownerSurface
        : undefined;
      layers.push(makeTextLayer({
        index: layers.length,
        located,
        pageId: options.pageId,
        pageWidth: options.width,
        pageHeight: options.height,
        color: sampleTextColor(raw.data, raw.info.width, raw.info.height, located.line.bbox, ownerSurface),
        ownershipReason: ownership.reason,
        ownerSurface,
        layoutOwnerSurface
      }));
    }
    harmonizeTextRows(layers, options.width, options.height);
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
  ownerSurface?: TextOwnerSurface;
  layoutOwnerSurface?: TextOwnerSurface;
}): TextLayer {
  const line = input.located.line;
  const script = scriptForText(line.text);
  const isPhysicalBBox = input.located.bboxSource === "m29_foreground" || input.located.bboxSource === "local_foreground";
  const renderSourceBBox = isPhysicalBBox ? { ...input.located.bbox } : { ...line.bbox };
  const fontSize = fitFontSize(line.text, renderSourceBBox, input.layoutOwnerSurface, isPhysicalBBox);
  const placementBBox = input.layoutOwnerSurface
    ? ownerAwareTextBBox(line.text, renderSourceBBox, input.layoutOwnerSurface.bbox, fontSize, script, input.pageWidth, input.pageHeight)
    : renderSourceBBox;
  const textRenderBBox = textRenderBounds(line.text, placementBBox, input.layoutOwnerSurface?.bbox, fontSize, script, input.pageWidth, input.pageHeight);
  const safeBBox = expandedTextBounds(placementBBox, input.pageWidth, input.pageHeight, fontSize, script);
  const rawKnockoutBBox = textKnockoutBounds(line.bbox, renderSourceBBox, input.pageWidth, input.pageHeight, fontSize);
  const knockoutBBox = input.layoutOwnerSurface
    ? intersectionBox(rawKnockoutBBox, input.layoutOwnerSurface.bbox) || rawKnockoutBBox
    : rawKnockoutBBox;
  const fontWeight = inferFontWeight(line.text, renderSourceBBox);
  const physicalBBox = input.located.physicalBBox || (
    input.located.bboxSource === "m29_foreground" || input.located.bboxSource === "local_foreground"
      ? { ...input.located.bbox }
      : undefined
  );
  return {
    id: `${input.pageId}__text_${String(input.index + 1).padStart(4, "0")}`,
    text: line.text.trim(),
    bbox: placementBBox,
    textRenderBBox,
    safeBBox,
    knockoutBBox,
    originalBBox: renderSourceBBox,
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
      originalBBox: renderSourceBBox,
      textRenderBBox,
      sourceBBoxBeforeOwnerFit: input.layoutOwnerSurface ? renderSourceBBox : undefined,
      ocrBBox: { ...line.bbox },
      physicalBBox,
      bboxSource: input.located.bboxSource,
      bboxMatchScore: input.located.bboxMatchScore,
      bboxFallbackReason: input.located.bboxFallbackReason,
      m29PrimitiveId: input.located.m29PrimitiveId,
      safeBBox,
      knockoutBBox,
      knockoutPolicy: "slice_studio_text_knockout_bounds.v1",
      safeBoundsPolicy: "slice_studio_text_safe_bounds.v1",
      script,
      confidence: line.confidence,
      wordCount: line.wordCount,
      textOwnershipPolicy: "slice_studio_text_ownership.v1",
      textOwnershipDecision: "editable_text",
      textOwnershipReason: input.ownershipReason,
      textOwnerSurface: input.ownerSurface ? {
        bbox: input.ownerSurface.bbox,
        fill: input.ownerSurface.fill,
        cornerRadius: input.ownerSurface.cornerRadius,
        confidence: input.ownerSurface.confidence,
        reason: input.ownerSurface.reason,
        fillRatio: input.ownerSurface.fillRatio,
        edgeCoverage: input.ownerSurface.edgeCoverage
      } : undefined,
      textLayoutOwnerSurface: input.layoutOwnerSurface ? {
        bbox: input.layoutOwnerSurface.bbox,
        fill: input.layoutOwnerSurface.fill,
        cornerRadius: input.layoutOwnerSurface.cornerRadius,
        confidence: input.layoutOwnerSurface.confidence,
        reason: input.layoutOwnerSurface.reason,
        fillRatio: input.layoutOwnerSurface.fillRatio,
        edgeCoverage: input.layoutOwnerSurface.edgeCoverage
      } : undefined,
      zRole: "editable_text"
    }
  };
}

function textKnockoutBounds(ocrBBox: BBox, renderSourceBBox: BBox, pageWidth: number, pageHeight: number, fontSize: number): BBox {
  const ocrArea = ocrBBox.width * ocrBBox.height;
  const renderArea = renderSourceBBox.width * renderSourceBBox.height;
  const source = renderArea > 0 && renderArea <= ocrArea ? renderSourceBBox : ocrBBox;
  const pad = Math.max(1, Math.min(3, Math.round(fontSize * 0.1)));
  return clampBox({
    x: source.x - pad,
    y: source.y - pad,
    width: source.width + pad * 2,
    height: source.height + pad * 2
  }, pageWidth, pageHeight);
}

function canUseOwnerSurfaceForLayout(ownerSurface: TextOwnerSurface, sourceBBox: BBox): boolean {
  if (ownerSurface.reason !== "filled_control_surface") return false;
  if (ownerSurface.bbox.width < sourceBBox.width * 0.92) return false;
  if (ownerSurface.bbox.height < sourceBBox.height * 0.92) return false;
  if (ownerSurface.bbox.width > sourceBBox.width * 8 && ownerSurface.bbox.height > sourceBBox.height * 3.4) return false;
  return true;
}

function harmonizeTextRows(layers: TextLayer[], pageWidth: number, pageHeight: number): void {
  const rows: TextLayer[][] = [];
  for (const layer of [...layers].sort((a, b) => centerY(a.bbox) - centerY(b.bbox) || a.bbox.x - b.bbox.x)) {
    let placed = false;
    for (const row of rows) {
      const first = row[0];
      const tolerance = Math.max(8, Math.min(first.bbox.height, layer.bbox.height) * 0.42);
      if (Math.abs(centerY(layer.bbox) - centerY(first.bbox)) <= tolerance) {
        row.push(layer);
        placed = true;
        break;
      }
    }
    if (!placed) rows.push([layer]);
  }

  for (const row of rows) {
    if (row.length < 3) continue;
    const clusters = new Map<string, TextLayer[]>();
    for (const layer of row) {
      const script = String(layer.metadata.script || "");
      const key = `${layer.fontFamily}:${script}:${colorFamily(layer.color)}`;
      clusters.set(key, [...(clusters.get(key) || []), layer]);
    }
    for (const cluster of clusters.values()) {
      if (cluster.length < 3) continue;
      const sizes = cluster.map((layer) => Math.round(layer.fontSize));
      const mode = rowFontSizeMode(sizes);
      const threshold = Math.max(3, Math.min(6, Math.round(mode * 0.18)));
      const eligible = cluster.filter((layer) => Math.abs(Math.round(layer.fontSize) - mode) <= threshold);
      if (eligible.length < 2) continue;
      for (const layer of eligible) {
        if (Math.round(layer.fontSize) === mode) continue;
        layer.metadata.rowOriginalFontSize = layer.fontSize;
        layer.metadata.rowHarmonized = true;
        layer.fontSize = mode;
        layer.lineHeight = 1;
        const script = String(layer.metadata.script || "cjk");
        layer.textRenderBBox = textRenderBounds(layer.text, layer.bbox, ownerSurfaceBBox(layer.metadata.textLayoutOwnerSurface), mode, script, pageWidth, pageHeight);
        layer.safeBBox = expandedTextBounds(layer.bbox, pageWidth, pageHeight, mode, script);
        layer.metadata.textRenderBBox = layer.textRenderBBox;
        layer.metadata.safeBBox = layer.safeBBox;
      }
    }
  }
}

function ownerSurfaceBBox(value: unknown): BBox | undefined {
  if (!value || typeof value !== "object") return undefined;
  const bbox = (value as { bbox?: Partial<BBox> }).bbox;
  if (!bbox) return undefined;
  const x = Number(bbox.x);
  const y = Number(bbox.y);
  const width = Number(bbox.width);
  const height = Number(bbox.height);
  if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) return undefined;
  return { x, y, width, height };
}

function rowFontSizeMode(sizes: number[]): number {
  const counts = new Map<number, number>();
  for (const size of sizes) counts.set(size, (counts.get(size) || 0) + 1);
  const bestCount = Math.max(...counts.values());
  const candidates = [...counts.entries()].filter(([, count]) => count === bestCount).map(([size]) => size);
  if (bestCount > 1) return Math.round(medianNumber(candidates));
  return Math.round(medianNumber(sizes));
}

function refineWithLocalForeground(
  data: Buffer,
  width: number,
  height: number,
  located: LocatedTextLine,
  blockers: BBox[],
  options: { refineOcrFallback: boolean }
): LocatedTextLine {
  if (located.bboxSource === "local_foreground") return located;
  const overlapsConfirmedSlice = textCandidateOverlapsBlocker(located, blockers);
  const shouldRefine = located.bboxSource === "ocr"
    ? options.refineOcrFallback || overlapsConfirmedSlice
    : overlapsConfirmedSlice;
  if (!shouldRefine) return located;
  const physicalBBox = localTextForegroundBBox(data, width, height, located.line.bbox, blockers);
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

function textCandidateOverlapsBlocker(located: LocatedTextLine, blockers: BBox[]): boolean {
  if (!blockers.length) return false;
  return blockers.some((blocker) => {
    const lineOverlap = intersectionArea(located.line.bbox, blocker);
    const locatedOverlap = intersectionArea(located.bbox, blocker);
    return lineOverlap >= 4 || locatedOverlap >= 4;
  });
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

function fitFontSize(text: string, bbox: BBox, ownerSurface?: TextOwnerSurface, isPhysicalBBox = false): number {
  const value = text.trim();
  if (!value || bbox.width <= 0 || bbox.height <= 0) return 8;

  const maxSize = clamp(Math.round(bbox.height * (isPhysicalBBox ? 0.92 : 0.8)), 8, 55);
  let targetWidth = Math.max(1, Math.round(bbox.width * (isPhysicalBBox ? 0.96 : 0.98)));
  let targetHeight = Math.max(1, Math.round(bbox.height * (isPhysicalBBox ? 0.86 : 0.98)));

  if (ownerSurface) {
    const horizontalPadding = Math.max(4, Math.round(ownerSurface.bbox.height * 0.28));
    const verticalPadding = Math.max(3, Math.round(ownerSurface.bbox.height * 0.18));
    const availableWidth = Math.max(1, ownerSurface.bbox.width - horizontalPadding * 2);
    const availableHeight = Math.max(1, ownerSurface.bbox.height - verticalPadding * 2);
    if (bbox.width >= ownerSurface.bbox.width * 0.30) {
      targetWidth = Math.min(
        Math.max(targetWidth, Math.round(availableWidth * 0.96)),
        Math.max(1, Math.round(ownerSurface.bbox.width * 0.88))
      );
    }
    targetHeight = Math.min(targetHeight, Math.round(availableHeight * 0.92));
  }

  for (let size = maxSize; size >= 8; size -= 1) {
    const measured = measureTextPixels(value, size);
    if (measured.width <= targetWidth && measured.height <= targetHeight) return size;
  }
  return 8;
}

function ownerAwareTextBBox(
  text: string,
  sourceBBox: BBox,
  ownerBBox: BBox,
  fontSize: number,
  script: string,
  pageWidth: number,
  pageHeight: number
): BBox {
  const measured = measureTextPixels(text, fontSize);
  const lineBoxHeight = Math.max(
    1,
    Math.min(ownerBBox.height, Math.max(Math.round(fontSize), measured.height, Math.round(sourceBBox.height)))
  );
  const horizontalPadding = Math.max(4, Math.round(ownerBBox.height * 0.20));
  const maxWidth = Math.max(1, ownerBBox.width - horizontalPadding * 2);
  const expectedWidth = Math.max(1, Math.min(maxWidth, Math.max(Math.round(sourceBBox.width), measured.width)));
  const centerX = sourceBBox.x + sourceBBox.width / 2;
  const centerY = ownerBBox.y + ownerBBox.height / 2;
  const minX = ownerBBox.x + horizontalPadding;
  const maxX = ownerBBox.x + ownerBBox.width - horizontalPadding - expectedWidth;
  let x = Math.round(centerX - expectedWidth / 2);
  if (maxX >= minX) {
    x = clamp(x, minX, maxX);
  } else {
    x = ownerBBox.x + Math.max(0, Math.round((ownerBBox.width - expectedWidth) / 2));
  }
  const centeredY = centerY - lineBoxHeight / 2;
  return clampBox({
    x,
    y: centeredY,
    width: expectedWidth,
    height: lineBoxHeight
  }, pageWidth, pageHeight);
}

function textRenderBounds(
  text: string,
  placementBBox: BBox,
  ownerBBox: BBox | undefined,
  fontSize: number,
  script: string,
  pageWidth: number,
  pageHeight: number
): BBox {
  const measured = measureTextPixels(text, fontSize);
  const horizontalPad = Math.max(2, Math.round(fontSize * (script === "latin" ? 0.12 : 0.14)));
  const compactWidth = Math.max(1, measured.width + horizontalPad * 2);
  const compactHeight = Math.max(
    measured.height,
    Math.round(fontSize * (script === "latin" ? 0.96 : script === "mixed" ? 1.02 : 1.05))
  );

  if (ownerBBox) {
    const ownerPad = Math.max(3, Math.round(ownerBBox.height * 0.12));
    const maxWidth = Math.max(1, ownerBBox.width - ownerPad * 2);
    const width = Math.max(1, Math.min(maxWidth, compactWidth));
    const height = Math.max(1, Math.min(ownerBBox.height, compactHeight));
    const centerX = placementBBox.x + placementBBox.width / 2;
    const centerY = ownerBBox.y + ownerBBox.height / 2;
    const minX = ownerBBox.x + ownerPad;
    const maxX = ownerBBox.x + ownerBBox.width - ownerPad - width;
    let x = Math.round(centerX - width / 2);
    if (maxX >= minX) {
      x = clamp(x, minX, maxX);
    } else {
      x = Math.round(ownerBBox.x + (ownerBBox.width - width) / 2);
    }
    return clampBox({
      x,
      y: Math.round(centerY - height / 2),
      width,
      height
    }, pageWidth, pageHeight);
  }

  const width = Math.max(placementBBox.width, compactWidth);
  const height = Math.max(placementBBox.height, compactHeight);
  return clampBox({
    x: Math.round(placementBBox.x),
    y: Math.round(placementBBox.y + placementBBox.height / 2 - height / 2),
    width,
    height
  }, pageWidth, pageHeight);
}

function estimatedRenderedTextWidth(text: string, fontSize: number, script: string): number {
  return Math.max(fontSize, textVisualUnits(text) * fontSize);
}

function measureTextPixels(text: string, fontSize: number): { width: number; height: number } {
  const script = scriptForText(text);
  return {
    width: Math.ceil(estimatedRenderedTextWidth(text, fontSize, script)),
    height: Math.ceil(fontSize * (script === "latin" ? 0.78 : script === "mixed" ? 0.86 : 0.84))
  };
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

function sampleTextColor(data: Buffer, width: number, height: number, bbox: BBox, ownerSurface?: TextOwnerSurface): string {
  const ownerFill = ownerSurface?.reason === "filled_control_surface" ? rgbFromHex(ownerSurface.fill) : null;
  const background = ownerFill || sampleBackgroundColor(data, width, height, bbox);
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
  const chosen = samples.slice(0, Math.max(1, Math.min(samples.length, Math.round(samples.length * 0.05), 80)));
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

function localTextForegroundBBox(data: Buffer, width: number, height: number, bbox: BBox, blockers: BBox[]): BBox | null {
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
  const blockerPad = Math.max(2, Math.min(4, Math.round(bbox.height * 0.12)));
  const localBlockers = blockers
    .map((blocker) => expandBox(blocker, blockerPad, width, height))
    .filter((blocker) => intersectionArea(search, blocker) > 0);
  const distances: number[] = [];
  for (let y = search.y; y < search.y + search.height; y += 1) {
    const row = y * width;
    for (let x = search.x; x < search.x + search.width; x += 1) {
      if (insideAnyBox(x, y, localBlockers)) continue;
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
  const mask = new Uint8Array(search.width * search.height);
  for (let y = search.y; y < search.y + search.height; y += 1) {
    const row = y * width;
    for (let x = search.x; x < search.x + search.width; x += 1) {
      if (insideAnyBox(x, y, localBlockers)) continue;
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      const distance = colorDistance({ r: data[offset], g: data[offset + 1], b: data[offset + 2] }, background);
      if (distance < threshold) continue;
      mask[(y - search.y) * search.width + (x - search.x)] = 1;
      left = Math.min(left, x);
      top = Math.min(top, y);
      right = Math.max(right, x + 1);
      bottom = Math.max(bottom, y + 1);
      count += 1;
    }
  }
  const minPixels = Math.max(3, Math.round((bbox.width * bbox.height) * 0.012));
  if (count < minPixels || right <= left || bottom <= top) return null;
  const components = textForegroundComponents(mask, search, bbox);
  if (!components.length) return null;
  const result = unionComponentBBox(components);
  if (result.width > bbox.width * 1.6 || result.height > bbox.height * 1.8) return null;
  return result;
}

function textForegroundComponents(mask: Uint8Array, search: BBox, textBBox: BBox): Array<{ bbox: BBox; area: number }> {
  const visited = new Uint8Array(mask.length);
  const components: Array<{ bbox: BBox; area: number }> = [];
  for (let localY = 0; localY < search.height; localY += 1) {
    for (let localX = 0; localX < search.width; localX += 1) {
      const start = localY * search.width + localX;
      if (!mask[start] || visited[start]) continue;
      const component = floodMarkedComponent(mask, visited, search, localX, localY);
      if (!componentLooksLikeTextForeground(component, textBBox)) continue;
      components.push(component);
    }
  }
  return components;
}

function componentLooksLikeTextForeground(component: { bbox: BBox; area: number }, textBBox: BBox): boolean {
  if (component.area < 4) return false;
  if (intersectionArea(component.bbox, textBBox) <= 0) return false;
  const horizontalRule = component.bbox.width > textBBox.width * 0.55 && component.bbox.height <= 4;
  if (horizontalRule) return false;
  const verticalRule = component.bbox.height > textBBox.height * 0.72 && component.bbox.width <= 3;
  if (verticalRule) return false;
  const oversizedSurface = component.bbox.width > textBBox.width * 1.15 && component.bbox.height > textBBox.height * 0.55;
  if (oversizedSurface) return false;
  return true;
}

function unionComponentBBox(components: Array<{ bbox: BBox }>): BBox {
  const left = Math.min(...components.map((component) => component.bbox.x));
  const top = Math.min(...components.map((component) => component.bbox.y));
  const right = Math.max(...components.map((component) => component.bbox.x + component.bbox.width));
  const bottom = Math.max(...components.map((component) => component.bbox.y + component.bbox.height));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function insideAnyBox(x: number, y: number, boxes: BBox[]): boolean {
  return boxes.some((box) => x >= box.x && x < box.x + box.width && y >= box.y && y < box.y + box.height);
}

function expandBox(bbox: BBox, pad: number, width: number, height: number): BBox {
  return clampBox({
    x: bbox.x - pad,
    y: bbox.y - pad,
    width: bbox.width + pad * 2,
    height: bbox.height + pad * 2
  }, width, height);
}

function detectTextOwnerSurface(data: Buffer, width: number, height: number, located: LocatedTextLine): TextOwnerSurface | undefined {
  const text = located.line.text.trim();
  if (!looksLikeShortControlText(text)) return undefined;
  const seededSurface = detectSeededFilledControlSurface(data, width, height, located.line.bbox);
  if (seededSurface) return seededSurface;

  const bbox = located.bbox;
  const padX = clamp(Math.round(Math.max(18, Math.min(120, bbox.height * 2.8))), 8, 140);
  const padY = clamp(Math.round(Math.max(8, Math.min(26, bbox.height * 0.85))), 4, 32);
  const search = clampBox({
    x: bbox.x - padX,
    y: bbox.y - padY,
    width: bbox.width + padX * 2,
    height: bbox.height + padY * 2
  }, width, height);
  if (search.width < 24 || search.height < 16) return undefined;

  const pageBackground = sampleSearchEdgeColor(data, width, height, search);
  const threshold = 30;
  const localMask = new Uint8Array(search.width * search.height);
  for (let y = search.y; y < search.y + search.height; y += 1) {
    const row = y * width;
    for (let x = search.x; x < search.x + search.width; x += 1) {
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      const distance = colorDistance({ r: data[offset], g: data[offset + 1], b: data[offset + 2] }, pageBackground);
      if (distance < threshold) continue;
      localMask[(y - search.y) * search.width + (x - search.x)] = 1;
    }
  }
  const component = selectedSurfaceComponent(localMask, search, bbox);
  if (!component || component.area < 12) return undefined;
  const candidate = component.bbox;
  if (!finiteControlSurfaceGeometry(candidate, bbox, width, height)) return undefined;

  const fillRatio = component.area / Math.max(1, candidate.width * candidate.height);
  const fill = sampleControlSurfaceFill(data, width, height, candidate, located.line.bbox, pageBackground);
  const edgeCoverage = markedEdgeCoverage(data, width, height, candidate, pageBackground, threshold);
  const filledSurface = fillRatio >= 0.42;
  if (filledSurface && !hasControlSurfacePadding(candidate, bbox)) return undefined;
  const strongOutline = edgeCoverage >= 0.55;
  const largerSurface = candidate.width >= bbox.width * 1.10 || candidate.height >= bbox.height * 1.10;
  const materialSurfaceEvidence = strongOutline || largerSurface;
  const extraSupport = filledSurface || strongOutline || largerSurface;
  if (!extraSupport) return undefined;
  if (filledSurface && !materialSurfaceEvidence) return undefined;
  if (!filledSurface && !strongOutline && edgeCoverage < 0.24) return undefined;

  return {
    bbox: candidate,
    fill: toHex(fill.r, fill.g, fill.b),
    cornerRadius: inferControlCornerRadius(data, width, height, candidate, fill),
    confidence: Math.round(Math.max(fillRatio, edgeCoverage) * 100) / 100,
    reason: fillRatio >= 0.42 ? "filled_control_surface" : "outlined_control_surface",
    fillRatio: Math.round(fillRatio * 1000) / 1000,
    edgeCoverage: Math.round(edgeCoverage * 1000) / 1000
  };
}

function detectSeededFilledControlSurface(data: Buffer, width: number, height: number, textBBox: BBox): TextOwnerSurface | undefined {
  const padX = clamp(Math.round(Math.max(32, Math.min(180, textBBox.width * 1.55))), 16, 220);
  const padY = clamp(Math.round(Math.max(22, Math.min(72, textBBox.height * 1.35))), 10, 90);
  const search = clampBox({
    x: textBBox.x - padX,
    y: textBBox.y - padY,
    width: textBBox.width + padX * 2,
    height: textBBox.height + padY * 2
  }, width, height);
  if (search.width < 24 || search.height < 16) return undefined;

  const pageBackground = sampleSearchEdgeColor(data, width, height, search);
  const seed = estimateSurfaceFillNearText(data, width, height, textBBox, search, pageBackground);
  const seedPageDistance = colorDistance(seed.fill, pageBackground);
  if (seedPageDistance < 48) return undefined;

  const closeThreshold = seedPageDistance >= 80
    ? 58
    : seedPageDistance >= 32
      ? Math.max(20, seedPageDistance * 0.7)
      : Math.max(10, seedPageDistance * 0.55);
  const mask = new Uint8Array(search.width * search.height);
  for (let y = search.y; y < search.y + search.height; y += 1) {
    const row = y * width;
    for (let x = search.x; x < search.x + search.width; x += 1) {
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      const distance = colorDistance({ r: data[offset], g: data[offset + 1], b: data[offset + 2] }, seed.fill);
      if (distance > closeThreshold) continue;
      mask[(y - search.y) * search.width + (x - search.x)] = 1;
    }
  }

  const component = bestSeededSurfaceComponent(mask, search, textBBox);
  if (!component || component.area < 16) return undefined;
  const candidate = component.bbox;
  if (!finiteControlSurfaceGeometry(candidate, textBBox, width, height)) return undefined;
  if (!hasControlSurfacePadding(candidate, textBBox)) return undefined;

  const fillRatio = component.area / Math.max(1, candidate.width * candidate.height);
  if (fillRatio < 0.30) return undefined;
  const fill = sampleControlSurfaceFill(data, width, height, candidate, textBBox, pageBackground);
  if (colorDistance(fill, pageBackground) < 42) return undefined;
  const edgeCoverage = filledSurfaceCoverage(data, width, height, candidate, fill, 64);
  if (edgeCoverage < 0.42 && fillRatio < 0.48) return undefined;

  return {
    bbox: candidate,
    fill: toHex(fill.r, fill.g, fill.b),
    cornerRadius: inferControlCornerRadius(data, width, height, candidate, fill),
    confidence: Math.round(Math.max(fillRatio, edgeCoverage) * 100) / 100,
    reason: "filled_control_surface",
    fillRatio: Math.round(fillRatio * 1000) / 1000,
    edgeCoverage: Math.round(edgeCoverage * 1000) / 1000
  };
}

function hasControlSurfacePadding(candidate: BBox, textBBox: BBox): boolean {
  const textArea = textBBox.width * textBBox.height;
  const candidateArea = candidate.width * candidate.height;
  if (textArea <= 0 || candidateArea <= 0) return false;
  if (candidateArea / textArea < 1.12) return false;

  const leftPad = textBBox.x - candidate.x;
  const rightPad = candidate.x + candidate.width - (textBBox.x + textBBox.width);
  const topPad = textBBox.y - candidate.y;
  const bottomPad = candidate.y + candidate.height - (textBBox.y + textBBox.height);
  if (Math.min(leftPad, rightPad, topPad, bottomPad) < -1) return false;
  if (leftPad + rightPad < Math.max(6, Math.round(candidate.width * 0.08))) return false;
  if (topPad + bottomPad < Math.max(4, Math.round(candidate.height * 0.08))) return false;
  return true;
}

function estimateSurfaceFillNearText(
  data: Buffer,
  width: number,
  height: number,
  textBBox: BBox,
  search: BBox,
  pageBackground: { r: number; g: number; b: number }
): { fill: { r: number; g: number; b: number }; coverage: number } {
  const outerPadX = Math.max(8, Math.min(80, Math.round(textBBox.width * 0.55)));
  const outerPadY = Math.max(6, Math.min(48, Math.round(textBBox.height * 1.35)));
  const outer = intersectionBox(clampBox({
    x: textBBox.x - outerPadX,
    y: textBBox.y - outerPadY,
    width: textBBox.width + outerPadX * 2,
    height: textBBox.height + outerPadY * 2
  }, width, height), search);
  if (!outer || outer.width <= 0 || outer.height <= 0) return { fill: pageBackground, coverage: 0 };

  const inner = clampBox({
    x: textBBox.x - 1,
    y: textBBox.y - 1,
    width: textBBox.width + 2,
    height: textBBox.height + 2
  }, width, height);
  const localPixels = collectRegionPixels(data, width, height, outer, inner);
  const local = dominantRgbStats(localPixels.length ? localPixels : collectRegionPixels(data, width, height, outer));
  const box = dominantRgbStats(collectRegionPixels(data, width, height, textBBox));
  const boxPageDistance = colorDistance(box.fill, pageBackground);
  const localPageDistance = colorDistance(local.fill, pageBackground);
  if (box.coverage >= 0.18 && boxPageDistance >= Math.max(48, localPageDistance + 28)) return box;
  return local;
}

function collectRegionPixels(
  data: Buffer,
  width: number,
  height: number,
  bbox: BBox,
  exclude?: BBox
): Array<{ r: number; g: number; b: number }> {
  const box = clampBox(bbox, width, height);
  const samples: Array<{ r: number; g: number; b: number }> = [];
  for (let y = box.y; y < box.y + box.height; y += 1) {
    const row = y * width;
    for (let x = box.x; x < box.x + box.width; x += 1) {
      if (exclude && containsPoint(exclude, x, y)) continue;
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      samples.push({ r: data[offset], g: data[offset + 1], b: data[offset + 2] });
    }
  }
  return samples;
}

function dominantRgbStats(samples: Array<{ r: number; g: number; b: number }>): { fill: { r: number; g: number; b: number }; coverage: number } {
  if (!samples.length) return { fill: { r: 255, g: 255, b: 255 }, coverage: 0 };
  const buckets = new Map<string, { count: number; samples: Array<{ r: number; g: number; b: number }> }>();
  for (const sample of samples) {
    const key = `${Math.round(sample.r / 20)}:${Math.round(sample.g / 20)}:${Math.round(sample.b / 20)}`;
    const bucket = buckets.get(key) || { count: 0, samples: [] };
    bucket.count += 1;
    bucket.samples.push(sample);
    buckets.set(key, bucket);
  }
  const candidates = [...buckets.values()].sort((a, b) => b.count - a.count);
  const best = candidates[0] || { count: 0, samples };
  return {
    fill: medianRgb(best.samples),
    coverage: best.count / Math.max(1, samples.length)
  };
}

function bestSeededSurfaceComponent(mask: Uint8Array, search: BBox, textBBox: BBox): { bbox: BBox; area: number } | null {
  const visited = new Uint8Array(mask.length);
  const seed = expandBox(textBBox, 2, search.x + search.width, search.y + search.height);
  let best: { bbox: BBox; area: number; score: number } | null = null;
  for (let localY = 0; localY < search.height; localY += 1) {
    for (let localX = 0; localX < search.width; localX += 1) {
      const start = localY * search.width + localX;
      if (!mask[start] || visited[start]) continue;
      const component = floodMarkedComponent(mask, visited, search, localX, localY);
      const denseCore = denseSurfaceCoreBBox(mask, search, component.bbox, textBBox) || component;
      const overlap = intersectionArea(denseCore.bbox, seed);
      if (overlap <= 0 && !containsPoint(denseCore.bbox, textBBox.x + textBBox.width / 2, textBBox.y + textBBox.height / 2)) continue;
      const areaRatio = denseCore.bbox.width * denseCore.bbox.height / Math.max(1, textBBox.width * textBBox.height);
      const score = overlap * 4 + denseCore.area - Math.max(0, areaRatio - 8) * 200;
      if (!best || score > best.score) best = { ...denseCore, score };
    }
  }
  return best ? { bbox: best.bbox, area: best.area } : null;
}

function denseSurfaceCoreBBox(mask: Uint8Array, search: BBox, componentBBox: BBox, textBBox: BBox): { bbox: BBox; area: number } | null {
  const localLeft = clamp(componentBBox.x - search.x, 0, search.width);
  const localTop = clamp(componentBBox.y - search.y, 0, search.height);
  const localRight = clamp(componentBBox.x + componentBBox.width - search.x, localLeft, search.width);
  const localBottom = clamp(componentBBox.y + componentBBox.height - search.y, localTop, search.height);
  const localWidth = localRight - localLeft;
  const localHeight = localBottom - localTop;
  if (localWidth <= 0 || localHeight <= 0) return null;

  const colCounts = new Array<number>(localWidth).fill(0);
  for (let y = localTop; y < localBottom; y += 1) {
    const row = y * search.width;
    for (let x = localLeft; x < localRight; x += 1) {
      if (mask[row + x]) colCounts[x - localLeft] += 1;
    }
  }
  const colThreshold = Math.max(4, Math.round(localHeight * 0.30));
  const colRun = bestDenseRun(
    colCounts.map((count) => count >= colThreshold),
    textBBox.x - componentBBox.x,
    textBBox.x + textBBox.width - componentBBox.x
  );
  if (!colRun) return null;

  const coreLocalLeft = localLeft + colRun.start;
  const coreLocalRight = localLeft + colRun.end;
  const coreWidth = coreLocalRight - coreLocalLeft;
  if (coreWidth <= 0) return null;

  const rowCounts = new Array<number>(localHeight).fill(0);
  for (let y = localTop; y < localBottom; y += 1) {
    const row = y * search.width;
    for (let x = coreLocalLeft; x < coreLocalRight; x += 1) {
      if (mask[row + x]) rowCounts[y - localTop] += 1;
    }
  }
  const rowThreshold = Math.max(4, Math.round(coreWidth * 0.30));
  const rowRun = bestDenseRun(
    rowCounts.map((count) => count >= rowThreshold),
    textBBox.y - componentBBox.y,
    textBBox.y + textBBox.height - componentBBox.y
  );
  if (!rowRun) return null;

  const coreLocalTop = localTop + rowRun.start;
  const coreLocalBottom = localTop + rowRun.end;
  const coreHeight = coreLocalBottom - coreLocalTop;
  if (coreHeight <= 0) return null;

  let area = 0;
  for (let y = coreLocalTop; y < coreLocalBottom; y += 1) {
    const row = y * search.width;
    for (let x = coreLocalLeft; x < coreLocalRight; x += 1) {
      if (mask[row + x]) area += 1;
    }
  }
  if (area < 16) return null;
  return {
    bbox: {
      x: search.x + coreLocalLeft,
      y: search.y + coreLocalTop,
      width: coreWidth,
      height: coreHeight
    },
    area
  };
}

function bestDenseRun(flags: boolean[], targetStart: number, targetEnd: number): { start: number; end: number } | null {
  const runs: Array<{ start: number; end: number; overlap: number; distance: number }> = [];
  let start = -1;
  for (let index = 0; index <= flags.length; index += 1) {
    const active = index < flags.length && flags[index];
    if (active && start < 0) start = index;
    if ((!active || index === flags.length) && start >= 0) {
      const end = index;
      const overlap = Math.max(0, Math.min(end, targetEnd) - Math.max(start, targetStart));
      const center = (start + end) / 2;
      const targetCenter = (targetStart + targetEnd) / 2;
      runs.push({ start, end, overlap, distance: Math.abs(center - targetCenter) });
      start = -1;
    }
  }
  if (!runs.length) return null;
  runs.sort((a, b) => b.overlap - a.overlap || a.distance - b.distance || (b.end - b.start) - (a.end - a.start));
  const best = runs[0];
  if (best.overlap <= 0) return null;
  return { start: best.start, end: best.end };
}

function filledSurfaceCoverage(
  data: Buffer,
  width: number,
  height: number,
  bbox: BBox,
  fill: { r: number; g: number; b: number },
  threshold: number
): number {
  const box = clampBox(bbox, width, height);
  let total = 0;
  let close = 0;
  for (let y = box.y; y < box.y + box.height; y += 1) {
    const row = y * width;
    for (let x = box.x; x < box.x + box.width; x += 1) {
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      total += 1;
      if (colorDistance({ r: data[offset], g: data[offset + 1], b: data[offset + 2] }, fill) <= threshold) close += 1;
    }
  }
  return total ? close / total : 0;
}

function sampleControlSurfaceFill(
  data: Buffer,
  width: number,
  height: number,
  candidate: BBox,
  textBBox: BBox,
  fallback: { r: number; g: number; b: number }
): { r: number; g: number; b: number } {
  const samples: Array<{ r: number; g: number; b: number }> = [];
  const yPad = Math.max(2, Math.min(10, Math.round(textBBox.height * 0.24)));
  const xPad = Math.max(3, Math.min(16, Math.round(textBBox.height * 0.42)));
  const verticalTop = clamp(Math.floor(textBBox.y - yPad), candidate.y, candidate.y + candidate.height);
  const verticalBottom = clamp(Math.ceil(textBBox.y + textBBox.height + yPad), verticalTop, candidate.y + candidate.height);
  const horizontalLeft = clamp(Math.floor(textBBox.x - xPad), candidate.x, candidate.x + candidate.width);
  const horizontalRight = clamp(Math.ceil(textBBox.x + textBBox.width + xPad), horizontalLeft, candidate.x + candidate.width);
  collectPixels(data, width, height, { x: candidate.x, y: verticalTop, width: Math.max(0, textBBox.x - candidate.x), height: verticalBottom - verticalTop }, samples, textBBox);
  collectPixels(data, width, height, { x: textBBox.x + textBBox.width, y: verticalTop, width: Math.max(0, candidate.x + candidate.width - (textBBox.x + textBBox.width)), height: verticalBottom - verticalTop }, samples, textBBox);
  if (samples.length < 12) {
    collectPixels(data, width, height, { x: horizontalLeft, y: candidate.y, width: horizontalRight - horizontalLeft, height: Math.max(0, textBBox.y - candidate.y) }, samples, textBBox);
    collectPixels(data, width, height, { x: horizontalLeft, y: textBBox.y + textBBox.height, width: horizontalRight - horizontalLeft, height: Math.max(0, candidate.y + candidate.height - (textBBox.y + textBBox.height)) }, samples, textBBox);
  }
  if (samples.length < 12) collectPixels(data, width, height, candidate, samples, textBBox);
  if (!samples.length) return fallback;
  return dominantRgb(samples);
}

function collectPixels(
  data: Buffer,
  width: number,
  height: number,
  bbox: BBox,
  samples: Array<{ r: number; g: number; b: number }>,
  textBBox: BBox
): void {
  const box = clampBox(bbox, width, height);
  for (let y = box.y; y < box.y + box.height; y += 1) {
    const row = y * width;
    for (let x = box.x; x < box.x + box.width; x += 1) {
      if (containsPoint(textBBox, x, y)) continue;
      const offset = (row + x) * 4;
      if (data[offset + 3] < 200) continue;
      samples.push({ r: data[offset], g: data[offset + 1], b: data[offset + 2] });
    }
  }
}

function dominantRgb(samples: Array<{ r: number; g: number; b: number }>): { r: number; g: number; b: number } {
  const buckets = new Map<string, { count: number; samples: Array<{ r: number; g: number; b: number }> }>();
  for (const sample of samples) {
    const key = `${Math.round(sample.r / 20)}:${Math.round(sample.g / 20)}:${Math.round(sample.b / 20)}`;
    const bucket = buckets.get(key) || { count: 0, samples: [] };
    bucket.count += 1;
    bucket.samples.push(sample);
    buckets.set(key, bucket);
  }
  const candidates = [...buckets.values()].sort((a, b) => b.count - a.count);
  return medianRgb(candidates[0]?.samples || samples);
}

function inferControlCornerRadius(
  data: Buffer,
  width: number,
  height: number,
  bbox: BBox,
  fill: { r: number; g: number; b: number }
): number {
  const maxRadius = Math.max(0, Math.min(bbox.width, bbox.height) / 2 - 1);
  if (maxRadius <= 0) return 0;
  const limit = Math.floor(Math.min(maxRadius, bbox.width / 2, bbox.height / 2));
  const runs: number[] = [];
  const corners: Array<[number, number, number, number]> = [
    [bbox.x, bbox.y, 1, 1],
    [bbox.x + bbox.width - 1, bbox.y, -1, 1],
    [bbox.x, bbox.y + bbox.height - 1, 1, -1],
    [bbox.x + bbox.width - 1, bbox.y + bbox.height - 1, -1, -1]
  ];
  for (const [startX, startY, stepX, stepY] of corners) {
    let run = 0;
    for (let offset = 0; offset < limit; offset += 1) {
      const x = Math.round(startX + offset * stepX);
      const y = Math.round(startY + offset * stepY);
      if (x < 0 || y < 0 || x >= width || y >= height) break;
      const pixelOffset = (y * width + x) * 4;
      const distance = colorDistance({ r: data[pixelOffset], g: data[pixelOffset + 1], b: data[pixelOffset + 2] }, fill);
      if (distance <= 64) break;
      run = offset + 1;
    }
    if (run > 0) runs.push(run);
  }
  if (!runs.length) return Math.round(maxRadius);
  return Math.max(0, Math.min(Math.round(medianNumber(runs) * 3.4), Math.round(maxRadius)));
}

function selectedSurfaceComponent(mask: Uint8Array, search: BBox, textBBox: BBox): { bbox: BBox; area: number } | null {
  const visited = new Uint8Array(mask.length);
  const selected: Array<{ bbox: BBox; area: number }> = [];
  const center = { x: textBBox.x + textBBox.width / 2, y: textBBox.y + textBBox.height / 2 };
  for (let localY = 0; localY < search.height; localY += 1) {
    for (let localX = 0; localX < search.width; localX += 1) {
      const start = localY * search.width + localX;
      if (!mask[start] || visited[start]) continue;
      const component = floodMarkedComponent(mask, visited, search, localX, localY);
      if (
        containsPoint(component.bbox, center.x, center.y)
        || horizontallyAnchorsText(component.bbox, textBBox, center.x)
        || intersectionArea(component.bbox, textBBox) > 0
      ) {
        selected.push(component);
      }
    }
  }
  if (!selected.length) return null;
  let left = Math.min(...selected.map((item) => item.bbox.x));
  let top = Math.min(...selected.map((item) => item.bbox.y));
  let right = Math.max(...selected.map((item) => item.bbox.x + item.bbox.width));
  let bottom = Math.max(...selected.map((item) => item.bbox.y + item.bbox.height));
  const area = selected.reduce((sum, item) => sum + item.area, 0);
  return { bbox: { x: left, y: top, width: right - left, height: bottom - top }, area };
}

function horizontallyAnchorsText(componentBBox: BBox, textBBox: BBox, centerXValue: number): boolean {
  if (centerXValue < componentBBox.x || centerXValue >= componentBBox.x + componentBBox.width) return false;
  const componentBottom = componentBBox.y + componentBBox.height;
  const textBottom = textBBox.y + textBBox.height;
  const verticalGap = componentBottom < textBBox.y
    ? textBBox.y - componentBottom
    : textBottom < componentBBox.y
      ? componentBBox.y - textBottom
      : 0;
  return verticalGap <= Math.max(6, textBBox.height * 1.25);
}

function floodMarkedComponent(mask: Uint8Array, visited: Uint8Array, search: BBox, startX: number, startY: number): { bbox: BBox; area: number } {
  const queue: Array<[number, number]> = [[startX, startY]];
  let cursor = 0;
  let left = startX;
  let top = startY;
  let right = startX + 1;
  let bottom = startY + 1;
  let area = 0;
  visited[startY * search.width + startX] = 1;
  while (cursor < queue.length) {
    const [x, y] = queue[cursor++];
    area += 1;
    left = Math.min(left, x);
    top = Math.min(top, y);
    right = Math.max(right, x + 1);
    bottom = Math.max(bottom, y + 1);
    for (let nextY = y - 1; nextY <= y + 1; nextY += 1) {
      for (let nextX = x - 1; nextX <= x + 1; nextX += 1) {
        if (nextX === x && nextY === y) continue;
        if (nextX < 0 || nextY < 0 || nextX >= search.width || nextY >= search.height) continue;
        const index = nextY * search.width + nextX;
        if (!mask[index] || visited[index]) continue;
        visited[index] = 1;
        queue.push([nextX, nextY]);
      }
    }
  }
  return {
    bbox: {
      x: search.x + left,
      y: search.y + top,
      width: right - left,
      height: bottom - top
    },
    area
  };
}

function containsPoint(bbox: BBox, x: number, y: number): boolean {
  return x >= bbox.x && x < bbox.x + bbox.width && y >= bbox.y && y < bbox.y + bbox.height;
}

function looksLikeShortControlText(text: string): boolean {
  const compact = text.replace(/\s+/g, "");
  if (!compact) return false;
  if (compact.length > 10) return false;
  if (/^[0-9:：.\-+¥￥$%\s]+$/u.test(compact)) return false;
  return true;
}

function finiteControlSurfaceGeometry(candidate: BBox, textBBox: BBox, pageWidth: number, pageHeight: number): boolean {
  if (candidate.width < 24 || candidate.height < 16) return false;
  if (candidate.height > 86) return false;
  if (candidate.width > Math.min(860, pageWidth * 0.94)) return false;
  if (candidate.width * candidate.height > Math.max(12000, pageWidth * pageHeight * 0.08)) return false;
  const aspect = candidate.width / Math.max(1, candidate.height);
  if (aspect < 0.75 || aspect > 9.5) return false;
  if (candidate.width < textBBox.width * 0.62 || candidate.height < textBBox.height * 0.62) return false;
  return true;
}

function sampleSearchEdgeColor(data: Buffer, width: number, height: number, bbox: BBox): { r: number; g: number; b: number } {
  const samples: Array<{ r: number; g: number; b: number }> = [];
  const left = clamp(Math.floor(bbox.x), 0, width);
  const top = clamp(Math.floor(bbox.y), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height), top, height);
  for (let y = top; y < bottom; y += 1) {
    for (let x = left; x < right; x += 1) {
      const onEdge = y < top + 2 || y >= bottom - 2 || x < left + 2 || x >= right - 2;
      if (!onEdge) continue;
      const offset = (y * width + x) * 4;
      if (data[offset + 3] < 200) continue;
      samples.push({ r: data[offset], g: data[offset + 1], b: data[offset + 2] });
    }
  }
  return samples.length ? medianRgb(samples) : { r: 255, g: 255, b: 255 };
}

function markedEdgeCoverage(data: Buffer, width: number, height: number, bbox: BBox, background: { r: number; g: number; b: number }, threshold: number): number {
  let edge = 0;
  let marked = 0;
  const left = clamp(Math.floor(bbox.x), 0, width);
  const top = clamp(Math.floor(bbox.y), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height), top, height);
  for (let y = top; y < bottom; y += 1) {
    for (let x = left; x < right; x += 1) {
      const onEdge = y < top + 2 || y >= bottom - 2 || x < left + 2 || x >= right - 2;
      if (!onEdge) continue;
      edge += 1;
      const offset = (y * width + x) * 4;
      if (data[offset + 3] < 200) continue;
      const distance = colorDistance({ r: data[offset], g: data[offset + 1], b: data[offset + 2] }, background);
      if (distance >= threshold) marked += 1;
    }
  }
  return edge ? marked / edge : 0;
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

function sampleDominantInteriorColor(data: Buffer, width: number, height: number, bbox: BBox): { r: number; g: number; b: number } | null {
  const left = clamp(Math.floor(bbox.x), 0, width);
  const top = clamp(Math.floor(bbox.y), 0, height);
  const right = clamp(Math.ceil(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.ceil(bbox.y + bbox.height), top, height);
  const buckets = new Map<string, { count: number; samples: Array<{ r: number; g: number; b: number }> }>();
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
  return medianRgb(candidates[0].samples);
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

function centerY(bbox: BBox): number {
  return bbox.y + bbox.height / 2;
}

function medianNumber(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[middle];
  return (sorted[middle - 1] + sorted[middle]) / 2;
}

function colorFamily(value: string): string {
  const rgb = rgbFromHex(value);
  if (!rgb) return "unknown";
  const channels = [rgb.r, rgb.g, rgb.b];
  if (Math.max(...channels) - Math.min(...channels) < 28) return "neutral";
  if (rgb.b >= rgb.r + 28 && rgb.b >= rgb.g + 16) return "blue";
  if (rgb.g >= rgb.r + 18 && rgb.g >= rgb.b + 18) return "green";
  if (rgb.r >= rgb.g + 18 && rgb.r >= rgb.b + 18) return "red_or_orange";
  return "chromatic";
}

function rgbFromHex(value: string): { r: number; g: number; b: number } | null {
  if (!value.startsWith("#")) return null;
  const hexValue = value.slice(1);
  if (!/^[0-9a-f]{6}$/iu.test(hexValue)) return null;
  return {
    r: Number.parseInt(hexValue.slice(0, 2), 16),
    g: Number.parseInt(hexValue.slice(2, 4), 16),
    b: Number.parseInt(hexValue.slice(4, 6), 16)
  };
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

function intersectionBox(a: BBox, b: BBox): BBox | null {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  if (right <= left || bottom <= top) return null;
  return { x: left, y: top, width: right - left, height: bottom - top };
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
