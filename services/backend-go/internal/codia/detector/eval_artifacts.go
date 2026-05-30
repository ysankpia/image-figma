package detector

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func WriteEvalArtifacts(outputDir string, doc EvalDocument) error {
	if outputDir == "" {
		return fmt.Errorf("missing output dir")
	}
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, "ui_detector_eval.v1.json"), data, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "ui_detector_eval_report.md"), []byte(EvalMarkdownReport(doc)), 0o644)
}

func EvalMarkdownReport(doc EvalDocument) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# UI Detector Eval\n\n")
	fmt.Fprintf(&b, "- candidates: `%s`\n", doc.Source.CandidatesPath)
	fmt.Fprintf(&b, "- golden: `%s`\n", doc.Source.GoldenPath)
	fmt.Fprintf(&b, "- goldenCount: `%d`\n", doc.Summary.GoldenCount)
	fmt.Fprintf(&b, "- detectorCount: `%d`\n", doc.Summary.DetectorCount)
	fmt.Fprintf(&b, "- matched@0.5: `%d`\n", doc.Summary.MatchedAt05)
	fmt.Fprintf(&b, "- matched@0.6: `%d`\n", doc.Summary.MatchedAt06)
	fmt.Fprintf(&b, "- extra@0.5: `%d`\n", doc.Summary.ExtraAt05)
	fmt.Fprintf(&b, "- missed@0.5: `%d`\n", doc.Summary.MissedAt05)

	fmt.Fprintf(&b, "\n## Role Metrics\n\n")
	fmt.Fprintf(&b, "| role | golden | detector | matched@0.5 | matched@0.6 | precision@0.5 | recall@0.5 | f1@0.5 |\n")
	fmt.Fprintf(&b, "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n")
	for _, item := range doc.Roles {
		fmt.Fprintf(&b, "| `%s` | %d | %d | %d | %d | %.3f | %.3f | %.3f |\n",
			item.Role, item.Golden, item.Detector, item.MatchedAt05, item.MatchedAt06, item.Precision05, item.Recall05, item.F105)
	}

	writeEvalNodeTable(&b, "Missed Golden Nodes", doc.Missed)
	writeEvalNodeTable(&b, "Extra Detector Candidates", doc.Extra)
	return b.String()
}

func writeEvalNodeTable(b *strings.Builder, title string, nodes []EvalNode) {
	fmt.Fprintf(b, "\n## %s\n\n", title)
	fmt.Fprintf(b, "| id | role | pass | bbox | best | bestIoU | label |\n")
	fmt.Fprintf(b, "| --- | --- | --- | --- | --- | ---: | --- |\n")
	if len(nodes) == 0 {
		fmt.Fprintf(b, "| none |  |  |  |  |  |  |\n")
		return
	}
	for i, node := range nodes {
		if i >= 50 {
			break
		}
		fmt.Fprintf(b, "| `%s` | `%s` | `%s` | `%.1f,%.1f,%.1f,%.1f` | `%s` | %.3f | `%s` |\n",
			node.ID, node.Role, node.PassID, node.BBox.X, node.BBox.Y, node.BBox.Width, node.BBox.Height, node.BestID, node.BestIoU, escapeMarkdownCell(node.Label))
	}
}
