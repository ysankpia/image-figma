import type { DesignDSL } from "@image-figma/dsl-schema";
import {
  createFigmaAdapter,
  type RenderResult,
  renderDraftRuntimeDesign,
  renderDesign,
  type RenderError,
  type RenderWarning
} from "@image-figma/image-to-figma-renderer";
import mobileHome from "../../packages/dsl-schema/examples/mobile-home.dsl.json";
import {
  API_BASE_URL,
  BackendApiError,
  type DraftDiagnostics,
  getDraftPreviewDsl,
  getDraftPreviewTask,
  uploadPngDraftPreview
} from "./apiClient";
import type {
  MainToPluginMessage,
  PluginDraftDiagnostics,
  PluginRenderMessage,
  PluginState,
  PluginToMainMessage
} from "./messages";
import type { TaskResult, UploadResult } from "./apiClient";

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

    if (message.type === "render-uploaded-png-draft") {
      await renderUploadedPngDraft(message.fileName, toUint8Array(message.bytes));
      return;
    }

    if (message.type === "render-slice-studio-dsl") {
      await renderSliceStudioDsl(message.dslUrl);
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

async function renderSliceStudioDsl(dslUrl: string): Promise<void> {
  postToUI({ type: "render-started", source: "draft" });
  postToUI({ type: "status", message: "Fetching DSL from Slice Studio.", tone: "normal" });

  const response = await fetch(dslUrl);
  if (!response.ok) throw new Error(`Failed to fetch DSL: ${response.status} ${response.statusText}`);
  const dsl = await response.json();

  const serverBase = new URL(dslUrl).origin;
  postToUI({ type: "status", message: "Writing design to Figma.", tone: "normal" });
  const result = await renderDraftRuntimeDesign(dsl, {
    figma: createFigmaAdapter(figma as never),
    validate: true,
    createOriginalReference: false,
    assetBaseUrl: serverBase
  });
  reportRenderResult(result);
}

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

async function renderUploadedPngDraft(fileName: string, bytes: Uint8Array): Promise<void> {
  postToUI({ type: "render-started", source: "draft" });
  postToUI({ type: "status", message: "Uploading PNG.", tone: "normal" });

  const upload = await uploadPngDraftPreview(fileName, bytes);
  postToUI({ type: "status", message: "Running Draft layer pipeline.", tone: "normal" });

  const task = await resolveCompletedTask(upload);
  if (task.status === "failed") {
    throw new BackendApiError("BACKEND_TASK_FAILED", task.message || "Backend task failed.", task.stage, task.taskId);
  }

  postToUI({ type: "status", message: "Fetching Draft Runtime design.", tone: "normal" });
  const dsl = await getDraftPreviewDsl(upload.taskId);

  postToUI({ type: "status", message: "Writing design to Figma.", tone: "normal" });
  const result = await renderDraftRuntimeDesign(dsl, {
    figma: createFigmaAdapter(figma as never),
    validate: true,
    createOriginalReference: false,
    assetBaseUrl: `${API_BASE_URL}/draft-preview/${encodeURIComponent(upload.taskId)}`
  });
  reportRenderResult(result, toPluginDraftDiagnostics(task.diagnostics || upload.diagnostics));
}

async function resolveCompletedTask(upload: UploadResult): Promise<TaskResult> {
  if (upload.status === "completed") {
    const task: TaskResult = {
      taskId: upload.taskId,
      status: upload.status
    };
    if (upload.stage !== undefined) {
      task.stage = upload.stage;
    }
    if (upload.progress !== undefined) {
      task.progress = upload.progress;
    }
    if (upload.dslUrl !== undefined) {
      task.dslUrl = upload.dslUrl;
    }
    if (upload.previewUrl !== undefined) {
      task.previewUrl = upload.previewUrl;
    }
    if (upload.diagnostics !== undefined) {
      task.diagnostics = upload.diagnostics;
    }
    return task;
  }
  return await waitForCompletedTaskWith(upload.taskId, getDraftPreviewTask, "draft_preview_poll");
}

async function waitForCompletedTaskWith(
  taskId: string,
  getTaskFn: (taskId: string) => Promise<TaskResult>,
  stage: string
): Promise<TaskResult> {
  for (let index = 0; index < 180; index += 1) {
    const task = await getTaskFn(taskId);
    if (task.status === "completed" || task.status === "failed") {
      return task;
    }
    await delay(1000);
  }
  throw new BackendApiError("BACKEND_TASK_TIMEOUT", "Backend task timed out.", stage, taskId);
}

function reportRenderResult(result: RenderResult, diagnostics?: PluginDraftDiagnostics): void {
  if (result.success) {
    const message: MainToPluginMessage = {
      type: "render-succeeded",
      renderedElementCount: result.renderedElementCount,
      warningCount: result.warnings.length,
      warnings: result.warnings.map(toPluginRenderMessage)
    };
    if (diagnostics !== undefined) {
      message.diagnostics = diagnostics;
    }
    postToUI(message);
    figma.notify(renderSuccessMessage(result, diagnostics));
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

function renderSuccessMessage(result: RenderResult, diagnostics?: PluginDraftDiagnostics): string {
  const suffix = diagnosticsSummary(diagnostics);
  const base = `Image-to-Figma rendered ${result.renderedElementCount} elements with ${result.warnings.length} warnings.`;
  return suffix ? `${base} ${suffix}` : base;
}

function toPluginDraftDiagnostics(diagnostics: DraftDiagnostics | undefined): PluginDraftDiagnostics | undefined {
  if (diagnostics === undefined) {
    return undefined;
  }
  const next: PluginDraftDiagnostics = {};
  if (diagnostics.ocrProvider !== undefined) {
    next.ocrProvider = diagnostics.ocrProvider;
  }
  if (diagnostics.ocrTextCount !== undefined) {
    next.ocrTextCount = diagnostics.ocrTextCount;
  }
  if (diagnostics.ocrCacheHit !== undefined) {
    next.ocrCacheHit = diagnostics.ocrCacheHit;
  }
  if (diagnostics.textLayerCount !== undefined) {
    next.textLayerCount = diagnostics.textLayerCount;
  }
  if (diagnostics.rasterLayerCount !== undefined) {
    next.rasterLayerCount = diagnostics.rasterLayerCount;
  }
  if (diagnostics.shapeLayerCount !== undefined) {
    next.shapeLayerCount = diagnostics.shapeLayerCount;
  }
  if (diagnostics.missingAssetCount !== undefined) {
    next.missingAssetCount = diagnostics.missingAssetCount;
  }
  return next;
}

function diagnosticsSummary(diagnostics: PluginDraftDiagnostics | undefined): string {
  if (diagnostics === undefined) {
    return "";
  }
  const parts: string[] = [];
  if (diagnostics.ocrProvider !== undefined) {
    const cache = diagnostics.ocrCacheHit === true ? "cache hit" : "fresh";
    parts.push(`OCR ${diagnostics.ocrProvider} ${cache}`);
  }
  if (diagnostics.ocrTextCount !== undefined) {
    parts.push(`text ${diagnostics.ocrTextCount}`);
  }
  if (
    diagnostics.textLayerCount !== undefined ||
    diagnostics.rasterLayerCount !== undefined ||
    diagnostics.shapeLayerCount !== undefined
  ) {
    parts.push(
      `layers T${diagnostics.textLayerCount || 0}/R${diagnostics.rasterLayerCount || 0}/S${diagnostics.shapeLayerCount || 0}`
    );
  }
  if (diagnostics.missingAssetCount !== undefined) {
    parts.push(`missing assets ${diagnostics.missingAssetCount}`);
  }
  return parts.join(", ");
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
