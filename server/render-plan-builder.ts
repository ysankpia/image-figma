import type { BBox, SliceRecord } from "../shared/types";
import type { TextLayer } from "./text-reconstruction";
import type { ControlSurfaceLayer, PageRenderPlan } from "./render-plan";

export function buildPageRenderPlan(input: {
  pageId: string;
  pageDirectory: string;
  width: number;
  height: number;
  textLayers: TextLayer[];
  slices: SliceRecord[];
}): PageRenderPlan {
  const controlSurfaces: ControlSurfaceLayer[] = [];
  const rasterOwnedControlTextIds = new Set(
    input.textLayers
      .filter((layer) => hasRasterOwnedFilledControlSurface(layer))
      .map((layer) => layer.id)
  );
  return {
    pageId: input.pageId,
    pageDirectory: input.pageDirectory,
    width: input.width,
    height: input.height,
    layers: {
      remainder: {
        id: `${input.pageId}__remainder`,
        zIndex: 0,
        visibleBBox: { x: 0, y: 0, width: input.width, height: input.height },
        provenance: "original_image"
      },
      controlSurfaces,
      text: input.textLayers.map((layer, index) => ({
        id: layer.id,
        zIndex: controlSurfaces.length + index + 1,
        layer,
        provenance: "ocr" as const
      })),
      slices: input.slices.map((slice, index) => ({
        id: `${input.pageId}__slice_${String(index + 1).padStart(4, "0")}`,
        zIndex: controlSurfaces.length + input.textLayers.length + index + 1,
        sliceId: slice.id,
        bbox: { ...slice.bbox },
        cutMode: slice.cutMode,
        provenance: "confirmed_slice" as const
      }))
    },
    remainder: {
      textKnockouts: input.textLayers
        .filter((layer) => !rasterOwnedControlTextIds.has(layer.id))
        .map((layer) => layer.knockoutBBox),
      surfaceKnockouts: []
    }
  };
}

function hasRasterOwnedFilledControlSurface(layer: TextLayer): boolean {
  const raw = layer.metadata.textLayoutOwnerSurface || layer.metadata.textOwnerSurface;
  if (!raw || typeof raw !== "object") return false;
  const candidate = raw as { bbox?: unknown; fill?: unknown; reason?: unknown };
  if (candidate.reason !== "filled_control_surface") return false;
  if (!candidate.bbox || typeof candidate.bbox !== "object" || typeof candidate.fill !== "string") return false;
  const bbox = candidate.bbox as Partial<BBox>;
  if (
    typeof bbox.x !== "number"
    || typeof bbox.y !== "number"
    || typeof bbox.width !== "number"
    || typeof bbox.height !== "number"
    || bbox.width <= 0
    || bbox.height <= 0
  ) return false;
  return !surfaceIsBackgroundLike(candidate.fill);
}

function surfaceIsBackgroundLike(fill: string): boolean {
  const rgb = rgbFromHex(fill);
  if (!rgb) return true;
  return rgb.r >= 245 && rgb.g >= 245 && rgb.b >= 245;
}

function rgbFromHex(value: string): { r: number; g: number; b: number } | null {
  if (!value.startsWith("#")) return null;
  const hex = value.slice(1);
  if (!/^[0-9a-f]{6}$/iu.test(hex)) return null;
  return {
    r: Number.parseInt(hex.slice(0, 2), 16),
    g: Number.parseInt(hex.slice(2, 4), 16),
    b: Number.parseInt(hex.slice(4, 6), 16)
  };
}
