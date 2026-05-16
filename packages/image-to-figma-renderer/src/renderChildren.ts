import type { DSLElement } from "@image-figma/dsl-schema";
import { renderElement } from "./renderElement";
import type { FigmaNode, RenderContext } from "./types";

export async function renderChildren(
  context: RenderContext,
  parent: FigmaNode,
  children: DSLElement[] | undefined,
  path: string
): Promise<void> {
  if (!children) {
    return;
  }

  for (const [index, child] of children.entries()) {
    const node = await renderElement(context, child, `${path}.children[${index}]`);
    if (node) {
      context.figma.appendChild(parent, node);
    }
  }
}
