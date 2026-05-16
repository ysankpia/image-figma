import type { DSLLayout } from "@image-figma/dsl-schema";
import type { FigmaAdapter, FigmaNode } from "./types";

export function applyLayout(figma: FigmaAdapter, node: FigmaNode, layout: DSLLayout): void {
  figma.setLayout(node, {
    x: layout.x,
    y: layout.y,
    width: layout.width,
    height: layout.height
  });
}
