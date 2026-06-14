import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { buildPencilManifest, createRemainderPng, frameLayoutXPositions, preparePencilSliceImage } from "../server/pencil-package";
import { validatePencilPackage, type PencilNode } from "../server/pencil-contract";
import { buildPageRenderPlan } from "../server/render-plan-builder";
import type { SurfaceKnockout, TextKnockout } from "../server/render-plan";
import { parseBaiduPpocrv5Rows, parseTesseractTsv } from "../server/text-ocr";
import { reconstructTextLayers, remainingRatio, textGeometryLooksEditable, type TextLayer } from "../server/text-reconstruction";
import { locateTextLinesFromM29 } from "../server/m29-text-locator";
import type { ProjectDetail } from "../shared/types";

type TestBox = { x: number; y: number; width: number; height: number };

function fillRawRect(rgba: Buffer, imageWidth: number, box: TestBox, rgb: [number, number, number]): void {
  for (let y = box.y; y < box.y + box.height; y += 1) {
    for (let x = box.x; x < box.x + box.width; x += 1) {
      const offset = (y * imageWidth + x) * 4;
      rgba[offset] = rgb[0];
      rgba[offset + 1] = rgb[1];
      rgba[offset + 2] = rgb[2];
      rgba[offset + 3] = 255;
    }
  }
}

function surfaceKnockout(bbox: TestBox, fill: string, cornerRadius: number, driftPad = 3): SurfaceKnockout {
  return {
    visibleShape: {
      kind: "rounded_rect",
      bbox,
      cornerRadius
    },
    sourceOwnerRegion: {
      kind: "owner_band",
      pad: driftPad,
      fill,
      backgroundSample: "outside_ring",
      connectivity: "from_visible_shape",
      provenance: "ocr_owner_surface"
    },
    provenance: "ocr_owner_surface"
  };
}

function testTextLayer(id: string, text: string, bbox: TestBox, metadata: Record<string, unknown> = {}): TextLayer {
  return {
    id,
    text,
    bbox,
    textRenderBBox: bbox,
    safeBBox: bbox,
    knockoutBBox: bbox,
    originalBBox: bbox,
    fontSize: 16,
    fontFamily: "PingFang SC",
    fontWeight: "400",
    lineHeight: 1,
    color: "#ffffff",
    confidence: 99,
    metadata
  };
}

function overlapArea(a: TestBox, b: TestBox): number {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  return right > left && bottom > top ? (right - left) * (bottom - top) : 0;
}

function pixelDistance(raw: Buffer, imageWidth: number, a: { x: number; y: number }, b: Buffer): number {
  const offset = (a.y * imageWidth + a.x) * 4;
  return Math.sqrt(
    ((raw[offset] - b[offset]) ** 2)
    + ((raw[offset + 1] - b[offset + 1]) ** 2)
    + ((raw[offset + 2] - b[offset + 2]) ** 2)
  );
}

function findWhitePixelInsideSafeOutsideKnockout(
  rgba: Buffer,
  imageWidth: number,
  safeBBox: TestBox,
  knockoutBBox: TestBox
): { x: number; y: number } | null {
  const paintPad = Math.max(1, Math.min(4, Math.round(knockoutBBox.height * 0.08)));
  const paddedKnockout = {
    x: knockoutBBox.x - paintPad,
    y: knockoutBBox.y - paintPad,
    width: knockoutBBox.width + paintPad * 2,
    height: knockoutBBox.height + paintPad * 2
  };
  const left = Math.floor(safeBBox.x);
  const top = Math.floor(safeBBox.y);
  const right = Math.ceil(safeBBox.x + safeBBox.width);
  const bottom = Math.ceil(safeBBox.y + safeBBox.height);
  for (let y = top; y < bottom; y += 1) {
    for (let x = left; x < right; x += 1) {
      if (
        x >= paddedKnockout.x
        && x < paddedKnockout.x + paddedKnockout.width
        && y >= paddedKnockout.y
        && y < paddedKnockout.y + paddedKnockout.height
      ) continue;
      const offset = (y * imageWidth + x) * 4;
      if (rgba[offset] > 245 && rgba[offset + 1] > 245 && rgba[offset + 2] > 245 && rgba[offset + 3] === 255) return { x, y };
    }
  }
  return null;
}

describe("pencil exporter", () => {
  it("clears selected slice rectangles from the remainder layer", async () => {
    const source = await sharp({
      create: {
        width: 8,
        height: 8,
        channels: 4,
        background: { r: 255, g: 0, b: 0, alpha: 1 }
      }
    }).png().toBuffer();

    const png = await createRemainderPng(source, [{ bbox: { x: 2, y: 2, width: 3, height: 3 } }]);
    const raw = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });

    expect(raw.info.width).toBe(8);
    expect(raw.info.height).toBe(8);
    expect(raw.data[(2 * raw.info.width + 2) * 4 + 3]).toBe(0);
    expect(raw.data[(6 * raw.info.width + 6) * 4 + 3]).toBe(255);
  });

  it("paints accepted OCR text regions out of the remainder without changing slice alpha behavior", async () => {
    const source = await sharp({
      create: {
        width: 24,
        height: 16,
        channels: 4,
        background: { r: 246, g: 242, b: 232, alpha: 1 }
      }
    })
      .composite([{
        input: await sharp({
          create: {
            width: 8,
            height: 4,
            channels: 4,
            background: { r: 10, g: 10, b: 10, alpha: 1 }
          }
        }).png().toBuffer(),
        left: 8,
        top: 6
      }])
      .png()
      .toBuffer();

    const png = await createRemainderPng(
      source,
      [{ bbox: { x: 2, y: 2, width: 3, height: 3 } }],
      [{ x: 8, y: 6, width: 8, height: 4 }]
    );
    const raw = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const textOffset = (7 * raw.info.width + 10) * 4;
    const sliceOffset = (3 * raw.info.width + 3) * 4;

    expect(raw.data[textOffset]).toBeGreaterThan(220);
    expect(raw.data[textOffset + 1]).toBeGreaterThan(210);
    expect(raw.data[textOffset + 2]).toBeGreaterThan(200);
    expect(raw.data[textOffset + 3]).toBe(255);
    expect(raw.data[sliceOffset + 3]).toBe(0);
  });

  it("inpaints dilated text masks so bright glyph shadows do not remain in raster-owned backgrounds", async () => {
    const width = 80;
    const height = 44;
    const rgba = Buffer.alloc(width * height * 4);
    fillRawRect(rgba, width, { x: 0, y: 0, width, height }, [0, 148, 65]);
    fillRawRect(rgba, width, { x: 24, y: 17, width: 28, height: 8 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 24, y: 25, width: 28, height: 2 }, [0, 104, 45]);
    const source = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const png = await createRemainderPng(source, [], [{
      bbox: { x: 22, y: 14, width: 32, height: 16 },
      foregroundColor: "#ffffff",
      provenance: "ocr_text"
    }]);
    const raw = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const whiteGlyph = (20 * width + 34) * 4;
    const darkShadow = (25 * width + 34) * 4;

    expect(raw.data[whiteGlyph]).toBeLessThan(24);
    expect(raw.data[whiteGlyph + 1]).toBeGreaterThan(120);
    expect(raw.data[whiteGlyph + 1]).toBeLessThan(180);
    expect(raw.data[whiteGlyph + 2]).toBeGreaterThan(44);
    expect(raw.data[darkShadow]).toBeLessThan(24);
    expect(raw.data[darkShadow + 1]).toBeGreaterThan(120);
    expect(raw.data[darkShadow + 1]).toBeLessThan(180);
    expect(raw.data[darkShadow + 2]).toBeGreaterThan(44);
    expect(raw.data[whiteGlyph + 3]).toBe(255);
    expect(raw.data[darkShadow + 3]).toBe(255);
  });

  it("preserves colored button surfaces when knocking out editable button text", async () => {
    const source = await sharp({
      create: {
        width: 100,
        height: 70,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    })
      .composite([
        {
          input: await sharp({
            create: {
              width: 70,
              height: 26,
              channels: 4,
              background: { r: 24, g: 145, b: 84, alpha: 1 }
            }
          }).png().toBuffer(),
          left: 10,
          top: 20
        },
        {
          input: await sharp({
            create: {
              width: 18,
              height: 8,
              channels: 4,
              background: { r: 255, g: 255, b: 255, alpha: 1 }
            }
          }).png().toBuffer(),
          left: 36,
          top: 29
        }
      ])
      .png()
      .toBuffer();

    const png = await createRemainderPng(source, [], [{ x: 30, y: 20, width: 30, height: 26 }]);
    const raw = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const offset = (32 * raw.info.width + 45) * 4;

    expect(raw.data[offset]).toBeLessThan(90);
    expect(raw.data[offset + 1]).toBeGreaterThan(110);
    expect(raw.data[offset + 2]).toBeLessThan(120);
    expect(raw.data[offset + 3]).toBe(255);
  });

  it("removes exported control surfaces from the remainder owner layer", async () => {
    const width = 120;
    const height = 80;
    const source = await sharp(Buffer.from(`
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"/>
        <rect x="24" y="24" width="72" height="32" rx="16" fill="#10b32f"/>
        <rect x="48" y="36" width="24" height="8" fill="#ffffff"/>
      </svg>
    `)).png().toBuffer();

    const remainder = await createRemainderPng(
      source,
      [],
      [{ x: 44, y: 32, width: 32, height: 16 }],
      [surfaceKnockout({ x: 24, y: 24, width: 72, height: 32 }, "#10b32f", 16)]
    );
    const raw = await sharp(remainder).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const buttonCenter = (40 * width + 60) * 4;
    const outsideButton = (12 * width + 12) * 4;

    expect(raw.data[buttonCenter + 3]).toBe(0);
    expect(raw.data[outsideButton + 3]).toBe(255);
  });

  it("clears small source-surface edge drift around exported control surfaces", async () => {
    const width = 160;
    const height = 90;
    const source = await sharp(Buffer.from(`
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="0" width="${width}" height="${height}" fill="#f2eadf"/>
        <rect x="24" y="22" width="96" height="36" rx="18" fill="#10b32f"/>
        <rect x="62" y="36" width="20" height="8" fill="#ffffff"/>
      </svg>
    `)).png().toBuffer();

    const remainder = await createRemainderPng(
      source,
      [],
      [{ x: 58, y: 34, width: 24, height: 12 }],
      [surfaceKnockout({ x: 27, y: 25, width: 90, height: 30 }, "#10b32f", 15)]
    );
    const raw = await sharp(remainder).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const sourceOnlyEdge = (22 * width + 72) * 4;
    const backgroundNearSurfaceEdge = (23 * width + 27) * 4;
    const outsideButton = (12 * width + 12) * 4;

    expect(raw.data[sourceOnlyEdge + 3]).toBe(0);
    expect(raw.data[backgroundNearSurfaceEdge + 3]).toBe(255);
    expect(raw.data[outsideButton + 3]).toBe(255);
  });

  it("clears connected owner/background blend pixels without erasing isolated lookalikes", async () => {
    const width = 90;
    const height = 70;
    const rgba = Buffer.alloc(width * height * 4);
    const background: [number, number, number] = [242, 234, 223];
    const fill: [number, number, number] = [16, 179, 47];
    const blend: [number, number, number] = [230, 249, 233];
    fillRawRect(rgba, width, { x: 0, y: 0, width, height }, background);
    fillRawRect(rgba, width, { x: 20, y: 20, width: 40, height: 20 }, fill);
    fillRawRect(rgba, width, { x: 25, y: 19, width: 30, height: 1 }, blend);
    fillRawRect(rgba, width, { x: 25, y: 17, width: 30, height: 1 }, blend);
    const source = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const remainder = await createRemainderPng(
      source,
      [],
      [],
      [surfaceKnockout({ x: 20, y: 20, width: 40, height: 20 }, "#10b32f", 0, 3)]
    );
    const raw = await sharp(remainder).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const connectedBlend = (19 * width + 30) * 4;
    const isolatedBlend = (17 * width + 30) * 4;
    const exactBackgroundBand = (18 * width + 30) * 4;
    const visibleSurface = (25 * width + 30) * 4;
    const farBackground = (10 * width + 10) * 4;

    expect(raw.data[visibleSurface + 3]).toBe(0);
    expect(raw.data[connectedBlend + 3]).toBe(0);
    expect(raw.data[isolatedBlend + 3]).toBe(255);
    expect(raw.data[exactBackgroundBand + 3]).toBe(255);
    expect(raw.data[farBackground + 3]).toBe(255);
  });

  it("keeps filled control surfaces raster-owned by default", () => {
    const plan = buildPageRenderPlan({
      pageId: "page_0001",
      pageDirectory: "P1",
      width: 200,
      height: 120,
      slices: [],
      textLayers: [
        testTextLayer("page_0001__text_0001", "预约", { x: 70, y: 40, width: 48, height: 20 }, {
          textOwnerSurface: {
            bbox: { x: 52, y: 30, width: 92, height: 38 },
            fill: "#10b32f",
            cornerRadius: 19,
            reason: "filled_control_surface"
          }
        }),
        testTextLayer("page_0001__text_0002", "价格", { x: 20, y: 84, width: 46, height: 18 }, {
          textOwnerSurface: {
            bbox: { x: 16, y: 80, width: 72, height: 26 },
            fill: "#fefefe",
            cornerRadius: 4,
            reason: "filled_control_surface"
          }
        })
      ]
    });

    expect(plan.layers.controlSurfaces).toEqual([]);
    expect(plan.remainder.surfaceKnockouts).toEqual([]);
    expect(plan.remainder.textKnockouts).toEqual([
      {
        bbox: { x: 70, y: 40, width: 48, height: 20 },
        clipShape: {
          kind: "rounded_rect",
          bbox: { x: 52, y: 30, width: 92, height: 38 },
          cornerRadius: 19
        },
        foregroundColor: "#ffffff",
        paintPadding: 0,
        provenance: "raster_owned_control_text"
      },
      {
        bbox: { x: 20, y: 84, width: 46, height: 18 },
        foregroundColor: "#ffffff",
        provenance: "ocr_text"
      }
    ]);
    expect(plan.layers.text[0].zIndex).toBe(1);
    expect(plan.layers.text[1].zIndex).toBe(2);
  });

  it("erases raster-owned control label glyphs without repainting outside the control", async () => {
    const width = 90;
    const height = 60;
    const rgba = Buffer.alloc(width * height * 4);
    fillRawRect(rgba, width, { x: 0, y: 0, width, height }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 20, y: 20, width: 42, height: 22 }, [16, 179, 47]);
    fillRawRect(rgba, width, { x: 34, y: 28, width: 16, height: 5 }, [255, 255, 255]);
    const source = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();
    const knockout: TextKnockout = {
      bbox: { x: 30, y: 20, width: 24, height: 18 },
      clipShape: {
        kind: "rounded_rect",
        bbox: { x: 20, y: 20, width: 42, height: 22 },
        cornerRadius: 0
      },
      foregroundColor: "#ffffff",
      paintPadding: 0,
      provenance: "raster_owned_control_text"
    };

    const remainder = await createRemainderPng(source, [], [knockout]);
    const raw = await sharp(remainder).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const outsideWhite = (19 * width + 40) * 4;
    const erasedGlyph = (30 * width + 40) * 4;

    expect(raw.data[outsideWhite]).toBe(255);
    expect(raw.data[outsideWhite + 1]).toBe(255);
    expect(raw.data[outsideWhite + 2]).toBe(255);
    expect(raw.data[outsideWhite + 3]).toBe(255);
    expect(raw.data[erasedGlyph]).toBeLessThan(60);
    expect(raw.data[erasedGlyph + 1]).toBeGreaterThan(120);
    expect(raw.data[erasedGlyph + 2]).toBeLessThan(90);
    expect(raw.data[erasedGlyph + 3]).toBe(255);
  });

  it("uses tight knockout bounds instead of Pencil safe bounds on rounded buttons", async () => {
    const width = 220;
    const height = 90;
    const source = await sharp(Buffer.from(`
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"/>
        <rect x="108" y="28" width="84" height="36" rx="18" fill="#18a64a"/>
        <rect x="134" y="39" width="46" height="13" fill="#ffffff"/>
      </svg>
    `)).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer: source,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "查看详情", bbox: { x: 132, y: 36, width: 54, height: 22 }, confidence: 98, wordCount: 1 },
          bbox: { x: 132, y: 36, width: 54, height: 22 },
          bboxSource: "ocr"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "查看详情", bbox: { x: 132, y: 36, width: 54, height: 22 }, confidence: 98, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.safeBBox.width * layer.safeBBox.height).toBeGreaterThan(layer.knockoutBBox.width * layer.knockoutBBox.height);

    const originalRaw = await sharp(source).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const probe = findWhitePixelInsideSafeOutsideKnockout(originalRaw.data, width, layer.safeBBox, layer.knockoutBBox);
    expect(probe).toBeTruthy();

    const remainder = await createRemainderPng(source, [], [layer.knockoutBBox]);
    const raw = await sharp(remainder).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const offset = (probe!.y * width + probe!.x) * 4;
    expect(raw.data[offset]).toBeGreaterThan(245);
    expect(raw.data[offset + 1]).toBeGreaterThan(245);
    expect(raw.data[offset + 2]).toBeGreaterThan(245);
    expect(raw.data[offset + 3]).toBe(255);
  });

  it("rejects low-contrast PSD-like text colors when local foreground has clear contrast", async () => {
    const width = 160;
    const height = 80;
    const source = await sharp(Buffer.from(`
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"/>
        <rect x="20" y="20" width="120" height="36" rx="12" fill="#019441"/>
        <rect x="46" y="32" width="64" height="12" fill="#ffffff"/>
      </svg>
    `)).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer: source,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "ocr",
        lines: [{
          line: { text: "待支付", bbox: { x: 44, y: 27, width: 70, height: 24 }, confidence: 98, wordCount: 1 },
          bbox: { x: 44, y: 27, width: 70, height: 24 },
          bboxSource: "ocr"
        }]
      }),
      textStyleResolver: async () => [{
        fontSize: 24,
        fontWeight: "500",
        fontFamily: "PingFang SC",
        color: "#019441",
        lineHeight: 1,
        textAlign: "left",
        measured: { width: 64, height: 20 },
        source: "psdlike"
      }],
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "待支付", bbox: { x: 44, y: 27, width: 70, height: 24 }, confidence: 98, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers[0].color).toBe("#ffffff");
    expect(reconstruction.layers[0].metadata.textStyleColorRejected).toEqual({
      measuredColor: "#019441",
      fallbackColor: "#ffffff",
      backgroundColor: "#019441",
      reason: "low_contrast_against_local_background"
    });
  });

  it("uses the union of OCR and physical text boxes for source knockout bounds", async () => {
    const width = 140;
    const height = 80;
    const source = await sharp({
      create: {
        width,
        height,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer: source,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "ocr",
        lines: [{
          line: { text: "立即支付", bbox: { x: 48, y: 28, width: 58, height: 22 }, confidence: 98, wordCount: 1 },
          bbox: { x: 34, y: 26, width: 42, height: 24 },
          bboxSource: "m29_foreground"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "立即支付", bbox: { x: 48, y: 28, width: 58, height: 22 }, confidence: 98, wordCount: 1 }
        ]
      }
    });

    const knockout = reconstruction.layers[0].knockoutBBox;
    expect(knockout.x).toBeLessThanOrEqual(34);
    expect(knockout.x + knockout.width).toBeGreaterThanOrEqual(106);
  });

  it("knocks out glyph foreground without flattening rounded gradient button surfaces", async () => {
    const width = 220;
    const height = 90;
    const source = await sharp(Buffer.from(`
      <svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="buttonFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#35d45c"/>
            <stop offset="52%" stop-color="#16b944"/>
            <stop offset="100%" stop-color="#10a83d"/>
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"/>
        <rect x="34" y="22" width="152" height="42" rx="21" fill="url(#buttonFill)"/>
        <rect x="80" y="38" width="60" height="12" fill="#ffffff"/>
      </svg>
    `)).png().toBuffer();

    const originalRaw = await sharp(source).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const remainder = await createRemainderPng(source, [], [{
      bbox: { x: 62, y: 20, width: 112, height: 44 },
      foregroundColor: "#ffffff",
      provenance: "ocr_text"
    }]);
    const raw = await sharp(remainder).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const gradientProbe = { x: 112, y: 25 };
    const textProbe = { x: 108, y: 43 };
    const textOffset = (textProbe.y * width + textProbe.x) * 4;

    expect(pixelDistance(raw.data, width, gradientProbe, originalRaw.data)).toBeLessThan(3);
    expect(raw.data[textOffset]).toBeLessThan(90);
    expect(raw.data[textOffset + 1]).toBeGreaterThan(120);
    expect(raw.data[textOffset + 2]).toBeLessThan(110);
    expect(raw.data[textOffset + 3]).toBe(255);
  });

  it("keeps remainder pixels under transparent subject slice areas", async () => {
    const width = 24;
    const height = 24;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 248;
      rgba[offset + 1] = 242;
      rgba[offset + 2] = 232;
      rgba[offset + 3] = 255;
    }
    for (let y = 8; y < 16; y += 1) {
      for (let x = 8; x < 16; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = 20;
        rgba[offset + 1] = 20;
        rgba[offset + 2] = 20;
      }
    }
    const source = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const png = await createRemainderPng(source, [{ cutMode: "subject", bbox: { x: 0, y: 0, width, height } }]);
    const raw = await sharp(png).ensureAlpha().raw().toBuffer({ resolveWithObject: true });

    expect(raw.data[3]).toBe(255);
    expect(raw.data[(10 * width + 10) * 4 + 3]).toBe(0);
  });

  it("builds project.zip manifest paths for Pencil visible assets", () => {
    const detail: ProjectDetail = {
      project: {
        id: "project_1",
        name: "Demo",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
        pageCount: 1,
        sliceCount: 1
      },
      pages: [{
        id: "page_0001",
        projectId: "project_1",
        pageIndex: 1,
        originalName: "home.png",
        displayName: "首页",
        width: 100,
        height: 80,
        sourceUrl: "/source",
        slices: [{
          id: "slice_1",
          projectId: "project_1",
          pageId: "page_0001",
          sliceIndex: 1,
          name: "hero",
          kind: "image",
          cutMode: "card",
          bbox: { x: 1, y: 2, width: 30, height: 20 },
          selected: true
        }]
      }]
    };

    const manifest = buildPencilManifest(detail, "2026-01-02T00:00:00.000Z");
    expect(manifest.schema).toBe("slice_studio_pencil_project_manifest.v1");
    expect(manifest.pencil.designPen).toBe("design.pen");
    expect(manifest.pages[0].original).toBe("assets/originals/P1-首页.png");
    expect(manifest.pages[0].remainder).toBe("assets/visible/remainders/P1-首页/remainder.png");
    expect(manifest.pages[0].slices[0].filename).toBe("assets/visible/slices/P1-首页/slice_0001.png");
    expect(manifest.pages[0].slices[0].cutMode).toBe("card");
    expect(manifest.pages[0].ocr.status).toBe("skipped");
    expect(manifest.pages[0].textLayerCount).toBe(0);
    expect(manifest.pages[0].textLayers).toEqual([]);
  });

  it("records OCR text layers in the Pencil manifest", () => {
    const detail: ProjectDetail = {
      project: {
        id: "project_1",
        name: "Demo",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
        pageCount: 1,
        sliceCount: 0
      },
      pages: [{
        id: "page_0001",
        projectId: "project_1",
        pageIndex: 1,
        originalName: "home.png",
        displayName: "首页",
        width: 100,
        height: 80,
        sourceUrl: "/source",
        slices: []
      }]
    };

    const manifest = buildPencilManifest(detail, "2026-01-02T00:00:00.000Z", new Map([[
      "page_0001",
      {
        ocr: {
          provider: "baidu_ppocrv5",
          status: "ok",
          language: "zh+en",
          model: "PP-OCRv5",
          sourceLineCount: 2,
          textLayerCount: 1,
          rasterPreservedTextCount: 0,
          skippedTextCount: 0,
          ownershipPolicy: "slice_studio_text_ownership.v1" as const
        },
        textLayerCount: 1,
        textLayers: [{
          id: "page_0001__text_0001",
          text: "去结算",
          placement: { x: 10, y: 20, width: 50, height: 16 },
          textRenderBBox: { x: 10, y: 20, width: 50, height: 16 },
          originalBBox: { x: 12, y: 22, width: 46, height: 12 },
          knockoutBBox: { x: 12, y: 22, width: 46, height: 12 },
          fontSize: 12,
          fontFamily: "PingFang SC",
          fontWeight: "400",
          color: "#111111",
          confidence: 88,
          textOwnerSurface: {
            bbox: { x: 8, y: 18, width: 56, height: 20 },
            fill: "#10b32f",
            cornerRadius: 10,
            confidence: 0.91,
            reason: "filled_control_surface",
            fillRatio: 0.82,
            edgeCoverage: 0.66
          },
          textLayoutOwnerSurface: {
            bbox: { x: 8, y: 18, width: 56, height: 20 },
            fill: "#10b32f",
            cornerRadius: 10,
            confidence: 0.91,
            reason: "filled_control_surface",
            fillRatio: 0.82,
            edgeCoverage: 0.66
          }
        }]
      }
    ]]));

    expect(manifest.pages[0].ocr.status).toBe("ok");
    expect(manifest.pages[0].ocr.sourceLineCount).toBe(2);
    expect(manifest.pages[0].textLayerCount).toBe(1);
    expect(manifest.pages[0].textLayers[0].text).toBe("去结算");
    expect(manifest.pages[0].textLayers[0].textOwnerSurface).toMatchObject({
      fill: "#10b32f",
      cornerRadius: 10,
      reason: "filled_control_surface"
    });
    expect(manifest.pages[0].textLayers[0].textLayoutOwnerSurface).toMatchObject({
      fill: "#10b32f",
      cornerRadius: 10,
      reason: "filled_control_surface"
    });
  });

  it("lays out variable-width Pencil frames without overlap", () => {
    expect(frameLayoutXPositions([
      { width: 941 },
      { width: 1092 },
      { width: 853 }
    ])).toEqual([0, 1101, 2353]);
  });

  it("requires exported Pencil page frames to clip overflowing editable text", () => {
    const files = [{ name: "assets/visible/remainders/P1/remainder.png", data: Buffer.alloc(0) }];
    const frame: PencilNode = {
      id: "page_0001__frame",
      type: "frame",
      name: "P1",
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      layout: "none",
      fill: "#FFFFFF",
      clip: true,
      metadata: { type: "slice_studio_page" },
      children: [{
        id: "page_0001__remainder",
        type: "rectangle",
        name: "P1 remainder",
        x: 0,
        y: 0,
        width: 100,
        height: 100,
        fill: {
          type: "image",
          enabled: true,
          url: "./assets/visible/remainders/P1/remainder.png",
          mode: "stretch"
        },
        metadata: { type: "slice_studio_remainder" }
      }]
    };

    expect(() => validatePencilPackage({ version: "2.11", children: [frame] }, files)).not.toThrow();
    expect(() => validatePencilPackage({
      version: "2.11",
      children: [{ ...frame, clip: false }]
    }, files)).toThrow(/page frames must clip/);
  });

  it("rejects editable Pencil text nodes with explicit lineHeight", () => {
    const files = [{ name: "assets/visible/remainders/P1/remainder.png", data: Buffer.alloc(0) }];
    const frame: PencilNode = {
      id: "page_0001__frame",
      type: "frame",
      name: "P1",
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      layout: "none",
      fill: "#FFFFFF",
      clip: true,
      metadata: { type: "slice_studio_page" },
      children: [{
        id: "page_0001__text_0001",
        type: "text",
        name: "text",
        x: 10,
        y: 10,
        width: 40,
        height: 22,
        content: "测试",
        textGrowth: "fixed-width-height",
        fontFamily: "PingFang SC",
        fontSize: 16,
        fontWeight: "400",
        lineHeight: 1,
        textAlignVertical: "middle",
        fill: "#111111",
        metadata: {
          type: "slice_studio_editable_text",
          textRenderBBox: { x: 10, y: 10, width: 40, height: 22 }
        }
      }]
    };

    expect(() => validatePencilPackage({ version: "2.11", children: [frame] }, files)).toThrow(/must not set lineHeight/);
  });

  it("allows raster-owned filled controls and validates optional vector control surfaces", () => {
    const ownerSurface = {
      bbox: { x: 20, y: 30, width: 120, height: 44 },
      fill: "#10b32f",
      cornerRadius: 22,
      confidence: 0.92,
      reason: "filled_control_surface",
      fillRatio: 0.86,
      edgeCoverage: 0.71
    };
    const text: PencilNode = {
      id: "page_0001__text_0001",
      type: "text",
      name: "text",
      x: 28,
      y: 36,
      width: 104,
      height: 32,
      content: "查看详情",
      textGrowth: "fixed-width-height",
      fontFamily: "PingFang SC",
      fontSize: 24,
      fontWeight: "600",
      textAlign: "center",
      textAlignVertical: "middle",
      fill: "#ffffff",
      metadata: {
        type: "slice_studio_editable_text",
        textRenderBBox: { x: 28, y: 36, width: 104, height: 32 },
        textLayoutOwnerSurface: ownerSurface,
        textOwnerSurface: ownerSurface
      }
    };
    const surface: PencilNode = {
      id: "page_0001__control_surface_0001",
      type: "rectangle",
      name: "control_surface_0001",
      x: 20,
      y: 30,
      width: 120,
      height: 44,
      fill: "#10b32f",
      cornerRadius: 22,
      metadata: {
        type: "slice_studio_control_surface",
        sourceTextId: "page_0001__text_0001"
      }
    };
    const frame: PencilNode = {
      id: "page_0001__frame",
      type: "frame",
      name: "P1",
      x: 0,
      y: 0,
      width: 200,
      height: 100,
      layout: "none",
      fill: "#FFFFFF",
      clip: true,
      metadata: { type: "slice_studio_page" },
      children: [surface, text]
    };

    expect(() => validatePencilPackage({ version: "2.11", children: [frame] }, [])).not.toThrow();
    expect(() => validatePencilPackage({ version: "2.11", children: [{ ...frame, children: [text] }] }, [])).not.toThrow();
    expect(() => validatePencilPackage({ version: "2.11", children: [{ ...frame, children: [text, surface] }] }, [])).toThrow(/must render below/);
    expect(() => validatePencilPackage({
      version: "2.11",
      children: [{ ...frame, children: [surface, { ...text, textAlign: "left" }] }]
    }, [])).toThrow(/must be center aligned/);
  });

  it("trims transparent subject assets before placing them in Pencil", async () => {
    const width = 10;
    const height = 10;
    const rgba = Buffer.alloc(width * height * 4);
    for (let y = 3; y < 9; y += 1) {
      for (let x = 2; x < 8; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = 20;
        rgba[offset + 1] = 30;
        rgba[offset + 2] = 40;
        rgba[offset + 3] = 255;
      }
    }
    const png = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();
    const prepared = await preparePencilSliceImage(png, { x: 100, y: 200, width, height }, "subject");
    const metadata = await sharp(prepared.data).metadata();

    expect(prepared.placement).toEqual({ x: 102, y: 203, width: 6, height: 6 });
    expect(prepared.alphaTrim).toEqual({ x: 2, y: 3, width: 6, height: 6 });
    expect(metadata.width).toBe(6);
    expect(metadata.height).toBe(6);
  });

  it("records alpha-trimmed Pencil slice placement in the manifest", () => {
    const detail: ProjectDetail = {
      project: {
        id: "project_1",
        name: "Demo",
        createdAt: "2026-01-01T00:00:00.000Z",
        updatedAt: "2026-01-01T00:00:00.000Z",
        pageCount: 1,
        sliceCount: 1
      },
      pages: [{
        id: "page_0001",
        projectId: "project_1",
        pageIndex: 1,
        originalName: "home.png",
        displayName: "",
        width: 100,
        height: 80,
        sourceUrl: "/source",
        slices: [{
          id: "slice_1",
          projectId: "project_1",
          pageId: "page_0001",
          sliceIndex: 1,
          name: "avatar",
          kind: "image",
          cutMode: "subject",
          bbox: { x: 10, y: 20, width: 30, height: 30 },
          selected: true
        }]
      }]
    };

    const manifest = buildPencilManifest(
      detail,
      "2026-01-02T00:00:00.000Z",
      new Map(),
      new Map([[
        "slice_1",
        {
          placement: { x: 13, y: 24, width: 22, height: 20 },
          originalBBox: { x: 10, y: 20, width: 30, height: 30 },
          alphaTrim: { x: 3, y: 4, width: 22, height: 20 }
        }
      ]])
    );

    expect(manifest.pages[0].slices[0].placement).toEqual({ x: 13, y: 24, width: 22, height: 20 });
    expect(manifest.pages[0].slices[0].originalBBox).toEqual({ x: 10, y: 20, width: 30, height: 30 });
    expect(manifest.pages[0].slices[0].alphaTrim).toEqual({ x: 3, y: 4, width: 22, height: 20 });
  });

  it("parses Baidu PP-OCRv5 JSONL rows into OCR lines", () => {
    const lines = parseBaiduPpocrv5Rows([{
      result: {
        ocrResults: [{
          prunedResult: {
            rec_texts: ["东方茉莉鲜奶茶", "低置信"],
            rec_scores: [0.96, 0.2],
            rec_boxes: [[100, 200, 280, 236], [1, 1, 10, 10]],
            rec_polys: []
          }
        }]
      }
    }], 0.7);

    expect(lines).toEqual([{
      text: "东方茉莉鲜奶茶",
      bbox: { x: 100, y: 200, width: 180, height: 36 },
      confidence: 96,
      wordCount: 1
    }]);
  });

  it("parses tesseract TSV words into readable lines", () => {
    const tsv = [
      "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
      "5\t1\t1\t1\t1\t1\t10\t20\t20\t10\t91\tHello",
      "5\t1\t1\t1\t1\t2\t36\t20\t24\t10\t90\tWorld",
      "5\t1\t2\t1\t1\t1\t10\t40\t30\t12\t89\t首页"
    ].join("\n");

    const lines = parseTesseractTsv(tsv);
    expect(lines).toHaveLength(2);
    expect(lines[0]).toMatchObject({
      text: "Hello World",
      bbox: { x: 10, y: 20, width: 50, height: 10 },
      confidence: 91,
      wordCount: 2
    });
    expect(lines[1].text).toBe("首页");
  });

  it("filters OCR lines covered by confirmed manual slices", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 120,
        height: 80,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    })
      .composite([{
        input: await sharp({
          create: {
            width: 40,
            height: 12,
            channels: 4,
            background: { r: 20, g: 20, b: 20, alpha: 1 }
          }
        }).png().toBuffer(),
        left: 10,
        top: 20
      }])
      .png()
      .toBuffer();

    expect(remainingRatio(
      { x: 10, y: 20, width: 40, height: 12 },
      [{ x: 8, y: 18, width: 48, height: 18 }]
    )).toBe(0);

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 120,
      height: 80,
      imageBuffer,
      slices: [{
        id: "slice_1",
        projectId: "project_1",
        pageId: "page_0001",
        sliceIndex: 1,
        name: "button",
        kind: "image",
        cutMode: "rect",
        bbox: { x: 8, y: 18, width: 48, height: 18 },
        selected: true
      }],
      ocr: {
        provider: "tesseract",
        status: "ok",
        language: "chi_sim+eng",
        lines: [
          { text: "去结算", bbox: { x: 10, y: 20, width: 40, height: 12 }, confidence: 92, wordCount: 1 },
          { text: "首页", bbox: { x: 80, y: 50, width: 20, height: 12 }, confidence: 90, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.ocr.sourceLineCount).toBe(2);
    expect(reconstruction.ocr.textLayerCount).toBe(1);
    expect(reconstruction.layers.map((layer) => layer.text)).toEqual(["首页"]);
    expect(reconstruction.layers[0].metadata.safeBoundsPolicy).toBe("slice_studio_text_safe_bounds.v1");
  });

  it("uses M29 physical evidence for text layer placement when it matches OCR text", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 180,
        height: 90,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 180,
      height: 90,
      imageBuffer,
      slices: [],
      locator: () => locateTextLinesFromM29([
        { text: "去结算", bbox: { x: 40, y: 30, width: 40, height: 16 }, confidence: 96, wordCount: 1 }
      ], {
        schemaName: "M29PhysicalEvidence",
        primitives: [{
          id: "prim_text",
          primitiveType: "symbol_region",
          bbox: { x: 48, y: 31, width: 45, height: 14 }
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "去结算", bbox: { x: 40, y: 30, width: 40, height: 16 }, confidence: 96, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.ocr.bboxProvider).toBe("m29_ocr_hybrid");
    expect(reconstruction.ocr.bboxProviderStatus).toBe("ok");
    expect(reconstruction.layers).toHaveLength(1);
    expect(reconstruction.layers[0].bbox).toEqual({ x: 48, y: 31, width: 45, height: 14 });
    expect(reconstruction.layers[0].originalBBox).toEqual({ x: 48, y: 31, width: 45, height: 14 });
    expect(reconstruction.layers[0].fontSize).toBeGreaterThan(8);
    expect(reconstruction.layers[0].fontSize).toBeLessThan(15);
    expect(reconstruction.layers[0].textRenderBBox.height).toBeLessThanOrEqual(reconstruction.layers[0].safeBBox.height);
    expect(reconstruction.layers[0].metadata.ocrBBox).toEqual({ x: 40, y: 30, width: 40, height: 16 });
    expect(reconstruction.layers[0].metadata.physicalBBox).toEqual({ x: 48, y: 31, width: 45, height: 14 });
    expect(reconstruction.layers[0].metadata.bboxSource).toBe("m29_foreground");
    expect(reconstruction.layers[0].metadata.m29PrimitiveId).toBe("prim_text");
    expect(reconstruction.layers[0].metadata.textOwnershipDecision).toBe("editable_text");
  });

  it("falls back when M29 physical evidence only covers a small fragment of an OCR line", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 750,
        height: 1334,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();
    const ocrBBox = { x: 151, y: 143, width: 157, height: 38 };

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0015",
      width: 750,
      height: 1334,
      imageBuffer,
      slices: [],
      locator: () => locateTextLinesFromM29([
        { text: "退款处理中", bbox: ocrBBox, confidence: 100, wordCount: 1 }
      ], {
        schemaName: "M29PhysicalEvidence",
        primitives: [{
          id: "prim_tiny_refund_status",
          primitiveType: "text_region",
          bbox: { x: 229, y: 160, width: 69, height: 11 },
          source: { kind: "m29", ocrBlockId: "ocr_0001" }
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "退款处理中", bbox: ocrBBox, confidence: 100, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.metadata.bboxSource).toBe("ocr");
    expect(layer.metadata.bboxFallbackReason).toBe("m29_bbox_too_small_for_ocr_line");
    expect(layer.originalBBox).toEqual(ocrBBox);
    expect(layer.textRenderBBox.width).toBeGreaterThan(ocrBBox.width);
  });

  it("keeps mixed CJK detail titles in a no-wrap render box", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 900,
        height: 1600,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();
    const ocrBBox = { x: 57, y: 578, width: 327, height: 37 };
    const physicalBBox = { x: 61, y: 581, width: 323, height: 34 };

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0012",
      width: 900,
      height: 1600,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "日常保洁（3小时深度）", bbox: ocrBBox, confidence: 94, wordCount: 1 },
          bbox: physicalBBox,
          bboxSource: "m29_foreground",
          physicalBBox,
          bboxMatchScore: 0.94,
          m29PrimitiveId: "prim_detail_title"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "日常保洁（3小时深度）", bbox: ocrBBox, confidence: 94, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.bbox.x).toBe(physicalBBox.x);
    expect(layer.bbox.width).toBe(physicalBBox.width);
    expect(layer.textRenderBBox.width).toBeGreaterThan(layer.bbox.width);
    expect(layer.textRenderBBox.height).toBeLessThan(layer.textRenderBBox.width / 6);
  });

  it("keeps price labels in a no-wrap render box while preserving the physical left edge", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 900,
        height: 1600,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();
    const ocrBBox = { x: 496, y: 511, width: 91, height: 45 };
    const physicalBBox = { x: 506, y: 523, width: 73, height: 25 };

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0011",
      width: 900,
      height: 1600,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "￥99起", bbox: ocrBBox, confidence: 99, wordCount: 1 },
          bbox: physicalBBox,
          bboxSource: "m29_foreground",
          physicalBBox,
          bboxMatchScore: 0.66,
          m29PrimitiveId: "prim_price"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "￥99起", bbox: ocrBBox, confidence: 99, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.bbox.x).toBe(physicalBBox.x);
    expect(layer.bbox.width).toBe(physicalBBox.width);
    expect(layer.textRenderBBox.width).toBeGreaterThanOrEqual(layer.bbox.width);
    expect(layer.textRenderBBox.height).toBeLessThan(layer.textRenderBBox.width / 3);
  });

  it("falls back from over-broad shared M29 text boxes before Pencil font sizing", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 1536,
        height: 120,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 1536,
      height: 120,
      imageBuffer,
      slices: [],
      locator: () => locateTextLinesFromM29([
        { text: "Zoom In", bbox: { x: 1224, y: 24, width: 62, height: 18 }, confidence: 97, wordCount: 2 },
        { text: "Zoom Out", bbox: { x: 1302, y: 24, width: 74, height: 18 }, confidence: 93, wordCount: 2 }
      ], {
        schemaName: "M29PhysicalEvidence",
        primitives: [{
          id: "prim_zoom_group",
          primitiveType: "symbol_region",
          bbox: { x: 1220, y: 19, width: 161, height: 31 }
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "Zoom In", bbox: { x: 1224, y: 24, width: 62, height: 18 }, confidence: 97, wordCount: 2 },
          { text: "Zoom Out", bbox: { x: 1302, y: 24, width: 74, height: 18 }, confidence: 93, wordCount: 2 }
        ]
      }
    });

    expect(reconstruction.layers).toHaveLength(2);
    expect(reconstruction.layers.map((layer) => layer.metadata.bboxSource)).toEqual(["ocr", "ocr"]);
    expect(reconstruction.layers.map((layer) => layer.metadata.bboxFallbackReason)).toEqual([
      "m29_bbox_too_broad_for_ocr_line",
      "m29_bbox_too_broad_for_ocr_line"
    ]);
    expect(reconstruction.layers[0].fontSize).toBeLessThan(16);
    expect(reconstruction.layers[1].fontSize).toBeLessThan(16);
  });

  it("falls back to OCR bbox when physical evidence does not match", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 180,
        height: 90,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 180,
      height: 90,
      imageBuffer,
      slices: [],
      locator: () => locateTextLinesFromM29([
        { text: "首页", bbox: { x: 40, y: 30, width: 30, height: 16 }, confidence: 92, wordCount: 1 }
      ], {
        schemaName: "M29PhysicalEvidence",
        primitives: [{
          id: "prim_far",
          primitiveType: "symbol_region",
          bbox: { x: 120, y: 70, width: 20, height: 10 }
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "首页", bbox: { x: 40, y: 30, width: 30, height: 16 }, confidence: 92, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers[0].originalBBox).toEqual({ x: 40, y: 30, width: 30, height: 16 });
    expect(reconstruction.layers[0].metadata.bboxSource).toBe("ocr");
    expect(reconstruction.layers[0].metadata.physicalBBox).toBeUndefined();
  });

  it("uses local foreground refinement for white button text when M29 has no text primitive", async () => {
    const width = 180;
    const height = 90;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    for (let y = 20; y < 64; y += 1) {
      for (let x = 50; x < 140; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = 214;
        rgba[offset + 1] = 47;
        rgba[offset + 2] = 47;
      }
    }
    for (let y = 34; y < 48; y += 1) {
      for (let x = 82; x < 118; x += 1) {
        if ((x - 82) % 9 > 5) continue;
        const offset = (y * width + x) * 4;
        rgba[offset] = 255;
        rgba[offset + 1] = 255;
        rgba[offset + 2] = 255;
      }
    }
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "去结算", bbox: { x: 70, y: 30, width: 58, height: 24 }, confidence: 94, wordCount: 1 },
          bbox: { x: 70, y: 30, width: 58, height: 24 },
          bboxSource: "ocr"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "去结算", bbox: { x: 70, y: 30, width: 58, height: 24 }, confidence: 94, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers[0].metadata.bboxSource).toBe("local_foreground");
    expect(reconstruction.layers[0].bbox).toEqual({ x: 82, y: 34, width: 33, height: 14 });
    expect(reconstruction.layers[0].originalBBox).toEqual({ x: 82, y: 34, width: 33, height: 14 });
    expect(reconstruction.layers[0].fontSize).toBeLessThan(14);
    expect(reconstruction.layers[0].metadata.physicalBBox).toMatchObject({
      x: expect.any(Number),
      width: expect.any(Number)
    });
    expect((reconstruction.layers[0].metadata.physicalBBox as { x: number }).x).toBeGreaterThan(70);
    expect((reconstruction.layers[0].metadata.physicalBBox as { width: number }).width).toBeLessThan(58);
  });

  it("samples white text color from a colored button surface", async () => {
    const width = 120;
    const height = 80;
    const source = await sharp({
      create: {
        width,
        height,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    })
      .composite([
        {
          input: await sharp({
            create: {
              width: 86,
              height: 32,
              channels: 4,
              background: { r: 20, g: 145, b: 84, alpha: 1 }
            }
          }).png().toBuffer(),
          left: 18,
          top: 24
        },
        {
          input: await sharp({
            create: {
              width: 22,
              height: 10,
              channels: 4,
              background: { r: 255, g: 255, b: 255, alpha: 1 }
            }
          }).png().toBuffer(),
          left: 50,
          top: 35
        }
      ])
      .png()
      .toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer: source,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "接单", bbox: { x: 42, y: 29, width: 40, height: 22 }, confidence: 96, wordCount: 1 },
          bbox: { x: 42, y: 29, width: 40, height: 22 },
          bboxSource: "ocr"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "接单", bbox: { x: 42, y: 29, width: 40, height: 22 }, confidence: 96, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers[0].color).toMatch(/^#[fF]/);
    expect(reconstruction.layers[0].color).not.toBe("#149154");
  });

  it("does not treat a tight title foreground box as a control owner surface", async () => {
    const width = 220;
    const height = 120;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    for (let y = 35; y < 63; y += 1) {
      for (let x = 70; x < 166; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = 0;
        rgba[offset + 1] = 0;
        rgba[offset + 2] = 0;
      }
    }
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "订单详情", bbox: { x: 70, y: 35, width: 96, height: 28 }, confidence: 96, wordCount: 1 },
          bbox: { x: 70, y: 35, width: 96, height: 28 },
          bboxSource: "ocr"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "订单详情", bbox: { x: 70, y: 35, width: 96, height: 28 }, confidence: 96, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.metadata.textOwnerSurface).toBeUndefined();
    expect(layer.bbox.x).toBe(70);
    expect(layer.fontSize).toBeGreaterThan(18);
  });

  it("keeps outlined control labels in the OCR replacement region", async () => {
    const width = 500;
    const height = 200;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    const green = [18, 155, 86];
    for (let y = 30; y < 74; y += 1) {
      for (let x = 20; x < 180; x += 1) {
        const edge = y < 32 || y >= 72 || x < 22 || x >= 178;
        if (!edge) continue;
        const offset = (y * width + x) * 4;
        rgba[offset] = green[0];
        rgba[offset + 1] = green[1];
        rgba[offset + 2] = green[2];
      }
    }
    for (let y = 44; y < 58; y += 1) {
      for (let x = 48; x < 62; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = green[0];
        rgba[offset + 1] = green[1];
        rgba[offset + 2] = green[2];
      }
    }
    for (let y = 42; y < 60; y += 1) {
      for (let x = 86; x < 138; x += 10) {
        const offset = (y * width + x) * 4;
        rgba[offset] = green[0];
        rgba[offset + 1] = green[1];
        rgba[offset + 2] = green[2];
        rgba[offset + 4] = green[0];
        rgba[offset + 5] = green[1];
        rgba[offset + 6] = green[2];
      }
    }
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "联系用户", bbox: { x: 44, y: 35, width: 110, height: 34 }, confidence: 96, wordCount: 1 },
          bbox: { x: 44, y: 35, width: 110, height: 34 },
          bboxSource: "ocr"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "联系用户", bbox: { x: 44, y: 35, width: 110, height: 34 }, confidence: 96, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.fontSize).toBe(17);
    expect(layer.bbox.x).toBeGreaterThan(44);
    expect(layer.bbox.width).toBeLessThan(110);
    expect(layer.metadata.textLayoutOwnerSurface).toBeUndefined();
    expect(layer.metadata.textOwnerSurface).toMatchObject({
      reason: "outlined_control_surface"
    });
  });

  it("preserves real icon-to-text distance by excluding confirmed icon slices from text foreground", async () => {
    const width = 220;
    const height = 90;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    const green = [18, 155, 86];
    for (let y = 20; y < 60; y += 1) {
      for (let x = 24; x < 190; x += 1) {
        const edge = y < 22 || y >= 58 || x < 26 || x >= 188;
        if (!edge) continue;
        const offset = (y * width + x) * 4;
        rgba[offset] = green[0];
        rgba[offset + 1] = green[1];
        rgba[offset + 2] = green[2];
      }
    }
    for (let y = 32; y < 52; y += 1) {
      for (let x = 48; x < 68; x += 1) {
        const offset = (y * width + x) * 4;
        rgba[offset] = green[0];
        rgba[offset + 1] = green[1];
        rgba[offset + 2] = green[2];
      }
    }
    for (let y = 34; y < 52; y += 1) {
      for (let x = 86; x < 138; x += 10) {
        const offset = (y * width + x) * 4;
        rgba[offset] = green[0];
        rgba[offset + 1] = green[1];
        rgba[offset + 2] = green[2];
        rgba[offset + 4] = green[0];
        rgba[offset + 5] = green[1];
        rgba[offset + 6] = green[2];
      }
    }
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [{
        id: "slice_icon",
        projectId: "project_1",
        pageId: "page_0001",
        sliceIndex: 1,
        name: "contact icon",
        kind: "image",
        cutMode: "rect",
        bbox: { x: 48, y: 32, width: 20, height: 20 },
        selected: true
      }],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "联系用户", bbox: { x: 44, y: 28, width: 110, height: 32 }, confidence: 96, wordCount: 1 },
          bbox: { x: 44, y: 28, width: 110, height: 32 },
          bboxSource: "ocr"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "联系用户", bbox: { x: 44, y: 28, width: 110, height: 32 }, confidence: 96, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    const iconRight = 68;
    expect(layer.bbox.x).toBeGreaterThan(iconRight);
    expect(layer.safeBBox.x).toBeGreaterThan(iconRight);
    expect(layer.fontSize).toBeLessThan(20);
    expect(layer.metadata.physicalBBox).toMatchObject({
      x: expect.any(Number),
      width: expect.any(Number)
    });
  });

  it("uses the inner filled control surface for nested search-button text", async () => {
    const width = 260;
    const height = 110;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    const green: [number, number, number] = [14, 176, 48];
    // Outer search-field stroke.
    fillRawRect(rgba, width, { x: 8, y: 30, width: 234, height: 3 }, green);
    fillRawRect(rgba, width, { x: 8, y: 74, width: 234, height: 3 }, green);
    fillRawRect(rgba, width, { x: 238, y: 34, width: 3, height: 40 }, green);
    // Inner filled search button.
    fillRawRect(rgba, width, { x: 158, y: 24, width: 86, height: 58 }, green);
    // Approximate white glyph strokes for "搜索".
    fillRawRect(rgba, width, { x: 184, y: 39, width: 9, height: 28 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 202, y: 39, width: 9, height: 28 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 178, y: 49, width: 42, height: 7 }, [255, 255, 255]);
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "搜索", bbox: { x: 174, y: 34, width: 58, height: 38 }, confidence: 99, wordCount: 1 },
          bbox: { x: 150, y: 20, width: 104, height: 66 },
          bboxSource: "m29_foreground",
          physicalBBox: { x: 150, y: 20, width: 104, height: 66 },
          bboxMatchScore: 0.9,
          m29PrimitiveId: "prim_search_button_mixed"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "搜索", bbox: { x: 174, y: 34, width: 58, height: 38 }, confidence: 99, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.metadata.textOwnerSurface).toMatchObject({
      reason: "filled_control_surface",
      fill: "#0eb030"
    });
    expect(layer.metadata.textLayoutOwnerSurface).toMatchObject({
      reason: "filled_control_surface",
      fill: "#0eb030"
    });
    const surface = layer.metadata.textOwnerSurface as { bbox: TestBox };
    expect(surface.bbox.x).toBeGreaterThanOrEqual(150);
    expect(surface.bbox.width).toBeLessThan(130);
    expect(layer.fontSize).toBeLessThan(48);
    expect(layer.textRenderBBox.width).toBeLessThanOrEqual(surface.bbox.width);
    expect(layer.textRenderBBox.height).toBeLessThan(surface.bbox.height);
    expect(layer.textRenderBBox.height).toBeLessThan(layer.safeBBox.height);
    expect(overlapArea(layer.knockoutBBox, surface.bbox)).toBe(layer.knockoutBBox.width * layer.knockoutBBox.height);
  });

  it("uses OCR text bounds when local foreground captures the whole filled button", async () => {
    const width = 220;
    const height = 100;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    const green: [number, number, number] = [16, 179, 47];
    fillRawRect(rgba, width, { x: 46, y: 26, width: 128, height: 48 }, green);
    fillRawRect(rgba, width, { x: 76, y: 40, width: 10, height: 22 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 98, y: 40, width: 10, height: 22 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 120, y: 40, width: 10, height: 22 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 142, y: 40, width: 10, height: 22 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 72, y: 49, width: 84, height: 5 }, [255, 255, 255]);
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const ocrBBox = { x: 72, y: 36, width: 86, height: 32 };
    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "查看详情", bbox: ocrBBox, confidence: 99, wordCount: 1 },
          bbox: { x: 46, y: 26, width: 128, height: 48 },
          bboxSource: "local_foreground",
          physicalBBox: { x: 46, y: 26, width: 128, height: 48 },
          bboxMatchScore: 1
        }]
      }),
      textStyleResolver: async ({ items }) => {
        expect(items).toHaveLength(1);
        expect(items[0].bbox).toEqual(ocrBBox);
        expect(items[0].ownerSurface).toMatchObject({
          fill: "#10b32f",
          reason: "filled_control_surface"
        });
        return [{
          fontSize: 25,
          fontWeight: "500",
          fontFamily: "PingFang SC",
          color: "#ffffff",
          lineHeight: 25,
          textAlign: "center",
          measured: { width: 100, height: 27 },
          source: "psdlike"
        }];
      },
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "查看详情", bbox: ocrBBox, confidence: 99, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    const surface = layer.metadata.textOwnerSurface as { bbox: TestBox };
    expect(layer.originalBBox).toEqual(ocrBBox);
    expect(layer.metadata.textLayoutOwnerSurface).toMatchObject({
      reason: "filled_control_surface"
    });
    expect(String(layer.metadata.bboxFallbackReason)).toContain("local_foreground_matched_owner_surface");
    expect(layer.textRenderBBox.y).toBeGreaterThanOrEqual(surface.bbox.y);
    expect(layer.textRenderBBox.y + layer.textRenderBBox.height).toBeLessThanOrEqual(surface.bbox.y + surface.bbox.height);
  });

  it("uses measured psdlike text style when the resolver returns one", async () => {
    const width = 260;
    const height = 110;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    const green: [number, number, number] = [14, 176, 48];
    fillRawRect(rgba, width, { x: 8, y: 30, width: 234, height: 3 }, green);
    fillRawRect(rgba, width, { x: 8, y: 74, width: 234, height: 3 }, green);
    fillRawRect(rgba, width, { x: 238, y: 34, width: 3, height: 40 }, green);
    fillRawRect(rgba, width, { x: 158, y: 24, width: 86, height: 58 }, green);
    fillRawRect(rgba, width, { x: 184, y: 39, width: 9, height: 28 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 202, y: 39, width: 9, height: 28 }, [255, 255, 255]);
    fillRawRect(rgba, width, { x: 178, y: 49, width: 42, height: 7 }, [255, 255, 255]);
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "搜索", bbox: { x: 174, y: 34, width: 58, height: 38 }, confidence: 99, wordCount: 1 },
          bbox: { x: 150, y: 20, width: 104, height: 66 },
          bboxSource: "m29_foreground",
          physicalBBox: { x: 150, y: 20, width: 104, height: 66 },
          bboxMatchScore: 0.9,
          m29PrimitiveId: "prim_search_button_mixed"
        }]
      }),
      textStyleResolver: async ({ items }) => {
        expect(items).toHaveLength(1);
        expect(items[0].bbox).toEqual({ x: 174, y: 34, width: 58, height: 38 });
        expect(items[0].ownerSurface).toMatchObject({
          fill: "#0eb030",
          reason: "filled_control_surface"
        });
        return [{
          fontSize: 31,
          fontWeight: "500",
          fontFamily: "PingFang SC",
          color: "#fcfdfc",
          lineHeight: 31,
          textAlign: "center",
          measured: { width: 62, height: 34 },
          source: "psdlike"
        }];
      },
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "搜索", bbox: { x: 174, y: 34, width: 58, height: 38 }, confidence: 99, wordCount: 1 }
        ]
      }
    });

    const layer = reconstruction.layers[0];
    expect(layer.fontSize).toBe(31);
    expect(layer.fontWeight).toBe("500");
    expect(layer.color).toBe("#fcfdfc");
    expect(layer.metadata.textStyleSource).toBe("psdlike");
    expect(layer.metadata.textStyleMeasured).toEqual({ width: 62, height: 34 });
  });

  it("falls back to local font estimates when measured text style is unavailable", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 180,
        height: 90,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 180,
      height: 90,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "首页", bbox: { x: 40, y: 30, width: 30, height: 16 }, confidence: 92, wordCount: 1 },
          bbox: { x: 40, y: 30, width: 30, height: 16 },
          bboxSource: "ocr"
        }]
      }),
      textStyleResolver: async () => null,
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "首页", bbox: { x: 40, y: 30, width: 30, height: 16 }, confidence: 92, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers).toHaveLength(1);
    expect(reconstruction.layers[0].fontSize).toBeGreaterThan(8);
    expect(reconstruction.layers[0].metadata.textStyleSource).toBe("fallback");
  });

  it.each([
    {
      name: "left icon",
      icon: { x: 28, y: 32, width: 20, height: 20 },
      textPixels: { x: 80, y: 36, width: 52, height: 12 },
      ocrBBox: { x: 24, y: 24, width: 128, height: 38 }
    },
    {
      name: "right icon",
      icon: { x: 120, y: 32, width: 20, height: 20 },
      textPixels: { x: 38, y: 36, width: 52, height: 12 },
      ocrBBox: { x: 34, y: 24, width: 128, height: 38 }
    },
    {
      name: "top icon",
      icon: { x: 76, y: 18, width: 20, height: 20 },
      textPixels: { x: 58, y: 68, width: 56, height: 12 },
      ocrBBox: { x: 52, y: 14, width: 80, height: 76 }
    },
    {
      name: "bottom icon",
      icon: { x: 76, y: 76, width: 20, height: 20 },
      textPixels: { x: 58, y: 24, width: 56, height: 12 },
      ocrBBox: { x: 52, y: 18, width: 80, height: 82 }
    }
  ])("refines OCR text foreground around a confirmed $name slice", async ({ icon, textPixels, ocrBBox }) => {
    const width = 180;
    const height = 120;
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    fillRawRect(rgba, width, icon, [18, 155, 86]);
    fillRawRect(rgba, width, textPixels, [12, 12, 12]);
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [{
        id: "slice_icon",
        projectId: "project_1",
        pageId: "page_0001",
        sliceIndex: 1,
        name: "icon",
        kind: "image",
        cutMode: "rect",
        bbox: icon,
        selected: true
      }],
      locator: () => ({
        status: "skipped",
        source: "ocr",
        reason: "test_ocr_only",
        lines: [{
          line: { text: "联系用户", bbox: ocrBBox, confidence: 96, wordCount: 1 },
          bbox: ocrBBox,
          bboxSource: "ocr",
          bboxFallbackReason: "test_ocr_only"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "联系用户", bbox: ocrBBox, confidence: 96, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers).toHaveLength(1);
    const layer = reconstruction.layers[0];
    expect(layer.metadata.bboxSource).toBe("local_foreground");
    expect(overlapArea(layer.bbox, icon)).toBe(0);
    expect(overlapArea(layer.safeBBox, icon)).toBe(0);
    expect(Math.abs(layer.bbox.x - textPixels.x)).toBeLessThanOrEqual(2);
    expect(Math.abs(layer.bbox.y - textPixels.y)).toBeLessThanOrEqual(2);
  });

  it("refines an over-broad M29 foreground box when it intersects a confirmed slice", async () => {
    const width = 180;
    const height = 90;
    const icon = { x: 24, y: 30, width: 20, height: 20 };
    const textPixels = { x: 76, y: 34, width: 58, height: 12 };
    const ocrBBox = { x: 20, y: 24, width: 132, height: 36 };
    const rgba = Buffer.alloc(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
      const offset = index * 4;
      rgba[offset] = 255;
      rgba[offset + 1] = 255;
      rgba[offset + 2] = 255;
      rgba[offset + 3] = 255;
    }
    fillRawRect(rgba, width, icon, [18, 155, 86]);
    fillRawRect(rgba, width, textPixels, [12, 12, 12]);
    const imageBuffer = await sharp(rgba, { raw: { width, height, channels: 4 } }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width,
      height,
      imageBuffer,
      slices: [{
        id: "slice_icon",
        projectId: "project_1",
        pageId: "page_0001",
        sliceIndex: 1,
        name: "icon",
        kind: "image",
        cutMode: "rect",
        bbox: icon,
        selected: true
      }],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [{
          line: { text: "联系用户", bbox: ocrBBox, confidence: 96, wordCount: 1 },
          bbox: ocrBBox,
          bboxSource: "m29_foreground",
          physicalBBox: ocrBBox,
          bboxMatchScore: 0.91,
          m29PrimitiveId: "prim_mixed_icon_text"
        }]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "联系用户", bbox: ocrBBox, confidence: 96, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers).toHaveLength(1);
    const layer = reconstruction.layers[0];
    expect(layer.metadata.bboxSource).toBe("local_foreground");
    expect(overlapArea(layer.bbox, icon)).toBe(0);
    expect(layer.bbox.x).toBeGreaterThan(icon.x + icon.width);
    expect(layer.fontSize).toBeLessThan(18);
  });

  it("exports Pencil-compatible text style without oversized bbox-height font sizing", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 220,
        height: 140,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 220,
      height: 140,
      imageBuffer,
      slices: [],
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "点单", bbox: { x: 50, y: 20, width: 128, height: 73 }, confidence: 96, wordCount: 1 },
          { text: "茶隐", bbox: { x: 20, y: 20, width: 28, height: 51 }, confidence: 96, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.layers.map((layer) => layer.text)).toEqual(["点单"]);
    expect(reconstruction.layers[0].fontFamily).toBe("PingFang SC");
    expect(reconstruction.layers[0].fontWeight).toBe("600");
    expect(reconstruction.layers[0].fontSize).toBeLessThan(56);
    expect(reconstruction.layers[0].bbox.x).toBe(50);
  });

  it("preserves generated asset marker labels as raster instead of editable Pencil text", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 240,
        height: 160,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 240,
      height: 160,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: [
          {
            line: { text: "img-11", bbox: { x: 20, y: 20, width: 34, height: 12 }, confidence: 98, wordCount: 1 },
            bbox: { x: 20, y: 20, width: 34, height: 12 },
            bboxSource: "ocr"
          },
          {
            line: { text: "Checkout", bbox: { x: 80, y: 60, width: 70, height: 16 }, confidence: 97, wordCount: 1 },
            bbox: { x: 80, y: 60, width: 70, height: 16 },
            bboxSource: "ocr"
          }
        ]
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "img-11", bbox: { x: 20, y: 20, width: 34, height: 12 }, confidence: 98, wordCount: 1 },
          { text: "Checkout", bbox: { x: 80, y: 60, width: 70, height: 16 }, confidence: 97, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.ocr.textLayerCount).toBe(1);
    expect(reconstruction.ocr.rasterPreservedTextCount).toBe(1);
    expect(reconstruction.layers.map((layer) => layer.text)).toEqual(["Checkout"]);
  });

  it("keeps high-confidence dense UI tiny text editable when OCR and M29 agree", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 320,
        height: 180,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();
    const tinyLine = { text: "DRESSES", bbox: { x: 40, y: 20, width: 52, height: 17 }, confidence: 100, wordCount: 1 };

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 320,
      height: 180,
      imageBuffer,
      slices: [],
      locator: () => ({
        status: "ok",
        source: "m29_ocr_hybrid",
        lines: Array.from({ length: 130 }, (_, index) => ({
          line: index === 0
            ? tinyLine
            : { text: `Label ${index}`, bbox: { x: 40, y: 24 + index, width: 56, height: 16 }, confidence: 96, wordCount: 1 },
          bbox: index === 0
            ? { x: 43, y: 24, width: 45, height: 9 }
            : { x: 40, y: 24 + index, width: 56, height: 16 },
          bboxSource: index === 0 ? "m29_foreground" : "ocr",
          bboxMatchScore: index === 0 ? 0.66 : undefined
        }))
      }),
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: Array.from({ length: 130 }, (_, index) => index === 0
          ? tinyLine
          : { text: `Label ${index}`, bbox: { x: 40, y: 24 + index, width: 56, height: 16 }, confidence: 96, wordCount: 1 })
      }
    });

    expect(reconstruction.layers[0].text).toBe("DRESSES");
    expect(reconstruction.layers[0].bbox).toEqual({ x: 43, y: 24, width: 45, height: 9 });
    expect(reconstruction.layers[0].metadata.bboxSource).toBe("m29_foreground");
    expect(reconstruction.layers[0].metadata.physicalBBox).toEqual({ x: 43, y: 24, width: 45, height: 9 });
    expect(reconstruction.ocr.rasterPreservedTextCount).toBe(0);
  });

  it("rejects oversized OCR noise lines before creating Pencil text layers", async () => {
    const imageBuffer = await sharp({
      create: {
        width: 941,
        height: 200,
        channels: 4,
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      }
    }).png().toBuffer();

    expect(textGeometryLooksEditable(
      { text: "@ a a @", bbox: { x: 20, y: 20, width: 900, height: 80 }, confidence: 95, wordCount: 4 },
      941
    )).toBe(false);

    const reconstruction = await reconstructTextLayers({
      pageId: "page_0001",
      width: 941,
      height: 200,
      imageBuffer,
      slices: [],
      ocr: {
        provider: "baidu_ppocrv5",
        status: "ok",
        language: "zh+en",
        model: "PP-OCRv5",
        lines: [
          { text: "@ a a @", bbox: { x: 20, y: 20, width: 900, height: 80 }, confidence: 95, wordCount: 4 },
          { text: "首页", bbox: { x: 80, y: 150, width: 36, height: 18 }, confidence: 92, wordCount: 1 }
        ]
      }
    });

    expect(reconstruction.ocr.sourceLineCount).toBe(2);
    expect(reconstruction.layers.map((layer) => layer.text)).toEqual(["首页"]);
  });
});
