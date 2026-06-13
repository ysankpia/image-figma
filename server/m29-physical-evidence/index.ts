import { backgroundColorHex, estimateBackground } from "./background";
import { connectedComponents } from "./connected-components";
import { decodeRgba, sha256Hex } from "./image";
import { createForegroundMask, fillBBox, newMask } from "./mask";
import { buildPrimitives } from "./primitives";
import { buildRelations } from "./relations";
import { maskCount, type M29PhysicalEvidenceDocument, type M29PhysicalEvidenceInput } from "./types";

export async function extractPhysicalEvidence(input: M29PhysicalEvidenceInput): Promise<M29PhysicalEvidenceDocument> {
  const image = await decodeRgba(input.imageBuffer);
  if (image.width <= 0 || image.height <= 0) throw new Error("invalid image size");

  const background = estimateBackground(image);
  const textMask = newMask(image.width, image.height);
  const ocrBlocks = normalizedOcrBlocks(input.ocrBlocks || [], image.width, image.height);
  for (const block of ocrBlocks) fillBBox(textMask, block.bbox, 2);
  const foreground = createForegroundMask(image, background);
  const components = connectedComponents(foreground, minComponentArea(image.width, image.height), 0.80);
  const primitives = buildPrimitives({
    image,
    background: background.color,
    components,
    ocrBlocks
  });
  const relations = buildRelations(primitives);

  return {
    schemaName: "M29PhysicalEvidence",
    version: "1.0",
    generator: { name: "ts-m29", mode: "sharp" },
    image: {
      width: image.width,
      height: image.height,
      sourcePath: input.sourcePath || "",
      sha256: sha256Hex(input.imageBuffer)
    },
    ocr: {
      provided: ocrBlocks.length > 0,
      blockCount: ocrBlocks.length
    },
    primitives,
    physicalRelations: relations,
    assets: [],
    diagnostics: {
      backgroundColor: backgroundColorHex(background),
      foregroundThreshold: background.threshold,
      foregroundPixelCount: foreground.foregroundPixelCount,
      componentCount: components.length,
      primitiveCount: primitives.length,
      textMaskPixelCount: maskCount(textMask)
    }
  };
}

export function minComponentArea(width: number, height: number): number {
  const minArea = Math.trunc((width * height) / 90000);
  if (minArea < 8) return 8;
  return minArea;
}

function normalizedOcrBlocks(blocks: NonNullable<M29PhysicalEvidenceInput["ocrBlocks"]>, width: number, height: number): NonNullable<M29PhysicalEvidenceInput["ocrBlocks"]> {
  const normalized: NonNullable<M29PhysicalEvidenceInput["ocrBlocks"]> = [];
  for (const [index, block] of blocks.entries()) {
    const text = block.text.trim();
    const bbox = clampBox(block.bbox, width, height);
    if (!text || bbox.width <= 0 || bbox.height <= 0) continue;
    normalized.push({
      id: block.id || `ocr_${String(index + 1).padStart(4, "0")}`,
      text,
      bbox,
      confidence: block.confidence
    });
  }
  return normalized;
}

function clampBox(bbox: { x: number; y: number; width: number; height: number }, width: number, height: number): { x: number; y: number; width: number; height: number } {
  const left = clamp(Math.round(bbox.x), 0, width);
  const top = clamp(Math.round(bbox.y), 0, height);
  const right = clamp(Math.round(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.round(bbox.y + bbox.height), top, height);
  return { x: left, y: top, width: right - left, height: bottom - top };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export type {
  BackgroundEstimate,
  DecodedRgbaImage,
  ForegroundMask,
  M29CompileHints,
  M29Measurements,
  M29OcrBlock,
  M29PhysicalEvidenceDocument,
  M29PhysicalEvidenceInput,
  M29PhysicalRelation,
  M29Primitive,
  Mask,
  PixelComponent,
  Rgb
} from "./types";
