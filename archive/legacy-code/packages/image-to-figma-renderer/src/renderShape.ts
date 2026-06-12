import type { DSLElement } from "@image-figma/dsl-schema";
import { applyLayout } from "./applyLayout";
import { applyBaseStyle } from "./applyStyle";
import type { FigmaNode, RenderContext } from "./types";

export function renderShape(context: RenderContext, element: DSLElement): FigmaNode {
  const node = context.figma.createRectangle();
  context.figma.setName(node, element.name ?? `Shape / ${element.id}`);
  applyLayout(context.figma, node, element.layout);
  applyBaseStyle(context.figma, node, element.style);
  context.renderedElementCount += 1;
  return node;
}
