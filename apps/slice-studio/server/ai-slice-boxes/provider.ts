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

  const payload: Record<string, unknown> = {
    model: aiSliceModel,
    input: [
      {
        role: "user",
        content: [
          { type: "input_text", text: buildPrompt(tile) },
          { type: "input_image", image_url: tile.dataUrl }
        ]
      }
    ],
    reasoning: { effort: aiSliceReasoningEffort },
    store: aiSliceStore
  };

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

function buildPrompt(tile: PreparedTile): string {
  return [
    "You are an asset slicing assistant for a UI screenshot tile.",
    "Return ONLY strict JSON. Do not use markdown.",
    "Find rectangular image assets that a designer would crop as raster assets.",
    "Include product photos, thumbnails, complex icons, logos, illustrations, badges, decorative images, and small visual assets that need raster fidelity.",
    "Exclude plain text, button text, button backgrounds, search bars, ordinary cards, dividers, full-page backgrounds, status bars, bottom navigation labels, and generic UI containers.",
    "Coordinates must be in the provided tile image pixel space, not the original full page.",
    "Use tight rectangles around the visible asset. Do not include large unrelated card/container padding.",
    "If uncertain, omit the box.",
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
