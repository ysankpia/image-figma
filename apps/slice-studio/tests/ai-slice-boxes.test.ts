import sharp from "sharp";
import { describe, expect, it } from "vitest";
import { mergeAiBoxesIntoSlices } from "../shared/ai-slices";
import { filterAiBoxes, parseAiBoxResponse } from "../server/ai-slice-boxes/boxes";
import {
  buildChatCompletionsPayload,
  buildOverviewPrompt,
  buildPrompt,
  buildResponsesPayload,
  extractChatCompletionsText,
  extractResponsesText,
  formatProviderError,
  requestUrl
} from "../server/ai-slice-boxes/provider";
import { generateTiles, mapTileBoxToPage, prepareTileImage } from "../server/ai-slice-boxes/tiles";
import type { PageRecord, SliceRecord } from "../shared/types";

describe("AI slice boxes", () => {
  it("generates six overlapping portrait tiles", () => {
    const tiles = generateTiles({ width: 400, height: 1200 }, 6, 60);

    expect(tiles).toHaveLength(6);
    expect(tiles[0]?.bbox).toEqual({ x: 0, y: 0, width: 400, height: 230 });
    expect(tiles[1]?.bbox.y).toBeLessThan(200);
    expect(tiles[5]?.bbox.y + tiles[5]!.bbox.height).toBe(1200);
  });

  it("generates six wide tiles in a 3x2 grid", () => {
    const tiles = generateTiles({ width: 1200, height: 400 }, 6, 60);

    expect(tiles).toHaveLength(6);
    expect(tiles[0]?.bbox.width).toBeGreaterThan(400);
    expect(tiles[1]?.bbox.x).toBeLessThan(400);
    expect(tiles[3]?.bbox.y).toBeLessThan(200);
  });

  it("maps tile-local boxes back to source coordinates", () => {
    const mapped = mapTileBoxToPage(
      { x: 10, y: 20, width: 50, height: 60 },
      { id: "tile_0001", bbox: { x: 100, y: 200, width: 400, height: 800 }, sentWidth: 200, sentHeight: 400, dataUrl: "data:image/jpeg;base64," }
    );

    expect(mapped).toEqual({ x: 120, y: 240, width: 100, height: 120 });
  });

  it("compresses tile images to a bounded JPEG data URL", async () => {
    const image = await sharp({
      create: {
        width: 100,
        height: 80,
        channels: 4,
        background: "#ffffff"
      }
    }).png().toBuffer();

    const tile = await prepareTileImage({
      imageBuffer: image,
      tile: { id: "tile_0001", bbox: { x: 0, y: 0, width: 100, height: 80 } },
      maxSide: 50,
      jpegQuality: 70
    });

    expect(tile.sentWidth).toBe(50);
    expect(tile.sentHeight).toBe(40);
    expect(tile.dataUrl.startsWith("data:image/jpeg;base64,")).toBe(true);
  });

  it("parses plain and fenced JSON box responses", () => {
    expect(parseAiBoxResponse('{"boxes":[{"x":1,"y":2,"width":30,"height":40,"label":"logo"}]}').boxes[0]?.name).toBe("logo");
    expect(parseAiBoxResponse("```json\n{\"boxes\":[]}\n```").boxes).toEqual([]);
    expect(parseAiBoxResponse("not json").error).toMatch(/^json_parse_error/);
  });

  it("uses the inclusive-icons prompt as the default AI slice strategy", () => {
    const tile = { id: "tile_0001", bbox: { x: 0, y: 0, width: 320, height: 640 }, sentWidth: 320, sentHeight: 640, dataUrl: "data:image/jpeg;base64," };
    const prompt = buildPrompt(tile);

    expect(prompt).toContain("stylized UI icons");
    expect(prompt).toContain("navigation icons");
    expect(prompt).toContain("distinct action button icons");
    expect(prompt).toContain("Plain text");
    expect(prompt).toContain("button backgrounds");
    expect(prompt).toContain("generic containers");
  });

  it("keeps overview review focused on merged medium and large assets", () => {
    const tile = { id: "overview_0001", bbox: { x: 0, y: 0, width: 941, height: 1672 }, sentWidth: 720, sentHeight: 1280, dataUrl: "data:image/jpeg;base64," };
    const prompt = buildOverviewPrompt(tile);

    expect(prompt).toContain("large artwork");
    expect(prompt).toContain("medium thumbnails");
    expect(prompt).toContain("stylized decorative graphics");
    expect(prompt).toContain("Small standalone icons are still out of scope for overview");
    expect(prompt).toContain("ordinary containers");
  });

  it("builds OpenAI-compatible responses and chat-completions image payloads", () => {
    const tile = { id: "tile_0001", bbox: { x: 0, y: 0, width: 320, height: 640 }, sentWidth: 320, sentHeight: 640, dataUrl: "data:image/jpeg;base64,abc123" };

    const responses = buildResponsesPayload("detect assets", tile);
    expect(JSON.stringify(responses)).toContain("input_image");
    expect(JSON.stringify(responses)).toContain(tile.dataUrl);

    const chat = buildChatCompletionsPayload("detect assets", tile);
    expect(JSON.stringify(chat)).toContain("image_url");
    expect(JSON.stringify(chat)).toContain(tile.dataUrl);
    expect(chat).toMatchObject({ temperature: 0 });
  });

  it("extracts text from responses and chat-completions provider payloads", () => {
    expect(extractResponsesText(JSON.stringify({ output_text: "{\"boxes\":[]}" }))).toBe("{\"boxes\":[]}");
    expect(extractResponsesText(JSON.stringify({
      output: [{ content: [{ type: "output_text", text: "{\"boxes\":[{\"x\":1}]}" }] }]
    }))).toBe("{\"boxes\":[{\"x\":1}]}");

    expect(extractChatCompletionsText(JSON.stringify({
      choices: [{ message: { content: "{\"boxes\":[]}" } }]
    }))).toBe("{\"boxes\":[]}");
    expect(extractChatCompletionsText(JSON.stringify({
      choices: [{ message: { content: [{ type: "text", text: "{\"boxes\":[{\"x\":2}]}" }] } }]
    }))).toBe("{\"boxes\":[{\"x\":2}]}");
  });

  it("recovers raw provider text when provider payload is not JSON", () => {
    expect(extractResponsesText("{\"boxes\":[]}")).toBe("{\"boxes\":[]}");
    expect(extractChatCompletionsText("{\"boxes\":[]}")).toBe("{\"boxes\":[]}");
  });

  it("normalizes OpenAI-compatible request URLs", () => {
    expect(requestUrl("https://api.openai.com", "/responses")).toBe("https://api.openai.com/v1/responses");
    expect(requestUrl("https://api.openai.com/v1", "/responses")).toBe("https://api.openai.com/v1/responses");
    expect(requestUrl("https://openrouter.ai/api/v1", "/chat/completions")).toBe("https://openrouter.ai/api/v1/chat/completions");
    expect(requestUrl("https://example.com/v1/chat/completions", "/chat/completions")).toBe("https://example.com/v1/chat/completions");
  });

  it("redacts provider diagnostics before surfacing errors", () => {
    const message = formatProviderError(502, JSON.stringify({
      error: "bad request",
      authorization: "Bearer secret-token",
      api_key: "secret-key",
      image: "data:image/jpeg;base64,abcdefghijklmnopqrstuvwxyz"
    }));

    expect(message).toContain("provider returned 502");
    expect(message).toContain("[REDACTED]");
    expect(message).toContain("[REDACTED_IMAGE]");
    expect(message).not.toContain("secret-token");
    expect(message).not.toContain("secret-key");
    expect(message).not.toContain("abcdefghijklmnopqrstuvwxyz");
  });

  it("filters invalid, huge, duplicate, and existing-overlap boxes", () => {
    const existing = [slice("manual", { x: 10, y: 10, width: 100, height: 100 })];
    const result = filterAiBoxes({
      bounds: { width: 500, height: 500 },
      existingSlices: existing,
      maxBoxes: 10,
      boxes: [
        { bbox: { x: 12, y: 12, width: 95, height: 95 }, sourceTileId: "t1" },
        { bbox: { x: 0, y: 0, width: 490, height: 490 }, sourceTileId: "t1" },
        { bbox: { x: 200, y: 200, width: 6, height: 6 }, sourceTileId: "t1" },
        { bbox: { x: 220, y: 220, width: 60, height: 60 }, sourceTileId: "t1" },
        { bbox: { x: 222, y: 222, width: 58, height: 58 }, sourceTileId: "t2" }
      ]
    });

    expect(result.boxes.map((box) => box.bbox)).toEqual([{ x: 220, y: 220, width: 60, height: 60 }]);
    expect(result.rejectedCount).toBe(4);
  });

  it("prefers usable overview boxes over contained tile fragments", () => {
    const result = filterAiBoxes({
      bounds: { width: 1000, height: 1600 },
      existingSlices: [],
      maxBoxes: 10,
      boxes: [
        { bbox: { x: 160, y: 300, width: 650, height: 620 }, sourceTileId: "overview_0001", sourceKind: "overview" },
        { bbox: { x: 170, y: 330, width: 640, height: 260 }, sourceTileId: "tile_0002", sourceKind: "tile" },
        { bbox: { x: 170, y: 525, width: 600, height: 340 }, sourceTileId: "tile_0003", sourceKind: "tile" },
        { bbox: { x: 40, y: 1200, width: 42, height: 42 }, sourceTileId: "tile_0005", sourceKind: "tile" }
      ]
    });

    expect(result.boxes.map((box) => box.bbox)).toEqual([
      { x: 160, y: 300, width: 650, height: 620 },
      { x: 40, y: 1200, width: 42, height: 42 }
    ]);
    expect(result.rejectedCount).toBe(2);
  });

  it("does not let unusable overview boxes suppress valid tile boxes", () => {
    const result = filterAiBoxes({
      bounds: { width: 1000, height: 1600 },
      existingSlices: [],
      maxBoxes: 10,
      boxes: [
        { bbox: { x: 0, y: 0, width: 1000, height: 1500 }, sourceTileId: "overview_0001", sourceKind: "overview" },
        { bbox: { x: 170, y: 330, width: 640, height: 260 }, sourceTileId: "tile_0002", sourceKind: "tile" }
      ]
    });

    expect(result.boxes.map((box) => box.bbox)).toEqual([
      { x: 170, y: 330, width: 640, height: 260 }
    ]);
    expect(result.rejectedCount).toBe(1);
  });

  it("merges AI boxes as ordinary rect slices without deleting existing slices", () => {
    const page = pageRecord();
    const result = mergeAiBoxesIntoSlices({
      projectId: "project_1",
      page: {
        ...page,
        slices: [slice("existing", { x: 10, y: 10, width: 100, height: 100 })]
      },
      boxes: [
        { bbox: { x: 12, y: 12, width: 96, height: 96 }, sourceTileId: "tile_0001" },
        { bbox: { x: 180, y: 180, width: 70, height: 70 }, sourceTileId: "tile_0002" }
      ],
      idSeed: "seed"
    });

    expect(result.addedCount).toBe(1);
    expect(result.skippedCount).toBe(1);
    expect(result.slices).toHaveLength(2);
    expect(result.slices[1]).toMatchObject({
      id: "page_0001__slice_ai_seed_001",
      cutMode: "rect",
      bbox: { x: 180, y: 180, width: 70, height: 70 }
    });
  });
});

function pageRecord(): PageRecord {
  return {
    id: "page_0001",
    projectId: "project_1",
    pageIndex: 1,
    originalName: "P1.png",
    displayName: "P1",
    width: 500,
    height: 500,
    sourceUrl: "/source.png"
  };
}

function slice(id: string, bbox: SliceRecord["bbox"]): SliceRecord {
  return {
    id,
    projectId: "project_1",
    pageId: "page_0001",
    sliceIndex: 1,
    name: "manual",
    kind: "image",
    cutMode: "rect",
    bbox,
    selected: true
  };
}
