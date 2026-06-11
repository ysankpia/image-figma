import fs from "node:fs";
import sharp from "sharp";
import {
  aiSliceJpegQuality,
  aiSliceMaxBoxesPerPage,
  aiSliceMaxTileSide,
  aiSliceProvider,
  aiSliceTileCount,
  aiSliceTileOverlap
} from "../config";
import { httpError } from "../errors";
import { getPageOriginalPath, getProjectDetail } from "../projects";
import type { AiSliceBoxesResponse } from "../../shared/types";
import { filterAiBoxes, parseAiBoxResponse } from "./boxes";
import { callAiSliceProvider } from "./provider";
import { generateTiles, mapTileBoxToPage, prepareTileImage } from "./tiles";
import type { RawAiBox } from "./types";

export async function generateAiSliceBoxes(projectId: string, pageId: string): Promise<AiSliceBoxesResponse> {
  if (aiSliceProvider === "disabled") throw httpError(400, "AI slice provider is disabled");

  const detail = getProjectDetail(projectId);
  const page = detail.pages.find((item) => item.id === pageId);
  if (!page) throw httpError(404, "Page not found");

  const originalPath = getPageOriginalPath(projectId, pageId);
  const imageBuffer = fs.readFileSync(originalPath);
  const metadata = await sharp(imageBuffer, { failOn: "none" }).metadata();
  const width = metadata.width || page.width;
  const height = metadata.height || page.height;
  const tiles = generateTiles({ width, height }, aiSliceTileCount, aiSliceTileOverlap);
  const tileResults = await Promise.all(tiles.map(async (tile) => {
    const prepared = await prepareTileImage({
      imageBuffer,
      tile,
      maxSide: aiSliceMaxTileSide,
      jpegQuality: aiSliceJpegQuality
    });
    const text = await callAiSliceProvider(prepared);
    const parsed = parseAiBoxResponse(text);
    if (parsed.error) return [];
    return parsed.boxes.map((box): RawAiBox => ({
      ...box,
      bbox: mapTileBoxToPage(box.bbox, prepared),
      sourceTileId: tile.id
    }));
  }));
  const rawBoxes = tileResults.flat();

  const filtered = filterAiBoxes({
    boxes: rawBoxes,
    existingSlices: page.slices,
    bounds: { width, height },
    maxBoxes: aiSliceMaxBoxesPerPage
  });

  return {
    ok: true,
    pageId,
    boxes: filtered.boxes,
    diagnostics: {
      tileCount: tiles.length,
      rawBoxCount: rawBoxes.length,
      acceptedBoxCount: filtered.boxes.length,
      rejectedBoxCount: filtered.rejectedCount
    }
  };
}
