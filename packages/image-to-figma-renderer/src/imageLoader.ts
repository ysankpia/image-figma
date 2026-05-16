import type { DSLElement } from "@image-figma/dsl-schema";
import { resolveImageSource } from "./assetResolver";
import { addWarning } from "./errors";
import type { FigmaPaint, RenderContext } from "./types";

export async function loadImagePaint(context: RenderContext, element: DSLElement): Promise<FigmaPaint | undefined> {
  const source = resolveImageSource(element, context.assetMap, context.options.assetBaseUrl);
  if (!source) {
    addWarning(context, {
      code: "IMAGE_SOURCE_NOT_FOUND",
      message: "Image source could not be resolved.",
      elementId: element.id
    });
    return undefined;
  }

  try {
    return await context.figma.createImagePaint(source, element.imageFill?.mode ?? "fill");
  } catch (error) {
    addWarning(context, {
      code: "IMAGE_LOAD_FAILED",
      message: error instanceof Error ? error.message : "Image loading failed.",
      elementId: element.id
    });
    return undefined;
  }
}
