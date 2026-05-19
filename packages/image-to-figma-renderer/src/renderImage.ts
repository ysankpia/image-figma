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
  const maskBBoxes = (element.meta as any)?.maskBBoxes;
  const hasSubtractions = parent && Array.isArray(maskBBoxes) && maskBBoxes.length > 0;

  figma.setName(baseNode, hasSubtractions ? `Image / ${element.id}` : (element.name ?? `Image / ${element.id}`));
  applyLayout(figma, baseNode, element.layout);
  applyBaseStyle(figma, baseNode, forceOriginalReferenceVisibility(element));

  const paint = await loadImagePaint(context, element);
  if (paint) {
    figma.setFills(baseNode, [paint]);
  }

  if (hasSubtractions) {
    figma.appendChild(parent!, baseNode);

    const maskNodes: FigmaNode[] = [];
    for (let i = 0; i < maskBBoxes.length; i++) {
      const bbox = maskBBoxes[i];
      if (Array.isArray(bbox) && bbox.length === 4) {
        const maskNode = figma.createRectangle();
        figma.setName(maskNode, `Mask Rectangle / ${i}`);
        figma.setLayout(maskNode, {
          x: bbox[0],
          y: bbox[1],
          width: bbox[2],
          height: bbox[3]
        });
        figma.appendChild(parent, maskNode);
        maskNodes.push(maskNode);
      }
    }

    if (maskNodes.length > 0) {
      const subtractNode = figma.createBooleanSubtract([baseNode, ...maskNodes], parent);
      figma.setName(subtractNode, element.name ?? `Fallback Region / ${element.id}`);

      // Apply image fills and style directly to the boolean subtract node itself.
      // Figma renders boolean operation groups using the group node's own fills/styles.
      if (paint) {
        figma.setFills(subtractNode, [paint]);
      }
      applyBaseStyle(figma, subtractNode, forceOriginalReferenceVisibility(element));

      context.renderedElementCount += 1;
      return subtractNode;
    }
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
