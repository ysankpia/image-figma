import type {
  DSLGradientFill,
  DSLRadius,
  DSLShadow,
  DSLStroke,
  DSLValidationError,
  DSLValidationWarning
} from "./types";

export type DraftRuntimeDSLVersion = "1.0";

export interface DraftRuntimeDSL {
  version: DraftRuntimeDSLVersion;
  kind: "draft_runtime";
  taskId: string;
  page: DraftRuntimePage;
  assets: DraftRuntimeAsset[];
  root: DraftRuntimeNode;
  meta?: Record<string, unknown>;
}

export interface DraftRuntimePage {
  name?: string;
  width: number;
  height: number;
  background?: string;
}

export interface DraftRuntimeAsset {
  assetId: string;
  type: "image";
  url: string;
  path?: string;
  format: "png" | "jpeg" | "jpg" | "webp";
  width?: number;
  height?: number;
  meta?: Record<string, unknown>;
}

export type DraftRuntimeNodeType = "frame" | "group" | "text" | "shape" | "image";

export interface DraftRuntimeNode {
  id: string;
  type: DraftRuntimeNodeType;
  name?: string;
  bbox: DraftRuntimeBBox;
  z?: number;
  visible?: boolean;
  style?: DraftRuntimeStyle;
  text?: DraftRuntimeText;
  image?: DraftRuntimeImage;
  children?: DraftRuntimeNode[];
  meta?: Record<string, unknown>;
}

export interface DraftRuntimeBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DraftRuntimeStyle {
  fill?: string | DSLGradientFill | null;
  color?: string;
  opacity?: number;
  visible?: boolean;
  radius?: number | DSLRadius;
  stroke?: DSLStroke;
  shadow?: DSLShadow[];
  clipContent?: boolean;
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: number;
  lineHeight?: number;
  textAlign?: "left" | "center" | "right";
  cornerRadius?: number;
}

export interface DraftRuntimeText {
  characters: string;
}

export interface DraftRuntimeImage {
  assetId?: string;
  url?: string;
  mode?: "fill" | "fit";
}

export interface DraftRuntimeValidationResult {
  valid: boolean;
  errors: DSLValidationError[];
  warnings: DSLValidationWarning[];
}
