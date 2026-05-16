import type { DSLElement } from "@image-figma/dsl-schema";
import { applyLayout } from "./applyLayout";
import { applyBaseStyle } from "./applyStyle";
import { loadImagePaint } from "./imageLoader";
import type { FigmaNode, RenderContext } from "./types";

export async function renderImage(context: RenderContext, element: DSLElement): Promise<FigmaNode> {
  const node = context.figma.createRectangle();
  context.figma.setName(node, element.name ?? `Image / ${element.id}`);
  applyLayout(context.figma, node, element.layout);
  applyBaseStyle(context.figma, node, forceOriginalReferenceVisibility(element));

  const paint = await loadImagePaint(context, element);
  if (paint) {
    context.figma.setFills(node, [paint]);
  }

  context.renderedElementCount += 1;
  return node;
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
