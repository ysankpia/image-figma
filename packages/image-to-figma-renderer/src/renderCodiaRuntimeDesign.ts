import {
  validateCodiaRuntimeDSL,
  type CodiaRuntimeAsset,
  type CodiaRuntimeDSL,
  type CodiaRuntimeNode,
  type CodiaRuntimeStyle
} from "@image-figma/dsl-schema";
import { applyLayout } from "./applyLayout";
import { applyBaseStyle, solidPaint } from "./applyStyle";
import type {
  FigmaAdapter,
  FigmaNode,
  FigmaPaint,
  RenderError,
  RenderOptions,
  RenderResult,
  RenderWarning,
  ResolvedImageSource
} from "./types";

interface CodiaRuntimeRenderContext {
  dsl: CodiaRuntimeDSL;
  figma: FigmaAdapter;
  options: Required<Pick<RenderOptions, "validate">> & {
    assetBaseUrl?: string | undefined;
  };
  assetMap: Map<string, CodiaRuntimeAsset>;
  warnings: RenderWarning[];
  errors: RenderError[];
  renderedElementCount: number;
}

export async function renderCodiaRuntimeDesign(
  dsl: CodiaRuntimeDSL,
  options: RenderOptions
): Promise<RenderResult> {
  const shouldValidate = options.validate ?? true;
  if (shouldValidate) {
    const validation = validateCodiaRuntimeDSL(dsl);
    if (!validation.valid) {
      return {
        success: false,
        renderedElementCount: 0,
        warnings: validation.warnings.map(cleanRenderMessage),
        errors: validation.errors.map(cleanRenderMessage)
      };
    }
  }

  const context: CodiaRuntimeRenderContext = {
    dsl,
    figma: options.figma,
    options: {
      validate: shouldValidate,
      assetBaseUrl: options.assetBaseUrl
    },
    assetMap: buildCodiaAssetMap(dsl.assets),
    warnings: [],
    errors: [],
    renderedElementCount: 0
  };

  try {
    const root = await renderCodiaNode(context, dsl.root, "$.root");
    context.figma.appendToCurrentPage?.(root);
    return {
      success: context.errors.length === 0,
      rootNodeId: context.figma.getNodeId(root),
      renderedElementCount: context.renderedElementCount,
      warnings: context.warnings,
      errors: context.errors
    };
  } catch (error) {
    addCodiaError(context, {
      code: "CODIA_RUNTIME_ROOT_RENDER_FAILED",
      message: error instanceof Error ? error.message : "Codia Runtime root render failed.",
      elementId: dsl.root.id,
      path: "$.root"
    });
    return {
      success: false,
      renderedElementCount: context.renderedElementCount,
      warnings: context.warnings,
      errors: context.errors
    };
  }
}

async function renderCodiaNode(
  context: CodiaRuntimeRenderContext,
  node: CodiaRuntimeNode,
  path: string
): Promise<FigmaNode> {
  let figmaNode: FigmaNode;
  try {
    switch (node.type) {
      case "frame":
      case "group":
        figmaNode = context.figma.createFrame();
        applyCommonNode(context, figmaNode, node);
        context.renderedElementCount += 1;
        await renderCodiaChildren(context, figmaNode, node, path);
        return figmaNode;
      case "text":
        figmaNode = await renderCodiaText(context, node);
        return figmaNode;
      case "shape":
        figmaNode = context.figma.createRectangle();
        applyCommonNode(context, figmaNode, node);
        context.renderedElementCount += 1;
        return figmaNode;
      case "image":
        figmaNode = await renderCodiaImage(context, node);
        return figmaNode;
      default:
        throw new Error(`Unsupported Codia Runtime node type: ${String(node.type)}.`);
    }
  } catch (error) {
    addCodiaWarning(context, {
      code: "CODIA_RUNTIME_ELEMENT_RENDER_FAILED",
      message: error instanceof Error ? error.message : "Codia Runtime node render failed.",
      elementId: node.id,
      path
    });
    return renderFallbackPlaceholder(context, node);
  }
}

async function renderCodiaChildren(
  context: CodiaRuntimeRenderContext,
  parent: FigmaNode,
  node: CodiaRuntimeNode,
  path: string
): Promise<void> {
  if (!node.children) {
    return;
  }
  const children = node.children
    .map((child, index) => ({ child, index }))
    .sort((left, right) => {
      const bucketDelta = paintOrderBucket(left.child) - paintOrderBucket(right.child);
      if (bucketDelta !== 0) {
        return bucketDelta;
      }
      return left.index - right.index;
    });
  for (const { child, index } of children) {
    const childNode = await renderCodiaNode(context, child, `${path}.children[${index}]`);
    context.figma.appendChild(parent, childNode);
  }
}

function paintOrderBucket(node: CodiaRuntimeNode): number {
  switch (node.type) {
    case "shape":
      return node.role.startsWith("bg_") || node.role === "Background" ? 0 : 2;
    case "image":
      return 1;
    case "frame":
    case "group":
      return 2;
    case "text":
      return 3;
    default:
      return 2;
  }
}

async function renderCodiaText(context: CodiaRuntimeRenderContext, node: CodiaRuntimeNode): Promise<FigmaNode> {
  const figmaNode = context.figma.createText();
  applyCommonNode(context, figmaNode, node);

  try {
    await context.figma.loadFont(node.style ?? {});
  } catch (error) {
    addCodiaWarning(context, {
      code: "FONT_LOAD_FAILED",
      message: error instanceof Error ? error.message : "Font loading failed.",
      elementId: node.id
    });
  }

  context.figma.setTextStyle(figmaNode, node.style ?? {});
  const text = node.text?.characters ?? "";
  const fontSize = node.style?.fontSize ?? 14;
  const isSingleLine = !text.includes("\n") && node.bbox.height < 2.0 * fontSize;
  context.figma.setTextAutoResize(figmaNode, isSingleLine ? "WIDTH_AND_HEIGHT" : "HEIGHT");
  context.figma.setText(figmaNode, text);
  if (node.style?.color) {
    context.figma.setFills(figmaNode, [solidPaint(node.style.color)]);
  }
  context.renderedElementCount += 1;
  return figmaNode;
}

async function renderCodiaImage(context: CodiaRuntimeRenderContext, node: CodiaRuntimeNode): Promise<FigmaNode> {
  const figmaNode = context.figma.createRectangle();
  applyCommonNode(context, figmaNode, node);

  const paint = await loadCodiaImagePaint(context, node);
  if (paint) {
    context.figma.setFills(figmaNode, [paint]);
  } else if (node.style?.fill === undefined) {
    context.figma.setFills(figmaNode, [solidPaint("#E5E7EB")]);
  }

  context.renderedElementCount += 1;
  return figmaNode;
}

function renderFallbackPlaceholder(context: CodiaRuntimeRenderContext, node: CodiaRuntimeNode): FigmaNode {
  const fallback = context.figma.createRectangle();
  context.figma.setName(fallback, node.name ?? `${node.role} / ${node.id}`);
  applyLayout(context.figma, fallback, node.bbox);
  context.figma.setFills(fallback, [solidPaint("#F3F4F6")]);
  context.renderedElementCount += 1;
  return fallback;
}

function applyCommonNode(context: CodiaRuntimeRenderContext, figmaNode: FigmaNode, node: CodiaRuntimeNode): void {
  context.figma.setName(figmaNode, node.name ?? `${node.role} / ${node.id}`);
  applyLayout(context.figma, figmaNode, node.bbox);
  applyBaseStyle(context.figma, figmaNode, node.style);
}

async function loadCodiaImagePaint(
  context: CodiaRuntimeRenderContext,
  node: CodiaRuntimeNode
): Promise<FigmaPaint | undefined> {
  const source = resolveCodiaImageSource(node, context.assetMap, context.options.assetBaseUrl);
  if (!source) {
    addCodiaWarning(context, {
      code: "CODIA_RUNTIME_IMAGE_SOURCE_NOT_FOUND",
      message: "Codia Runtime image source could not be resolved; rendering placeholder fill.",
      elementId: node.id
    });
    return undefined;
  }

  try {
    return await context.figma.createImagePaint(source, node.image?.mode ?? "fill");
  } catch (error) {
    addCodiaWarning(context, {
      code: "IMAGE_LOAD_FAILED",
      message: error instanceof Error ? error.message : "Image loading failed.",
      elementId: node.id
    });
    return undefined;
  }
}

function resolveCodiaImageSource(
  node: CodiaRuntimeNode,
  assetMap: Map<string, CodiaRuntimeAsset>,
  assetBaseUrl?: string
): ResolvedImageSource | undefined {
  const image = node.image;
  if (!image) {
    return undefined;
  }
  if (image.assetId) {
    const asset = assetMap.get(image.assetId);
    if (!asset) {
      return undefined;
    }
    return {
      assetId: asset.assetId,
      url: resolveUrl(image.url ?? asset.url, assetBaseUrl)
    };
  }
  if (image.url) {
    return {
      url: resolveUrl(image.url, assetBaseUrl)
    };
  }
  return undefined;
}

function buildCodiaAssetMap(assets: CodiaRuntimeAsset[]): Map<string, CodiaRuntimeAsset> {
  return new Map(assets.map((asset) => [asset.assetId, asset]));
}

function resolveUrl(url: string, assetBaseUrl?: string): string {
  if (!assetBaseUrl || /^https?:\/\//.test(url)) {
    return url;
  }
  return `${assetBaseUrl.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}

function addCodiaWarning(context: CodiaRuntimeRenderContext, warning: RenderWarning): void {
  context.warnings.push(cleanRenderMessage(warning) as RenderWarning);
}

function addCodiaError(context: CodiaRuntimeRenderContext, error: RenderError): void {
  context.errors.push(cleanRenderMessage(error) as RenderError);
}

function cleanRenderMessage(message: RenderWarning | RenderError): RenderWarning | RenderError {
  const next: RenderWarning | RenderError = {
    code: message.code,
    message: message.message
  };
  if (message.elementId !== undefined) {
    next.elementId = message.elementId;
  }
  if (message.path !== undefined) {
    next.path = message.path;
  }
  return next;
}
