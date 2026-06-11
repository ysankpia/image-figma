import type { BBox } from "../../shared/types";
import { clampFloat, colorCountInBBox, colorDistance, grayAt, hexRgb, meanInBBox, quantizedColorKey, rgbAt, round2, round4 } from "./image";
import type { DecodedRgbaImage, M29Measurements, PixelComponent, Rgb } from "./types";

export function measureComponent(image: DecodedRgbaImage, component: PixelComponent, background: Rgb): M29Measurements {
  const bboxArea = component.bbox.width * component.bbox.height;
  const fillRatio = bboxArea > 0 ? component.area / bboxArea : 0;
  let sumR = 0;
  let sumG = 0;
  let sumB = 0;
  const colors = new Set<string>();
  for (const index of component.pixels) {
    const x = index % image.width;
    const y = Math.trunc(index / image.width);
    const rgb = rgbAt(image, x, y);
    sumR += rgb.r;
    sumG += rgb.g;
    sumB += rgb.b;
    colors.add(quantizedColorKey(rgb));
  }
  const mean = component.area > 0
    ? {
        r: Math.trunc(sumR / component.area),
        g: Math.trunc(sumG / component.area),
        b: Math.trunc(sumB / component.area)
      }
    : { r: 0, g: 0, b: 0 };
  const edgeDensity = edgeDensityInBBox(image, component.bbox);
  const colorCount = colors.size;
  const textureScore = clampFloat(edgeDensity + colorCount / 96, 0, 1);
  return {
    area: component.area,
    fillRatio: round4(fillRatio),
    meanColor: hexRgb(mean),
    colorCount,
    edgeDensity: round4(edgeDensity),
    textureScore: round4(textureScore),
    localContrast: round2(colorDistance(mean, background)),
    cornerRadiusEstimate: 0
  };
}

export function measureSurface(image: DecodedRgbaImage, bbox: BBox, background: Rgb): M29Measurements {
  const area = bbox.width * bbox.height;
  const mean = meanInBBox(image, bbox);
  const edgeDensity = edgeDensityInBBox(image, bbox);
  const colorCount = colorCountInBBox(image, bbox, 512);
  return {
    area,
    fillRatio: 1,
    meanColor: hexRgb(mean),
    colorCount,
    edgeDensity: round4(edgeDensity),
    textureScore: round4(clampFloat(edgeDensity + colorCount / 512, 0, 1)),
    localContrast: round2(colorDistance(mean, background)),
    cornerRadiusEstimate: 0
  };
}

export function edgeDensityInBBox(image: DecodedRgbaImage, bbox: BBox): number {
  if (bbox.width <= 2 || bbox.height <= 2) return 0;
  let total = 0;
  let edge = 0;
  for (let y = bbox.y + 1; y < bbox.y + bbox.height - 1; y += 1) {
    for (let x = bbox.x + 1; x < bbox.x + bbox.width - 1; x += 1) {
      const gx = Math.abs(grayAt(image, x + 1, y) - grayAt(image, x - 1, y));
      const gy = Math.abs(grayAt(image, x, y + 1) - grayAt(image, x, y - 1));
      total += 1;
      if (gx + gy > 48) edge += 1;
    }
  }
  if (!total) return 0;
  return edge / total;
}
