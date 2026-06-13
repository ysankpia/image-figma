import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { m29extractPath, physicalEvidenceProvider, textBBoxSource } from "./config";
import { extractPhysicalEvidence } from "./m29-physical-evidence";
import type { OcrLine, OcrResult } from "./text-ocr";
import type { BBox } from "../shared/types";

export type TextBBoxSource = "m29_foreground" | "local_foreground" | "ocr";

export type LocatedTextLine = {
  line: OcrLine;
  bbox: BBox;
  bboxSource: TextBBoxSource;
  physicalBBox?: BBox;
  bboxMatchScore?: number;
  m29PrimitiveId?: string;
  bboxFallbackReason?: string;
};

export type TextLocationResult = {
  status: "ok" | "skipped" | "failed";
  source: "m29_ocr_hybrid" | "ocr";
  reason?: string;
  lines: LocatedTextLine[];
};

type M29Primitive = {
  id: string;
  primitiveType: string;
  bbox: BBox;
  source?: {
    kind?: string;
    ocrBlockId?: string;
    text?: string;
  };
};

type M29Document = {
  schemaName?: string;
  primitives?: M29Primitive[];
};

type Match = {
  primitive: M29Primitive;
  score: number;
};

const minMatchScore = 0.42;

export async function locateTextLinesWithM29(input: {
  imageBuffer: Buffer;
  width: number;
  height: number;
  ocr: OcrResult;
}): Promise<TextLocationResult> {
  if (input.ocr.status !== "ok" || input.ocr.lines.length === 0) return fallbackToOcr(input.ocr.lines, "ocr_not_ok_or_empty");
  if (textBBoxSource !== "m29_ocr_hybrid") return fallbackToOcr(input.ocr.lines, "text_bbox_source_ocr");
  if (physicalEvidenceProvider === "ocr") return fallbackToOcr(input.ocr.lines, "physical_evidence_provider_ocr");
  if (physicalEvidenceProvider === "ts_m29_physical_evidence") return locateWithTsPhysicalEvidence(input);
  return locateWithGoM29Extract(input);
}

async function locateWithTsPhysicalEvidence(input: {
  imageBuffer: Buffer;
  width: number;
  height: number;
  ocr: OcrResult;
}): Promise<TextLocationResult> {
  try {
    const doc = await extractPhysicalEvidence({
      imageBuffer: input.imageBuffer,
      ocrBlocks: input.ocr.lines.map((line, index) => ({
        id: ocrBlockId(index),
        text: line.text,
        bbox: line.bbox,
        confidence: line.confidence / 100
      }))
    });
    return locateTextLinesFromM29(input.ocr.lines, doc);
  } catch (error) {
    return fallbackToOcr(input.ocr.lines, `ts_m29_physical_evidence_failed:${normalizeReason(error instanceof Error ? error.message : String(error))}`);
  }
}

function locateWithGoM29Extract(input: {
  imageBuffer: Buffer;
  width: number;
  height: number;
  ocr: OcrResult;
}): TextLocationResult {
  if (!fs.existsSync(m29extractPath)) return fallbackToOcr(input.ocr.lines, "m29extract_not_found");

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slice-studio-m29-text-"));
  const imagePath = path.join(tmpDir, "input.png");
  const outDir = path.join(tmpDir, "m29");
  try {
    fs.writeFileSync(imagePath, input.imageBuffer);
    const result = spawnSync(m29extractPath, ["--input", imagePath, "--out", outDir, "--ocr-provider", "none"], {
      encoding: "utf8",
      maxBuffer: 20 * 1024 * 1024
    });
    if (result.error) return fallbackToOcr(input.ocr.lines, result.error.message);
    if (result.status !== 0) {
      return fallbackToOcr(input.ocr.lines, normalizeReason(result.stderr) || `m29extract_exit_${result.status ?? "unknown"}`);
    }
    const evidencePath = path.join(outDir, "m29_physical_evidence.v1.json");
    const doc = JSON.parse(fs.readFileSync(evidencePath, "utf8")) as M29Document;
    return locateTextLinesFromM29(input.ocr.lines, doc);
  } catch (error) {
    return fallbackToOcr(input.ocr.lines, error instanceof Error ? error.message : String(error));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

export function locateTextLinesFromM29(lines: OcrLine[], doc: M29Document): TextLocationResult {
  if (doc.schemaName !== "M29PhysicalEvidence" || !Array.isArray(doc.primitives)) {
    return fallbackToOcr(lines, "invalid_m29_evidence");
  }
  const primitives = doc.primitives.filter((primitive) => primitive.bbox.width > 0 && primitive.bbox.height > 0);
  const located = lines.map((line, index) => {
    const blockId = ocrBlockId(index);
    const direct = primitives.find((primitive) => primitive.primitiveType === "text_region" && primitive.source?.ocrBlockId === blockId);
    const directPhysical = direct?.source?.kind === "ocr" ? undefined : direct;
    const match = directPhysical
      ? { primitive: directPhysical, score: 1 }
      : bestPhysicalMatch(line, primitives);
    if (match && match.score >= minMatchScore) {
      if (physicalTextBoxIsTooBroad(line.bbox, match.primitive.bbox)) {
        return fallbackLine(line, "m29_bbox_too_broad_for_ocr_line");
      }
      return {
        line,
        bbox: { ...match.primitive.bbox },
        bboxSource: "m29_foreground" as const,
        physicalBBox: { ...match.primitive.bbox },
        bboxMatchScore: Math.round(match.score * 1000) / 1000,
        m29PrimitiveId: match.primitive.id
      };
    }
    return direct?.source?.kind === "ocr"
      ? { ...fallbackLine(line, "m29_text_region_ocr_mask_only"), m29PrimitiveId: direct.id }
      : { ...fallbackLine(line, "no_matching_m29_text_bbox") };
  });
  return {
    status: "ok",
    source: "m29_ocr_hybrid",
    lines: demoteSharedPhysicalMatches(located)
  };
}

function bestPhysicalMatch(line: OcrLine, primitives: M29Primitive[]): Match | null {
  const candidates = primitives
    .filter((primitive) => isTextLikePrimitive(primitive))
    .filter((primitive) => fragmentCanBelongToLine(line.bbox, primitive.bbox));
  const clustered = unionCandidates(line.bbox, candidates);
  let best: Match | null = clustered ? { primitive: clustered, score: matchScore(line.bbox, clustered.bbox) } : null;
  for (const primitive of candidates) {
    const score = matchScore(line.bbox, primitive.bbox) * 0.82;
    if (!best || score > best.score) best = { primitive, score };
  }
  return best;
}

function isTextLikePrimitive(primitive: M29Primitive): boolean {
  if (primitive.primitiveType === "text_region" && primitive.source?.kind === "ocr") return false;
  if (primitive.primitiveType === "surface_region" || primitive.primitiveType === "image_region") return false;
  if (primitive.bbox.width > 260 || primitive.bbox.height > 96) return false;
  return true;
}

function fragmentCanBelongToLine(lineBBox: BBox, fragmentBBox: BBox): boolean {
  const search = expandBBox(lineBBox, Math.max(8, Math.round(lineBBox.height * 0.8)), Math.max(6, Math.round(lineBBox.height * 0.45)));
  if (intersectionArea(search, fragmentBBox) <= 0) return false;
  const lineCenterY = centerY(lineBBox);
  const fragmentCenterY = centerY(fragmentBBox);
  if (Math.abs(fragmentCenterY - lineCenterY) > Math.max(lineBBox.height, fragmentBBox.height) * 0.95) return false;
  if (fragmentBBox.height > lineBBox.height * 2.6 && fragmentBBox.width > lineBBox.width * 0.35) return false;
  return true;
}

function unionCandidates(lineBBox: BBox, candidates: M29Primitive[]): M29Primitive | null {
  const included = candidates.filter((candidate) => {
    const overlap = intersectionArea(expandBBox(lineBBox, 2, 3), candidate.bbox);
    if (overlap <= 0) return false;
    const fragmentInsideRatio = overlap / Math.max(1, area(candidate.bbox));
    return fragmentInsideRatio >= 0.18;
  });
  if (!included.length) return null;
  const left = Math.min(...included.map((item) => item.bbox.x));
  const top = Math.min(...included.map((item) => item.bbox.y));
  const right = Math.max(...included.map((item) => item.bbox.x + item.bbox.width));
  const bottom = Math.max(...included.map((item) => item.bbox.y + item.bbox.height));
  return {
    id: included.length === 1 ? included[0].id : included.map((item) => item.id).join("+"),
    primitiveType: "text_foreground_cluster",
    bbox: { x: left, y: top, width: right - left, height: bottom - top }
  };
}

function matchScore(ocrBBox: BBox, physicalBBox: BBox): number {
  const overlap = intersectionArea(ocrBBox, physicalBBox);
  const union = area(ocrBBox) + area(physicalBBox) - overlap;
  const iou = union <= 0 ? 0 : overlap / union;
  const yOverlap = overlap / Math.max(1, Math.min(ocrBBox.height, physicalBBox.height) * Math.min(ocrBBox.width, physicalBBox.width));
  const centerDistance = Math.hypot(centerX(ocrBBox) - centerX(physicalBBox), centerY(ocrBBox) - centerY(physicalBBox));
  const distanceScore = Math.max(0, 1 - centerDistance / Math.max(1, Math.max(ocrBBox.width, physicalBBox.width)));
  const heightRatio = Math.min(ocrBBox.height, physicalBBox.height) / Math.max(ocrBBox.height, physicalBBox.height, 1);
  return iou * 0.52 + yOverlap * 0.18 + distanceScore * 0.2 + heightRatio * 0.1;
}

function fallbackToOcr(lines: OcrLine[], reason: string): TextLocationResult {
  return {
    status: reason === "text_bbox_source_ocr" || reason === "ocr_not_ok_or_empty" || reason === "physical_evidence_provider_ocr" ? "skipped" : "failed",
    source: "ocr",
    reason,
    lines: lines.map((line) => fallbackLine(line, reason))
  };
}

function fallbackLine(line: OcrLine, reason: string): LocatedTextLine {
  return {
    line,
    bbox: { ...line.bbox },
    bboxSource: "ocr",
    bboxFallbackReason: reason
  };
}

function demoteSharedPhysicalMatches(lines: LocatedTextLine[]): LocatedTextLine[] {
  const counts = new Map<string, number>();
  for (const line of lines) {
    if (line.bboxSource !== "m29_foreground" || !line.m29PrimitiveId) continue;
    counts.set(line.m29PrimitiveId, (counts.get(line.m29PrimitiveId) || 0) + 1);
  }
  return lines.map((line) => {
    if (line.bboxSource !== "m29_foreground" || !line.m29PrimitiveId) return line;
    if ((counts.get(line.m29PrimitiveId) || 0) <= 1) return line;
    return fallbackLine(line.line, "shared_m29_bbox_for_multiple_ocr_lines");
  });
}

function physicalTextBoxIsTooBroad(ocrBBox: BBox, physicalBBox: BBox): boolean {
  const ocrArea = area(ocrBBox);
  const physicalArea = area(physicalBBox);
  if (ocrArea <= 0 || physicalArea <= 0) return true;

  const widthRatio = physicalBBox.width / Math.max(1, ocrBBox.width);
  const heightRatio = physicalBBox.height / Math.max(1, ocrBBox.height);
  const areaRatio = physicalArea / ocrArea;

  if (heightRatio >= 1.32 && areaRatio >= 1.85) return true;
  if (widthRatio >= 1.85 && heightRatio >= 1.12) return true;
  if (widthRatio >= 2.4) return true;
  return false;
}

function expandBBox(bbox: BBox, padX: number, padY: number): BBox {
  return {
    x: bbox.x - padX,
    y: bbox.y - padY,
    width: bbox.width + padX * 2,
    height: bbox.height + padY * 2
  };
}

function intersectionArea(a: BBox, b: BBox): number {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  return Math.max(0, right - left) * Math.max(0, bottom - top);
}

function area(bbox: BBox): number {
  return Math.max(0, bbox.width) * Math.max(0, bbox.height);
}

function centerX(bbox: BBox): number {
  return bbox.x + bbox.width / 2;
}

function centerY(bbox: BBox): number {
  return bbox.y + bbox.height / 2;
}

function ocrBlockId(index: number): string {
  return `ocr_${String(index + 1).padStart(4, "0")}`;
}

function normalizeReason(value: string): string {
  return value.trim().replace(/\s+/g, " ").slice(0, 240);
}
