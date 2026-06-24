import { containsBbox } from "../shared/bbox";
import type { BBox, SliceRecord } from "../shared/types";
import type { OcrLine } from "./text-ocr";

// Minimal DraftRuntimeDSL types (mirrors archive/legacy-code/packages/dsl-schema/src/draftRuntimeTypes.ts)
export type DraftNode = {
  id: string;
  type: "frame" | "image" | "text" | "shape";
  name?: string;
  bbox: BBox;
  style?: {
    fill?: string | null;
    color?: string;
    radius?: number;
    fontSize?: number;
    fontWeight?: number;
    fontFamily?: string;
    clipContent?: boolean;
  };
  text?: { characters: string };
  image?: { assetId?: string; mode?: "fill" | "fit" };
  children?: DraftNode[];
};

export type DraftAsset = {
  assetId: string;
  type: "image";
  url: string;
  format: "png";
  width?: number;
  height?: number;
};

export type DraftRuntimeDSL = {
  version: "1.0";
  kind: "draft_runtime";
  taskId: string;
  page: { name?: string; width: number; height: number };
  assets: DraftAsset[];
  root: DraftNode;
};

type SliceWithAbsoluteBbox = SliceRecord & { _absX: number; _absY: number };

function sliceArea(s: SliceRecord): number {
  return s.bbox.width * s.bbox.height;
}

// Returns absolute bbox of a slice (same as stored bbox since slices are page-absolute)
function absBbox(s: SliceRecord): BBox {
  return s.bbox;
}

export function compileSlicesToDraft(
  slices: SliceRecord[],
  ocrLines: OcrLine[],
  page: { id: string; displayName: string; width: number; height: number },
  projectId: string,
  serverBaseUrl: string
): DraftRuntimeDSL {
  // Sort by area descending so larger (parent candidates) come first
  const sorted = [...slices].sort((a, b) => sliceArea(b) - sliceArea(a));

  // Map slice id → parent slice id (smallest containing slice)
  const parentOf = new Map<string, string>();
  for (let i = sorted.length - 1; i >= 0; i--) {
    const child = sorted[i]!;
    let bestParentId: string | null = null;
    let bestParentArea = Infinity;
    for (let j = 0; j < i; j++) {
      const candidate = sorted[j]!;
      if (
        containsBbox(absBbox(candidate), absBbox(child)) &&
        sliceArea(candidate) < bestParentArea
      ) {
        bestParentId = candidate.id;
        bestParentArea = sliceArea(candidate);
      }
    }
    if (bestParentId !== null) {
      // Enforce max depth 3
      let depth = 1;
      let ancestor = bestParentId;
      while (parentOf.has(ancestor)) {
        ancestor = parentOf.get(ancestor)!;
        depth++;
      }
      if (depth < 3) {
        parentOf.set(child.id, bestParentId);
      }
    }
  }

  const assets: DraftAsset[] = [];
  const nodeMap = new Map<string, DraftNode>();

  for (const slice of sorted) {
    const isContainer = slice.cutMode === "card";
    const node: DraftNode = {
      id: slice.id,
      type: isContainer ? "frame" : "image",
      name: slice.name,
      bbox: { x: 0, y: 0, width: slice.bbox.width, height: slice.bbox.height }, // relative coords set below
      style: isContainer ? { fill: null, clipContent: true } : undefined,
      image: isContainer
        ? undefined
        : { assetId: slice.id, mode: "fill" },
    };

    if (!isContainer) {
      assets.push({
        assetId: slice.id,
        type: "image",
        url: `${serverBaseUrl}/api/projects/${projectId}/slices/${slice.id}/preview.png`,
        format: "png",
        width: slice.bbox.width,
        height: slice.bbox.height,
      });
    }

    nodeMap.set(slice.id, node);
  }

  // Set parent-relative bbox coords and build children arrays
  for (const slice of sorted) {
    const node = nodeMap.get(slice.id)!;
    const parentId = parentOf.get(slice.id);
    if (parentId) {
      const parentSlice = slices.find((s) => s.id === parentId)!;
      node.bbox = {
        x: slice.bbox.x - parentSlice.bbox.x,
        y: slice.bbox.y - parentSlice.bbox.y,
        width: slice.bbox.width,
        height: slice.bbox.height,
      };
      const parentNode = nodeMap.get(parentId)!;
      parentNode.children = parentNode.children ?? [];
      parentNode.children.push(node);
    } else {
      // Root-level slice: keep absolute coords
      node.bbox = { ...slice.bbox };
    }
  }

  // Assign OCR text lines to deepest containing node
  const minConfidence = 30;
  const absoluteBboxOf = (sliceId: string): BBox => {
    return slices.find((s) => s.id === sliceId)!.bbox;
  };

  for (const line of ocrLines) {
    if (line.confidence < minConfidence) continue;
    const centerX = line.bbox.x + line.bbox.width / 2;
    const centerY = line.bbox.y + line.bbox.height / 2;

    // Find deepest (smallest area) containing slice
    let bestSliceId: string | null = null;
    let bestArea = Infinity;
    for (const slice of sorted) {
      const ab = absoluteBboxOf(slice.id);
      if (
        centerX >= ab.x &&
        centerX <= ab.x + ab.width &&
        centerY >= ab.y &&
        centerY <= ab.y + ab.height &&
        sliceArea(slice) < bestArea
      ) {
        bestSliceId = slice.id;
        bestArea = sliceArea(slice);
      }
    }

    if (bestSliceId === null) continue;
    const parentSlice = slices.find((s) => s.id === bestSliceId)!;
    const textNode: DraftNode = {
      id: `text_${line.bbox.x}_${line.bbox.y}`,
      type: "text",
      name: line.text,
      bbox: {
        x: line.bbox.x - parentSlice.bbox.x,
        y: line.bbox.y - parentSlice.bbox.y,
        width: line.bbox.width,
        height: line.bbox.height,
      },
      text: { characters: line.text },
      style: {
        fontSize: Math.max(10, Math.round(line.bbox.height * 0.72)),
        color: "#000000",
        fontFamily: "Inter",
      },
    };
    const parentNode = nodeMap.get(bestSliceId)!;
    parentNode.children = parentNode.children ?? [];
    parentNode.children.push(textNode);
  }

  // Root-level nodes (no parent)
  const rootChildren = sorted
    .filter((s) => !parentOf.has(s.id))
    .map((s) => nodeMap.get(s.id)!);

  return {
    version: "1.0",
    kind: "draft_runtime",
    taskId: `ss_${projectId}_${page.id}`,
    page: { name: page.displayName, width: page.width, height: page.height },
    assets,
    root: {
      id: "root",
      type: "frame",
      name: page.displayName,
      bbox: { x: 0, y: 0, width: page.width, height: page.height },
      style: { fill: null, clipContent: true },
      children: rootChildren,
    },
  };
}
