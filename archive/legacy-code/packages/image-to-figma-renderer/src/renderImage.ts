import type { DSLElement } from "@image-figma/dsl-schema";
import { applyLayout } from "./applyLayout";
import { applyBaseStyle } from "./applyStyle";
import { loadImagePaint } from "./imageLoader";
import type { FigmaNode, RenderContext } from "./types";

export async function renderImage(
  context: RenderContext,
  element: DSLElement,
  parent?: FigmaNode
): Promise<FigmaNode> {
  const figma = context.figma;
  const baseNode = figma.createRectangle();

  figma.setName(baseNode, element.name ?? `Image / ${element.id}`);
  applyLayout(figma, baseNode, element.layout);
  applyBaseStyle(figma, baseNode, forceOriginalReferenceVisibility(element));

  const paint = await loadImagePaint(context, element);
  if (paint) {
    figma.setFills(baseNode, [paint]);
  }

  context.renderedElementCount += 1;
  return baseNode;
}

function forceOriginalReferenceVisibility(element: DSLElement) {
  if (element.role !== "original_reference") {
    return element.style;
  }
  return {
    ...(element.style ?? {}),
    visible: false
  };
}
