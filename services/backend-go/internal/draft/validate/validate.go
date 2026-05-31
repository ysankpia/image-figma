package validate

import (
	"fmt"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

type Severity string

const (
	SeverityError   Severity = "error"
	SeverityWarning Severity = "warning"
)

type Finding struct {
	Severity Severity `json:"severity"`
	Code     string   `json:"code"`
	LayerID  string   `json:"layerId,omitempty"`
	Message  string   `json:"message"`
}

type Report struct {
	Version      string    `json:"version"`
	ErrorCount   int       `json:"errorCount"`
	WarningCount int       `json:"warningCount"`
	Findings     []Finding `json:"findings,omitempty"`
}

func Graph(doc contract.Document) Report {
	report := Report{Version: "draft_validation_report.v1"}
	if doc.Version != contract.Version {
		report.addError("", "DRAFT_VERSION_INVALID", fmt.Sprintf("expected %s, got %q", contract.Version, doc.Version))
	}

	assetIDs := map[string]bool{}
	for _, asset := range doc.Assets {
		if asset.ID != "" {
			assetIDs[asset.ID] = true
		}
	}

	imageBounds := geometry.Rect{Width: doc.Image.Width, Height: doc.Image.Height}
	for _, layer := range doc.Layers {
		if layer.ID == "" {
			report.addError("", "DRAFT_LAYER_ID_MISSING", "layer id is required")
		}
		if layer.Kind == contract.LayerReferenceImage && layer.Visible {
			report.addError(layer.ID, "DRAFT_REFERENCE_IMAGE_VISIBLE", "reference image must not be visible")
		}
		if layer.Visible && layer.Kind == contract.LayerRaster && layer.Raster != nil {
			if layer.Raster.AssetID == "" {
				report.addError(layer.ID, "DRAFT_ASSET_ID_MISSING", "visible raster layer requires asset id")
			} else if !assetIDs[layer.Raster.AssetID] {
				report.addError(layer.ID, "DRAFT_ASSET_NOT_FOUND", "visible raster layer references missing asset")
			}
			if imageBounds.Area() > 0 && geometry.IoA(imageBounds, layer.BBox) >= 0.98 {
				report.addError(layer.ID, "DRAFT_VISIBLE_FULL_IMAGE_BACKING", "visible raster layer covers the full source image")
			}
		}
		if layer.Decision.State == "" || layer.Decision.Reason == "" {
			report.addError(layer.ID, "DRAFT_DECISION_MISSING", "layer decision state and reason are required")
		}
	}

	for _, text := range doc.Layers {
		if !text.Visible || text.Kind != contract.LayerText {
			continue
		}
		for _, cover := range doc.Layers {
			if !cover.Visible || cover.ID == text.ID || cover.Z <= text.Z {
				continue
			}
			if cover.Kind != contract.LayerRaster && cover.Kind != contract.LayerShape {
				continue
			}
			if geometry.IoA(text.BBox, cover.BBox) >= 0.80 {
				report.addError(text.ID, "DRAFT_TEXT_COVERED", fmt.Sprintf("text is covered by higher z layer %s", cover.ID))
			}
		}
	}

	return report
}

func (r *Report) addError(layerID, code, message string) {
	r.ErrorCount++
	r.Findings = append(r.Findings, Finding{
		Severity: SeverityError,
		Code:     code,
		LayerID:  layerID,
		Message:  message,
	})
}
