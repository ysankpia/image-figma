import sharp from "sharp";
import type { BBox, CutMode } from "../shared/types";

type CropSlice = {
  bbox: BBox;
  cutMode: CutMode;
};

export async function cropSliceToPng(originalBuffer: Buffer, slice: CropSlice): Promise<Buffer> {
  const box = {
    left: Math.round(slice.bbox.x),
    top: Math.round(slice.bbox.y),
    width: Math.round(slice.bbox.width),
    height: Math.round(slice.bbox.height)
  };
  const cropped = await sharp(originalBuffer)
    .extract(box)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const width = cropped.info.width;
  const height = cropped.info.height;
  const data = slice.cutMode === "shape"
    ? applyShapeCutout(cropped.data, width, height)
    : Buffer.from(cropped.data);

  return sharp(data, { raw: { width, height, channels: 4 } }).png().toBuffer();
}

export function applyShapeCutout(source: Uint8Array, width: number, height: number): Buffer {
  if (width < 4 || height < 4) return Buffer.from(source);

  const background = estimateBackground(source, width, height);
  const threshold = 32;
  const feather = 24;
  const result = Buffer.from(source);
  let foregroundPixels = 0;

  for (let index = 0; index < width * height; index += 1) {
    const offset = index * 4;
    const originalAlpha = source[offset + 3];
    if (originalAlpha < 10) {
      result[offset + 3] = 0;
      continue;
    }

    const distance = colorDistance(
      source[offset],
      source[offset + 1],
      source[offset + 2],
      background.red,
      background.green,
      background.blue
    );

    if (distance <= threshold) {
      result[offset + 3] = 0;
    } else if (distance < threshold + feather) {
      const alphaRatio = (distance - threshold) / feather;
      result[offset + 3] = Math.round(originalAlpha * alphaRatio);
      foregroundPixels += alphaRatio > 0.35 ? 1 : 0;
    } else {
      result[offset + 3] = originalAlpha;
      foregroundPixels += 1;
    }
  }

  const foregroundRatio = foregroundPixels / (width * height);
  if (foregroundRatio < 0.01 || foregroundRatio > 0.95) return Buffer.from(source);
  return result;
}

function estimateBackground(source: Uint8Array, width: number, height: number): { red: number; green: number; blue: number } {
  const samples: Array<[number, number, number]> = [];
  const stride = Math.max(1, Math.floor(Math.max(width, height) / 64));

  for (let x = 0; x < width; x += stride) {
    pushSample(samples, source, width, x, 0);
    pushSample(samples, source, width, x, height - 1);
  }
  for (let y = 0; y < height; y += stride) {
    pushSample(samples, source, width, 0, y);
    pushSample(samples, source, width, width - 1, y);
  }

  return {
    red: median(samples.map((sample) => sample[0])),
    green: median(samples.map((sample) => sample[1])),
    blue: median(samples.map((sample) => sample[2]))
  };
}

function pushSample(samples: Array<[number, number, number]>, source: Uint8Array, width: number, x: number, y: number): void {
  const offset = (y * width + x) * 4;
  if (source[offset + 3] < 10) return;
  samples.push([source[offset], source[offset + 1], source[offset + 2]]);
}

function median(values: number[]): number {
  if (!values.length) return 255;
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor(sorted.length / 2)];
}

function colorDistance(redA: number, greenA: number, blueA: number, redB: number, greenB: number, blueB: number): number {
  return Math.sqrt(
    (redA - redB) ** 2 +
    (greenA - greenB) ** 2 +
    (blueA - blueB) ** 2
  );
}
