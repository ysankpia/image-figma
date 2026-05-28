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
			{ID: "p_surface", PrimitiveType: "surface_region", BBox: contract.BBox{X: 30, Y: 40, Width: 260, Height: 42}},
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
	}
	if doc.Diagnostics.TokenTypeCounts["symbol_cluster_token"] != 1 {
		t.Fatalf("symbol inside surface should stay foreground token, got %#v", doc.Diagnostics.TokenTypeCounts)
	}
	if doc.Diagnostics.TokenTypeCounts["texture_fragment_token"] != 0 {
		t.Fatalf("surface foreground should not be suppressed as raster texture, got %#v", doc.Diagnostics.TokenTypeCounts)
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
