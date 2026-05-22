import type { DesignDSL } from "@image-figma/dsl-schema";
import {
  createFigmaAdapter,
  type RenderResult,
  renderDesign,
  type RenderError,
  type RenderWarning
} from "@image-figma/image-to-figma-renderer";
import mobileHome from "../../packages/dsl-schema/examples/mobile-home.dsl.json";
import { API_BASE_URL, BackendApiError, getTask, getTaskDsl, getTaskM29DirectDsl, uploadPngM30Preview } from "./apiClient";
import type { MainToPluginMessage, PluginRenderMessage, PluginState, PluginToMainMessage } from "./messages";

declare const __html__: string;

const PLUGIN_STATE: PluginState = {
  pluginName: "Image-to-Figma Design",
  mode: "upload",
  rendererReady: true,
  apiBaseUrl: API_BASE_URL
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

    if (message.type === "render-uploaded-png") {
      await renderUploadedPng(message.fileName, toUint8Array(message.bytes));
      return;
    }

    if (message.type === "render-uploaded-png-compare") {
      await renderUploadedPngCompare(message.fileName, toUint8Array(message.bytes));
      return;
    }

    postToUI({
      type: "status",
      message: "Unsupported plugin action.",
      tone: "error"
    });
  } catch (error) {
    const pluginError = toCaughtPluginError(error);
    postToUI({
      type: "render-failed",
      message: pluginError.message,
      errors: [pluginError],
      warnings: []
    });
    figma.notify(`Image-to-Figma failed: ${pluginError.message}`, { error: true });
  }
};

postToUI({ type: "plugin-state", state: PLUGIN_STATE });

async function renderSampleDesign(): Promise<void> {
  postToUI({ type: "render-started", source: "sample" });
  postToUI({ type: "status", message: "Writing sample design to Figma.", tone: "normal" });

  const result = await renderDesign(mobileHome as DesignDSL, {
    figma: createFigmaAdapter(figma as never),
    validate: true,
    createOriginalReference: true
  });

  reportRenderResult(result);
}

async function renderUploadedPng(fileName: string, bytes: Uint8Array): Promise<void> {
  postToUI({ type: "render-started", source: "upload" });
  postToUI({ type: "status", message: "Uploading PNG.", tone: "normal" });

  const upload = await uploadPngM30Preview(fileName, bytes);
  postToUI({ type: "status", message: "Running OCR + M29 evidence pipeline.", tone: "normal" });

  const task = await waitForCompletedTask(upload.taskId);
  if (task.status === "failed") {
    throw new BackendApiError("BACKEND_TASK_FAILED", task.message || "Backend task failed.", task.stage, task.taskId);
  }

  postToUI({ type: "status", message: "Fetching M30 materialized design.", tone: "normal" });
  const dsl = await getTaskDsl(upload.taskId);

  postToUI({ type: "status", message: "Writing design to Figma.", tone: "normal" });
  const result = await renderDesign(dsl, {
    figma: createFigmaAdapter(figma as never),
    validate: true,
    createOriginalReference: true
  });
  reportRenderResult(result);
}

async function renderUploadedPngCompare(fileName: string, bytes: Uint8Array): Promise<void> {
  postToUI({ type: "render-started", source: "upload_compare" });
  postToUI({ type: "status", message: "Uploading PNG.", tone: "normal" });

  const upload = await uploadPngM30Preview(fileName, bytes);
  postToUI({ type: "status", message: "Running comparison pipelines.", tone: "normal" });

  const task = await waitForCompletedTask(upload.taskId);
  if (task.status === "failed") {
    throw new BackendApiError("BACKEND_TASK_FAILED", task.message || "Backend task failed.", task.stage, task.taskId);
  }

  postToUI({ type: "status", message: "Fetching comparison designs.", tone: "normal" });
  const m29DirectDsl = await getTaskM29DirectDsl(upload.taskId);
  const mainlineDsl = await getTaskDsl(upload.taskId);

  postToUI({ type: "status", message: "Writing comparison to Figma.", tone: "normal" });
  const leftDsl = labelRoot(cloneDsl(m29DirectDsl), `M29 Direct Replay / ${fileName}`, 0);
  const rightDsl = labelRoot(cloneDsl(mainlineDsl), `Current Mainline / ${fileName}`, (m29DirectDsl.page?.width || mainlineDsl.page.width) + 80);

  const adapter = createFigmaAdapter(figma as never);
  const leftResult = await renderDesign(leftDsl, {
    figma: adapter,
    validate: true,
    createOriginalReference: true
  });
  const rightResult = await renderDesign(rightDsl, {
    figma: adapter,
    validate: true,
    createOriginalReference: true
  });
  reportCombinedRenderResult([leftResult, rightResult]);
}

async function waitForCompletedTask(taskId: string) {
  for (let index = 0; index < 180; index += 1) {
    const task = await getTask(taskId);
    if (task.status === "completed" || task.status === "failed") {
      return task;
    }
    await delay(1000);
  }
  throw new BackendApiError("BACKEND_TASK_TIMEOUT", "Backend task timed out.", "task_poll", taskId);
}

function reportRenderResult(result: RenderResult): void {
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

  const firstError = result.errors.length > 0 ? result.errors[0] : undefined;
  const message = firstError ? firstError.message : "Renderer returned an unknown error.";
  postToUI({
    type: "render-failed",
    message,
    errors: result.errors.map(toPluginRenderMessage),
    warnings: result.warnings.map(toPluginRenderMessage)
  });
  figma.notify(`Image-to-Figma failed: ${message}`, { error: true });
}

function reportCombinedRenderResult(results: RenderResult[]): void {
  const warnings = results.flatMap((result) => result.warnings);
  const errors = results.flatMap((result) => result.errors);
  const renderedElementCount = results.reduce((total, result) => total + result.renderedElementCount, 0);
  if (errors.length === 0 && results.every((result) => result.success)) {
    postToUI({
      type: "render-succeeded",
      renderedElementCount,
      warningCount: warnings.length,
      warnings: warnings.map(toPluginRenderMessage)
    });
    figma.notify(`Image-to-Figma rendered comparison with ${renderedElementCount} elements.`);
    return;
  }

  const firstError = errors.length > 0 ? errors[0] : undefined;
  const message = firstError ? firstError.message : "Comparison render failed.";
  postToUI({
    type: "render-failed",
    message,
    errors: errors.map(toPluginRenderMessage),
    warnings: warnings.map(toPluginRenderMessage)
  });
  figma.notify(`Image-to-Figma comparison failed: ${message}`, { error: true });
}

function cloneDsl(dsl: DesignDSL): DesignDSL {
  return JSON.parse(JSON.stringify(dsl)) as DesignDSL;
}

function labelRoot(dsl: DesignDSL, name: string, x: number): DesignDSL {
  dsl.root.name = name;
  dsl.root.layout = {
    ...dsl.root.layout,
    x
  };
  return dsl;
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

function toCaughtPluginError(error: unknown): PluginRenderMessage {
  if (error instanceof BackendApiError) {
    return {
      code: error.code,
      message: error.message
    };
  }
  return {
    code: "PLUGIN_UNHANDLED_ERROR",
    message: error instanceof Error ? error.message : "Unknown plugin error."
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function toUint8Array(bytes: ArrayBuffer | Uint8Array | number[]): Uint8Array {
  if (bytes instanceof Uint8Array) {
    return bytes;
  }
  if (bytes instanceof ArrayBuffer) {
    return new Uint8Array(bytes);
  }
  return new Uint8Array(bytes);
}
