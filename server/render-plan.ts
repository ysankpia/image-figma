import type { BBox, CutMode } from "../shared/types";
import type { TextLayer } from "./text-reconstruction";

export type PageRenderPlan = {
  pageId: string;
  pageDirectory: string;
  width: number;
  height: number;
  layers: {
    remainder: RemainderLayer;
    controlSurfaces: ControlSurfaceLayer[];
    text: TextRenderLayer[];
    slices: SliceRenderLayer[];
  };
  remainder: {
    textKnockouts: BBox[];
    surfaceKnockouts: SurfaceKnockout[];
  };
};

export type RemainderLayer = {
  id: string;
  zIndex: number;
  visibleBBox: BBox;
  provenance: "original_image";
};

export type ControlSurfaceLayer = {
  id: string;
  pageId: string;
  zIndex: number;
  sourceTextId: string;
  visibleBBox: BBox;
  fill: string;
  cornerRadius: number;
  knockout: SurfaceKnockout;
  provenance: "ocr_owner_surface";
};

export type SurfaceKnockout = {
  visibleShape: RoundedRectShape;
  sourceOwnerRegion: SourceOwnerRegion;
  provenance: "ocr_owner_surface";
};

export type RoundedRectShape = {
  kind: "rounded_rect";
  bbox: BBox;
  cornerRadius: number;
};

export type SourceOwnerRegion = {
  kind: "owner_band";
  pad: number;
  fill: string;
  backgroundSample: "outside_ring";
  connectivity: "from_visible_shape";
  provenance: "ocr_owner_surface";
};

export type TextRenderLayer = {
  id: string;
  zIndex: number;
  layer: TextLayer;
  provenance: "ocr";
};

export type SliceRenderLayer = {
  id: string;
  zIndex: number;
  sliceId: string;
  bbox: BBox;
  cutMode: CutMode;
  provenance: "confirmed_slice";
};
