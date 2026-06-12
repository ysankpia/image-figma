package evidence

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
)

func TestCompilePreservesTextAndSuppressesRasterFragments(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "m29_physical_evidence.v1.json")
	source := contract.Document{
		SchemaName: "M29PhysicalEvidence",
		Version:    "1.0",
		Image:      contract.ImageInfo{Width: 400, Height: 300},
		Primitives: []contract.Primitive{
			{ID: "p_text", PrimitiveType: "text_region", BBox: contract.BBox{X: 10, Y: 10, Width: 80, Height: 20}},
			{ID: "p_image", PrimitiveType: "image_region", BBox: contract.BBox{X: 100, Y: 40, Width: 200, Height: 120}},
			{ID: "p_frag", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 130, Y: 60, Width: 8, Height: 8}},
			{ID: "p_icon_a", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 20, Y: 220, Width: 12, Height: 12}},
			{ID: "p_icon_b", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 35, Y: 222, Width: 12, Height: 12}},
		},
	}
	writeSource(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.PrimitiveCount != 5 {
		t.Fatalf("unexpected primitive count: %#v", doc.Diagnostics)
	}
	if doc.Diagnostics.TokenTypeCounts["text_token"] != 1 {
		t.Fatalf("expected one text token: %#v", doc.Diagnostics.TokenTypeCounts)
	}
	if doc.Diagnostics.TokenTypeCounts["texture_fragment_token"] != 1 {
		t.Fatalf("expected one suppressed texture fragment: %#v", doc.Diagnostics.TokenTypeCounts)
	}
	if doc.Diagnostics.TokenTypeCounts["symbol_cluster_token"] != 1 {
		t.Fatalf("expected one symbol cluster: %#v", doc.Diagnostics.TokenTypeCounts)
	}
	assertFileExists(t, filepath.Join(tmp, "evidence_tokens.v1.json"))
}

func TestCompileDemotesOversizedSymbolClusterToReview(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "m29_physical_evidence.v1.json")
	source := contract.Document{
		SchemaName: "M29PhysicalEvidence",
		Version:    "1.0",
		Image:      contract.ImageInfo{Width: 500, Height: 300},
		Primitives: []contract.Primitive{
			{ID: "p_a", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 10, Y: 20, Width: 12, Height: 6}},
			{ID: "p_b", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 28, Y: 20, Width: 12, Height: 6}},
			{ID: "p_c", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 46, Y: 20, Width: 12, Height: 6}},
			{ID: "p_d", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 64, Y: 20, Width: 12, Height: 6}},
			{ID: "p_e", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 82, Y: 20, Width: 12, Height: 6}},
			{ID: "p_f", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 100, Y: 20, Width: 12, Height: 6}},
		},
	}
	writeSource(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.ReviewTokenCount == 0 {
		t.Fatalf("expected review token count, got %#v", doc.Diagnostics)
	}
	if doc.Diagnostics.HighAspectClusterReviewCount == 0 {
		t.Fatalf("expected high aspect cluster review count, got %#v", doc.Diagnostics)
	}
	for _, token := range doc.Tokens {
		if token.TokenType == "symbol_cluster_token" && token.Disposition != "review" {
			t.Fatalf("expected symbol cluster review disposition, got %#v", token)
		}
	}
}

func TestCompilePreservesSurfaceRegionTokenInsideRasterParent(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "m29_physical_evidence.v1.json")
	source := contract.Document{
		SchemaName: "M29PhysicalEvidence",
		Version:    "1.0",
		Image:      contract.ImageInfo{Width: 500, Height: 300},
		Primitives: []contract.Primitive{
			{ID: "p_raster", PrimitiveType: "image_region", BBox: contract.BBox{X: 0, Y: 0, Width: 500, Height: 160}},
			{
				ID:            "p_surface",
				PrimitiveType: "surface_region",
				BBox:          contract.BBox{X: 30, Y: 40, Width: 260, Height: 42},
				Measurements:  contract.Measurements{CornerRadiusEstimate: 12},
			},
			{ID: "p_text", PrimitiveType: "text_region", BBox: contract.BBox{X: 70, Y: 50, Width: 120, Height: 20}},
			{ID: "p_icon", PrimitiveType: "symbol_region", BBox: contract.BBox{X: 44, Y: 50, Width: 18, Height: 18}},
		},
	}
	writeSource(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.TokenTypeCounts["surface_region_token"] != 1 {
		t.Fatalf("expected surface_region_token, got %#v", doc.Diagnostics.TokenTypeCounts)
	}
	for _, token := range doc.Tokens {
		if token.TokenType == "surface_region_token" && token.Disposition != "main" {
			t.Fatalf("surface token should stay main, got %#v", token)
		}
		if token.TokenType == "surface_region_token" && token.Measurements.CornerRadiusEstimate != 12 {
			t.Fatalf("surface token should preserve corner radius estimate, got %#v", token.Measurements)
		}
	}
	if doc.Diagnostics.TokenTypeCounts["symbol_cluster_token"] != 1 {
		t.Fatalf("symbol inside surface should stay foreground token, got %#v", doc.Diagnostics.TokenTypeCounts)
	}
	if doc.Diagnostics.TokenTypeCounts["texture_fragment_token"] != 0 {
		t.Fatalf("surface foreground should not be suppressed as raster texture, got %#v", doc.Diagnostics.TokenTypeCounts)
	}
}

func TestCompilePreservesForegroundSymbolsInsideRasterParent(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "m29_physical_evidence.v1.json")
	source := contract.Document{
		SchemaName: "M29PhysicalEvidence",
		Version:    "1.0",
		Image:      contract.ImageInfo{Width: 500, Height: 300},
		Primitives: []contract.Primitive{
			{ID: "p_raster", PrimitiveType: "image_region", BBox: contract.BBox{X: 0, Y: 0, Width: 500, Height: 240}},
			{
				ID:            "p_icon",
				PrimitiveType: "symbol_region",
				BBox:          contract.BBox{X: 120, Y: 120, Width: 34, Height: 34},
				CompileHints:  contract.CompileHints{CanBeIcon: true, Reasons: []string{"compact_foreground_component"}},
			},
			{
				ID:            "p_rule",
				PrimitiveType: "line",
				BBox:          contract.BBox{X: 180, Y: 130, Width: 42, Height: 2},
				CompileHints:  contract.CompileHints{HasStableRectGeometry: true, Reasons: []string{"thin_component"}},
			},
		},
	}
	writeSource(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.SuppressedCount != 0 {
		t.Fatalf("foreground evidence inside raster should stay available, got %#v", doc.Diagnostics)
	}
	if doc.Diagnostics.TokenTypeCounts["symbol_cluster_token"] != 1 {
		t.Fatalf("expected preserved icon foreground, got %#v", doc.Diagnostics.TokenTypeCounts)
	}
	if doc.Diagnostics.TokenTypeCounts["line_token"] != 1 {
		t.Fatalf("expected preserved line foreground, got %#v", doc.Diagnostics.TokenTypeCounts)
	}
}

func TestCompilePreservesInternalRasterCropCandidates(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "m29_physical_evidence.v1.json")
	source := contract.Document{
		SchemaName: "M29PhysicalEvidence",
		Version:    "1.0",
		Image:      contract.ImageInfo{Width: 500, Height: 500},
		Primitives: []contract.Primitive{
			{
				ID:            "p_parent",
				PrimitiveType: "image_region",
				BBox:          contract.BBox{X: 20, Y: 40, Width: 440, Height: 360},
				CompileHints:  contract.CompileHints{CanBeImage: true, Reasons: []string{"high_texture_or_color_variance"}},
			},
			{
				ID:            "p_crop",
				PrimitiveType: "image_region",
				BBox:          contract.BBox{X: 380, Y: 100, Width: 42, Height: 150},
				CompileHints:  contract.CompileHints{CanBeImage: true, Reasons: []string{"internal_raster_crop_candidate", "repeated_internal_raster_slot", "side_rail_crop_candidate"}},
			},
		},
	}
	writeSource(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.TokenTypeCounts["raster_region_token"] != 2 {
		t.Fatalf("expected parent and internal crop raster tokens, got %#v", doc.Diagnostics.TokenTypeCounts)
	}
	var cropToken *Token
	for i := range doc.Tokens {
		if len(doc.Tokens[i].SourcePrimitiveIDs) == 1 && doc.Tokens[i].SourcePrimitiveIDs[0] == "p_crop" {
			cropToken = &doc.Tokens[i]
			break
		}
	}
	if cropToken == nil || cropToken.Disposition != "main" || !hasReason(*cropToken, "raster_region") {
		t.Fatalf("expected internal crop to remain a main raster token, got %#v", cropToken)
	}
	if cropToken == nil || !reasonListHas(cropToken.CompileHints.Reasons, "side_rail_crop_candidate") {
		t.Fatalf("expected crop reasons to preserve side rail evidence, got %#v", cropToken)
	}
}

func TestCompileSuppressesRasterParentCoveredByRepeatedInternalCrops(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "m29_physical_evidence.v1.json")
	source := contract.Document{
		SchemaName: "M29PhysicalEvidence",
		Version:    "1.0",
		Image:      contract.ImageInfo{Width: 700, Height: 1200},
		Primitives: []contract.Primitive{
			{
				ID:            "p_parent",
				PrimitiveType: "image_region",
				BBox:          contract.BBox{X: 20, Y: 200, Width: 620, Height: 900},
				CompileHints:  contract.CompileHints{CanBeImage: true, Reasons: []string{"high_texture_or_color_variance"}},
			},
			internalCropPrimitive("p_crop_1", contract.BBox{X: 44, Y: 390, Width: 140, Height: 160}),
			internalCropPrimitive("p_crop_2", contract.BBox{X: 586, Y: 390, Width: 54, Height: 160}),
			internalCropPrimitive("p_crop_3", contract.BBox{X: 44, Y: 590, Width: 140, Height: 160}),
			internalCropPrimitive("p_crop_4", contract.BBox{X: 586, Y: 590, Width: 54, Height: 160}),
			internalCropPrimitive("p_crop_5", contract.BBox{X: 44, Y: 790, Width: 140, Height: 160}),
		},
	}
	writeSource(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	var parentToken *Token
	mainCrops := 0
	for i := range doc.Tokens {
		token := &doc.Tokens[i]
		if len(token.SourcePrimitiveIDs) == 1 && token.SourcePrimitiveIDs[0] == "p_parent" {
			parentToken = token
		}
		if len(token.SourcePrimitiveIDs) == 1 && stringsHasPrefix(token.SourcePrimitiveIDs[0], "p_crop_") && token.Disposition == "main" {
			mainCrops++
		}
	}
	if parentToken == nil || parentToken.Disposition != "suppressed" || !hasReason(*parentToken, "covered_by_internal_raster_crops") {
		t.Fatalf("expected parent raster to be suppressed by repeated child crops, got %#v", parentToken)
	}
	if mainCrops != 5 {
		t.Fatalf("expected internal crops to stay main, got %d tokens in %#v", mainCrops, doc.Tokens)
	}
}

func TestCompilePromotesLargeTexturedSymbolToRasterTokenBeforeClustering(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "m29_physical_evidence.v1.json")
	source := contract.Document{
		SchemaName: "M29PhysicalEvidence",
		Version:    "1.0",
		Image:      contract.ImageInfo{Width: 500, Height: 500},
		Primitives: []contract.Primitive{
			{
				ID:            "p_textured_symbol",
				PrimitiveType: "symbol_region",
				BBox:          contract.BBox{X: 100, Y: 100, Width: 72, Height: 64},
				Measurements: contract.Measurements{
					Area:         2600,
					FillRatio:    0.56,
					ColorCount:   120,
					EdgeDensity:  0.34,
					TextureScore: 1,
				},
				CompileHints: contract.CompileHints{CanBeIcon: true, Reasons: []string{"compact_foreground_component"}},
			},
			{
				ID:            "p_contained_fragment",
				PrimitiveType: "symbol_region",
				BBox:          contract.BBox{X: 112, Y: 132, Width: 44, Height: 22},
				Measurements: contract.Measurements{
					Area:         650,
					FillRatio:    0.67,
					ColorCount:   80,
					EdgeDensity:  0.31,
					TextureScore: 0.9,
				},
				CompileHints: contract.CompileHints{CanBeIcon: true, Reasons: []string{"compact_foreground_component"}},
			},
			{
				ID:            "p_nearby_fragment",
				PrimitiveType: "symbol_region",
				BBox:          contract.BBox{X: 176, Y: 120, Width: 8, Height: 8},
				Measurements: contract.Measurements{
					Area:         36,
					FillRatio:    0.56,
					ColorCount:   4,
					EdgeDensity:  0.1,
					TextureScore: 0.2,
				},
				CompileHints: contract.CompileHints{CanBeIcon: true, Reasons: []string{"compact_foreground_component"}},
			},
		},
	}
	writeSource(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	var promoted *Token
	for i := range doc.Tokens {
		if len(doc.Tokens[i].SourcePrimitiveIDs) == 1 && doc.Tokens[i].SourcePrimitiveIDs[0] == "p_textured_symbol" {
			promoted = &doc.Tokens[i]
			break
		}
	}
	if promoted == nil || promoted.TokenType != "raster_region_token" || promoted.Disposition != "main" {
		t.Fatalf("expected textured symbol to be promoted to main raster token, got %#v", promoted)
	}
	if promoted == nil || !hasReason(*promoted, "large_textured_symbol_as_raster") {
		t.Fatalf("expected promotion reason, got %#v", promoted)
	}
	for _, token := range doc.Tokens {
		if len(token.SourcePrimitiveIDs) == 1 && token.SourcePrimitiveIDs[0] == "p_contained_fragment" && token.TokenType == "raster_region_token" {
			t.Fatalf("contained textured fragment should not become a duplicate raster token: %#v", token)
		}
	}
}

func internalCropPrimitive(id string, box contract.BBox) contract.Primitive {
	return contract.Primitive{
		ID:            id,
		PrimitiveType: "image_region",
		BBox:          box,
		CompileHints: contract.CompileHints{
			CanBeImage: true,
			Reasons:    []string{"internal_raster_crop_candidate", "repeated_internal_raster_slot"},
		},
	}
}

func writeSource(t *testing.T, path string, source contract.Document) {
	t.Helper()
	data, err := json.Marshal(source)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func assertFileExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected file %s: %v", path, err)
	}
}

func reasonListHas(reasons []string, reason string) bool {
	for _, item := range reasons {
		if item == reason {
			return true
		}
	}
	return false
}

func stringsHasPrefix(value string, prefix string) bool {
	if len(value) < len(prefix) {
		return false
	}
	return value[:len(prefix)] == prefix
}
