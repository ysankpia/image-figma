import type { DesignDSL } from "@image-figma/dsl-schema";
import {
  createFigmaAdapter,
  renderDesign,
  type RenderError,
  type RenderWarning
} from "@image-figma/image-to-figma-renderer";
import mobileHome from "../../packages/dsl-schema/examples/mobile-home.dsl.json";
import type { MainToPluginMessage, PluginRenderMessage, PluginState, PluginToMainMessage } from "./messages";

declare const __html__: string;

const PLUGIN_STATE: PluginState = {
  pluginName: "Image-to-Figma Design",
  mode: "sample",
  rendererReady: true
};

figma.showUI(__html__, { width: 420, height: 560, themeColors: true });

figma.ui.onmessage = async (message: PluginToMainMessage) => {
  try {
    if (message.type === "cancel") {
      figma.closePlugin();
      return;
    }

    if (message.type === "request-plugin-state") {
      postToUI({ type: "plugin-state", state: PLUGIN_STATE });
      return;
    }

    if (message.type === "render-sample") {
      await renderSampleDesign();
      return;
    }

    postToUI({
      type: "status",
      message: "Unsupported plugin action.",
      tone: "error"
    });
  } catch (error) {
    const messageText = getErrorMessage(error);
    postToUI({
      type: "render-failed",
      message: messageText,
      errors: [{ code: "PLUGIN_UNHANDLED_ERROR", message: messageText }],
      warnings: []
    });
    figma.notify(`Image-to-Figma failed: ${messageText}`, { error: true });
  }
};

postToUI({ type: "plugin-state", state: PLUGIN_STATE });

async function renderSampleDesign(): Promise<void> {
  postToUI({ type: "render-started" });
  postToUI({ type: "status", message: "Writing sample design to Figma.", tone: "normal" });

  const result = await renderDesign(mobileHome as DesignDSL, {
    figma: createFigmaAdapter(figma as never),
    validate: true,
    createOriginalReference: true
  });

  if (result.success) {
    postToUI({
      type: "render-succeeded",
      renderedElementCount: result.renderedElementCount,
      warningCount: result.warnings.length,
      warnings: result.warnings.map(toPluginRenderMessage)
    });
    figma.notify(
      `Image-to-Figma rendered ${result.renderedElementCount} elements with ${result.warnings.length} warnings.`
    );
    return;
  }

  const message = result.errors[0]?.message ?? "Renderer returned an unknown error.";
  postToUI({
    type: "render-failed",
    message,
    errors: result.errors.map(toPluginRenderMessage),
    warnings: result.warnings.map(toPluginRenderMessage)
  });
  figma.notify(`Image-to-Figma failed: ${message}`, { error: true });
}

function postToUI(message: MainToPluginMessage): void {
  figma.ui.postMessage(message);
}

function toPluginRenderMessage(message: RenderWarning | RenderError): PluginRenderMessage {
  const next: PluginRenderMessage = {
    code: message.code,
    message: message.message
  };
  if (message.elementId !== undefined) {
    next.elementId = message.elementId;
  }
  return next;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown plugin error.";
}
