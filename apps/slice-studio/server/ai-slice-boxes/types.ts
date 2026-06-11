import type { BBox } from "../../shared/types";

export type Tile = {
  id: string;
  bbox: BBox;
};

export type PreparedTile = Tile & {
  sentWidth: number;
  sentHeight: number;
  dataUrl: string;
};

export type RawAiBox = {
  bbox: BBox;
  name?: string;
  confidence?: number;
  reason?: string;
  sourceTileId: string;
};

export type AiBoxDiagnostics = {
  tileCount: number;
  rawBoxCount: number;
  acceptedBoxCount: number;
  rejectedBoxCount: number;
};
