import { normalizeDSL } from "./normalize";
import { validateDSL } from "./validator";
import type {
  DesignDSL,
  DSLElement,
  DSLRepairRecord,
  DSLRepairResult,
  DSLRadius,
  DSLStyle
} from "./types";

export function repairDSL(dsl: DesignDSL): DSLRepairResult {
  const repairs: DSLRepairRecord[] = [];
  const repaired = normalizeDSL(cloneDSL(dsl));
  repairElement(repaired.root, "$.root", repairs);
  const validation = validateDSL(repaired);

  return {
    dsl: repaired,
    repairs,
    validation
  };
}

function repairElement(element: DSLElement, path: string, repairs: DSLRepairRecord[]): void {
  repairStyle(element, path, repairs);

  if (!Array.isArray(element.children)) {
    element.children = [];
    repairs.push({
      code: "CHILDREN_REPAIRED",
      message: "children was repaired to an empty array.",
      path: `${path}.children`,
      elementId: element.id
    });
  }

  element.children.forEach((child, index) => {
    repairElement(child, `${path}.children[${index}]`, repairs);
  });
}

function repairStyle(element: DSLElement, path: string, repairs: DSLRepairRecord[]): void {
  const style = element.style ?? {};
  let changed = false;

  if (typeof style.opacity === "number") {
    const clamped = clamp(style.opacity, 0, 1);
    if (clamped !== style.opacity) {
      style.opacity = clamped;
      changed = true;
      repairs.push({
        code: "OPACITY_CLAMPED",
        message: "opacity was clamped to 0..1.",
        path: `${path}.style.opacity`,
        elementId: element.id
      });
    }
  }

  if (typeof style.radius === "number" && style.radius < 0) {
    style.radius = 0;
    changed = true;
    repairs.push({
      code: "RADIUS_REPAIRED",
      message: "negative radius was repaired to 0.",
      path: `${path}.style.radius`,
      elementId: element.id
    });
  } else if (isRadiusObject(style.radius)) {
    repairRadiusObject(style, path, element.id, repairs);
    changed = true;
  }

  if (changed) {
    element.style = style;
  }
}

function repairRadiusObject(style: DSLStyle, path: string, elementId: string, repairs: DSLRepairRecord[]): void {
  const radius = style.radius as DSLRadius;
  for (const key of ["topLeft", "topRight", "bottomRight", "bottomLeft"] as const) {
    const value = radius[key];
    if (typeof value === "number" && value < 0) {
      radius[key] = 0;
      repairs.push({
        code: "RADIUS_REPAIRED",
        message: `negative ${key} radius was repaired to 0.`,
        path: `${path}.style.radius.${key}`,
        elementId
      });
    }
  }
}

function cloneDSL(dsl: DesignDSL): DesignDSL {
  return structuredClone(dsl);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function isRadiusObject(value: unknown): value is DSLRadius {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
