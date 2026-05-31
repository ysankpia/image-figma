package validate

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
)

func TestGraphRejectsVisibleReferenceImage(t *testing.T) {
	doc := baseDocument()
	doc.Layers = append(doc.Layers, contract.Layer{
		ID:      "ref",
		Kind:    contract.LayerReferenceImage,
		BBox:    geometry.Rect{Width: 100, Height: 100},
		Visible: true,
		Decision: contract.Decision{
			State:         contract.DecisionReferenceOnly,
			BBoxAuthority: contract.BBoxAuthoritySourceImage,
			Reason:        "source_reference",
		},
	})

	report := Graph(doc)
	assertFinding(t, report, "DRAFT_REFERENCE_IMAGE_VISIBLE")
}

func TestGraphRejectsVisibleFullImageBacking(t *testing.T) {
	doc := baseDocument()
	doc.Assets = append(doc.Assets, contract.Asset{ID: "asset_full", Type: "image"})
	doc.Layers = append(doc.Layers, contract.Layer{
		ID:      "full",
		Kind:    contract.LayerRaster,
		BBox:    geometry.Rect{Width: 100, Height: 100},
		Visible: true,
		Raster:  &contract.Raster{AssetID: "asset_full"},
		Decision: contract.Decision{
			State:         contract.DecisionEmit,
			BBoxAuthority: contract.BBoxAuthoritySourceImage,
			Reason:        "bad_full_backing",
		},
	})

	report := Graph(doc)
	assertFinding(t, report, "DRAFT_VISIBLE_FULL_IMAGE_BACKING")
}

func TestGraphRejectsMissingRasterAsset(t *testing.T) {
	doc := baseDocument()
	doc.Layers = append(doc.Layers, contract.Layer{
		ID:      "image",
		Kind:    contract.LayerRaster,
		BBox:    geometry.Rect{X: 10, Y: 10, Width: 20, Height: 20},
		Visible: true,
		Raster:  &contract.Raster{AssetID: "missing"},
		Decision: contract.Decision{
			State:         contract.DecisionEmit,
			BBoxAuthority: contract.BBoxAuthorityM29,
			Reason:        "compact_image",
		},
	})

	report := Graph(doc)
	assertFinding(t, report, "DRAFT_ASSET_NOT_FOUND")
}

func TestGraphRejectsTextCoveredByHigherRaster(t *testing.T) {
	doc := baseDocument()
	doc.Assets = append(doc.Assets, contract.Asset{ID: "asset_cover", Type: "image"})
	doc.Layers = append(doc.Layers,
		contract.Layer{
			ID:      "text",
			Kind:    contract.LayerText,
			BBox:    geometry.Rect{X: 10, Y: 10, Width: 50, Height: 12},
			Z:       10,
			Visible: true,
			Text:    &contract.Text{Characters: "Hello"},
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityOCR,
				Reason:        "ocr_text",
			},
		},
		contract.Layer{
			ID:      "cover",
			Kind:    contract.LayerRaster,
			BBox:    geometry.Rect{X: 0, Y: 0, Width: 80, Height: 40},
			Z:       20,
			Visible: true,
			Raster:  &contract.Raster{AssetID: "asset_cover"},
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityM29,
				Reason:        "bad_order",
			},
		},
	)

	report := Graph(doc)
	assertFinding(t, report, "DRAFT_TEXT_COVERED")
}

func TestGraphAcceptsTextAboveRaster(t *testing.T) {
	doc := baseDocument()
	doc.Assets = append(doc.Assets, contract.Asset{ID: "asset_cover", Type: "image"})
	doc.Layers = append(doc.Layers,
		contract.Layer{
			ID:      "cover",
			Kind:    contract.LayerRaster,
			BBox:    geometry.Rect{X: 0, Y: 0, Width: 80, Height: 40},
			Z:       10,
			Visible: true,
			Raster:  &contract.Raster{AssetID: "asset_cover"},
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityM29,
				Reason:        "compact_image",
			},
		},
		contract.Layer{
			ID:      "text",
			Kind:    contract.LayerText,
			BBox:    geometry.Rect{X: 10, Y: 10, Width: 50, Height: 12},
			Z:       20,
			Visible: true,
			Text:    &contract.Text{Characters: "Hello"},
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityOCR,
				Reason:        "ocr_text",
			},
		},
	)

	report := Graph(doc)
	if report.ErrorCount != 0 {
		t.Fatalf("expected no validation errors, got %+v", report.Findings)
	}
}

func TestGraphRejectsDuplicateVisibleOwners(t *testing.T) {
	doc := baseDocument()
	doc.Layers = append(doc.Layers,
		contract.Layer{
			ID:      "shape_a",
			Kind:    contract.LayerShape,
			BBox:    geometry.Rect{X: 10, Y: 10, Width: 60, Height: 40},
			Z:       10,
			Visible: true,
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityM29,
				Reason:        "surface",
			},
		},
		contract.Layer{
			ID:      "shape_b",
			Kind:    contract.LayerShape,
			BBox:    geometry.Rect{X: 11, Y: 11, Width: 59, Height: 39},
			Z:       11,
			Visible: true,
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityM29,
				Reason:        "surface",
			},
		},
	)

	report := Graph(doc)
	assertFinding(t, report, "DRAFT_DUPLICATE_VISIBLE_OWNER")
}

func TestGraphAcceptsBackgroundBehindRaster(t *testing.T) {
	doc := baseDocument()
	doc.Assets = append(doc.Assets, contract.Asset{ID: "asset_cover", Type: "image"})
	doc.Layers = append(doc.Layers,
		contract.Layer{
			ID:      "background",
			Kind:    contract.LayerShape,
			BBox:    geometry.Rect{X: 0, Y: 0, Width: 90, Height: 70},
			Z:       10,
			Visible: true,
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityM29,
				Reason:        "surface",
			},
		},
		contract.Layer{
			ID:      "cover",
			Kind:    contract.LayerRaster,
			BBox:    geometry.Rect{X: 10, Y: 10, Width: 60, Height: 40},
			Z:       20,
			Visible: true,
			Raster:  &contract.Raster{AssetID: "asset_cover"},
			Decision: contract.Decision{
				State:         contract.DecisionEmit,
				BBoxAuthority: contract.BBoxAuthorityM29,
				Reason:        "compact_image",
			},
		},
	)

	report := Graph(doc)
	if report.ErrorCount != 0 {
		t.Fatalf("expected no validation errors, got %+v", report.Findings)
	}
}

func baseDocument() contract.Document {
	return contract.Document{
		Version: contract.Version,
		Image:   contract.ImageMeta{Width: 100, Height: 100},
	}
}

func assertFinding(t *testing.T, report Report, code string) {
	t.Helper()
	for _, finding := range report.Findings {
		if finding.Code == code {
			return
		}
	}
	t.Fatalf("missing finding %s in %+v", code, report.Findings)
}
