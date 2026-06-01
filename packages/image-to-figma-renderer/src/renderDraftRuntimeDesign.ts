import {
  validateDraftRuntimeDSL,
  type DraftRuntimeAsset,
  type DraftRuntimeDSL,
  type DraftRuntimeNode,
  type DraftRuntimeStyle,
  type DSLStyle
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

interface DraftRuntimeRenderContext {
  dsl: DraftRuntimeDSL;
  figma: FigmaAdapter;
  options: Required<Pick<RenderOptions, "validate">> & {
    assetBaseUrl?: string | undefined;
  };
  assetMap: Map<string, DraftRuntimeAsset>;
  warnings: RenderWarning[];
  errors: RenderError[];
  renderedElementCount: number;
}

export async function renderDraftRuntimeDesign(
  dsl: DraftRuntimeDSL,
  options: RenderOptions
): Promise<RenderResult> {
  const shouldValidate = options.validate ?? true;
  if (shouldValidate) {
    const validation = validateDraftRuntimeDSL(dsl);
    if (!validation.valid) {
      return {
        success: false,
        renderedElementCount: 0,
        warnings: validation.warnings.map(cleanRenderMessage),
        errors: validation.errors.map(cleanRenderMessage)
      };
    }
  }

  const context: DraftRuntimeRenderContext = {
    dsl,
    figma: options.figma,
    options: {
      validate: shouldValidate,
      assetBaseUrl: options.assetBaseUrl
    },
    assetMap: new Map((dsl.assets ?? []).map((asset) => [asset.assetId, asset])),
    warnings: [],
    errors: [],
    renderedElementCount: 0
  };

  try {
    const root = await renderDraftNode(context, dsl.root, "$.root");
    if (dsl.page.background) {
      context.figma.setFills(root, [solidPaint(dsl.page.background)]);
    }
    context.figma.appendToCurrentPage?.(root);
    return {
      success: context.errors.length === 0,
      rootNodeId: context.figma.getNodeId(root),
      renderedElementCount: context.renderedElementCount,
      warnings: context.warnings,
      errors: context.errors
    };
  } catch (error) {
    addWarning(context, {
      code: "DRAFT_RUNTIME_ROOT_RENDER_FAILED",
      message: error instanceof Error ? error.message : "Draft Runtime root render failed.",
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

async function renderDraftNode(
  context: DraftRuntimeRenderContext,
  node: DraftRuntimeNode,
  path: string
): Promise<FigmaNode> {
  try {
    switch (node.type) {
      case "frame":
      case "group": {
        const figmaNode = context.figma.createFrame();
        applyCommonNode(context, figmaNode, node);
        context.renderedElementCount += 1;
        await renderChildren(context, figmaNode, node, path);
        return figmaNode;
      }
      case "text":
        return await renderText(context, node);
      case "shape": {
        const figmaNode = context.figma.createRectangle();
        applyCommonNode(context, figmaNode, node);
        context.renderedElementCount += 1;
        return figmaNode;
      }
      case "image":
        return await renderImage(context, node);
      default:
        throw new Error(`Unsupported Draft Runtime node type: ${String(node.type)}.`);
    }
  } catch (error) {
    addWarning(context, {
      code: "DRAFT_RUNTIME_ELEMENT_RENDER_FAILED",
      message: error instanceof Error ? error.message : "Draft Runtime node render failed.",
      elementId: node.id,
      path
    });
    return renderFallbackPlaceholder(context, node);
  }
}

async function renderChildren(
  context: DraftRuntimeRenderContext,
  parent: FigmaNode,
  node: DraftRuntimeNode,
  path: string
): Promise<void> {
  const children = (node.children ?? [])
    .map((child, index) => ({ child, index }))
    .sort((left, right) => {
      const zDelta = (left.child.z ?? 0) - (right.child.z ?? 0);
      if (zDelta !== 0) {
        return zDelta;
      }
      return left.index - right.index;
    });
  for (const { child, index } of children) {
    const childNode = await renderDraftNode(context, child, `${path}.children[${index}]`);
    context.figma.appendChild(parent, childNode);
  }
}

async function renderText(context: DraftRuntimeRenderContext, node: DraftRuntimeNode): Promise<FigmaNode> {
  const figmaNode = context.figma.createText();
  applyCommonNode(context, figmaNode, node);
  const style = toDSLStyle(node.style);
  try {
    await context.figma.loadFont(style ?? {});
  } catch (error) {
    addWarning(context, {
      code: "FONT_LOAD_FAILED",
      message: error instanceof Error ? error.message : "Font loading failed.",
      elementId: node.id
    });
  }
  context.figma.setTextStyle(figmaNode, style ?? {});
  context.figma.setTextAutoResize(figmaNode, "NONE");
  context.figma.setText(figmaNode, node.text?.characters ?? "");
  applyLayout(context.figma, figmaNode, node.bbox);
  if (node.style?.color) {
    context.figma.setFills(figmaNode, [solidPaint(node.style.color)]);
  }
  context.renderedElementCount += 1;
  return figmaNode;
}

async function renderImage(context: DraftRuntimeRenderContext, node: DraftRuntimeNode): Promise<FigmaNode> {
  const figmaNode = context.figma.createRectangle();
  applyCommonNode(context, figmaNode, node);
  const paint = await loadImagePaint(context, node);
  if (paint) {
    context.figma.setFills(figmaNode, [paint]);
  } else if (node.style?.fill === undefined) {
    context.figma.setFills(figmaNode, [solidPaint("#E5E7EB")]);
  }
  context.renderedElementCount += 1;
  return figmaNode;
}

function renderFallbackPlaceholder(context: DraftRuntimeRenderContext, node: DraftRuntimeNode): FigmaNode {
  const fallback = context.figma.createRectangle();
  context.figma.setName(fallback, node.name ?? node.id);
  applyLayout(context.figma, fallback, node.bbox);
  context.figma.setFills(fallback, [solidPaint("#F3F4F6")]);
  context.renderedElementCount += 1;
  return fallback;
}

function applyCommonNode(context: DraftRuntimeRenderContext, figmaNode: FigmaNode, node: DraftRuntimeNode): void {
  context.figma.setName(figmaNode, node.name ?? node.id);
  applyLayout(context.figma, figmaNode, node.bbox);
  applyBaseStyle(context.figma, figmaNode, toDSLStyle(node.style));
}

function toDSLStyle(style: DraftRuntimeStyle | undefined): DSLStyle | undefined {
  if (!style) {
    return undefined;
  }
  const next: DSLStyle = { ...style };
  if (next.radius === undefined && style.cornerRadius !== undefined) {
    next.radius = style.cornerRadius;
  }
  return next;
}

async function loadImagePaint(
  context: DraftRuntimeRenderContext,
  node: DraftRuntimeNode
): Promise<FigmaPaint | undefined> {
  const source = resolveImageSource(node, context.assetMap, context.options.assetBaseUrl);
  if (!source) {
    addWarning(context, {
      code: "DRAFT_RUNTIME_IMAGE_SOURCE_NOT_FOUND",
      message: "Draft Runtime image source could not be resolved; rendering placeholder fill.",
      elementId: node.id
    });
    return undefined;
  }
  try {
    return await context.figma.createImagePaint(source, node.image?.mode ?? "fill");
  } catch (error) {
    addWarning(context, {
      code: "IMAGE_LOAD_FAILED",
      message: error instanceof Error ? error.message : "Image loading failed.",
      elementId: node.id
    });
    return undefined;
  }
}

function resolveImageSource(
  node: DraftRuntimeNode,
  assetMap: Map<string, DraftRuntimeAsset>,
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
    return { url: resolveUrl(image.url, assetBaseUrl) };
  }
  return undefined;
}

function resolveUrl(url: string, assetBaseUrl?: string): string {
  if (!assetBaseUrl || /^https?:\/\//.test(url)) {
    return url;
  }
  return `${assetBaseUrl.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}

function addWarning(context: DraftRuntimeRenderContext, warning: RenderWarning): void {
  context.warnings.push(cleanRenderMessage(warning) as RenderWarning);
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
