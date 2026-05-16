import type { DSLElement } from "@image-figma/dsl-schema";
import { applyLayout } from "./applyLayout";
import { applyBaseStyle } from "./applyStyle";
import { renderChildren } from "./renderChildren";
import type { FigmaNode, RenderContext } from "./types";

export async function renderFrame(context: RenderContext, element: DSLElement, path: string): Promise<FigmaNode> {
  const node = context.figma.createFrame();
  context.figma.setName(node, element.name ?? `Frame / ${element.id}`);
  applyLayout(context.figma, node, element.layout);
  applyBaseStyle(context.figma, node, element.style);
  context.renderedElementCount += 1;
  await renderChildren(context, node, element.children, path);
  return node;
}
