export type DSLVersion = "0.1";

export interface DesignDSL {
  version: DSLVersion;
  taskId: string;
  page: DSLPage;
  assets: DSLAsset[];
  root: DSLElement;
  meta?: DSLMeta;
}

export interface DSLPage {
  name?: string;
  width: number;
  height: number;
  originalWidth?: number;
  originalHeight?: number;
  scaleFactor?: number;
  viewportHeight?: number;
  isScrollable?: boolean;
  background?: PageBackground;
  safeArea?: SafeArea;
}

export interface SafeArea {
  top?: number;
  bottom?: number;
}

export type PageBackground =
  | {
      type: "color";
      value: string;
    }
  | {
      type: "gradient";
      gradient: DSLGradientFill;
    }
  | {
      type: "image";
      assetId: string;
    };

export interface DSLAsset {
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

export type DSLElementType =
  | "frame"
  | "group"
  | "text"
  | "shape"
  | "image"
  | "icon"
  | "line";

export interface DSLElement {
  id: string;
  type: DSLElementType;
  role?: string;
  name?: string;
  layout: DSLLayout;
  rawLayout?: DSLLayout;
  style?: DSLStyle;
  content?: DSLContent;
  source?: DSLSource;
  imageFill?: DSLImageFill;
  children?: DSLElement[];
  meta?: DSLElementMeta;
}

export interface DSLLayout {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DSLStyle {
  fill?: string | DSLGradientFill;
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

export interface DSLRadius {
  topLeft?: number;
  topRight?: number;
  bottomRight?: number;
  bottomLeft?: number;
}

export interface DSLStroke {
  color: string;
  width: number;
}

export interface DSLShadow {
  type: "drop_shadow";
  x: number;
  y: number;
  blur: number;
  spread?: number;
  color: string;
}

export interface DSLGradientFill {
  type: "linear_gradient";
  angle: number;
  stops: DSLGradientStop[];
}

export interface DSLGradientStop {
  color: string;
  position: number;
}

export interface DSLContent {
  text?: string;
}

export type DSLSource =
  | {
      assetId: string;
      url?: string;
    }
  | {
      kind: "builtin_svg";
      iconName: string;
    };

export interface DSLImageFill {
  mode: "fill" | "fit";
}

export interface DSLMeta {
  createdAt?: string;
  source?: "png";
  platformHint?: "mobile" | "desktop_web" | "admin_dashboard" | "unknown";
  qualityFlags?: string[];
  fallbackCount?: number;
  elementCount?: number;
  promptVersion?: string;
  model?: string;
  notes?: string;
}

export interface DSLElementMeta {
  confidence?: number;
  ocrConfidence?: number;
  semanticType?: string;
  correctionPolicy?: "safe" | "no_free_rewrite";
  fallback?: boolean;
  reason?: string;
  sourceBBox?: [number, number, number, number];
  qualityFlags?: string[];
  componentSpec?: {
    kind: string;
    variant?: string;
    confidence?: number;
  };
  [key: string]: unknown;
}

export interface DSLValidationResult {
  valid: boolean;
  errors: DSLValidationError[];
  warnings: DSLValidationWarning[];
}

export interface DSLValidationError {
  code: string;
  message: string;
  path?: string;
  elementId?: string;
}

export interface DSLValidationWarning {
  code: string;
  message: string;
  path?: string;
  elementId?: string;
}

export interface DSLRepairResult {
  dsl: DesignDSL;
  repairs: DSLRepairRecord[];
  validation: DSLValidationResult;
}

export interface DSLRepairRecord {
  code: string;
  message: string;
  path?: string;
  elementId?: string;
}
