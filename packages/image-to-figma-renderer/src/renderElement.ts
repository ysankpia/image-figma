import type { DSLElement } from "@image-figma/dsl-schema";
import { addWarning } from "./errors";
import { renderFrame } from "./renderFrame";
import { renderGroup } from "./renderGroup";
import { renderImage } from "./renderImage";
import { renderLine } from "./renderLine";
import { renderShape } from "./renderShape";
import { renderText } from "./renderText";
import type { FigmaNode, RenderContext } from "./types";

export async function renderElement(
  context: RenderContext,
  element: DSLElement,
  path: string,
  parent?: FigmaNode
): Promise<FigmaNode | undefined> {
  try {
    switch (element.type) {
      case "frame":
        return await renderFrame(context, element, path);
      case "group":
        return await renderGroup(context, element, path);
      case "text":
        return await renderText(context, element);
      case "shape":
        return renderShape(context, element);
      case "image":
        return await renderImage(context, element, parent);
      case "line":
        return renderLine(context, element);
      case "icon":
        addWarning(context, {
          code: "UNSUPPORTED_ELEMENT_TYPE",
          message: "icon rendering is not implemented in M2.",
          elementId: element.id,
          path
        });
        return undefined;
      default:
        addWarning(context, {
          code: "UNSUPPORTED_ELEMENT_TYPE",
          message: `Unsupported element type: ${String(element.type)}.`,
          elementId: element.id,
          path
        });
        return undefined;
    }
  } catch (error) {
    addWarning(context, {
      code: "ELEMENT_RENDER_FAILED",
      message: error instanceof Error ? error.message : "Element render failed.",
      elementId: element.id,
      path
    });
    return undefined;
  }
}
