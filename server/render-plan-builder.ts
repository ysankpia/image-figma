import type { BBox, SliceRecord } from "../shared/types";
import type { TextLayer } from "./text-reconstruction";
import type { ControlSurfaceLayer, PageRenderPlan, SurfaceKnockout } from "./render-plan";

type ControlSurfaceCandidate = {
  key: string;
  visibleBBox: BBox;
  fill: string;
  cornerRadius: number;
  sourceTextId: string;
};

export function buildPageRenderPlan(input: {
  pageId: string;
  pageDirectory: string;
  width: number;
  height: number;
  textLayers: TextLayer[];
  slices: SliceRecord[];
}): PageRenderPlan {
  const controlSurfaces = controlSurfacesFromTextLayers(input.pageId, input.textLayers);
  const controlSurfaceTextIds = new Set(controlSurfaces.map((surface) => surface.sourceTextId));
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
        .filter((layer) => !controlSurfaceTextIds.has(layer.id))
        .map((layer) => layer.knockoutBBox),
      surfaceKnockouts: controlSurfaces.map((surface) => surface.knockout)
    }
  };
}

function controlSurfacesFromTextLayers(pageId: string, layers: TextLayer[]): ControlSurfaceLayer[] {
  const surfaces = new Map<string, ControlSurfaceCandidate>();
  for (const layer of layers) {
    const surface = parseControlSurface(layer);
    if (!surface) continue;
    if (surfaceIsBackgroundLike(surface.fill)) continue;
    if (!surfaces.has(surface.key)) surfaces.set(surface.key, surface);
  }

  return [...surfaces.values()].map((surface, index) => {
    const visibleBBox = roundBBox(surface.visibleBBox);
    const maxRadius = Math.floor(Math.min(visibleBBox.width, visibleBBox.height) / 2);
    const cornerRadius = Math.min(surface.cornerRadius, maxRadius);
    const knockout: SurfaceKnockout = {
      visibleShape: {
        kind: "rounded_rect",
        bbox: visibleBBox,
        cornerRadius
      },
      sourceOwnerRegion: {
        kind: "owner_band",
        pad: controlSurfaceOwnerPad(visibleBBox),
        fill: surface.fill,
        backgroundSample: "outside_ring",
        connectivity: "from_visible_shape",
        provenance: "ocr_owner_surface"
      },
      provenance: "ocr_owner_surface"
    };
    return {
      id: `${pageId}__control_surface_${String(index + 1).padStart(4, "0")}`,
      pageId,
      zIndex: index + 1,
      sourceTextId: surface.sourceTextId,
      visibleBBox,
      fill: surface.fill,
      cornerRadius,
      knockout,
      provenance: "ocr_owner_surface"
    };
  });
}

function parseControlSurface(layer: TextLayer): ControlSurfaceCandidate | null {
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
  const rounded = roundBBox(bbox as BBox);
  const maxRadius = Math.floor(Math.min(rounded.width, rounded.height) / 2);
  const cornerRadius = typeof candidate.cornerRadius === "number"
    ? Math.max(0, Math.round(candidate.cornerRadius))
    : maxRadius;
  const fill = candidate.fill;
  return {
    key: `${rounded.x}:${rounded.y}:${rounded.width}:${rounded.height}:${fill}`,
    visibleBBox: rounded,
    fill,
    cornerRadius: Math.min(cornerRadius, maxRadius),
    sourceTextId: layer.id
  };
}

function controlSurfaceOwnerPad(bbox: BBox): number {
  return clamp(Math.max(3, Math.ceil(Math.max(bbox.width, bbox.height) * 0.02)), 3, 8);
}

function surfaceIsBackgroundLike(fill: string): boolean {
  const rgb = rgbFromHex(fill);
  if (!rgb) return true;
  return rgb.r >= 245 && rgb.g >= 245 && rgb.b >= 245;
}

function roundBBox(bbox: BBox): BBox {
  return {
    x: Math.round(bbox.x),
    y: Math.round(bbox.y),
    width: Math.round(bbox.width),
    height: Math.round(bbox.height)
  };
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

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
