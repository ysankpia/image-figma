import sharp from "sharp";
import type { BBox } from "../shared/types";

function toHex(r: number, g: number, b: number): string {
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
}

// Sample the dominant background color of a bbox region.
// Crops to bbox, samples a border ring of pixels (avoids center content), returns median hex color.
export async function sampleBgColor(imgBuf: Buffer, bbox: BBox): Promise<string> {
  const { data, info } = await sharp(imgBuf)
    .extract({ left: bbox.x, top: bbox.y, width: bbox.width, height: bbox.height })
    .resize(16, 16, { fit: "fill" })
    .raw()
    .toBuffer({ resolveWithObject: true });

  const channels = info.channels; // 3 or 4
  const rs: number[] = [];
  const gs: number[] = [];
  const bs: number[] = [];

  // Collect edge pixels only (top row, bottom row, left col, right col)
  for (let i = 0; i < 16 * 16; i++) {
    const row = Math.floor(i / 16);
    const col = i % 16;
    if (row === 0 || row === 15 || col === 0 || col === 15) {
      rs.push(data[i * channels]!);
      gs.push(data[i * channels + 1]!);
      bs.push(data[i * channels + 2]!);
    }
  }

  rs.sort((a, b) => a - b);
  gs.sort((a, b) => a - b);
  bs.sort((a, b) => a - b);
  const mid = Math.floor(rs.length / 2);
  return toHex(rs[mid]!, gs[mid]!, bs[mid]!);
}

// Estimate corner radius by comparing corner pixels vs edge midpoint pixels.
// Returns 0 if no rounding detected, otherwise estimates radius.
export async function estimateCornerRadius(imgBuf: Buffer, bbox: BBox): Promise<number> {
  const size = 24;
  const { data } = await sharp(imgBuf)
    .extract({ left: bbox.x, top: bbox.y, width: bbox.width, height: bbox.height })
    .resize(size, size, { fit: "fill" })
    .raw()
    .toBuffer({ resolveWithObject: true });

  function px(col: number, row: number): [number, number, number] {
    const i = (row * size + col) * 3;
    return [data[i]!, data[i + 1]!, data[i + 2]!];
  }

  function dist([r1, g1, b1]: [number, number, number], [r2, g2, b2]: [number, number, number]): number {
    return Math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2);
  }

  const mid = Math.floor(size / 2);
  const edgeMid = (px(mid, 0)[0] + px(0, mid)[0] + px(size - 1, mid)[0] + px(mid, size - 1)[0]) / 4;
  const edgeColor: [number, number, number] = [edgeMid, edgeMid, edgeMid];

  const corners = [px(0, 0), px(size - 1, 0), px(0, size - 1), px(size - 1, size - 1)];
  const avgCornerDist = corners.reduce((sum, c) => sum + dist(c, edgeColor), 0) / 4;

  if (avgCornerDist > 30) {
    return Math.round(Math.min(bbox.width, bbox.height) * 0.15 / 4) * 4;
  }
  return 0;
}
