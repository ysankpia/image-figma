import { normalizeBox } from "../../shared/bbox";
import type { AiSliceBox, BBox, SliceRecord } from "../../shared/types";
import type { RawAiBox } from "./types";

const minBoxSize = 8;
const duplicateIouThreshold = 0.72;
const existingIouThreshold = 0.6;
const maxPageAreaRatio = 0.82;

export function parseAiBoxResponse(text: string): { boxes: Array<Omit<RawAiBox, "sourceTileId">>; error: string } {
  const cleaned = cleanJsonText(text);
  let payload: unknown;
  try {
    payload = JSON.parse(cleaned);
  } catch (error) {
    return { boxes: [], error: `json_parse_error:${error instanceof Error ? error.message : "unknown"}` };
  }
  if (!payload || typeof payload !== "object" || !Array.isArray((payload as { boxes?: unknown }).boxes)) {
    return { boxes: [], error: "boxes_missing" };
  }

  const boxes: Array<Omit<RawAiBox, "sourceTileId">> = [];
  for (const raw of (payload as { boxes: unknown[] }).boxes) {
    if (!raw || typeof raw !== "object") continue;
    const item = raw as Record<string, unknown>;
    boxes.push({
      bbox: {
        x: Number(item.x),
        y: Number(item.y),
        width: Number(item.width),
        height: Number(item.height)
      },
      name: typeof item.label === "string" ? item.label.trim().slice(0, 80) : undefined,
      confidence: finiteOrUndefined(item.confidence),
      reason: typeof item.reason === "string" ? item.reason.trim().slice(0, 240) : undefined
    });
  }
  return { boxes, error: "" };
}

export function filterAiBoxes(input: {
  boxes: RawAiBox[];
  existingSlices: SliceRecord[];
  bounds: { width: number; height: number };
  maxBoxes: number;
}): { boxes: AiSliceBox[]; rejectedCount: number } {
  const accepted: AiSliceBox[] = [];
  let rejectedCount = 0;
  const pageArea = input.bounds.width * input.bounds.height;

  for (const raw of input.boxes) {
    if (!isFiniteBox(raw.bbox)) {
      rejectedCount += 1;
      continue;
    }
    const bbox = normalizeBox(raw.bbox, input.bounds, 1);
    if (bbox.width < minBoxSize || bbox.height < minBoxSize) {
      rejectedCount += 1;
      continue;
    }
    if (bbox.width * bbox.height / pageArea > maxPageAreaRatio) {
      rejectedCount += 1;
      continue;
    }
    if (input.existingSlices.some((slice) => iou(bbox, slice.bbox) >= existingIouThreshold)) {
      rejectedCount += 1;
      continue;
    }
    if (accepted.some((box) => iou(bbox, box.bbox) >= duplicateIouThreshold)) {
      rejectedCount += 1;
      continue;
    }
    accepted.push({
      bbox,
      name: raw.name || undefined,
      confidence: raw.confidence,
      reason: raw.reason,
      sourceTileId: raw.sourceTileId
    });
    if (accepted.length >= input.maxBoxes) break;
  }

  rejectedCount += Math.max(0, input.boxes.length - accepted.length - rejectedCount);
  return { boxes: accepted, rejectedCount };
}

export function iou(a: BBox, b: BBox): number {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  const intersection = Math.max(0, right - left) * Math.max(0, bottom - top);
  if (intersection <= 0) return 0;
  const areaA = a.width * a.height;
  const areaB = b.width * b.height;
  return intersection / (areaA + areaB - intersection);
}

function cleanJsonText(text: string): string {
  let cleaned = text.trim();
  if (cleaned.startsWith("```")) {
    const lines = cleaned.split(/\r?\n/);
    if (lines[0]?.startsWith("```")) lines.shift();
    if (lines[lines.length - 1]?.trim() === "```") lines.pop();
    cleaned = lines.join("\n").trim();
  }
  if (!cleaned.startsWith("{")) {
    const first = cleaned.indexOf("{");
    const last = cleaned.lastIndexOf("}");
    if (first >= 0 && last > first) cleaned = cleaned.slice(first, last + 1);
  }
  return cleaned;
}

function isFiniteBox(box: BBox): boolean {
  return Number.isFinite(box.x) && Number.isFinite(box.y) && Number.isFinite(box.width) && Number.isFinite(box.height) && box.width > 0 && box.height > 0;
}

function finiteOrUndefined(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}
