import sharp from "sharp";
import { clamp } from "../../shared/bbox";
import type { BBox } from "../../shared/types";
import type { PreparedTile, Tile } from "./types";

export function generateTiles(bounds: { width: number; height: number }, tileCount: number, overlap: number): Tile[] {
  const grid = chooseTileGrid(bounds.width, bounds.height, tileCount);
  const pad = Math.max(0, Math.floor(overlap / 2));
  const tiles: Tile[] = [];

  for (let row = 0; row < grid.rows; row += 1) {
    for (let col = 0; col < grid.cols; col += 1) {
      const cellLeft = Math.floor(col * bounds.width / grid.cols);
      const cellTop = Math.floor(row * bounds.height / grid.rows);
      const cellRight = Math.ceil((col + 1) * bounds.width / grid.cols);
      const cellBottom = Math.ceil((row + 1) * bounds.height / grid.rows);
      const left = clamp(cellLeft - (col > 0 ? pad : 0), 0, Math.max(0, bounds.width - 1));
      const top = clamp(cellTop - (row > 0 ? pad : 0), 0, Math.max(0, bounds.height - 1));
      const right = clamp(cellRight + (col < grid.cols - 1 ? pad : 0), left + 1, bounds.width);
      const bottom = clamp(cellBottom + (row < grid.rows - 1 ? pad : 0), top + 1, bounds.height);
      tiles.push({
        id: `tile_${String(tiles.length + 1).padStart(4, "0")}`,
        bbox: { x: left, y: top, width: right - left, height: bottom - top }
      });
    }
  }

  return tiles.slice(0, Math.max(1, Math.round(tileCount)));
}

export function mapTileBoxToPage(box: BBox, tile: PreparedTile): BBox {
  const scaleX = tile.bbox.width / tile.sentWidth;
  const scaleY = tile.bbox.height / tile.sentHeight;
  return {
    x: Math.round(tile.bbox.x + box.x * scaleX),
    y: Math.round(tile.bbox.y + box.y * scaleY),
    width: Math.round(box.width * scaleX),
    height: Math.round(box.height * scaleY)
  };
}

export async function prepareTileImage(input: {
  imageBuffer: Buffer;
  tile: Tile;
  maxSide: number;
  jpegQuality: number;
}): Promise<PreparedTile> {
  const tileImage = sharp(input.imageBuffer, { failOn: "none" })
    .extract({
      left: input.tile.bbox.x,
      top: input.tile.bbox.y,
      width: input.tile.bbox.width,
      height: input.tile.bbox.height
    })
    .flatten({ background: "#ffffff" });

  const resizeRatio = Math.min(1, input.maxSide / Math.max(input.tile.bbox.width, input.tile.bbox.height));
  const sentWidth = Math.max(1, Math.round(input.tile.bbox.width * resizeRatio));
  const sentHeight = Math.max(1, Math.round(input.tile.bbox.height * resizeRatio));
  const buffer = await tileImage
    .resize(sentWidth, sentHeight, { fit: "fill" })
    .jpeg({ quality: clamp(Math.round(input.jpegQuality), 1, 100), mozjpeg: true })
    .toBuffer();

  return {
    ...input.tile,
    sentWidth,
    sentHeight,
    dataUrl: `data:image/jpeg;base64,${buffer.toString("base64")}`
  };
}

function chooseTileGrid(width: number, height: number, tileCount: number): { cols: number; rows: number } {
  const count = Math.max(1, Math.round(tileCount));
  if (count === 6) {
    if (height / Math.max(1, width) >= 1.25) return { cols: 1, rows: 6 };
    if (width / Math.max(1, height) >= 1.25) return { cols: 3, rows: 2 };
    return { cols: 2, rows: 3 };
  }
  const aspect = width / Math.max(1, height);
  const cols = Math.max(1, Math.round(Math.sqrt(count * aspect)));
  return { cols, rows: Math.ceil(count / cols) };
}
