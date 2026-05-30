package control

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func WriteArtifacts(outputDir string, result Result) error {
	if outputDir == "" {
		return fmt.Errorf("missing output dir")
	}
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	stageData, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, StageArtifactName), stageData, 0o644); err != nil {
		return err
	}
	doc := ToDocument(result)
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, ArtifactName), data, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "codia_control_ir_report.md"), []byte(MarkdownReport(result)), 0o644)
}

func MarkdownReport(result Result) string {
	doc := ToDocument(result)
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Control IR\n\n")
	fmt.Fprintf(&b, "- input: `%s`\n", doc.Source.InputPath)
	fmt.Fprintf(&b, "- nodeCount: `%d`\n", doc.Summary.NodeCount)
	fmt.Fprintf(&b, "- maxDepth: `%d`\n", doc.Summary.MaxDepth)
	fmt.Fprintf(&b, "- controls: `%d`\n", result.Diagnostics.ControlCount)
	fmt.Fprintf(&b, "- remaining: `%d`\n", result.Diagnostics.RemainingCount)
	fmt.Fprintf(&b, "- candidates: `%d`\n", result.Diagnostics.CandidateCount)
	fmt.Fprintf(&b, "- rejections: `%d`\n", result.Diagnostics.RejectedCount)
	writeCountsTable(&b, "Roles", doc.Summary.RoleCounts)
	writeCountsTable(&b, "Figma Types", doc.Summary.FigmaTypeCounts)
	fmt.Fprintf(&b, "\n## Controls\n\n")
	fmt.Fprintf(&b, "| id | role | schema | bbox | children |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | ---: |\n")
	for _, node := range result.Controls {
		fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%d,%d,%d,%d` | %d |\n", node.ID, node.Role, node.SchemaID, node.SourceBBox.X, node.SourceBBox.Y, node.SourceBBox.Width, node.SourceBBox.Height, len(node.Children))
	}
	if len(result.Rejections) > 0 {
		fmt.Fprintf(&b, "\n## Rejections\n\n")
		fmt.Fprintf(&b, "| background | reason | evidence | bbox | foreground |\n")
		fmt.Fprintf(&b, "| --- | --- | --- | --- | --- |\n")
		for _, item := range result.Rejections {
			fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%d,%d,%d,%d` | `%s` |\n", item.BackgroundID, item.Reason, item.EvidenceKind, item.BBox.X, item.BBox.Y, item.BBox.Width, item.BBox.Height, strings.Join(item.ForegroundIDs, ", "))
		}
	}
	return b.String()
}

func writeCountsTable(b *strings.Builder, title string, counts map[string]int) {
	fmt.Fprintf(b, "\n## %s\n\n", title)
	if len(counts) == 0 {
		fmt.Fprintf(b, "- none\n")
		return
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		if counts[keys[i]] != counts[keys[j]] {
			return counts[keys[i]] > counts[keys[j]]
		}
		return keys[i] < keys[j]
	})
	fmt.Fprintf(b, "| item | count |\n")
	fmt.Fprintf(b, "| --- | ---: |\n")
	for _, key := range keys {
		fmt.Fprintf(b, "| `%s` | %d |\n", key, counts[key])
	}
}
