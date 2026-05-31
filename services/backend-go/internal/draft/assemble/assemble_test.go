package assemble

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	m29contract "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	visiondetector "github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

func TestBuildEmitsEditableTextAboveRasterAndShape(t *testing.T) {
	graph, err := Build(Input{
		Image: contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{Tokens: []evidence.Token{
			{
				ID:                 "token_surface",
				TokenType:          "surface_region_token",
				BBox:               m29contract.BBox{X: 20, Y: 20, Width: 200, Height: 80},
				SourcePrimitiveIDs: []string{"prim_surface"},
				Disposition:        "main",
				Reasons:            []string{"surface_region"},
				Measurements:       evidence.TokenMeasurements{MeanColor: "#F5F5F5", CornerRadiusEstimate: 8},
			},
			{
				ID:                 "token_raster",
				TokenType:          "raster_region_token",
				BBox:               m29contract.BBox{X: 40, Y: 35, Width: 96, Height: 48},
				SourcePrimitiveIDs: []string{"prim_raster"},
				Disposition:        "main",
				Reasons:            []string{"raster_region"},
				CompileHints:       m29contract.CompileHints{CanBeImage: true},
			},
			{
				ID:                 "token_text",
				TokenType:          "text_token",
				BBox:               m29contract.BBox{X: 54, Y: 50, Width: 80, Height: 20},
				SourcePrimitiveIDs: []string{"prim_text"},
				Disposition:        "main",
				Reasons:            []string{"ocr_text_region"},
				Content:            evidence.TokenContent{Text: "确认协议并支付"},
			},
		}},
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	text := findLayer(graph, contract.LayerText)
	raster := findLayer(graph, contract.LayerRaster)
	shape := findLayer(graph, contract.LayerShape)
	if text == nil || raster == nil || shape == nil {
		t.Fatalf("expected text/raster/shape layers, got %+v", graph.Layers)
	}
	if text.Z <= raster.Z || raster.Z <= shape.Z {
		t.Fatalf("bad z order: text=%d raster=%d shape=%d", text.Z, raster.Z, shape.Z)
	}
	if text.Text == nil || text.Text.Characters != "确认协议并支付" {
		t.Fatalf("bad text payload: %+v", text.Text)
	}
	if raster.Raster == nil || raster.Raster.AssetID == "" || len(graph.Assets) != 1 {
		t.Fatalf("expected raster asset, layer=%+v assets=%+v", raster, graph.Assets)
	}
	if shape.Shape == nil || shape.Shape.Fill != "#F5F5F5" || shape.Shape.CornerRadius != 8 {
		t.Fatalf("bad shape payload: %+v", shape.Shape)
	}
}

func TestBuildSuppressesVisibleFullImageRaster(t *testing.T) {
	graph, err := Build(Input{
		Image: contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{Tokens: []evidence.Token{{
			ID:                 "token_full",
			TokenType:          "raster_region_token",
			BBox:               m29contract.BBox{X: 0, Y: 0, Width: 400, Height: 300},
			SourcePrimitiveIDs: []string{"prim_full"},
			Disposition:        "main",
			Reasons:            []string{"raster_region"},
			CompileHints:       m29contract.CompileHints{CanBeImage: true},
		}}},
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if layer := findLayer(graph, contract.LayerRaster); layer != nil {
		t.Fatalf("full image raster should not be visible: %+v", layer)
	}
	if len(graph.Assets) != 0 {
		t.Fatalf("full image raster should not create asset: %+v", graph.Assets)
	}
}

func TestBuildIgnoresReviewAndSuppressedTokens(t *testing.T) {
	graph, err := Build(Input{
		Image: contract.ImageMeta{Width: 200, Height: 200},
		Tokens: evidence.Document{Tokens: []evidence.Token{
			{ID: "review", TokenType: "text_token", BBox: m29contract.BBox{X: 10, Y: 10, Width: 80, Height: 20}, Disposition: "review", Content: evidence.TokenContent{Text: "review"}},
			{ID: "suppressed", TokenType: "text_token", BBox: m29contract.BBox{X: 10, Y: 40, Width: 80, Height: 20}, Disposition: "suppressed", Content: evidence.TokenContent{Text: "suppressed"}},
		}},
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if layer := findLayer(graph, contract.LayerText); layer != nil {
		t.Fatalf("non-main tokens should not emit visible text: %+v", layer)
	}
}

func TestBuildSuppressesDuplicateShapeOwners(t *testing.T) {
	graph, err := Build(Input{
		Image: contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{Tokens: []evidence.Token{
			{
				ID:          "shape_a",
				TokenType:   "surface_region_token",
				BBox:        m29contract.BBox{X: 40, Y: 40, Width: 120, Height: 80},
				Disposition: "main",
				Reasons:     []string{"surface_region"},
			},
			{
				ID:          "shape_b",
				TokenType:   "surface_region_token",
				BBox:        m29contract.BBox{X: 41, Y: 41, Width: 118, Height: 79},
				Disposition: "main",
				Reasons:     []string{"surface_region"},
			},
		}},
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	visibleShapes := 0
	suppressedShapes := 0
	for _, layer := range graph.Layers {
		if layer.Kind != contract.LayerShape {
			continue
		}
		if layer.Visible {
			visibleShapes++
		}
		if layer.Decision.State == contract.DecisionSuppress {
			suppressedShapes++
		}
	}
	if visibleShapes != 1 || suppressedShapes != 1 {
		t.Fatalf("expected one visible and one suppressed duplicate shape, visible=%d suppressed=%d layers=%+v", visibleShapes, suppressedShapes, graph.Layers)
	}
}

func TestBuildCreatesMajorGroups(t *testing.T) {
	graph, err := Build(Input{
		Image: contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{Tokens: []evidence.Token{
			{
				ID:          "surface",
				TokenType:   "surface_region_token",
				BBox:        m29contract.BBox{X: 20, Y: 20, Width: 180, Height: 120},
				Disposition: "main",
				Reasons:     []string{"surface_region"},
			},
			{
				ID:           "raster",
				TokenType:    "raster_region_token",
				BBox:         m29contract.BBox{X: 40, Y: 40, Width: 60, Height: 50},
				Disposition:  "main",
				Reasons:      []string{"raster_region"},
				CompileHints: m29contract.CompileHints{CanBeImage: true},
			},
			{
				ID:          "text",
				TokenType:   "text_token",
				BBox:        m29contract.BBox{X: 110, Y: 48, Width: 52, Height: 18},
				Disposition: "main",
				Content:     evidence.TokenContent{Text: "Title"},
			},
		}},
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if len(graph.Groups) != 1 {
		t.Fatalf("expected one major group, got %+v", graph.Groups)
	}
	if len(graph.Groups[0].ChildLayerIDs) != 3 {
		t.Fatalf("expected group to own three layers, got %+v", graph.Groups[0])
	}
	for _, id := range graph.Groups[0].ChildLayerIDs {
		layer := findLayerByID(graph, id)
		if layer == nil || layer.GroupID != graph.Groups[0].ID {
			t.Fatalf("layer %s not assigned to group %+v", id, layer)
		}
	}
}

func TestBuildEmitsCompactVisionImageCandidate(t *testing.T) {
	graph, err := Build(Input{
		Image: contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{Tokens: []evidence.Token{{
			ID:          "text",
			TokenType:   "text_token",
			BBox:        m29contract.BBox{X: 20, Y: 20, Width: 80, Height: 20},
			Disposition: "main",
			Content:     evidence.TokenContent{Text: "Title"},
		}}},
		Detector: detectorDoc(visiondetector.Candidate{
			ID:         "cand_img",
			Role:       visiondetector.RoleImageView,
			Confidence: 0.91,
			BBox:       visiondetector.BBox{X: 120, Y: 48, Width: 96, Height: 72},
		}),
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	vision := findLayerByID(graph, "vision_image_0002")
	if vision == nil || vision.Kind != contract.LayerRaster || !vision.Visible {
		t.Fatalf("expected visible vision raster layer, got %+v", graph.Layers)
	}
	if vision.Decision.BBoxAuthority != contract.BBoxAuthorityVision {
		t.Fatalf("vision bbox authority = %q", vision.Decision.BBoxAuthority)
	}
	if vision.Raster == nil || vision.Raster.AssetID == "" {
		t.Fatalf("vision raster missing asset: %+v", vision)
	}
	if len(graph.Evidence) != 1 || graph.Evidence[0].State != contract.DecisionEmit || graph.Evidence[0].LayerID != vision.ID {
		t.Fatalf("expected emit evidence for vision candidate, got %+v", graph.Evidence)
	}
	text := findLayer(graph, contract.LayerText)
	if text == nil || text.Z <= vision.Z {
		t.Fatalf("text must remain above vision raster, text=%+v vision=%+v", text, vision)
	}
}

func TestBuildKeepsNonImageVisionRolesHintOnly(t *testing.T) {
	graph, err := Build(Input{
		Image:  contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{},
		Detector: detectorDoc(
			visiondetector.Candidate{ID: "button", Role: visiondetector.RoleButton, Confidence: 0.92, BBox: visiondetector.BBox{X: 20, Y: 20, Width: 100, Height: 40}},
			visiondetector.Candidate{ID: "bg", Role: visiondetector.RoleBackground, Confidence: 0.88, BBox: visiondetector.BBox{X: 0, Y: 0, Width: 400, Height: 80}},
			visiondetector.Candidate{ID: "list", Role: visiondetector.RoleListView, Confidence: 0.80, BBox: visiondetector.BBox{X: 0, Y: 80, Width: 400, Height: 180}},
		),
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if layer := findLayer(graph, contract.LayerRaster); layer != nil {
		t.Fatalf("non-image detector roles must not emit raster layers: %+v", layer)
	}
	if len(graph.Evidence) != 3 {
		t.Fatalf("expected three hint evidence items, got %+v", graph.Evidence)
	}
	for _, item := range graph.Evidence {
		if item.State != contract.DecisionHint {
			t.Fatalf("expected hint-only evidence, got %+v", graph.Evidence)
		}
	}
}

func TestBuildSuppressesLargeVisionImageCandidate(t *testing.T) {
	graph, err := Build(Input{
		Image:  contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{},
		Detector: detectorDoc(visiondetector.Candidate{
			ID:         "hero",
			Role:       visiondetector.RoleImageView,
			Confidence: 0.95,
			BBox:       visiondetector.BBox{X: 0, Y: 0, Width: 400, Height: 160},
		}),
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	if layer := findLayer(graph, contract.LayerRaster); layer != nil {
		t.Fatalf("large detector image should not emit visible raster: %+v", layer)
	}
	if len(graph.Evidence) != 1 || graph.Evidence[0].State != contract.DecisionSuppress {
		t.Fatalf("expected suppress evidence, got %+v", graph.Evidence)
	}
}

func TestBuildSuppressesDuplicateVisionImageCandidate(t *testing.T) {
	graph, err := Build(Input{
		Image: contract.ImageMeta{Width: 400, Height: 300},
		Tokens: evidence.Document{Tokens: []evidence.Token{{
			ID:           "raster",
			TokenType:    "raster_region_token",
			BBox:         m29contract.BBox{X: 80, Y: 60, Width: 100, Height: 80},
			Disposition:  "main",
			Reasons:      []string{"raster_region"},
			CompileHints: m29contract.CompileHints{CanBeImage: true},
		}}},
		Detector: detectorDoc(visiondetector.Candidate{
			ID:         "duplicate",
			Role:       visiondetector.RoleImageView,
			Confidence: 0.93,
			BBox:       visiondetector.BBox{X: 82, Y: 62, Width: 96, Height: 76},
		}),
	})
	if err != nil {
		t.Fatalf("Build() error = %v", err)
	}
	visibleRasters := 0
	for _, layer := range graph.Layers {
		if layer.Kind == contract.LayerRaster && layer.Visible {
			visibleRasters++
		}
	}
	if visibleRasters != 1 {
		t.Fatalf("expected only the M29 raster to remain visible, visible rasters=%d layers=%+v", visibleRasters, graph.Layers)
	}
	if len(graph.Evidence) != 1 || graph.Evidence[0].State != contract.DecisionSuppress {
		t.Fatalf("expected suppressed duplicate vision evidence, got %+v", graph.Evidence)
	}
}

func findLayer(graph contract.Document, kind contract.LayerKind) *contract.Layer {
	for i := range graph.Layers {
		if graph.Layers[i].Kind == kind {
			return &graph.Layers[i]
		}
	}
	return nil
}

func findLayerByID(graph contract.Document, id string) *contract.Layer {
	for i := range graph.Layers {
		if graph.Layers[i].ID == id {
			return &graph.Layers[i]
		}
	}
	return nil
}

func detectorDoc(candidates ...visiondetector.Candidate) *visiondetector.Document {
	out := &visiondetector.Document{
		Version:    visiondetector.CandidatesVersion,
		Candidates: append([]visiondetector.Candidate(nil), candidates...),
	}
	for i := range out.Candidates {
		if out.Candidates[i].Source.Kind == "" {
			out.Candidates[i].Source.Kind = "vision_detector"
		}
		if out.Candidates[i].Source.PassID == "" {
			out.Candidates[i].Source.PassID = "imageview"
		}
	}
	return out
}
