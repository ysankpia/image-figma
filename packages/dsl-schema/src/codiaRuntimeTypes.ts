import type {
  DSLGradientFill,
  DSLRadius,
  DSLShadow,
  DSLStroke,
  DSLValidationError,
  DSLValidationWarning
} from "./types";

export type CodiaRuntimeDSLVersion = "0.2";

export interface CodiaRuntimeDSL {
  version: CodiaRuntimeDSLVersion;
  kind: "codia_runtime";
  taskId: string;
  page: CodiaRuntimePage;
  assets: CodiaRuntimeAsset[];
  root: CodiaRuntimeNode;
  meta?: Record<string, unknown>;
}

export interface CodiaRuntimePage {
  name?: string;
  width: number;
  height: number;
  background?: {
    type: "color";
    value: string;
  };
}

export interface CodiaRuntimeAsset {
  assetId: string;
  type: "image";
  role?: string;
  url: string;
  format: "png" | "jpeg" | "jpg" | "webp";
  width?: number;
  height?: number;
  storage?: "local" | "oss";
  objectKey?: string;
  expiresAt?: string;
  meta?: Record<string, unknown>;
}

export type CodiaRuntimeRole =
  | "Root"
  | "Groups"
  | "Button"
  | "Text"
  | "Image"
  | "Background"
  | "ViewGroup"
  | "ListView"
  | "BottomNavigation"
  | "ActionBar"
  | "StatusBar"
  | "ImageView"
  | "TextView"
  | "EditText"
  | "bg_Button"
  | "bg_EditText";

export type CodiaRuntimeNodeType = "frame" | "group" | "text" | "shape" | "image";

export interface CodiaRuntimeNode {
  id: string;
  schemaId?: string;
  role: CodiaRuntimeRole;
  type: CodiaRuntimeNodeType;
  name?: string;
  bbox: CodiaRuntimeBBox;
  style?: CodiaRuntimeStyle;
  text?: CodiaRuntimeText;
  image?: CodiaRuntimeImage;
  children?: CodiaRuntimeNode[];
  meta?: Record<string, unknown>;
}

export interface CodiaRuntimeBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CodiaRuntimeStyle {
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
}

export interface CodiaRuntimeText {
  characters: string;
}

export interface CodiaRuntimeImage {
  assetId?: string;
  url?: string;
  mode?: "fill" | "fit";
}

export interface CodiaRuntimeValidationResult {
  valid: boolean;
  errors: DSLValidationError[];
  warnings: DSLValidationWarning[];
}
