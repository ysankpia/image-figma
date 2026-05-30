package primitive

import (
	"math"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/components"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

func Classify(component components.Component, measurements contract.Measurements, imageArea int) (string, contract.CompileHints) {
	b := component.BBox
	minDim := min(b.Width, b.Height)
	maxDim := max(b.Width, b.Height)
	areaRatio := float64(component.Area) / float64(max(1, imageArea))
	aspect := float64(maxDim) / float64(max(1, minDim))

	if minDim <= 2 && maxDim >= 12 {
		return "line", contract.CompileHints{
			HasStableRectGeometry: true,
			Confidence:            0.86,
			Reasons:               []string{"thin_component", "long_axis"},
		}
	}

	if measurements.FillRatio >= 0.72 && measurements.ColorCount <= 10 && measurements.EdgeDensity <= 0.18 {
		return "rect", contract.CompileHints{
			CanBeLayerBackground:  areaRatio >= 0.0015,
			CanContainForeground:  areaRatio >= 0.003,
			HasStableRectGeometry: true,
			Confidence:            clampFloat(0.72+measurements.FillRatio*0.2, 0, 0.95),
			Reasons:               []string{"stable_rect", "low_texture"},
		}
	}

	if measurements.ColorCount <= 12 && measurements.EdgeDensity <= 0.22 && areaRatio >= 0.0008 && minDim >= 18 && maxDim <= 220 {
		return "surface_region", SurfaceHint([]string{"control_surface_component", "low_texture_control_surface"})
	}

	if areaRatio >= 0.004 && (measurements.ColorCount >= 24 || measurements.EdgeDensity >= 0.22 || measurements.TextureScore >= 0.45) {
		return "image_region", contract.CompileHints{
			CanBeImage: true,
			Confidence: clampFloat(0.55+math.Min(measurements.TextureScore, 0.4), 0, 0.92),
			Reasons:    []string{"high_texture_or_color_variance"},
		}
	}

	if areaRatio <= 0.01 && maxDim <= 128 && measurements.FillRatio >= 0.05 {
		return "symbol_region", contract.CompileHints{
			CanBeIcon:  true,
			Confidence: 0.62,
			Reasons:    []string{"compact_foreground_component"},
		}
	}

	if aspect >= 8 && minDim <= 6 {
		return "line", contract.CompileHints{
			HasStableRectGeometry: true,
			Confidence:            0.7,
			Reasons:               []string{"line_like_aspect"},
		}
	}

	return "unknown_region", contract.CompileHints{
		Confidence: 0.35,
		Reasons:    []string{"unclassified_physical_component"},
	}
}

func OCRHint() contract.CompileHints {
	return contract.CompileHints{
		Confidence: 1,
		Reasons:    []string{"ocr_text_bbox"},
	}
}

func SurfaceHint(reasons []string) contract.CompileHints {
	return contract.CompileHints{
		CanBeLayerBackground:  true,
		CanContainForeground:  true,
		HasStableRectGeometry: true,
		Confidence:            0.74,
		Reasons:               reasons,
	}
}
