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

  return callProvider(buildPrompt(tile), tile);
}

export async function callAiSliceOverviewProvider(tile: PreparedTile): Promise<string> {
  if (!aiSliceApiKey) throw httpError(400, "AI slice API key is not configured");

  return callProvider(buildOverviewPrompt(tile), tile);
}

async function callProvider(prompt: string, tile: PreparedTile): Promise<string> {
  if (aiSliceWireApi === "responses") return callOpenAiCompatible(buildResponsesPayload(prompt, tile), "/responses", extractResponsesText);
  if (aiSliceWireApi === "chat_completions") return callOpenAiCompatible(buildChatCompletionsPayload(prompt, tile), "/chat/completions", extractChatCompletionsText);
  throw httpError(400, `Unsupported AI slice wire API: ${aiSliceWireApi satisfies never}`);
}

export function buildResponsesPayload(prompt: string, tile: PreparedTile): Record<string, unknown> {
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

export function buildChatCompletionsPayload(prompt: string, tile: PreparedTile): Record<string, unknown> {
  return {
    model: aiSliceModel,
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text: prompt },
          { type: "image_url", image_url: { url: tile.dataUrl } }
        ]
      }
    ],
    temperature: 0
  };
}

async function callOpenAiCompatible(payload: Record<string, unknown>, apiPath: string, extractText: (raw: string) => string): Promise<string> {
  for (let attempt = 0; attempt < Math.max(1, aiSliceTransportRetries); attempt += 1) {
    try {
      const response = await fetch(requestUrl(aiSliceBaseUrl, apiPath), {
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
      if (!response.ok) throw new Error(formatProviderError(response.status, body));
      const text = extractText(body);
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

export function requestUrl(baseURL: string, apiPath: string): string {
  const base = baseURL.trim().replace(/\/+$/, "");
  const path = `/${apiPath.replace(/^\/+/, "")}`;
  if (base.endsWith("/v1")) return `${base}${path}`;
  if (base.endsWith(path) || base.includes("/v1/")) return base;
  return `${base}/v1${path}`;
}

export function extractResponsesText(raw: string): string {
  let root: unknown;
  try {
    root = JSON.parse(raw);
  } catch {
    return raw;
  }
  if (isAiBoxesPayload(root)) return raw;
  if (root && typeof root === "object" && typeof (root as { output_text?: unknown }).output_text === "string") {
    return (root as { output_text: string }).output_text;
  }
  const texts: string[] = [];
  collectText(root, texts);
  return texts.join("\n");
}

export function extractChatCompletionsText(raw: string): string {
  let root: unknown;
  try {
    root = JSON.parse(raw);
  } catch {
    return raw;
  }
  if (isAiBoxesPayload(root)) return raw;
  const choices = root && typeof root === "object" ? (root as { choices?: unknown }).choices : undefined;
  if (!Array.isArray(choices)) return "";
  const texts: string[] = [];
  for (const choice of choices) {
    if (!choice || typeof choice !== "object") continue;
    const message = (choice as { message?: unknown }).message;
    if (!message || typeof message !== "object") continue;
    const content = (message as { content?: unknown }).content;
    if (typeof content === "string") {
      texts.push(content);
      continue;
    }
    collectChatContent(content, texts);
  }
  return texts.join("\n");
}

function isAiBoxesPayload(value: unknown): boolean {
  return !!value && typeof value === "object" && Array.isArray((value as { boxes?: unknown }).boxes);
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

function collectChatContent(value: unknown, texts: string[]): void {
  if (Array.isArray(value)) {
    for (const item of value) collectChatContent(item, texts);
    return;
  }
  if (!value || typeof value !== "object") return;
  const object = value as Record<string, unknown>;
  if ((object.type === "text" || object.type === "output_text") && typeof object.text === "string") {
    texts.push(object.text);
  }
  for (const child of Object.values(object)) collectChatContent(child, texts);
}

export function formatProviderError(status: number, body: string): string {
  return `provider returned ${status}: ${redactProviderPayload(body)}`;
}

export function redactProviderPayload(value: string): string {
  return value
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer [REDACTED]")
    .replace(/("authorization"\s*:\s*")([^"]+)(")/gi, "$1[REDACTED]$3")
    .replace(/("api[_-]?key"\s*:\s*")([^"]+)(")/gi, "$1[REDACTED]$3")
    .replace(/(data:image\/[a-z0-9.+-]+;base64,)[A-Za-z0-9+/=]+/gi, "$1[REDACTED_IMAGE]")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 500);
}
