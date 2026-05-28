package relation

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

func TestCompileBuildsSurfaceContainmentRelations(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	source := evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  400,
			ImageHeight: 300,
		},
		Tokens: []evidence.Token{
			makeToken("token_surface", "surface_region_token", "main", contract.BBox{X: 20, Y: 30, Width: 260, Height: 48}),
			makeToken("token_text", "text_token", "main", contract.BBox{X: 64, Y: 42, Width: 120, Height: 20}),
			makeToken("token_icon", "symbol_cluster_token", "main", contract.BBox{X: 34, Y: 42, Width: 20, Height: 20}),
		},
	}
	writeEvidence(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	assertRelation(t, doc, "contains", "token_surface", "token_text")
	assertRelation(t, doc, "contains", "token_surface", "token_icon")
	assertRelation(t, doc, "inside_surface", "token_text", "token_surface")
	assertRelation(t, doc, "inside_surface", "token_icon", "token_surface")
	assertRelationCategory(t, doc, "inside_surface", "structural")
	assertFileExists(t, filepath.Join(tmp, "relation_graph.v1.json"))
	assertFileExists(t, filepath.Join(tmp, "relation_report.md"))
}

func TestCompileBuildsRasterSameBandRelations(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	source := evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  700,
			ImageHeight: 400,
		},
		Tokens: []evidence.Token{
			makeToken("token_left", "raster_region_token", "main", contract.BBox{X: 40, Y: 80, Width: 260, Height: 120}),
			makeToken("token_right", "raster_region_token", "main", contract.BBox{X: 305, Y: 82, Width: 250, Height: 118}),
		},
	}
	writeEvidence(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	assertRelation(t, doc, "same_band", "token_left", "token_right")
	assertRelation(t, doc, "raster_parts_same_region", "token_left", "token_right")
	assertRelationCategory(t, doc, "raster_parts_same_region", "grouping")
	if doc.Diagnostics.RasterPartsSameRegionCount != 1 {
		t.Fatalf("expected one raster_parts_same_region relation, got %#v", doc.Diagnostics)
	}
}

func TestCompileExcludesSuppressedTokensFromRelationGraph(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	source := evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  400,
			ImageHeight: 300,
		},
		Tokens: []evidence.Token{
			makeToken("token_surface", "surface_region_token", "main", contract.BBox{X: 20, Y: 30, Width: 260, Height: 48}),
			makeToken("token_suppressed", "texture_fragment_token", "suppressed", contract.BBox{X: 64, Y: 42, Width: 120, Height: 20}),
		},
	}
	writeEvidence(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if doc.Diagnostics.EligibleTokenCount != 1 {
		t.Fatalf("expected one eligible token, got %#v", doc.Diagnostics)
	}
	if doc.Diagnostics.RelationCount != 0 {
		t.Fatalf("suppressed token should not create relations: %#v", doc.Relations)
	}
}

func TestCompileCategorizesLayoutHints(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	source := evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  400,
			ImageHeight: 300,
		},
		Tokens: []evidence.Token{
			makeToken("token_a", "text_token", "main", contract.BBox{X: 20, Y: 30, Width: 60, Height: 20}),
			makeToken("token_b", "text_token", "main", contract.BBox{X: 84, Y: 31, Width: 70, Height: 20}),
		},
	}
	writeEvidence(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	assertRelationCategory(t, doc, "same_row", "layout_hint")
	if doc.Diagnostics.LayoutHintRelationCount == 0 {
		t.Fatalf("expected layout hint diagnostics, got %#v", doc.Diagnostics)
	}
}

func TestCompileDoesNotMarkContainedBackgroundAsSameBand(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "evidence_tokens.v1.json")
	source := evidence.Document{
		SchemaName: "M29EvidenceTokens",
		Version:    "1.0",
		Source: evidence.Source{
			ImageWidth:  900,
			ImageHeight: 700,
		},
		Tokens: []evidence.Token{
			makeToken("token_raster", "raster_region_token", "main", contract.BBox{X: 0, Y: 0, Width: 850, Height: 570}),
			makeToken("token_surface", "surface_region_token", "main", contract.BBox{X: 31, Y: 204, Width: 790, Height: 85}),
			makeToken("token_text", "text_token", "main", contract.BBox{X: 107, Y: 232, Width: 251, Height: 25}),
		},
	}
	writeEvidence(t, input, source)

	doc, err := Compile(Options{InputPath: input, OutputDir: tmp})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	assertRelation(t, doc, "contains", "token_raster", "token_surface")
	assertRelation(t, doc, "contains", "token_surface", "token_text")
	assertNoRelation(t, doc, "same_band", "token_raster", "token_surface")
}

func makeToken(id string, tokenType string, disposition string, bbox contract.BBox) evidence.Token {
	return evidence.Token{
		ID:          id,
		TokenType:   tokenType,
		BBox:        bbox,
		Disposition: disposition,
	}
}

func writeEvidence(t *testing.T, path string, source evidence.Document) {
	t.Helper()
	data, err := json.Marshal(source)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func assertRelation(t *testing.T, doc Document, relationType string, fromID string, toID string) {
	t.Helper()
	for _, relation := range doc.Relations {
		if relation.RelationType == relationType && relation.FromID == fromID && relation.ToID == toID {
			return
		}
	}
	t.Fatalf("missing relation %s %s -> %s in %#v", relationType, fromID, toID, doc.Relations)
}

func assertRelationCategory(t *testing.T, doc Document, relationType string, category string) {
	t.Helper()
	for _, relation := range doc.Relations {
		if relation.RelationType == relationType {
			if relation.Category != category {
				t.Fatalf("expected %s category %s, got %#v", relationType, category, relation)
			}
			return
		}
	}
	t.Fatalf("missing relation type %s in %#v", relationType, doc.Relations)
}

func assertNoRelation(t *testing.T, doc Document, relationType string, fromID string, toID string) {
	t.Helper()
	for _, relation := range doc.Relations {
		if relation.RelationType == relationType && relation.FromID == fromID && relation.ToID == toID {
			t.Fatalf("unexpected relation %s %s -> %s in %#v", relationType, fromID, toID, doc.Relations)
		}
	}
}

func assertFileExists(t *testing.T, path string) {
	t.Helper()
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("expected file %s: %v", path, err)
	}
}
