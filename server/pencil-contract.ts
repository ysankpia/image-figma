import type { ZipFile } from "../shared/zip";

export type PencilNode = {
  id: string;
  type: "frame" | "rectangle" | "text";
  name: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  layout?: "none";
  fill?: string | { type: "image"; enabled: true; url: string; mode: "stretch" };
  cornerRadius?: number;
  content?: string;
  textGrowth?: "auto" | "fixed-width-height";
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: string;
  lineHeight?: number;
  letterSpacing?: number;
  textAlign?: "left" | "center";
  textAlignVertical?: "middle";
  clip?: boolean;
  locked?: boolean;
  visible?: boolean;
  opacity?: number;
  metadata?: Record<string, unknown>;
  children?: PencilNode[];
};

export type PencilDocument = {
  version: string;
  children: PencilNode[];
};

export function validatePencilPackage(document: PencilDocument, files: ZipFile[]): void {
  const fileNames = new Set(files.map((file) => file.name));
  const ids = new Set<string>();
  const visit = (node: PencilNode) => {
    if (ids.has(node.id)) throw new Error(`duplicate .pen node id: ${node.id}`);
    ids.add(node.id);
    if (node.fill && typeof node.fill === "object" && node.fill.type === "image") {
      validateImageRef(node.fill.url, fileNames, node.id);
    }
    if (node.type === "frame" && node.metadata?.type === "slice_studio_page" && node.clip !== true) {
      throw new Error(`Pencil contract violation: page frames must clip overflowing children on ${node.id}`);
    }
    if (node.type === "text" && node.metadata?.type === "slice_studio_editable_text") {
      if (node.textGrowth !== "fixed-width-height" || node.width === undefined || node.height === undefined) {
        throw new Error(`Pencil contract violation: editable text must use fixed render bounds on ${node.id}`);
      }
      if (!bboxMatchesMetadata(node, node.metadata.textRenderBBox)) {
        throw new Error(`Pencil contract violation: editable text node must match metadata.textRenderBBox on ${node.id}`);
      }
      if (node.lineHeight !== undefined) {
        throw new Error(`Pencil contract violation: editable text must not set lineHeight on ${node.id}`);
      }
      if (node.textAlignVertical !== "middle") {
        throw new Error(`Pencil contract violation: editable text must use vertical middle alignment on ${node.id}`);
      }
      if (hasVisibleFilledControlSurface(node.metadata.textLayoutOwnerSurface) && node.textAlign !== "center") {
        throw new Error(`Pencil contract violation: control-surface text must be center aligned on ${node.id}`);
      }
    }
    validateControlSurfaceSiblings(node);
    for (const child of node.children || []) visit(child);
  };
  for (const frame of document.children) visit(frame);
}

function bboxMatchesMetadata(node: PencilNode, value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const bbox = value as { x?: unknown; y?: unknown; width?: unknown; height?: unknown };
  return Math.round(Number(bbox.x)) === node.x
    && Math.round(Number(bbox.y)) === node.y
    && Math.round(Number(bbox.width)) === node.width
    && Math.round(Number(bbox.height)) === node.height;
}

function validateControlSurfaceSiblings(parent: PencilNode): void {
  const children = parent.children || [];
  if (!children.length) return;

  const controlSurfaceByTextId = new Map<string, { node: PencilNode; index: number }>();
  const controlSurfaceByKey = new Map<string, { node: PencilNode; index: number }>();
  for (const [index, child] of children.entries()) {
    if (child.type !== "rectangle" || child.metadata?.type !== "slice_studio_control_surface") continue;
    const sourceTextId = child.metadata.sourceTextId;
    if (typeof sourceTextId !== "string") {
      throw new Error(`Pencil contract violation: control surface missing sourceTextId on ${child.id}`);
    }
    if (typeof child.fill !== "string" || isBackgroundLikeHex(child.fill)) {
      throw new Error(`Pencil contract violation: control surface must have visible non-background fill on ${child.id}`);
    }
    if (typeof child.cornerRadius !== "number") {
      throw new Error(`Pencil contract violation: control surface must preserve cornerRadius on ${child.id}`);
    }
    controlSurfaceByTextId.set(sourceTextId, { node: child, index });
    controlSurfaceByKey.set(controlSurfaceKey(child), { node: child, index });
  }

  for (const [index, child] of children.entries()) {
    if (child.type !== "text" || child.metadata?.type !== "slice_studio_editable_text") continue;
    const ownerSurface = hasVisibleFilledControlSurface(child.metadata.textLayoutOwnerSurface)
      ? child.metadata.textLayoutOwnerSurface
      : child.metadata.textOwnerSurface;
    if (!hasVisibleFilledControlSurface(ownerSurface)) continue;
    const surface = controlSurfaceByTextId.get(child.id) || controlSurfaceByKey.get(controlSurfaceKeyFromOwnerSurface(ownerSurface));
    if (!surface) continue;
    if (surface.index >= index) {
      throw new Error(`Pencil contract violation: control surface must render below editable text on ${child.id}`);
    }
    const fill = (ownerSurface as { fill: string }).fill;
    if (surface.node.fill !== fill) {
      throw new Error(`Pencil contract violation: control surface fill mismatch on ${child.id}`);
    }
  }
}

function controlSurfaceKey(node: PencilNode): string {
  return `${node.x}:${node.y}:${node.width}:${node.height}:${node.fill}`;
}

function controlSurfaceKeyFromOwnerSurface(value: unknown): string {
  const surface = value as { bbox?: Partial<PencilNode>; fill?: unknown };
  const bbox = surface.bbox || {};
  return `${Math.round(Number(bbox.x))}:${Math.round(Number(bbox.y))}:${Math.round(Number(bbox.width))}:${Math.round(Number(bbox.height))}:${surface.fill}`;
}

function hasVisibleFilledControlSurface(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const surface = value as { reason?: unknown; fill?: unknown };
  return surface.reason === "filled_control_surface"
    && typeof surface.fill === "string"
    && !isBackgroundLikeHex(surface.fill);
}

function isBackgroundLikeHex(value: string): boolean {
  const rgb = rgbFromHex(value);
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

function validateImageRef(url: string, fileNames: Set<string>, nodeId: string): void {
  if (!url.startsWith("./assets/visible/")) {
    throw new Error(`Pencil contract violation: image url outside visible assets on ${nodeId}: ${url}`);
  }
  if (url.includes("://") || url.startsWith("/") || url.startsWith("../") || url.includes("/../")) {
    throw new Error(`Pencil contract violation: non-portable image url on ${nodeId}: ${url}`);
  }
  if (url.includes("debug/") || url.includes("raw") || url.includes("masks/")) {
    throw new Error(`Pencil contract violation: forbidden image url on ${nodeId}: ${url}`);
  }
  const fileName = url.slice(2);
  if (!fileNames.has(fileName)) {
    throw new Error(`Pencil contract violation: missing image asset on ${nodeId}: ${url}`);
  }
}
