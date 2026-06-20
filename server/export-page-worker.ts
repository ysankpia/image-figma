import sharp from "sharp";
import { cropSliceToPng } from "./shape-cutout";
import { createRemainderPng, preparePencilSliceImage } from "./pencil-package";
import { reconstructTextLayers, type TextReconstruction } from "./text-reconstruction";
import { buildPageRenderPlan } from "./render-plan-builder";
import { pageExportDirectory } from "../shared/manifest";
import type { OcrResult } from "./text-ocr";
import type { TextLocationResult } from "./m29-text-locator";
import type { BBox, SliceRecord } from "../shared/types";

sharp.concurrency(1);

export type WorkerInput = {
  originalBuffer: Buffer;
  pageId: string;
  width: number;
  height: number;
  pageIndex: number;
  displayName: string;
  slices: SliceRecord[];
  ocr: OcrResult;
  m29Location: TextLocationResult | null;
};

export type WorkerOutput = {
  pageId: string;
  pageIndex: number;
  slicePngs: Buffer[];
  pencilSliceImages: Array<{ data: Buffer; placement: BBox; alphaTrim?: BBox }>;
  textReconstruction: TextReconstruction;
  renderPlan: ReturnType<typeof buildPageRenderPlan>;
  remainderPng: Buffer;
  error?: string;
};

self.onmessage = async (event: MessageEvent<WorkerInput>) => {
  const input = event.data;
  try {
    const out = await processPage(input);
    const buffers: ArrayBuffer[] = [
      ...out.slicePngs.map((b) => (b.buffer as ArrayBuffer)),
      ...out.pencilSliceImages.map((p) => (p.data.buffer as ArrayBuffer)),
      (out.remainderPng.buffer as ArrayBuffer)
    ];
    self.postMessage(out, { transfer: buffers });
  } catch (err) {
    self.postMessage({
      pageId: input.pageId,
      pageIndex: input.pageIndex,
      error: err instanceof Error ? err.message : String(err)
    } as WorkerOutput);
  }
};

async function processPage(input: WorkerInput): Promise<WorkerOutput> {
  const { originalBuffer, pageId, width, height, slices, ocr, m29Location, displayName, pageIndex } = input;
  const pageDirectory = pageExportDirectory(pageIndex + 1, displayName);

  const rawOriginal = await sharp(originalBuffer).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const preDecodedRaw = { data: rawOriginal.data, width: rawOriginal.info.width, height: rawOriginal.info.height };

  const slicePngs = await Promise.all(slices.map((slice) => cropSliceToPng(originalBuffer, slice)));
  const pencilSliceImages = await Promise.all(
    slices.map((slice, i) => preparePencilSliceImage(slicePngs[i], slice.bbox, slice.cutMode))
  );

  const textReconstruction = await reconstructTextLayers({
    pageId,
    width,
    height,
    imageBuffer: originalBuffer,
    slices,
    ocr,
    preDecodedRaw,
    preLocated: m29Location ?? undefined
  });

  const renderPlan = buildPageRenderPlan({
    pageId,
    pageDirectory,
    width,
    height,
    textLayers: textReconstruction.layers,
    slices
  });

  const remainderPng = await createRemainderPng(
    originalBuffer,
    slices.map((slice, i) => ({ ...slice, png: slicePngs[i] })),
    renderPlan.remainder.textKnockouts,
    renderPlan.remainder.surfaceKnockouts,
    preDecodedRaw
  );

  return {
    pageId,
    pageIndex,
    slicePngs,
    pencilSliceImages,
    textReconstruction,
    renderPlan,
    remainderPng
  };
}
