package detector

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func TestEvalMatchesByRoleAndIoU(t *testing.T) {
	tmp := t.TempDir()
	candidatesPath := filepath.Join(tmp, "ui_detector_candidates.v1.json")
	goldenPath := filepath.Join(tmp, "codia_ir.v1.json")
	out := filepath.Join(tmp, "eval")
	writeJSON(t, candidatesPath, Document{
		Version: CandidatesVersion,
		Candidates: []Candidate{
			{ID: "det_000001", Role: RoleImageView, BBox: BBox{X: 10, Y: 10, Width: 20, Height: 20}, Source: CandidateSource{PassID: "imageview"}},
			{ID: "det_000002", Role: RoleImageView, BBox: BBox{X: 80, Y: 80, Width: 10, Height: 10}, Source: CandidateSource{PassID: "imageview"}},
			{ID: "det_000003", Role: RoleBackground, BBox: BBox{X: 0, Y: 0, Width: 100, Height: 100}, Source: CandidateSource{PassID: "background"}},
		},
	})
	writeJSON(t, goldenPath, ir.Document{
		SchemaName: ir.SchemaName,
		Version:    ir.Version,
		Root: ir.Node{
			ID:        "root",
			Role:      ir.RoleRoot,
			FigmaBBox: ir.BBox{X: 0, Y: 0, Width: 100, Height: 100},
			Children: []ir.Node{
				{ID: "gold_img", Role: ir.RoleImageView, FigmaBBox: ir.BBox{X: 10, Y: 10, Width: 20, Height: 20}},
				{ID: "gold_text", Role: ir.RoleTextView, FigmaBBox: ir.BBox{X: 40, Y: 40, Width: 20, Height: 10}},
			},
		},
	})
	doc, err := Eval(EvalOptions{CandidatesPath: candidatesPath, GoldenPath: goldenPath, OutputDir: out})
	if err != nil {
		t.Fatalf("eval: %v", err)
	}
	if doc.Summary.MatchedAt05 != 1 || doc.Summary.ExtraAt05 != 2 || doc.Summary.MissedAt05 != 1 {
		t.Fatalf("unexpected summary: %+v", doc.Summary)
	}
	if _, err := os.Stat(filepath.Join(out, "ui_detector_eval.v1.json")); err != nil {
		t.Fatalf("expected eval json: %v", err)
	}
	if _, err := os.Stat(filepath.Join(out, "ui_detector_eval_report.md")); err != nil {
		t.Fatalf("expected eval report: %v", err)
	}
}

func writeJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}
