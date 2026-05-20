import type { DSLStyle } from "@image-figma/dsl-schema";
import type { FigmaAdapter, FigmaNode, FigmaPaint, RGBColor } from "./types";

export function applyBaseStyle(figma: FigmaAdapter, node: FigmaNode, style: DSLStyle | undefined): void {
  if (!style) {
    return;
  }

  if (style.visible !== undefined) {
    figma.setVisible(node, style.visible);
  }
  if (style.opacity !== undefined) {
    figma.setOpacity(node, style.opacity);
  }
  if (style.fill === null) {
    figma.setFills(node, []);
  }
  if (typeof style.fill === "string") {
    figma.setFills(node, [solidPaint(style.fill)]);
  }
  if (style.stroke) {
    figma.setStrokes(node, [solidPaint(style.stroke.color)], style.stroke.width);
  }
  if (typeof style.radius === "number") {
    figma.setCornerRadius(node, Math.max(0, style.radius));
  }
}

export function solidPaint(hex: string, opacity = 1): FigmaPaint {
  return {
    type: "SOLID",
    color: parseHexColor(hex),
    opacity
  };
}

export function parseHexColor(hex: string): RGBColor {
  const normalized = hex.trim().replace("#", "");
  const value =
    normalized.length === 3
      ? normalized
          .split("")
          .map((char) => char + char)
          .join("")
      : normalized;

  if (!/^[0-9a-fA-F]{6}$/.test(value)) {
    return { r: 0, g: 0, b: 0 };
  }

  return {
    r: Number.parseInt(value.slice(0, 2), 16) / 255,
    g: Number.parseInt(value.slice(2, 4), 16) / 255,
    b: Number.parseInt(value.slice(4, 6), 16) / 255
  };
}
