import {
  aiSliceApiKey,
  aiSliceBaseUrl,
  aiSliceModel,
  aiSliceReasoningEffort,
  aiSliceStore,
  aiSliceTimeoutSeconds,
  aiSliceTransportRetries,
  aiSliceWireApi
} from "../config";
import { httpError } from "../errors";
import type { PreparedTile } from "./types";

export async function callAiSliceProvider(tile: PreparedTile): Promise<string> {
  if (!aiSliceApiKey) throw httpError(400, "AI slice API key is not configured");
  if (aiSliceWireApi !== "responses") throw httpError(400, `Unsupported AI slice wire API: ${aiSliceWireApi}`);

  return callResponses(buildPayload(buildPrompt(tile), tile));
}

export async function callAiSliceOverviewProvider(tile: PreparedTile): Promise<string> {
  if (!aiSliceApiKey) throw httpError(400, "AI slice API key is not configured");
  if (aiSliceWireApi !== "responses") throw httpError(400, `Unsupported AI slice wire API: ${aiSliceWireApi}`);

  return callResponses(buildPayload(buildOverviewPrompt(tile), tile));
}

function buildPayload(prompt: string, tile: PreparedTile): Record<string, unknown> {
  return {
    model: aiSliceModel,
    input: [
      {
        role: "user",
        content: [
          { type: "input_text", text: prompt },
          { type: "input_image", image_url: tile.dataUrl }
        ]
      }
    ],
    reasoning: { effort: aiSliceReasoningEffort },
    store: aiSliceStore
  };
}

async function callResponses(payload: Record<string, unknown>): Promise<string> {
  for (let attempt = 0; attempt < Math.max(1, aiSliceTransportRetries); attempt += 1) {
    try {
      const response = await fetch(requestUrl(aiSliceBaseUrl, "/responses"), {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "accept": "application/json",
          "authorization": `Bearer ${aiSliceApiKey}`
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(Math.max(1, aiSliceTimeoutSeconds) * 1000)
      });
      const body = await response.text();
      if (!response.ok) throw new Error(`provider returned ${response.status}: ${trimForError(body)}`);
      const text = extractResponseText(body);
      if (!text.trim()) throw new Error("provider returned no text");
      return text;
    } catch (error) {
      if (attempt + 1 >= Math.max(1, aiSliceTransportRetries)) {
        throw httpError(502, error instanceof Error ? error.message : "AI slice provider failed");
      }
      await new Promise((resolve) => setTimeout(resolve, 750 * (attempt + 1)));
    }
  }

  throw httpError(502, "AI slice provider failed");
}

export function buildPrompt(tile: PreparedTile): string {
  return [
    "You are an asset slicing assistant for a UI screenshot tile.",
    "Return ONLY strict JSON. Do not use markdown wrappers.",
    "",
    "TASK:",
    "Identify visual assets that should be exported as raster images. Be active in capturing distinct icons, including stylized bottom navigation icons and feature icons, but strict about avoiding structural UI containers.",
    "",
    "DECISION GUIDELINE:",
    "- INCLUDE: Product photos, thumbnails, avatars, illustrations, brand logos, stylized UI icons, decorative graphics, navigation icons, and distinct action button icons.",
    "- EXCLUDE: Plain text, button backgrounds, search bar fields, ordinary cards, generic containers, background grids, status bars, dividers, or plain button rectangles.",
    "- Do not slice a plain text label together with its icon. Crop ONLY the visual icon itself, with a tight box.",
    "- Avoid slicing micro-utility controls like simple chevrons, close symbols, or simple checkboxes unless they carry unique brand stylization.",
    "",
    "COORDINATES & SIZE:",
    "Coordinates must be in the provided tile image pixel space, not the original full page.",
    "Use tight, minimal bounding boxes around the visible asset. Do not include empty padding, labels, or container cards.",
    "",
    "CONFIDENCE DEFINITION:",
    "The confidence score must reflect how important it is to export this as an independent raster asset, not just whether a graphic is visible.",
    "",
    "Return shape: {\"boxes\":[{\"x\":0,\"y\":0,\"width\":100,\"height\":100,\"label\":\"asset\",\"confidence\":0.8,\"reason\":\"short reason\"}]}",
    `Tile id: ${tile.id}`,
    `Tile sent size: ${tile.sentWidth}x${tile.sentHeight}`,
    `Tile source bbox in full page: x=${tile.bbox.x}, y=${tile.bbox.y}, width=${tile.bbox.width}, height=${tile.bbox.height}`
  ].join("\n");
}

export function buildOverviewPrompt(tile: PreparedTile): string {
  return [
    "You are reviewing a compressed full-page UI screenshot to identify large and medium visual assets that span across multiple tiles.",
    "Return ONLY strict JSON. Do not use markdown wrappers.",
    "",
    "TASK:",
    "Find large or medium visual assets that should be captured as one single, continuous rectangular raster crop.",
    "",
    "CRITICAL CONSTRAINTS:",
    "1. Return large or medium visual assets, including large artwork, product photos, album covers, medium thumbnails, rich visual panels, and stylized decorative graphics.",
    "2. Do not return plain text, button backgrounds, ordinary containers, or status/navigation bars.",
    "3. Small standalone icons are still out of scope for overview unless they are part of a medium visual asset.",
    "4. If an asset is a full-page background inseparable from text/content overlaying it, omit it to avoid exporting the whole screen.",
    "",
    "COORDINATES & SIZE:",
    "Coordinates must be in the provided compressed full-page image pixel space.",
    "Use one single, tight rectangle covering the entire unified asset.",
    "",
    "CONFIDENCE DEFINITION:",
    "The confidence score reflects how critical it is to treat this as a single merged visual asset.",
    "",
    "Return shape: {\"boxes\":[{\"x\":0,\"y\":0,\"width\":100,\"height\":100,\"label\":\"asset\",\"confidence\":0.8,\"reason\":\"short reason\"}]}",
    `Tile id: ${tile.id}`,
    `Tile sent size: ${tile.sentWidth}x${tile.sentHeight}`,
    `Tile source bbox in full page: x=${tile.bbox.x}, y=${tile.bbox.y}, width=${tile.bbox.width}, height=${tile.bbox.height}`
  ].join("\n");
}

function requestUrl(baseURL: string, apiPath: string): string {
  const base = baseURL.trim().replace(/\/+$/, "");
  const path = `/${apiPath.replace(/^\/+/, "")}`;
  if (base.endsWith("/v1")) return `${base}${path}`;
  if (base.endsWith(path) || base.includes("/v1/")) return base;
  return `${base}/v1${path}`;
}

function extractResponseText(raw: string): string {
  let root: unknown;
  try {
    root = JSON.parse(raw);
  } catch {
    return raw;
  }
  if (root && typeof root === "object" && typeof (root as { output_text?: unknown }).output_text === "string") {
    return (root as { output_text: string }).output_text;
  }
  const texts: string[] = [];
  collectText(root, texts);
  return texts.join("\n");
}

function collectText(value: unknown, texts: string[]): void {
  if (Array.isArray(value)) {
    for (const item of value) collectText(item, texts);
    return;
  }
  if (!value || typeof value !== "object") return;
  const object = value as Record<string, unknown>;
  if ((object.type === "output_text" || object.type === "text") && typeof object.text === "string") {
    texts.push(object.text);
  }
  for (const child of Object.values(object)) collectText(child, texts);
}

function trimForError(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, 500);
}
