import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { buildPencilManifest, createRemainderPng, frameLayoutXPositions, preparePencilSliceImage } from "../server/pencil-package";
import { parseBaiduPpocrv5Rows, parseTesseractTsv } from "../server/text-ocr";
import { reconstructTextLayers, remainingRatio, textGeometryLooksEditable } from "../server/text-reconstruction";
import { locateTextLinesFromM29 } from "../server/m29-text-locator";
import type { ProjectDetail } from "../shared/types";

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
          originalBBox: { x: 12, y: 22, width: 46, height: 12 },
          fontSize: 12,
          fontFamily: "PingFang SC",
          fontWeight: "400",
          color: "#111111",
          confidence: 88
        }]
      }
    ]]));

    expect(manifest.pages[0].ocr.status).toBe("ok");
    expect(manifest.pages[0].ocr.sourceLineCount).toBe(2);
    expect(manifest.pages[0].textLayerCount).toBe(1);
    expect(manifest.pages[0].textLayers[0].text).toBe("去结算");
  });

  it("lays out variable-width Pencil frames without overlap", () => {
    expect(frameLayoutXPositions([
      { width: 941 },
      { width: 1092 },
      { width: 853 }
    ])).toEqual([0, 1101, 2353]);
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
    expect(reconstruction.layers[0].originalBBox).toEqual({ x: 48, y: 31, width: 45, height: 14 });
    expect(reconstruction.layers[0].fontSize).toBeGreaterThan(10);
    expect(reconstruction.layers[0].fontSize).toBeLessThan(18);
    expect(reconstruction.layers[0].metadata.ocrBBox).toEqual({ x: 40, y: 30, width: 40, height: 16 });
    expect(reconstruction.layers[0].metadata.physicalBBox).toEqual({ x: 48, y: 31, width: 45, height: 14 });
    expect(reconstruction.layers[0].metadata.bboxSource).toBe("m29_foreground");
    expect(reconstruction.layers[0].metadata.m29PrimitiveId).toBe("prim_text");
    expect(reconstruction.layers[0].metadata.textOwnershipDecision).toBe("editable_text");
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
    expect(reconstruction.layers[0].originalBBox.x).toBeGreaterThan(70);
    expect(reconstruction.layers[0].originalBBox.width).toBeLessThan(58);
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
