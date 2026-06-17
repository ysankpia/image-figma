import sharp from "sharp";
import {
  aiSliceJpegQuality,
  aiSliceMaxBoxesPerPage,
  aiSliceMaxTileSide,
  aiSliceOverviewReview,
  aiSliceProvider,
  aiSliceTileCount,
  aiSliceTileOverlap
} from "../config";
import { consumeAiCall } from "../billing";
import { httpError } from "../errors";
import { getPageOriginalPath, getProjectDetail } from "../projects";
import { storage } from "../storage";
import type { AiSliceBoxesResponse } from "../../shared/types";
import { filterAiBoxes, parseAiBoxResponse } from "./boxes";
import { callAiSliceOverviewProvider, callAiSliceProvider } from "./provider";
import { generateTiles, mapTileBoxToPage, prepareTileImage } from "./tiles";
import type { RawAiBox } from "./types";

export async function generateAiSliceBoxes(userId: string, projectId: string, pageId: string): Promise<AiSliceBoxesResponse> {
  if (aiSliceProvider === "disabled") throw httpError(400, "AI slice provider is disabled");

  const detail = getProjectDetail(userId, projectId);
  const page = detail.pages.find((item) => item.id === pageId);
  if (!page) throw httpError(404, "Page not found");
  consumeAiCall(userId, projectId, { pageId, provider: aiSliceProvider });

  getPageOriginalPath(userId, projectId, pageId);
  const imageBuffer = storage.read(storage.projectOriginalImageKey(projectId, pageId), "Original image not found");
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
      sourceTileId: tile.id,
      sourceKind: "tile"
    }));
  }));
  const overviewAttempted = aiSliceOverviewReview;
  const overviewBoxes = overviewAttempted
    ? await generateOverviewBoxes(imageBuffer, { width, height }).catch(() => [])
    : [];
  const rawBoxes = [...overviewBoxes, ...tileResults.flat()];

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
      tileCount: tiles.length + (overviewAttempted ? 1 : 0),
      rawBoxCount: rawBoxes.length,
      acceptedBoxCount: filtered.boxes.length,
      rejectedBoxCount: filtered.rejectedCount
    }
  };
}

async function generateOverviewBoxes(imageBuffer: Buffer, bounds: { width: number; height: number }): Promise<RawAiBox[]> {
  const tile = { id: "overview_0001", bbox: { x: 0, y: 0, width: bounds.width, height: bounds.height } };
  const prepared = await prepareTileImage({
    imageBuffer,
    tile,
    maxSide: aiSliceMaxTileSide,
    jpegQuality: aiSliceJpegQuality
  });
  const text = await callAiSliceOverviewProvider(prepared);
  const parsed = parseAiBoxResponse(text);
  if (parsed.error) return [];
  return parsed.boxes.map((box): RawAiBox => ({
    ...box,
    bbox: mapTileBoxToPage(box.bbox, prepared),
    sourceTileId: tile.id,
    sourceKind: "overview"
  }));
}
