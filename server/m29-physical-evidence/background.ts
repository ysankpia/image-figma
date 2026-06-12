import { clampFloat, colorDistance, hexRgb, medianRgb, percentile, rgbAt } from "./image";
import type { BackgroundEstimate, DecodedRgbaImage, Rgb } from "./types";

export function estimateBackground(image: DecodedRgbaImage): BackgroundEstimate {
  const samples = edgeSamples(image);
  const color = medianRgb(samples);
  const distances = samples.map((sample) => colorDistance(sample, color)).sort((a, b) => a - b);
  const p95 = percentile(distances, 0.95);
  return {
    color,
    threshold: clampFloat(Math.max(18, p95 * 2.2), 18, 52)
  };
}

export function backgroundColorHex(estimate: BackgroundEstimate): string {
  return hexRgb(estimate.color);
}

function edgeSamples(image: DecodedRgbaImage): Rgb[] {
  const samples: Rgb[] = [];
  const step = Math.max(1, Math.floor(Math.min(image.width, image.height) / 160));
  for (let x = 0; x < image.width; x += step) {
    samples.push(rgbAt(image, x, 0), rgbAt(image, x, image.height - 1));
  }
  for (let y = 0; y < image.height; y += step) {
    samples.push(rgbAt(image, 0, y), rgbAt(image, image.width - 1, y));
  }
  return samples;
}
