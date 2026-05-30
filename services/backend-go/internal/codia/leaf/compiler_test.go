package leaf

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

func TestCompileBuildsCodiaLeafIRFromM29EvidenceTokens(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	writeEvidenceTokens(t, input, evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  320,
			ImageHeight: 640,
			SourcePath:  "sample.png",
		},
		Tokens: []evidence.Token{
			{
				ID:        "token_text",
				TokenType: "text_token",
				BBox:      contract.BBox{X: 12, Y: 20, Width: 80, Height: 24},
				Content:   evidence.TokenContent{Text: "Hi"},
				Measurements: evidence.TokenMeasurements{
					Area: 1920,
				},
				Disposition:  "main",
				CompileHints: contract.CompileHints{Confidence: 1},
			},
			{
				ID:        "token_bg",
				TokenType: "surface_region_token",
				BBox:      contract.BBox{X: 8, Y: 16, Width: 120, Height: 40},
				Measurements: evidence.TokenMeasurements{
					Area:                 4800,
					MeanColor:            "#112233",
					CornerRadiusEstimate: 9,
				},
				Disposition:  "main",
				CompileHints: contract.CompileHints{Confidence: 0.8, Reasons: []string{"control_surface_candidate"}},
			},
			{
				ID:          "token_image",
				TokenType:   "raster_region_token",
				BBox:        contract.BBox{X: 100, Y: 80, Width: 64, Height: 64},
				Disposition: "main",
			},
			{
				ID:          "token_review",
				TokenType:   "unknown_token",
				BBox:        contract.BBox{X: 1, Y: 1, Width: 10, Height: 10},
				Disposition: "review",
			},
		},
	})
	doc, err := Compile(Options{TokenPath: input})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.SchemaName != ir.SchemaName || doc.Root.Role != ir.RoleRoot {
		t.Fatalf("unexpected document root: %#v", doc)
	}
	if doc.Root.SourceBBox.Width != 320 || doc.Root.SourceBBox.Height != 640 {
		t.Fatalf("unexpected root bbox: %#v", doc.Root.SourceBBox)
	}
	if len(doc.Root.Children) != 3 {
		t.Fatalf("expected 3 leaf children, got %d", len(doc.Root.Children))
	}
	if doc.Summary.RoleCounts[string(ir.RoleTextView)] != 1 ||
		doc.Summary.RoleCounts[string(ir.RoleBackground)] != 1 ||
		doc.Summary.RoleCounts[string(ir.RoleImageView)] != 1 {
		t.Fatalf("unexpected role counts: %#v", doc.Summary.RoleCounts)
	}
	text := doc.Root.Children[1]
	if text.Role != ir.RoleTextView || text.VisibleName != "Hi" || text.Text == nil || text.Text.Characters != "Hi" {
		t.Fatalf("expected TextView leaf, got %#v", text)
	}
	background := doc.Root.Children[0]
	if background.Role != ir.RoleBackground || background.Style.CornerRadius == nil || background.Style.CornerRadius.TopLeft != 9 {
		t.Fatalf("expected rounded Background leaf, got %#v", background)
	}
	if background.Style.FillPaints[0].Color == nil || background.Style.FillPaints[0].Color.R == 0 {
		t.Fatalf("expected parsed background color, got %#v", background.Style.FillPaints)
	}
	if background.Evidence[0].Kind != "control_surface_background" {
		t.Fatalf("expected control surface evidence to be preserved, got %#v", background.Evidence)
	}
	image := doc.Root.Children[2]
	if image.Role != ir.RoleImageView || image.Asset == nil || image.Asset.Kind != "crop" {
		t.Fatalf("expected ImageView crop leaf, got %#v", image)
	}
	if image.SchemaID != "ImageView_100_80_3" {
		t.Fatalf("expected deterministic schema id, got %q", image.SchemaID)
	}
}

func TestCompileAdmitsReviewUnknownOnlyWithForegroundEvidence(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	writeEvidenceTokens(t, input, evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  320,
			ImageHeight: 640,
		},
		Tokens: []evidence.Token{
			{
				ID:          "token_unknown_bg",
				TokenType:   "unknown_token",
				BBox:        contract.BBox{X: 20, Y: 20, Width: 160, Height: 44},
				Disposition: "review",
				Measurements: evidence.TokenMeasurements{
					MeanColor: "#eeeeee",
				},
			},
			{
				ID:          "token_text",
				TokenType:   "text_token",
				BBox:        contract.BBox{X: 48, Y: 30, Width: 80, Height: 20},
				Content:     evidence.TokenContent{Text: "Search"},
				Disposition: "main",
			},
			{
				ID:          "token_unknown_noise",
				TokenType:   "unknown_token",
				BBox:        contract.BBox{X: 200, Y: 20, Width: 80, Height: 30},
				Disposition: "review",
			},
		},
	})
	doc, err := Compile(Options{TokenPath: input})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Summary.RoleCounts[string(ir.RoleBackground)] != 1 || doc.Summary.RoleCounts[string(ir.RoleTextView)] != 1 {
		t.Fatalf("unexpected role counts: %#v", doc.Summary.RoleCounts)
	}
	var admitted ir.Node
	for _, child := range doc.Root.Children {
		if child.Role == ir.RoleBackground {
			admitted = child
			break
		}
	}
	if admitted.Evidence[0].Kind != "control_background_candidate" {
		t.Fatalf("expected control background candidate evidence, got %#v", admitted.Evidence)
	}
}

func TestCompileRoutesImageLikeSurfaceTokenToImageView(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	writeEvidenceTokens(t, input, evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  320,
			ImageHeight: 640,
		},
		Tokens: []evidence.Token{
			{
				ID:        "token_image_surface",
				TokenType: "surface_region_token",
				BBox:      contract.BBox{X: 42, Y: 80, Width: 52, Height: 50},
				Measurements: evidence.TokenMeasurements{
					Area:         2600,
					MeanColor:    "#85a7e5",
					ColorCount:   154,
					EdgeDensity:  0.15,
					TextureScore: 0.45,
				},
				Disposition: "main",
				CompileHints: contract.CompileHints{
					Confidence: 0.74,
					Reasons:    []string{"ocr_anchored_low_texture_surface", "local_surface_color_region"},
				},
			},
			{
				ID:        "token_control_surface",
				TokenType: "surface_region_token",
				BBox:      contract.BBox{X: 20, Y: 160, Width: 120, Height: 44},
				Measurements: evidence.TokenMeasurements{
					Area:         5280,
					MeanColor:    "#eeeeee",
					ColorCount:   18,
					TextureScore: 0.50,
				},
				Disposition: "main",
				CompileHints: contract.CompileHints{
					Confidence: 0.74,
					Reasons:    []string{"control_surface_candidate", "contrast_control_surface_candidate"},
				},
			},
		},
	})

	doc, err := Compile(Options{TokenPath: input})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Summary.RoleCounts[string(ir.RoleImageView)] != 1 ||
		doc.Summary.RoleCounts[string(ir.RoleBackground)] != 1 {
		t.Fatalf("expected one image-like surface and one background surface, got %#v", doc.Summary.RoleCounts)
	}
	var imageNode ir.Node
	for _, child := range doc.Root.Children {
		if child.SourceGUID == "token_image_surface" {
			imageNode = child
		}
	}
	if imageNode.Role != ir.RoleImageView || imageNode.Evidence[0].Kind != "image_surface_crop" || imageNode.Asset == nil {
		t.Fatalf("expected image-like surface to become ImageView crop, got %#v", imageNode)
	}
}

func TestCompileSuppressesLineLikeBackgroundTokens(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	writeEvidenceTokens(t, input, evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  320,
			ImageHeight: 640,
		},
		Tokens: []evidence.Token{
			{
				ID:          "token_separator",
				TokenType:   "layer_background_token",
				BBox:        contract.BBox{X: 20, Y: 120, Width: 260, Height: 4},
				Disposition: "main",
				Measurements: evidence.TokenMeasurements{
					MeanColor: "#eeeeee",
				},
			},
			{
				ID:          "token_surface_rule",
				TokenType:   "surface_region_token",
				BBox:        contract.BBox{X: 40, Y: 180, Width: 160, Height: 5},
				Disposition: "main",
				Measurements: evidence.TokenMeasurements{
					MeanColor: "#dddddd",
				},
			},
			{
				ID:          "token_background",
				TokenType:   "surface_region_token",
				BBox:        contract.BBox{X: 24, Y: 220, Width: 180, Height: 48},
				Disposition: "main",
				Measurements: evidence.TokenMeasurements{
					MeanColor: "#f8f8f8",
				},
			},
		},
	})

	doc, err := Compile(Options{TokenPath: input})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Summary.RoleCounts[string(ir.RoleBackground)] != 1 {
		t.Fatalf("expected only the real background to survive, got %#v", doc.Summary.RoleCounts)
	}
	if len(doc.Root.Children) != 1 || doc.Root.Children[0].SourceGUID != "token_background" {
		t.Fatalf("line-like background tokens should be suppressed, got %#v", doc.Root.Children)
	}
}

func TestWriteArtifactsWritesLeafIRAndReport(t *testing.T) {
	tmp := t.TempDir()
	doc := ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Source:     ir.Source{InputPath: "tokens"},
		Root: ir.Node{
			ID:         "root_0",
			Role:       ir.RoleRoot,
			SourceBBox: ir.BBox{Width: 100, Height: 100},
			FigmaBBox:  ir.BBox{Width: 100, Height: 100},
			FigmaType:  ir.FigmaFrame,
		},
		Summary: ir.Summary{
			NodeCount:       1,
			MaxDepth:        0,
			RoleCounts:      map[string]int{"root": 1},
			FigmaTypeCounts: map[string]int{"FRAME": 1},
		},
	}
	if err := WriteArtifacts(tmp, doc); err != nil {
		t.Fatalf("WriteArtifacts() error = %v", err)
	}
	for _, name := range []string{ArtifactName, "codia_leaf_ir_report.md"} {
		if _, err := os.Stat(filepath.Join(tmp, name)); err != nil {
			t.Fatalf("expected artifact %s: %v", name, err)
		}
	}
}

func writeEvidenceTokens(t *testing.T, path string, doc evidence.Document) {
	t.Helper()
	data, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}
