import type {
  FigmaAdapter,
  FigmaFontName,
  FigmaLayout,
  FigmaNode,
  FigmaPaint,
  ResolvedImageSource
} from "../src";
import type { DSLStyle } from "@image-figma/dsl-schema";

export interface FakeNode extends FigmaNode {
  name: string;
  layout?: FigmaLayout;
  visible?: boolean;
  opacity?: number;
  fills?: FigmaPaint[];
  strokes?: FigmaPaint[];
  strokeWeight?: number;
  cornerRadius?: number;
  characters?: string;
  textStyle?: DSLStyle;
  fontName?: FigmaFontName;
  textAutoResize?: "NONE" | "WIDTH_AND_HEIGHT" | "HEIGHT";
  children: FakeNode[];
}

export interface FakeAdapterOptions {
  failImageUrls?: Set<string>;
  failFontLoad?: boolean;
  failElementIds?: Set<string>;
}

export class FakeFigmaAdapter implements FigmaAdapter {
  readonly nodes: FakeNode[] = [];
  readonly currentPage: FakeNode[] = [];
  readonly imageSources: ResolvedImageSource[] = [];
  private nextId = 1;

  constructor(private readonly options: FakeAdapterOptions = {}) {}

  createFrame(): FigmaNode {
    return this.createNode("FRAME");
  }

  createRectangle(): FigmaNode {
    return this.createNode("RECTANGLE");
  }

  createText(): FigmaNode {
    return this.createNode("TEXT");
  }

  appendChild(parent: FigmaNode, child: FigmaNode): void {
    this.asFakeNode(parent).children.push(this.asFakeNode(child));
  }

  appendToCurrentPage(node: FigmaNode): void {
    this.currentPage.push(this.asFakeNode(node));
  }

  setName(node: FigmaNode, name: string): void {
    this.asFakeNode(node).name = name;
    if (this.options.failElementIds?.has(name)) {
      throw new Error(`Forced failure for ${name}`);
    }
  }

  setLayout(node: FigmaNode, layout: FigmaLayout): void {
    this.asFakeNode(node).layout = layout;
  }

  setVisible(node: FigmaNode, visible: boolean): void {
    this.asFakeNode(node).visible = visible;
  }

  setOpacity(node: FigmaNode, opacity: number): void {
    this.asFakeNode(node).opacity = opacity;
  }

  setFills(node: FigmaNode, fills: FigmaPaint[]): void {
    this.asFakeNode(node).fills = fills;
  }

  setStrokes(node: FigmaNode, strokes: FigmaPaint[], strokeWeight?: number): void {
    const fake = this.asFakeNode(node);
    fake.strokes = strokes;
    if (strokeWeight !== undefined) {
      fake.strokeWeight = strokeWeight;
    }
  }

  setCornerRadius(node: FigmaNode, radius: number): void {
    this.asFakeNode(node).cornerRadius = radius;
  }

  setText(node: FigmaNode, text: string): void {
    this.asFakeNode(node).characters = text;
  }

  setTextStyle(node: FigmaNode, style: DSLStyle): void {
    const fake = this.asFakeNode(node);
    fake.textStyle = style;
    fake.fontName = toFakeFontName(style);
  }

  setTextAutoResize(node: FigmaNode, autoResize: "NONE" | "WIDTH_AND_HEIGHT" | "HEIGHT"): void {
    this.asFakeNode(node).textAutoResize = autoResize;
  }

  async loadFont(style: DSLStyle = {}): Promise<FigmaFontName> {
    if (this.options.failFontLoad) {
      throw new Error("forced font failure");
    }
    return toFakeFontName(style);
  }

  async createImagePaint(source: ResolvedImageSource, mode: "fill" | "fit"): Promise<FigmaPaint> {
    this.imageSources.push(source);
    if (this.options.failImageUrls?.has(source.url)) {
      throw new Error(`forced image failure: ${source.url}`);
    }
    return {
      type: "IMAGE",
      imageHash: `hash:${source.url}`,
      scaleMode: mode === "fit" ? "FIT" : "FILL"
    };
  }

  getNodeId(node: FigmaNode): string {
    return node.id;
  }


  findNodeByName(name: string): FakeNode | undefined {
    return this.nodes.find((node) => node.name === name);
  }

  private createNode(type: string): FakeNode {
    const node: FakeNode = {
      id: `fake_${this.nextId++}`,
      type,
      name: "",
      children: []
    };
    this.nodes.push(node);
    return node;
  }

  private asFakeNode(node: FigmaNode): FakeNode {
    return node as FakeNode;
  }
}

function toFakeFontName(style: DSLStyle): FigmaFontName {
  return {
    family: style.fontFamily ?? "Inter",
    style: style.fontWeight !== undefined && style.fontWeight >= 600 ? "Bold" : "Regular"
  };
}
