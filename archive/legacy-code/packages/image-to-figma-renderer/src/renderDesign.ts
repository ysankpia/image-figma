import { normalizeDSL, validateDSL, type DesignDSL } from "@image-figma/dsl-schema";
import { buildAssetMap } from "./assetResolver";
import { addError } from "./errors";
import { renderFrame } from "./renderFrame";
import type { RenderContext, RenderError, RenderOptions, RenderResult, RenderWarning } from "./types";

export async function renderDesign(dsl: DesignDSL, options: RenderOptions): Promise<RenderResult> {
  const shouldValidate = options.validate ?? true;
  if (shouldValidate) {
    const validation = validateDSL(dsl);
    if (!validation.valid) {
      return {
        success: false,
        renderedElementCount: 0,
        warnings: validation.warnings.map((warning) => cleanRenderMessage(warning)),
        errors: validation.errors.map((error) => cleanRenderMessage(error))
      };
    }
  }

  const normalized = normalizeDSL(dsl);
  const renderOptions: RenderContext["options"] = {
    validate: shouldValidate,
    createOriginalReference: options.createOriginalReference ?? true,
    assetBaseUrl: options.assetBaseUrl
  };

  const context: RenderContext = {
    dsl: normalized,
    figma: options.figma,
    options: renderOptions,
    assetMap: buildAssetMap(normalized.assets),
    warnings: [],
    errors: [],
    renderedElementCount: 0
  };

  try {
    const root = await renderFrame(context, normalized.root, "$.root");
    context.figma.appendToCurrentPage?.(root);
    return {
      success: context.errors.length === 0,
      rootNodeId: context.figma.getNodeId(root),
      renderedElementCount: context.renderedElementCount,
      warnings: context.warnings,
      errors: context.errors
    };
  } catch (error) {
    addError(context, {
      code: "ROOT_RENDER_FAILED",
      message: error instanceof Error ? error.message : "Root frame render failed.",
      elementId: normalized.root.id,
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
