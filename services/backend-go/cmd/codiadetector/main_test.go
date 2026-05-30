package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestCodiaDetectorEvalCLIWritesArtifacts(t *testing.T) {
	tmp := t.TempDir()
	candidatesPath := filepath.Join(tmp, "ui_detector_candidates.v1.json")
	goldenPath := filepath.Join(tmp, "codia_ir.v1.json")
	out := filepath.Join(tmp, "out")
	writeFixtureJSON(t, candidatesPath, detector.Document{
		Version: detector.CandidatesVersion,
		Candidates: []detector.Candidate{
			{ID: "det_000001", Role: detector.RoleImageView, BBox: detector.BBox{X: 10, Y: 10, Width: 20, Height: 20}},
		},
	})
	writeFixtureJSON(t, goldenPath, ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root: ir.Node{
			ID: "root",
			Children: []ir.Node{
				{ID: "gold_img", Role: ir.RoleImageView, FigmaBBox: ir.BBox{X: 10, Y: 10, Width: 20, Height: 20}},
			},
		},
	})
	cmd := exec.Command("go", "run", ".", "-eval", "-candidates", candidatesPath, "-golden", goldenPath, "-out", out)
	cmd.Dir = "."
	data, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go run . failed: %v\n%s", err, string(data))
	}
	if !strings.Contains(string(data), "matched@0.5 1") {
		t.Fatalf("unexpected output: %s", string(data))
	}
	for _, name := range []string{"ui_detector_eval.v1.json", "ui_detector_eval_report.md"} {
		if _, err := os.Stat(filepath.Join(out, name)); err != nil {
			t.Fatalf("expected %s: %v", name, err)
		}
	}
}

func writeFixtureJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatalf("marshal fixture: %v", err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
}
