import type { DSLElement } from "@image-figma/dsl-schema";
import { applyLayout } from "./applyLayout";
import { applyBaseStyle, solidPaint } from "./applyStyle";
import { addWarning } from "./errors";
import type { FigmaNode, RenderContext } from "./types";

export async function renderText(context: RenderContext, element: DSLElement): Promise<FigmaNode> {
  const node = context.figma.createText();
  context.figma.setName(node, element.name ?? `Text / ${element.id}`);
  applyLayout(context.figma, node, element.layout);
  applyBaseStyle(context.figma, node, element.style);

  try {
    await context.figma.loadFont(element.style ?? {});
  } catch (error) {
    addWarning(context, {
      code: "FONT_LOAD_FAILED",
      message: error instanceof Error ? error.message : "Font loading failed.",
      elementId: element.id
    });
  }

  context.figma.setTextStyle(node, element.style ?? {});

  const fontSize = element.style?.fontSize ?? 14;
  const isSingleLine = !element.content?.text?.includes("\n") && element.layout.height < 2.0 * fontSize;
  const autoResize = isSingleLine ? "WIDTH_AND_HEIGHT" : "HEIGHT";
  context.figma.setTextAutoResize(node, autoResize);

  context.figma.setText(node, element.content?.text ?? "");
  if (element.style?.color) {
    context.figma.setFills(node, [solidPaint(element.style.color)]);
  }
  context.renderedElementCount += 1;
  return node;
}
