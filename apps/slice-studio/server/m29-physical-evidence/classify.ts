import type { M29CompileHints, M29Measurements, PixelComponent, PrimitiveClassification } from "./types";

export function classifyComponent(component: PixelComponent, measurements: M29Measurements, imageArea: number): PrimitiveClassification {
  const b = component.bbox;
  const minDim = Math.min(b.width, b.height);
  const maxDim = Math.max(b.width, b.height);
  const areaRatio = component.area / Math.max(1, imageArea);
  const aspect = maxDim / Math.max(1, minDim);

  if (minDim <= 2 && maxDim >= 12) {
    return {
      primitiveType: "line",
      compileHints: {
        canBeLayerBackground: false,
        canContainForeground: false,
        canBeImage: false,
        canBeIcon: false,
        hasStableRectGeometry: true,
        confidence: 0.86,
        reasons: ["thin_component", "long_axis"]
      }
    };
  }

  if (measurements.fillRatio >= 0.72 && measurements.colorCount <= 10 && measurements.edgeDensity <= 0.18) {
    return {
      primitiveType: "rect",
      compileHints: {
        canBeLayerBackground: areaRatio >= 0.0015,
        canContainForeground: areaRatio >= 0.003,
        canBeImage: false,
        canBeIcon: false,
        hasStableRectGeometry: true,
        confidence: clampFloat(0.72 + measurements.fillRatio * 0.2, 0, 0.95),
        reasons: ["stable_rect", "low_texture"]
      }
    };
  }

  if (measurements.colorCount <= 12 && measurements.edgeDensity <= 0.22 && areaRatio >= 0.0008 && minDim >= 18 && maxDim <= 220) {
    return {
      primitiveType: "surface_region",
      compileHints: surfaceHint(["control_surface_component", "low_texture_control_surface"])
    };
  }

  if (areaRatio >= 0.004 && (measurements.colorCount >= 24 || measurements.edgeDensity >= 0.22 || measurements.textureScore >= 0.45)) {
    return {
      primitiveType: "image_region",
      compileHints: {
        canBeLayerBackground: false,
        canContainForeground: false,
        canBeImage: true,
        canBeIcon: false,
        hasStableRectGeometry: false,
        confidence: clampFloat(0.55 + Math.min(measurements.textureScore, 0.4), 0, 0.92),
        reasons: ["high_texture_or_color_variance"]
      }
    };
  }

  if (areaRatio <= 0.01 && maxDim <= 128 && measurements.fillRatio >= 0.05) {
    return {
      primitiveType: "symbol_region",
      compileHints: {
        canBeLayerBackground: false,
        canContainForeground: false,
        canBeImage: false,
        canBeIcon: true,
        hasStableRectGeometry: false,
        confidence: 0.62,
        reasons: ["compact_foreground_component"]
      }
    };
  }

  if (aspect >= 8 && minDim <= 6) {
    return {
      primitiveType: "line",
      compileHints: {
        canBeLayerBackground: false,
        canContainForeground: false,
        canBeImage: false,
        canBeIcon: false,
        hasStableRectGeometry: true,
        confidence: 0.7,
        reasons: ["line_like_aspect"]
      }
    };
  }

  return {
    primitiveType: "unknown_region",
    compileHints: {
      canBeLayerBackground: false,
      canContainForeground: false,
      canBeImage: false,
      canBeIcon: false,
      hasStableRectGeometry: false,
      confidence: 0.35,
      reasons: ["unclassified_physical_component"]
    }
  };
}

export function surfaceHint(reasons: string[]): M29CompileHints {
  return {
    canBeLayerBackground: true,
    canContainForeground: true,
    canBeImage: false,
    canBeIcon: false,
    hasStableRectGeometry: true,
    confidence: 0.74,
    reasons
  };
}

function clampFloat(value: number, min: number, max: number): number {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}
