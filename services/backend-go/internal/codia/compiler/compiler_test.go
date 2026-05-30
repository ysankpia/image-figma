package compiler

import (
	"encoding/json"
	"image"
	"image/color"
	"image/draw"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func TestCompileWritesEndToEndArtifacts(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	ocrPath := filepath.Join(tmp, "ocr.json")
	out := filepath.Join(tmp, "out")
	writeFixturePNG(t, input)
	if err := os.WriteFile(ocrPath, []byte(`{"image":{"width":160,"height":120},"blocks":[{"id":"ocr_1","text":"Pay","bbox":{"x":48,"y":45,"width":48,"height":20},"confidence":1}]}`), 0o644); err != nil {
		t.Fatalf("write ocr fixture: %v", err)
	}

	result, err := Compile(Options{InputPath: input, OCRPath: ocrPath, OutputDir: out})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if result.TreeIR.SchemaName == "" || result.FigmaLikeTree.SchemaName == "" {
		t.Fatalf("expected tree and emitted artifacts in result")
	}
	for _, name := range []string{
		filepath.Join("extract", "m29_physical_evidence.v1.json"),
		filepath.Join("tokens", "evidence_tokens.v1.json"),
		filepath.Join("leaves", "codia_leaf_ir.v1.json"),
		filepath.Join("assembly", "codia_ir.v1.json"),
		filepath.Join("assembly", "codia_source_candidates.v1.json"),
		filepath.Join("assembly", "codia_ownership_graph.v1.json"),
		filepath.Join("assembly", "codia_assembly_report.md"),
		filepath.Join("controls", "codia_control_stage.v1.json"),
		filepath.Join("controls", "codia_control_ir.v1.json"),
		"codia_tree_ir.v1.json",
		"codia_figma_like_tree.v1.json",
	} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected artifact %s: %v", name, err)
		}
	}
}

func TestCompileWritesDiffAndAuditWhenGoldenProvided(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	ocrPath := filepath.Join(tmp, "ocr.json")
	goldenPath := filepath.Join(tmp, "golden.json")
	out := filepath.Join(tmp, "out")
	writeFixturePNG(t, input)
	if err := os.WriteFile(ocrPath, []byte(`{"image":{"width":160,"height":120},"blocks":[{"id":"ocr_1","text":"Pay","bbox":{"x":48,"y":45,"width":48,"height":20},"confidence":1}]}`), 0o644); err != nil {
		t.Fatalf("write ocr fixture: %v", err)
	}
	writeGoldenRoot(t, goldenPath)

	result, err := Compile(Options{InputPath: input, OCRPath: ocrPath, GoldenPath: goldenPath, OutputDir: out})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if result.StructureDiff == nil || result.FailureAudit == nil {
		t.Fatalf("expected structure diff and failure audit in result")
	}
	for _, name := range []string{
		filepath.Join("diff", "codia_structure_diff.v1.json"),
		filepath.Join("diff", "codia_structure_diff_report.md"),
		filepath.Join("audit", "codia_failure_audit.v1.json"),
		filepath.Join("audit", "codia_failure_audit_report.md"),
	} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected artifact %s: %v", name, err)
		}
	}
}

func TestCompileAcceptsDetectorCandidatesReportOnly(t *testing.T) {
	tmp := t.TempDir()
	input := filepath.Join(tmp, "input.png")
	ocrPath := filepath.Join(tmp, "ocr.json")
	detectorPath := filepath.Join(tmp, "ui_detector_candidates.v1.json")
	out := filepath.Join(tmp, "out")
	writeFixturePNG(t, input)
	if err := os.WriteFile(ocrPath, []byte(`{"image":{"width":160,"height":120},"blocks":[{"id":"ocr_1","text":"Pay","bbox":{"x":48,"y":45,"width":48,"height":20},"confidence":1}]}`), 0o644); err != nil {
		t.Fatalf("write ocr fixture: %v", err)
	}
	if err := os.WriteFile(detectorPath, []byte(`{"version":"ui_detector_candidates.v1","summary":{"total":1,"roleCounts":{"ImageView":1},"passCounts":{"imageview":1}},"candidates":[{"id":"det_000001","role":"ImageView","confidence":0.9,"bbox":{"x":10,"y":10,"width":20,"height":20},"source":{"kind":"vision_model","passId":"imageview","modelOutputIndex":0},"merge":{"state":"report_only"}}]}`), 0o644); err != nil {
		t.Fatalf("write detector fixture: %v", err)
	}

	result, err := Compile(Options{InputPath: input, OCRPath: ocrPath, DetectorCandidates: detectorPath, OutputDir: out})
	if err != nil {
		t.Fatalf("Compile() error = %v", err)
	}
	if result.DetectorManifest == nil {
		t.Fatalf("expected detector manifest in result")
	}
	if result.DetectorManifest.Mode != "report_only" || result.DetectorManifest.Summary.Total != 1 {
		t.Fatalf("unexpected detector manifest: %+v", result.DetectorManifest)
	}
	if _, err := os.Stat(filepath.Join(out, "detector", "detector_manifest.v1.json")); err != nil {
		t.Fatalf("expected detector manifest artifact: %v", err)
	}
	if result.TreeIR.Summary.NodeCount == 0 {
		t.Fatalf("expected normal compile tree to still be produced")
	}
}

func writeFixturePNG(t *testing.T, path string) {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 160, 120))
	draw.Draw(img, img.Bounds(), &image.Uniform{C: color.RGBA{R: 245, G: 245, B: 245, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(32, 36, 116, 76), &image.Uniform{C: color.RGBA{R: 40, G: 110, B: 220, A: 255}}, image.Point{}, draw.Src)
	draw.Draw(img, image.Rect(54, 48, 92, 62), &image.Uniform{C: color.RGBA{R: 255, G: 255, B: 255, A: 255}}, image.Point{}, draw.Src)
	if err := imageio.WritePNG(path, img); err != nil {
		t.Fatalf("write png fixture: %v", err)
	}
}

func writeGoldenRoot(t *testing.T, path string) {
	t.Helper()
	root := ir.Node{
		ID:          "root_0",
		Role:        ir.RoleRoot,
		SourceBBox:  ir.BBox{X: 0, Y: 0, Width: 160, Height: 120},
		FigmaBBox:   ir.BBox{X: 0, Y: 0, Width: 160, Height: 120},
		FigmaType:   ir.FigmaFrame,
		VisibleName: "Root",
		SchemaID:    "root_0",
	}
	doc := ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root:       root,
		Summary: ir.Summary{
			NodeCount:       1,
			MaxDepth:        0,
			RoleCounts:      map[string]int{"root": 1},
			FigmaTypeCounts: map[string]int{"FRAME": 1},
		},
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		t.Fatalf("marshal golden: %v", err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write golden: %v", err)
	}
}
