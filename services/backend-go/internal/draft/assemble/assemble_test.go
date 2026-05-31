package assemble

import (
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	m29contract "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
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

func findLayer(graph contract.Document, kind contract.LayerKind) *contract.Layer {
	for i := range graph.Layers {
		if graph.Layers[i].Kind == kind {
			return &graph.Layers[i]
		}
	}
	return nil
}
