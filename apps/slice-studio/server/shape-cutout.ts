import sharp from "sharp";
import type { BBox, CutMode } from "../shared/types";

type CropSlice = {
  bbox: BBox;
  cutMode: CutMode;
};

type ShapeCutoutOptions = {
  targetBox?: {
    left: number;
    top: number;
    width: number;
    height: number;
  };
};

export async function cropSliceToPng(originalBuffer: Buffer, slice: CropSlice): Promise<Buffer> {
  const box = {
    left: Math.round(slice.bbox.x),
    top: Math.round(slice.bbox.y),
    width: Math.round(slice.bbox.width),
    height: Math.round(slice.bbox.height)
  };

  if (slice.cutMode === "shape") {
    const metadata = await sharp(originalBuffer).metadata();
    const imageWidth = metadata.width ?? box.left + box.width;
    const imageHeight = metadata.height ?? box.top + box.height;
    const expandedBox = expandBox(box, imageWidth, imageHeight);
    const cropped = await sharp(originalBuffer)
      .extract(expandedBox)
      .ensureAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });

    const left = box.left - expandedBox.left;
    const top = box.top - expandedBox.top;
    const cutout = applyShapeCutout(cropped.data, cropped.info.width, cropped.info.height, {
      targetBox: { left, top, width: box.width, height: box.height }
    });
    return sharp(cutout, { raw: { width: cropped.info.width, height: cropped.info.height, channels: 4 } })
      .extract({ left, top, width: box.width, height: box.height })
      .png()
      .toBuffer();
  }

  const cropped = await sharp(originalBuffer)
    .extract(box)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  return sharp(cropped.data, { raw: { width: cropped.info.width, height: cropped.info.height, channels: 4 } })
    .png()
    .toBuffer();
}

export function applyShapeCutout(source: Uint8Array, width: number, height: number, options: ShapeCutoutOptions = {}): Buffer {
  if (width < 4 || height < 4) return Buffer.from(source);

  const background = estimateBackground(source, width, height);
  const threshold = background.threshold;
  const backgroundMask = new Uint8Array(width * height);
  const blockedMask = buildInteriorGuard(width, height, options.targetBox);
  const outsideMask = new Uint8Array(width * height);
  const queue: number[] = [];
  const result = Buffer.from(source);

  for (let index = 0; index < width * height; index += 1) {
    const offset = index * 4;
    const originalAlpha = source[offset + 3];
    if (originalAlpha < 10) {
      backgroundMask[index] = 1;
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

    if (distance <= threshold) backgroundMask[index] = 1;
  }

  for (let x = 0; x < width; x += 1) {
    pushFloodSeed(x, 0, width, height, backgroundMask, blockedMask, outsideMask, queue);
    pushFloodSeed(x, height - 1, width, height, backgroundMask, blockedMask, outsideMask, queue);
  }
  for (let y = 0; y < height; y += 1) {
    pushFloodSeed(0, y, width, height, backgroundMask, blockedMask, outsideMask, queue);
    pushFloodSeed(width - 1, y, width, height, backgroundMask, blockedMask, outsideMask, queue);
  }

  for (let cursor = 0; cursor < queue.length; cursor += 1) {
    const index = queue[cursor];
    const x = index % width;
    const y = Math.floor(index / width);
    pushFloodSeed(x + 1, y, width, height, backgroundMask, blockedMask, outsideMask, queue);
    pushFloodSeed(x - 1, y, width, height, backgroundMask, blockedMask, outsideMask, queue);
    pushFloodSeed(x, y + 1, width, height, backgroundMask, blockedMask, outsideMask, queue);
    pushFloodSeed(x, y - 1, width, height, backgroundMask, blockedMask, outsideMask, queue);
  }

  const outsideRatio = queue.length / (width * height);
  if (outsideRatio < 0.003 || outsideRatio > 0.92) return Buffer.from(source);

  for (const index of queue) {
    result[index * 4 + 3] = 0;
  }

  return result;
}

function expandBox(
  box: { left: number; top: number; width: number; height: number },
  imageWidth: number,
  imageHeight: number
): { left: number; top: number; width: number; height: number } {
  const padding = Math.min(96, Math.max(12, Math.round(Math.min(box.width, box.height) * 0.28)));
  const left = Math.max(0, box.left - padding);
  const top = Math.max(0, box.top - padding);
  const right = Math.min(imageWidth, box.left + box.width + padding);
  const bottom = Math.min(imageHeight, box.top + box.height + padding);
  return {
    left,
    top,
    width: Math.max(1, right - left),
    height: Math.max(1, bottom - top)
  };
}

function pushFloodSeed(
  x: number,
  y: number,
  width: number,
  height: number,
  backgroundMask: Uint8Array,
  blockedMask: Uint8Array,
  outsideMask: Uint8Array,
  queue: number[]
): void {
  if (x < 0 || y < 0 || x >= width || y >= height) return;
  const index = y * width + x;
  if (!backgroundMask[index] || blockedMask[index] || outsideMask[index]) return;
  outsideMask[index] = 1;
  queue.push(index);
}

function buildInteriorGuard(
  width: number,
  height: number,
  targetBox?: { left: number; top: number; width: number; height: number }
): Uint8Array {
  const guard = new Uint8Array(width * height);
  if (!targetBox) return guard;

  const minSide = Math.min(targetBox.width, targetBox.height);
  const area = targetBox.width * targetBox.height;
  if (minSide < 72 || area < 4096) return guard;

  const inset = clamp(Math.round(minSide * 0.06), 8, 16);
  const left = Math.max(0, Math.round(targetBox.left + inset));
  const top = Math.max(0, Math.round(targetBox.top + inset));
  const right = Math.min(width, Math.round(targetBox.left + targetBox.width - inset));
  const bottom = Math.min(height, Math.round(targetBox.top + targetBox.height - inset));
  if (right <= left || bottom <= top) return guard;

  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      guard[row + x] = 1;
    }
  }

  return guard;
}

function estimateBackground(source: Uint8Array, width: number, height: number): { red: number; green: number; blue: number; threshold: number } {
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

  const red = median(samples.map((sample) => sample[0]));
  const green = median(samples.map((sample) => sample[1]));
  const blue = median(samples.map((sample) => sample[2]));
  const distances = samples.map((sample) => colorDistance(sample[0], sample[1], sample[2], red, green, blue));
  const threshold = clamp(percentile(distances, 0.82) + 24, 36, 76);
  return { red, green, blue, threshold };
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

function percentile(values: number[], ratio: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * ratio)));
  return sorted[index];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function colorDistance(redA: number, greenA: number, blueA: number, redB: number, greenB: number, blueB: number): number {
  return Math.sqrt(
    (redA - redB) ** 2 +
    (greenA - greenB) ** 2 +
    (blueA - blueB) ** 2
  );
}
