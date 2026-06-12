import crypto from "node:crypto";
import sharp from "sharp";
import type { BBox } from "../../shared/types";
import type { DecodedRgbaImage, Rgb } from "./types";

export async function decodeRgba(imageBuffer: Buffer): Promise<DecodedRgbaImage> {
  const raw = await sharp(imageBuffer).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  return {
    data: raw.data,
    width: raw.info.width,
    height: raw.info.height
  };
}

export function sha256Hex(buffer: Buffer): string {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

export function rgbAt(image: DecodedRgbaImage, x: number, y: number): Rgb {
  const clampedX = clamp(Math.trunc(x), 0, image.width - 1);
  const clampedY = clamp(Math.trunc(y), 0, image.height - 1);
  const offset = (clampedY * image.width + clampedX) * 4;
  return {
    r: image.data[offset],
    g: image.data[offset + 1],
    b: image.data[offset + 2]
  };
}

export function grayAt(image: DecodedRgbaImage, x: number, y: number): number {
  const c = rgbAt(image, x, y);
  return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b;
}

export function colorDistance(a: Rgb, b: Rgb): number {
  const dr = a.r - b.r;
  const dg = a.g - b.g;
  const db = a.b - b.b;
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

export function hexRgb(color: Rgb): string {
  return `#${hex(color.r)}${hex(color.g)}${hex(color.b)}`;
}

export function medianRgb(samples: Rgb[]): Rgb {
  if (!samples.length) return { r: 255, g: 255, b: 255 };
  const rs = samples.map((sample) => sample.r).sort((a, b) => a - b);
  const gs = samples.map((sample) => sample.g).sort((a, b) => a - b);
  const bs = samples.map((sample) => sample.b).sort((a, b) => a - b);
  const mid = Math.floor(samples.length / 2);
  return { r: rs[mid], g: gs[mid], b: bs[mid] };
}

export function percentile(values: number[], p: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = clamp(Math.round((sorted.length - 1) * p), 0, sorted.length - 1);
  return sorted[index];
}

export function meanInBBox(image: DecodedRgbaImage, bbox: BBox): Rgb {
  const x1 = clamp(bbox.x, 0, image.width);
  const y1 = clamp(bbox.y, 0, image.height);
  const x2 = clamp(bbox.x + bbox.width, x1, image.width);
  const y2 = clamp(bbox.y + bbox.height, y1, image.height);
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  let count = 0;
  for (let y = y1; y < y2; y += 1) {
    for (let x = x1; x < x2; x += 1) {
      const c = rgbAt(image, x, y);
      sumR += c.r;
      sumG += c.g;
      sumB += c.b;
      count += 1;
    }
  }
  if (!count) return { r: 0, g: 0, b: 0 };
  return {
    r: Math.trunc(sumR / count),
    g: Math.trunc(sumG / count),
    b: Math.trunc(sumB / count)
  };
}

export function colorCountInBBox(image: DecodedRgbaImage, bbox: BBox, limit: number): number {
  const colors = new Set<string>();
  const x1 = clamp(bbox.x, 0, image.width);
  const y1 = clamp(bbox.y, 0, image.height);
  const x2 = clamp(bbox.x + bbox.width, x1, image.width);
  const y2 = clamp(bbox.y + bbox.height, y1, image.height);
  for (let y = y1; y < y2; y += 1) {
    for (let x = x1; x < x2; x += 1) {
      colors.add(quantizedColorKey(rgbAt(image, x, y)));
      if (colors.size >= limit) return colors.size;
    }
  }
  return colors.size;
}

export function quantizedColorKey(color: Rgb): string {
  return `${color.r >> 4}:${color.g >> 4}:${color.b >> 4}`;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

export function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

export function clampFloat(value: number, min: number, max: number): number {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

function hex(value: number): string {
  return clamp(Math.round(value), 0, 255).toString(16).padStart(2, "0");
}
