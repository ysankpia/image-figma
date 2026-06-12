import { describe, expect, it, vi } from "vitest";
import sharp from "sharp";
import { estimateBackground } from "../server/m29-physical-evidence/background";
import { connectedComponents } from "../server/m29-physical-evidence/connected-components";
import { createForegroundMask } from "../server/m29-physical-evidence/mask";
import { decodeRgba } from "../server/m29-physical-evidence/image";
import { extractPhysicalEvidence, minComponentArea } from "../server/m29-physical-evidence";

describe("m29 physical evidence", () => {
  it("ports Go background estimation threshold semantics", async () => {
    const image = await decodeRgba(await testImage({
      width: 80,
      height: 50,
      background: [248, 245, 236],
      rects: [{ x: 24, y: 18, width: 18, height: 10, color: [18, 18, 18] }]
    }));

    const estimate = estimateBackground(image);
    expect(estimate.color).toEqual({ r: 248, g: 245, b: 236 });
    expect(estimate.threshold).toBe(18);
  });

  it("builds a Go-style foreground mask and connected components", async () => {
    const image = await decodeRgba(await testImage({
      width: 90,
      height: 60,
      background: [250, 248, 242],
      rects: [
        { x: 12, y: 15, width: 8, height: 12, color: [20, 20, 20] },
        { x: 44, y: 30, width: 10, height: 6, color: [30, 30, 30] }
      ]
    }));

    const mask = createForegroundMask(image, estimateBackground(image));
    const components = connectedComponents(mask, minComponentArea(image.width, image.height), 0.80);
    expect(mask.foregroundPixelCount).toBe(156);
    expect(components).toHaveLength(2);
    expect(components.map((component) => component.bbox)).toEqual([
      { x: 12, y: 15, width: 8, height: 12 },
      { x: 44, y: 30, width: 10, height: 6 }
    ]);
    expect(components[0].area).toBe(96);
  });

  it("emits Go M29 contract fields and does not synthesize OCR text regions", async () => {
    const imageBuffer = await testImage({
      width: 120,
      height: 80,
      background: [250, 248, 242],
      rects: [
        { x: 12, y: 12, width: 32, height: 16, color: [20, 20, 20] },
        { x: 16, y: 62, width: 84, height: 2, color: [20, 20, 20] }
      ]
    });

    const doc = await extractPhysicalEvidence({ imageBuffer, sourcePath: "input.png" });

    expect(doc.schemaName).toBe("M29PhysicalEvidence");
    expect(doc.version).toBe("1.0");
    expect(doc.generator).toEqual({ name: "ts-m29", mode: "sharp" });
    expect(doc.ocr).toEqual({ provided: false, blockCount: 0 });
    expect(doc.image.sourcePath).toBe("input.png");
    expect(doc.diagnostics.backgroundColor).toBe("#faf8f2");
    expect(doc.diagnostics.textMaskPixelCount).toBe(0);
    expect(doc.primitives.some((primitive) => primitive.primitiveType === "text_region")).toBe(false);
    expect(doc.primitives.some((primitive) => primitive.primitiveType === "rect")).toBe(true);
    expect(doc.primitives.some((primitive) => primitive.primitiveType === "line")).toBe(true);
    expect(doc.primitives.every((primitive) => primitive.source.kind === "pixel")).toBe(true);
  });

  it("keeps text pixels as physical symbol evidence in no-OCR mode", async () => {
    const imageBuffer = await testImage({
      width: 500,
      height: 300,
      background: [250, 248, 242],
      rects: [
        ...glyphRects(30, 25),
        ...glyphRects(44, 25),
        ...glyphRects(58, 25)
      ]
    });

    const doc = await extractPhysicalEvidence({ imageBuffer });

    expect(doc.primitives.filter((primitive) => primitive.primitiveType === "symbol_region")).toHaveLength(3);
    expect(doc.primitives.some((primitive) => primitive.primitiveType === "text_region")).toBe(false);
  });

  it("uses TS no-OCR physical evidence as the default text locator provider", async () => {
    vi.resetModules();
    const previousProvider = process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER;
    process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER = "ts_m29_physical_evidence";
    const { locateTextLinesWithM29 } = await import("../server/m29-text-locator");
    const imageBuffer = await testImage({
      width: 500,
      height: 300,
      background: [250, 248, 242],
      rects: [
        ...glyphRects(30, 25),
        ...glyphRects(44, 25),
        ...glyphRects(58, 25)
      ]
    });

    const result = await locateTextLinesWithM29({
      width: 500,
      height: 300,
      imageBuffer,
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "测试", bbox: { x: 26, y: 22, width: 48, height: 20 }, confidence: 96, wordCount: 1 }
        ]
      }
    });

    expect(result.source).toBe("m29_ocr_hybrid");
    expect(result.status).toBe("ok");
    expect(result.lines[0].bboxSource).toBe("m29_foreground");
    expect(result.lines[0].bbox).toEqual({ x: 30, y: 25, width: 36, height: 14 });
    expect(result.lines[0].m29PrimitiveId).toContain("+");
    restoreProvider(previousProvider);
  });

  it("falls back to OCR location when physical evidence extraction fails", async () => {
    vi.resetModules();
    const previousProvider = process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER;
    process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER = "ts_m29_physical_evidence";
    const { locateTextLinesWithM29 } = await import("../server/m29-text-locator");
    const result = await locateTextLinesWithM29({
      width: 100,
      height: 60,
      imageBuffer: Buffer.from("not a png"),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "首页", bbox: { x: 20, y: 20, width: 24, height: 12 }, confidence: 95, wordCount: 1 }
        ]
      }
    });

    expect(result.source).toBe("ocr");
    expect(result.status).toBe("failed");
    expect(result.reason).toContain("ts_m29_physical_evidence_failed");
    expect(result.lines[0].bboxSource).toBe("ocr");
    expect(result.lines[0].bbox).toEqual({ x: 20, y: 20, width: 24, height: 12 });
    restoreProvider(previousProvider);
  });
});

async function testImage(input: {
  width: number;
  height: number;
  background: [number, number, number];
  rects: Array<{ x: number; y: number; width: number; height: number; color: [number, number, number] }>;
}): Promise<Buffer> {
  const rgba = Buffer.alloc(input.width * input.height * 4);
  for (let index = 0; index < input.width * input.height; index += 1) {
    const offset = index * 4;
    rgba[offset] = input.background[0];
    rgba[offset + 1] = input.background[1];
    rgba[offset + 2] = input.background[2];
    rgba[offset + 3] = 255;
  }
  for (const rect of input.rects) {
    for (let y = rect.y; y < rect.y + rect.height; y += 1) {
      for (let x = rect.x; x < rect.x + rect.width; x += 1) {
        const offset = (y * input.width + x) * 4;
        rgba[offset] = rect.color[0];
        rgba[offset + 1] = rect.color[1];
        rgba[offset + 2] = rect.color[2];
      }
    }
  }
  return sharp(rgba, { raw: { width: input.width, height: input.height, channels: 4 } }).png().toBuffer();
}

function restoreProvider(previousProvider: string | undefined): void {
  if (previousProvider === undefined) delete process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER;
  else process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER = previousProvider;
}

function glyphRects(x: number, y: number): Array<{ x: number; y: number; width: number; height: number; color: [number, number, number] }> {
  const color: [number, number, number] = [20, 20, 20];
  return [
    { x, y, width: 3, height: 14, color },
    { x, y, width: 8, height: 3, color },
    { x, y: y + 6, width: 8, height: 3, color }
  ];
}
