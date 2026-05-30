import type { DesignDSL, DSLAsset, DSLElement, DSLStyle } from "@image-figma/dsl-schema";

export interface RenderOptions {
  figma: FigmaAdapter;
  validate?: boolean;
  createOriginalReference?: boolean;
  assetBaseUrl?: string;
}

export interface RenderResult {
  success: boolean;
  rootNodeId?: string;
  renderedElementCount: number;
  warnings: RenderWarning[];
  errors: RenderError[];
}

export interface RenderWarning {
  code: string;
  message: string;
  elementId?: string;
  path?: string;
}

export interface RenderError {
  code: string;
  message: string;
  elementId?: string;
  path?: string;
}

export interface RenderContext {
  dsl: DesignDSL;
  figma: FigmaAdapter;
  options: Required<Pick<RenderOptions, "validate" | "createOriginalReference">> & {
    assetBaseUrl?: string | undefined;
  };
  assetMap: Map<string, DSLAsset>;
  warnings: RenderWarning[];
  errors: RenderError[];
  renderedElementCount: number;
}

export interface FigmaAdapter {
  createFrame(): FigmaNode;
  createRectangle(): FigmaNode;
  createText(): FigmaNode;
  appendChild(parent: FigmaNode, child: FigmaNode): void;
  appendToCurrentPage?(node: FigmaNode): void;
  setName(node: FigmaNode, name: string): void;
  setLayout(node: FigmaNode, layout: FigmaLayout): void;
  setVisible(node: FigmaNode, visible: boolean): void;
  setOpacity(node: FigmaNode, opacity: number): void;
  setClipsContent?(node: FigmaNode, clipsContent: boolean): void;
  setFills(node: FigmaNode, fills: FigmaPaint[]): void;
  setStrokes(node: FigmaNode, strokes: FigmaPaint[], strokeWeight?: number): void;
  setCornerRadius(node: FigmaNode, radius: number): void;
  setText(node: FigmaNode, text: string): void;
  setTextStyle(node: FigmaNode, style: DSLStyle): void;
  setTextAutoResize(node: FigmaNode, autoResize: "NONE" | "WIDTH_AND_HEIGHT" | "HEIGHT"): void;
  loadFont(style: DSLStyle): Promise<FigmaFontName>;
  createImagePaint(source: ResolvedImageSource, mode: "fill" | "fit"): Promise<FigmaPaint>;
  getNodeId(node: FigmaNode): string;
}

export interface FigmaNode {
  id: string;
  type: string;
}

export interface FigmaLayout {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface FigmaPaint {
  type: "SOLID" | "IMAGE";
  color?: RGBColor | undefined;
  opacity?: number | undefined;
  imageHash?: string | undefined;
  scaleMode?: "FILL" | "FIT" | undefined;
}

export interface FigmaFontName {
  family: string;
  style: string;
}

export interface RGBColor {
  r: number;
  g: number;
  b: number;
}

export interface ResolvedImageSource {
  url: string;
  assetId?: string;
}

export interface RenderedElement {
  node: FigmaNode;
  element: DSLElement;
}
