import type { BBox } from "../../shared/types";

export type Rgb = {
  r: number;
  g: number;
  b: number;
};

export type DecodedRgbaImage = {
  data: Buffer;
  width: number;
  height: number;
};

export type M29PhysicalEvidenceInput = {
  imageBuffer: Buffer;
  sourcePath?: string;
};

export type M29PhysicalEvidenceDocument = {
  schemaName: "M29PhysicalEvidence";
  version: "1.0";
  generator: {
    name: "ts-m29";
    mode: "sharp";
  };
  image: {
    width: number;
    height: number;
    sourcePath: string;
    sha256: string;
  };
  ocr: {
    provided: false;
    blockCount: 0;
  };
  primitives: M29Primitive[];
  physicalRelations: M29PhysicalRelation[];
  assets: [];
  diagnostics: {
    backgroundColor: string;
    foregroundThreshold: number;
    foregroundPixelCount: number;
    componentCount: number;
    primitiveCount: number;
    textMaskPixelCount: 0;
  };
};

export type M29Primitive = {
  id: string;
  primitiveType:
    | "text_region"
    | "surface_region"
    | "image_region"
    | "symbol_region"
    | "rect"
    | "line"
    | "unknown_region";
  bbox: BBox;
  maskRef?: string;
  cropRef?: string;
  source: {
    kind: "pixel" | "ocr";
    ocrBlockId?: string;
    text?: string;
  };
  measurements: M29Measurements;
  compileHints: M29CompileHints;
};

export type M29Measurements = {
  area: number;
  fillRatio: number;
  meanColor: string;
  colorCount: number;
  edgeDensity: number;
  textureScore: number;
  localContrast: number;
  cornerRadiusEstimate: number;
  textMaskArea?: number;
};

export type M29CompileHints = {
  canBeLayerBackground: boolean;
  canContainForeground: boolean;
  canBeImage: boolean;
  canBeIcon: boolean;
  hasStableRectGeometry: boolean;
  confidence: number;
  reasons: string[];
};

export type M29PhysicalRelation = {
  id: string;
  kind: "contains_bbox" | "near_text";
  fromId: string;
  toId: string;
  distance?: number;
  ratio?: number;
};

export type PixelComponent = {
  id: number;
  bbox: BBox;
  area: number;
  pixels: number[];
};

export type Mask = {
  width: number;
  height: number;
  data: Uint8Array;
};

export type ForegroundMask = Mask & {
  foregroundPixelCount: number;
};

export type BackgroundEstimate = {
  color: Rgb;
  threshold: number;
};

export type PrimitiveClassification = {
  primitiveType: M29Primitive["primitiveType"];
  compileHints: M29CompileHints;
};

export function emptyCompileHints(): M29CompileHints {
  return {
    canBeLayerBackground: false,
    canContainForeground: false,
    canBeImage: false,
    canBeIcon: false,
    hasStableRectGeometry: false,
    confidence: 0,
    reasons: []
  };
}

export function maskCount(mask: Mask): number {
  let total = 0;
  for (const value of mask.data) {
    if (value) total += 1;
  }
  return total;
}
