import type { BBox, SliceRecord } from "../shared/types";
import type { TextLayer } from "./text-reconstruction";
import type { ControlSurfaceLayer, PageRenderPlan, RoundedRectShape, TextKnockout } from "./render-plan";

export function buildPageRenderPlan(input: {
  pageId: string;
  pageDirectory: string;
  width: number;
  height: number;
  textLayers: TextLayer[];
  slices: SliceRecord[];
}): PageRenderPlan {
  const controlSurfaces: ControlSurfaceLayer[] = [];
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
      textKnockouts: input.textLayers.map((layer) => textKnockoutFromLayer(layer)),
      surfaceKnockouts: []
    }
  };
}

function textKnockoutFromLayer(layer: TextLayer): TextKnockout {
  const clipShape = rasterOwnedControlClip(layer);
  if (!clipShape) {
    return {
      bbox: layer.knockoutBBox,
      foregroundColor: layer.color,
      provenance: "ocr_text"
    };
  }

  return {
    bbox: intersectionBox(layer.knockoutBBox, clipShape.bbox) || layer.knockoutBBox,
    clipShape,
    foregroundColor: layer.color,
    paintPadding: 0,
    provenance: "raster_owned_control_text"
  };
}

function rasterOwnedControlClip(layer: TextLayer): RoundedRectShape | null {
  const raw = layer.metadata.textLayoutOwnerSurface || layer.metadata.textOwnerSurface;
  if (!raw || typeof raw !== "object") return null;
  const candidate = raw as { bbox?: unknown; fill?: unknown; cornerRadius?: unknown; reason?: unknown };
  if (candidate.reason !== "filled_control_surface") return null;
  if (!candidate.bbox || typeof candidate.bbox !== "object" || typeof candidate.fill !== "string") return null;
  const bbox = candidate.bbox as Partial<BBox>;
  if (
    typeof bbox.x !== "number"
    || typeof bbox.y !== "number"
    || typeof bbox.width !== "number"
    || typeof bbox.height !== "number"
    || bbox.width <= 0
    || bbox.height <= 0
  ) return null;
  if (surfaceIsBackgroundLike(candidate.fill)) return null;
  const rounded = roundBBox(bbox as BBox);
  const maxRadius = Math.floor(Math.min(rounded.width, rounded.height) / 2);
  const cornerRadius = typeof candidate.cornerRadius === "number"
    ? Math.max(0, Math.round(candidate.cornerRadius))
    : maxRadius;
  return {
    kind: "rounded_rect",
    bbox: rounded,
    cornerRadius: Math.min(cornerRadius, maxRadius)
  };
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

function roundBBox(bbox: BBox): BBox {
  return {
    x: Math.round(bbox.x),
    y: Math.round(bbox.y),
    width: Math.round(bbox.width),
    height: Math.round(bbox.height)
  };
}

function intersectionBox(a: BBox, b: BBox): BBox | null {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.width, b.x + b.width);
  const bottom = Math.min(a.y + a.height, b.y + b.height);
  if (right <= left || bottom <= top) return null;
  return { x: left, y: top, width: right - left, height: bottom - top };
}
