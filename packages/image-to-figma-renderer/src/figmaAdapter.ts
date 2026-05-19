import type { DSLStyle } from "@image-figma/dsl-schema";
import type {
  FigmaAdapter,
  FigmaFontName,
  FigmaLayout,
  FigmaNode,
  FigmaPaint,
  ResolvedImageSource
} from "./types";

export interface FigmaPluginApiLike {
  createFrame(): FigmaNodeLike;
  createRectangle(): FigmaNodeLike;
  createText(): FigmaTextNodeLike;
  loadFontAsync(fontName: FigmaFontName): Promise<void>;
  createImage(data: Uint8Array): { hash: string };
  currentPage: {
    appendChild(child: FigmaNodeLike): void;
  };
  subtract(nodes: readonly FigmaNodeLike[], parent: FigmaNodeLike): FigmaNodeLike;
}

export interface FigmaNodeLike {
  id: string;
  type: string;
  name: string;
  x: number;
  y: number;
  visible: boolean;
  opacity: number;
  fills?: FigmaPaintLike[];
  strokes?: FigmaPaintLike[];
  strokeWeight?: number;
  cornerRadius?: number;
  resize(width: number, height: number): void;
  appendChild?(child: FigmaNodeLike): void;
}

export interface FigmaTextNodeLike extends FigmaNodeLike {
  characters: string;
  fontName: FigmaFontName | typeof figmaMixed;
  fontSize: number | typeof figmaMixed;
  fontWeight?: number;
  lineHeight: FigmaLineHeight | typeof figmaMixed;
  textAlignHorizontal: "LEFT" | "CENTER" | "RIGHT" | "JUSTIFIED";
  textAutoResize?: "NONE" | "WIDTH_AND_HEIGHT" | "HEIGHT" | "TRUNCATE";
}

export interface FigmaPaintLike {
  type: "SOLID" | "IMAGE";
  color?: { r: number; g: number; b: number } | undefined;
  opacity?: number | undefined;
  imageHash?: string | undefined;
  scaleMode?: "FILL" | "FIT" | undefined;
}

export interface FigmaLineHeight {
  unit: "PIXELS";
  value: number;
}

const figmaMixed = Symbol("figma.mixed");

export function createFigmaAdapter(figmaApi: FigmaPluginApiLike): FigmaAdapter {
  return {
    createFrame: () => figmaApi.createFrame(),
    createRectangle: () => figmaApi.createRectangle(),
    createText: () => figmaApi.createText(),
    appendChild(parent, child) {
      toFigmaNode(parent).appendChild?.(toFigmaNode(child));
    },
    appendToCurrentPage(node) {
      figmaApi.currentPage.appendChild(toFigmaNode(node));
    },
    setName(node, name) {
      toFigmaNode(node).name = name;
    },
    setLayout(node, layout) {
      const figmaNode = toFigmaNode(node);
      figmaNode.x = layout.x;
      figmaNode.y = layout.y;
      figmaNode.resize(layout.width, layout.height);
    },
    setVisible(node, visible) {
      toFigmaNode(node).visible = visible;
    },
    setOpacity(node, opacity) {
      toFigmaNode(node).opacity = opacity;
    },
    setFills(node, fills) {
      toFigmaNode(node).fills = fills.map(toFigmaPaint);
    },
    setStrokes(node, strokes, strokeWeight) {
      const figmaNode = toFigmaNode(node);
      figmaNode.strokes = strokes.map(toFigmaPaint);
      if (strokeWeight !== undefined) {
        figmaNode.strokeWeight = strokeWeight;
      }
    },
    setCornerRadius(node, radius) {
      toFigmaNode(node).cornerRadius = radius;
    },
    setText(node, text) {
      toTextNode(node).characters = text;
    },
    setTextStyle(node, style) {
      const textNode = toTextNode(node);
      textNode.fontName = toFontName(style);
      textNode.fontSize = style.fontSize ?? 14;
      textNode.textAlignHorizontal = toTextAlign(style.textAlign);
      if (style.lineHeight !== undefined) {
        textNode.lineHeight = { unit: "PIXELS", value: style.lineHeight };
      }
    },
    setTextAutoResize(node, autoResize) {
      toTextNode(node).textAutoResize = autoResize;
    },
    async loadFont(style) {
      const fontName = toFontName(style);
      await figmaApi.loadFontAsync(fontName);
      return fontName;
    },
    async createImagePaint(source, mode) {
      const bytes = await fetchBytes(source);
      const image = figmaApi.createImage(bytes);
      return {
        type: "IMAGE",
        imageHash: image.hash,
        scaleMode: mode === "fit" ? "FIT" : "FILL"
      };
    },
    getNodeId(node) {
      return node.id;
    },
    createBooleanSubtract(nodes, parent) {
      return figmaApi.subtract(nodes.map(toFigmaNode), toFigmaNode(parent)) as FigmaNode;
    }
  };
}

export function toFontName(style: DSLStyle): FigmaFontName {
  return {
    family: style.fontFamily ?? "Inter",
    style: fontStyleFromWeight(style.fontWeight)
  };
}

function fontStyleFromWeight(weight: number | undefined): string {
  if (weight !== undefined && weight >= 600) {
    return "Bold";
  }
  return "Regular";
}

function toTextAlign(value: DSLStyle["textAlign"]): FigmaTextNodeLike["textAlignHorizontal"] {
  if (value === "center") {
    return "CENTER";
  }
  if (value === "right") {
    return "RIGHT";
  }
  return "LEFT";
}

function toFigmaPaint(paint: FigmaPaint): FigmaPaintLike {
  if (paint.type === "IMAGE") {
    return {
      type: "IMAGE",
      imageHash: paint.imageHash,
      scaleMode: paint.scaleMode
    };
  }
  return {
    type: "SOLID",
    color: paint.color,
    opacity: paint.opacity
  };
}

function toFigmaNode(node: FigmaNode): FigmaNodeLike {
  return node as FigmaNodeLike;
}

function toTextNode(node: FigmaNode): FigmaTextNodeLike {
  return node as FigmaTextNodeLike;
}

async function fetchBytes(source: ResolvedImageSource): Promise<Uint8Array> {
  const response = await fetch(source.url);
  if (!response.ok) {
    throw new Error(`Failed to load image: ${response.status} ${response.statusText}`);
  }
  return new Uint8Array(await response.arrayBuffer());
}
