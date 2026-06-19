import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { aiSliceYoloClasses, aiSliceYoloConfidence, aiSliceYoloImageSize, aiSliceYoloModelPath, aiSliceYoloPython } from "../config";
import { httpError } from "../errors";
import type { RawAiBox } from "./types";

export async function detectYoloSliceBoxes(imageBuffer: Buffer): Promise<RawAiBox[]> {
  if (!aiSliceYoloModelPath.trim()) throw httpError(400, "YOLO model path is not configured");
  if (!fs.existsSync(aiSliceYoloModelPath)) throw httpError(400, `YOLO model not found: ${aiSliceYoloModelPath}`);

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "slice-yolo-"));
  const imagePath = path.join(dir, "source.png");
  fs.writeFileSync(imagePath, imageBuffer);
  try {
    const script = [
      "import json, sys",
      "from ultralytics import YOLO",
      "model_path, image_path, conf, imgsz = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])",
      "model = YOLO(model_path)",
      "result = model.predict(image_path, conf=conf, imgsz=imgsz, verbose=False)[0]",
      "names = result.names",
      "out = []",
      "for box in result.boxes:",
      "    cls = int(box.cls[0])",
      "    name = names.get(cls, str(cls)) if isinstance(names, dict) else str(cls)",
      "    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]",
      "    out.append({'className': name, 'confidence': float(box.conf[0]), 'bbox': {'x': x1, 'y': y1, 'width': x2 - x1, 'height': y2 - y1}})",
      "print(json.dumps({'boxes': out}, ensure_ascii=False))"
    ].join("\n");
    const result = spawnSync(aiSliceYoloPython, ["-c", script, aiSliceYoloModelPath, imagePath, String(aiSliceYoloConfidence), String(aiSliceYoloImageSize)], {
      encoding: "utf8",
      maxBuffer: 20 * 1024 * 1024
    });
    if (result.error) {
      throw httpError(502, `YOLO detection failed to start ${aiSliceYoloPython}: ${result.error.message}`);
    }
    if (result.status !== 0) {
      throw httpError(502, `YOLO detection failed: ${trimProcessOutput(result.stderr || result.stdout)}`);
    }
    const parsed = JSON.parse(result.stdout) as { boxes?: Array<{ className?: string; confidence?: number; bbox?: RawAiBox["bbox"] }> };
    const assetClasses = new Set(aiSliceYoloClasses);
    return (parsed.boxes || [])
      .filter((box) => box.className && assetClasses.has(box.className) && box.bbox)
      .map((box): RawAiBox => ({
        bbox: box.bbox!,
        name: box.className,
        confidence: box.confidence,
        reason: `yolo:${box.className}`,
        sourceTileId: "yolo_full_page",
        sourceKind: "overview"
      }));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function trimProcessOutput(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, 500) || "unknown error";
}
