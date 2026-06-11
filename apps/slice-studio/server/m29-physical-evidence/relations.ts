import type { BBox } from "../../shared/types";
import type { M29PhysicalRelation, M29Primitive } from "./types";

export function buildRelations(primitives: M29Primitive[]): M29PhysicalRelation[] {
  const relations: M29PhysicalRelation[] = [];
  let nextId = 1;
  for (let i = 0; i < primitives.length; i += 1) {
    for (let j = 0; j < primitives.length; j += 1) {
      if (i === j) continue;
      const a = primitives[i];
      const b = primitives[j];
      if (contains(a.bbox, b.bbox, 2) && area(a.bbox) > area(b.bbox)) {
        relations.push({
          id: `rel_${String(nextId).padStart(4, "0")}`,
          kind: "contains_bbox",
          fromId: a.id,
          toId: b.id,
          ratio: intersectionRatio(a.bbox, b.bbox)
        });
        nextId += 1;
        continue;
      }
      if (a.primitiveType !== "text_region" && b.primitiveType === "text_region") {
        const distance = bboxDistance(a.bbox, b.bbox);
        if (distance <= 12) {
          relations.push({
            id: `rel_${String(nextId).padStart(4, "0")}`,
            kind: "near_text",
            fromId: a.id,
            toId: b.id,
            distance
          });
          nextId += 1;
        }
      }
    }
  }
  return relations;
}

function contains(parent: BBox, child: BBox, tolerance: number): boolean {
  return parent.x - tolerance <= child.x &&
    parent.y - tolerance <= child.y &&
    parent.x + parent.width + tolerance >= child.x + child.width &&
    parent.y + parent.height + tolerance >= child.y + child.height;
}

function area(bbox: BBox): number {
  return Math.max(0, bbox.width) * Math.max(0, bbox.height);
}

function intersectionRatio(a: BBox, b: BBox): number {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.width, b.x + b.width);
  const y2 = Math.min(a.y + a.height, b.y + b.height);
  const intersection = area({ x: x1, y: y1, width: x2 - x1, height: y2 - y1 });
  if (area(b) === 0) return 0;
  return Math.round((intersection / area(b)) * 10000) / 10000;
}

function bboxDistance(a: BBox, b: BBox): number {
  const ax2 = a.x + a.width;
  const ay2 = a.y + a.height;
  const bx2 = b.x + b.width;
  const by2 = b.y + b.height;
  const dx = Math.max(Math.max(b.x - ax2, a.x - bx2), 0);
  const dy = Math.max(Math.max(b.y - ay2, a.y - by2), 0);
  return Math.round(Math.sqrt(dx * dx + dy * dy) * 100) / 100;
}
