import { backgroundColorHex, estimateBackground } from "./background";
import { connectedComponents } from "./connected-components";
import { decodeRgba, sha256Hex } from "./image";
import { createForegroundMask, newMask } from "./mask";
import { buildPrimitives } from "./primitives";
import { buildRelations } from "./relations";
import type { M29PhysicalEvidenceDocument, M29PhysicalEvidenceInput } from "./types";

export async function extractPhysicalEvidence(input: M29PhysicalEvidenceInput): Promise<M29PhysicalEvidenceDocument> {
  const image = await decodeRgba(input.imageBuffer);
  if (image.width <= 0 || image.height <= 0) throw new Error("invalid image size");

  const background = estimateBackground(image);
  const textMask = newMask(image.width, image.height);
  const foreground = createForegroundMask(image, background, textMask);
  const components = connectedComponents(foreground, minComponentArea(image.width, image.height), 0.80);
  const primitives = buildPrimitives({
    image,
    background: background.color,
    components
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
      provided: false,
      blockCount: 0
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
      textMaskPixelCount: 0
    }
  };
}

export function minComponentArea(width: number, height: number): number {
  const minArea = Math.trunc((width * height) / 90000);
  if (minArea < 8) return 8;
  return minArea;
}

export type {
  BackgroundEstimate,
  DecodedRgbaImage,
  ForegroundMask,
  M29CompileHints,
  M29Measurements,
  M29PhysicalEvidenceDocument,
  M29PhysicalEvidenceInput,
  M29PhysicalRelation,
  M29Primitive,
  Mask,
  PixelComponent,
  Rgb
} from "./types";
