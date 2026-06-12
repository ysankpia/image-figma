import type { BBox } from "../../shared/types";
import { colorDistance, rgbAt } from "./image";
import type { BackgroundEstimate, DecodedRgbaImage, ForegroundMask, Mask } from "./types";

export function newMask(width: number, height: number): Mask {
  return { width, height, data: new Uint8Array(width * height) };
}

export function inBounds(mask: Mask, x: number, y: number): boolean {
  return x >= 0 && y >= 0 && x < mask.width && y < mask.height;
}

export function getMask(mask: Mask, x: number, y: number): boolean {
  if (!inBounds(mask, x, y)) return false;
  return mask.data[y * mask.width + x] === 1;
}

export function setMask(mask: Mask, x: number, y: number, value: boolean): void {
  if (!inBounds(mask, x, y)) return;
  mask.data[y * mask.width + x] = value ? 1 : 0;
}

export function fillBBox(mask: Mask, bbox: BBox, padding: number): void {
  const x1 = Math.max(0, bbox.x - padding);
  const y1 = Math.max(0, bbox.y - padding);
  const x2 = Math.min(mask.width, bbox.x + bbox.width + padding);
  const y2 = Math.min(mask.height, bbox.y + bbox.height + padding);
  for (let y = y1; y < y2; y += 1) {
    for (let x = x1; x < x2; x += 1) {
      setMask(mask, x, y, true);
    }
  }
}

export function bboxMask(width: number, height: number, bbox: BBox): Mask {
  const mask = newMask(width, height);
  fillBBox(mask, bbox, 0);
  return mask;
}

export function createForegroundMask(image: DecodedRgbaImage, background: BackgroundEstimate, textMask = newMask(image.width, image.height)): ForegroundMask {
  const mask = newMask(image.width, image.height) as ForegroundMask;
  let foregroundPixelCount = 0;
  for (let y = 0; y < image.height; y += 1) {
    for (let x = 0; x < image.width; x += 1) {
      if (getMask(textMask, x, y)) continue;
      if (colorDistance(rgbAt(image, x, y), background.color) > background.threshold) {
        setMask(mask, x, y, true);
        foregroundPixelCount += 1;
      }
    }
  }
  mask.foregroundPixelCount = foregroundPixelCount;
  return mask;
}
