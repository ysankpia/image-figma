import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BackendApiError,
  getDraftPreviewTask,
  normalizeDraftRuntimeDsl,
  normalizeTaskResult,
  normalizeUploadResult,
  uploadPngDraftPreview,
  type DraftDiagnostics
} from "../src/apiClient";

describe("PSD-like plugin API response normalization", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("normalizes psdlike-python direct upload response", () => {
    const result = normalizeUploadResult({
      taskId: "task_direct",
      status: "completed",
      dslUrl: "/api/draft-preview/task_direct/dsl",
      previewUrl: "/api/draft-preview/task_direct/preview",
      diagnostics: diagnostics()
    });

    expect(result.taskId).toBe("task_direct");
    expect(result.status).toBe("completed");
    expect(result.dslUrl).toBe("/api/draft-preview/task_direct/dsl");
    expect(result.diagnostics?.ocrProvider).toBe("baidu_ppocrv5");
    expect(result.diagnostics?.missingAssetCount).toBe(0);
  });

  it("normalizes envelope upload response", () => {
    const result = normalizeUploadResult({
      success: true,
      data: {
        taskId: "task_envelope",
        status: "queued",
        stage: "draft_queued",
        progress: 1
      }
    });

    expect(result).toEqual({
      taskId: "task_envelope",
      status: "queued",
      stage: "draft_queued",
      progress: 1
    });
  });

  it("normalizes direct task response", () => {
    const result = normalizeTaskResult({
      taskId: "task_direct",
      status: "completed",
      diagnostics: diagnostics()
    });

    expect(result.taskId).toBe("task_direct");
    expect(result.status).toBe("completed");
    expect(result.diagnostics?.textLayerCount).toBe(27);
  });

  it("accepts pure Draft Runtime DSL JSON", () => {
    const dsl = draftDsl();

    expect(normalizeDraftRuntimeDsl(dsl)).toBe(dsl);
  });

  it("accepts envelope Draft Runtime DSL JSON", () => {
    const dsl = draftDsl();

    expect(normalizeDraftRuntimeDsl({ success: true, data: { dsl } })).toBe(dsl);
  });

  it("rejects malformed Draft Runtime DSL JSON", () => {
    expect(() => normalizeDraftRuntimeDsl({ success: true, data: { kind: "draft_runtime" } })).toThrow(
      BackendApiError
    );
  });

  it("turns failure envelopes into readable backend errors", async () => {
    stubFetchJson(
      {
        success: false,
        error: {
          code: "OCR_FAILED",
          message: "BAIDU_PADDLE_OCR_TOKEN is missing.",
          stage: "ocr",
          taskId: "task_ocr"
        }
      },
      true,
      200
    );

    await expect(getDraftPreviewTask("task_ocr")).rejects.toMatchObject({
      code: "OCR_FAILED",
      message: "BAIDU_PADDLE_OCR_TOKEN is missing.",
      stage: "ocr",
      taskId: "task_ocr"
    });
  });

  it("turns FastAPI detail strings into readable backend errors", async () => {
    stubFetchJson({ detail: "Field required: image" }, false, 422);

    await expect(uploadPngDraftPreview("screen.png", new Uint8Array([1, 2, 3]))).rejects.toMatchObject({
      code: "HTTP_422",
      message: "Field required: image"
    });
  });
});

function stubFetchJson(payload: unknown, ok: boolean, status: number): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok,
      status,
      json: async () => payload
    }))
  );
}

function diagnostics(): DraftDiagnostics {
  return {
    ocrProvider: "baidu_ppocrv5",
    ocrPresent: true,
    ocrTextCount: 29,
    ocrCacheHit: true,
    textLayerCount: 27,
    rasterLayerCount: 36,
    shapeLayerCount: 26,
    missingAssetCount: 0,
    fullPageVisibleRaster: 0,
    shapeAssetCount: 0
  };
}

function draftDsl() {
  return {
    version: "1.0",
    kind: "draft_runtime",
    taskId: "task_direct",
    page: { width: 240, height: 120 },
    assets: [],
    root: {
      id: "root",
      type: "frame",
      bbox: { x: 0, y: 0, width: 240, height: 120 },
      children: []
    }
  };
}
