import { DSL_DEFAULTS } from "./defaults.js";
import type { DesignDSL, DSLElement, DSLLayout, DSLStyle } from "./types.js";

export function normalizeDSL(dsl: DesignDSL): DesignDSL {
  return {
    ...dsl,
    assets: dsl.assets ?? [],
    meta: dsl.meta ?? {},
    root: normalizeElement(dsl.root)
  };
}

export function normalizeElement(element: DSLElement): DSLElement {
  const style = normalizeStyle(element.style ?? {});
  const normalized: DSLElement = {
    ...element,
    role: element.role ?? DSL_DEFAULTS.role,
    name: element.name ?? makeElementName(element),
    layout: normalizeLayout(element.layout),
    style,
    children: Array.isArray(element.children)
      ? element.children.map((child) => normalizeElement(child))
      : [],
    meta: element.meta ?? {}
  };

  return normalized;
}

function normalizeStyle(style: DSLStyle): DSLStyle {
  return {
    ...style,
    opacity: style.opacity ?? DSL_DEFAULTS.opacity,
    visible: style.visible ?? DSL_DEFAULTS.visible
  };
}

function normalizeLayout(layout: DSLLayout): DSLLayout {
  return {
    x: roundToHalf(layout.x),
    y: roundToHalf(layout.y),
    width: roundToHalf(layout.width),
    height: roundToHalf(layout.height)
  };
}

function roundToHalf(value: number): number {
  return Math.round(value * 2) / 2;
}

function makeElementName(element: DSLElement): string {
  const label = element.type.charAt(0).toUpperCase() + element.type.slice(1);
  return `${label} / ${element.id}`;
}
