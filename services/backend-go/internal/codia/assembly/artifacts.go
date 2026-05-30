package assembly

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
	sourceData, err := json.MarshalIndent(result.SourceCandidates, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, SourceCandidatesArtifactName), sourceData, 0o644); err != nil {
		return err
	}
	graphData, err := json.MarshalIndent(result.OwnershipGraph, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, OwnershipGraphArtifactName), graphData, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, ReportArtifactName), []byte(MarkdownReport(result)), 0o644)
}

func MarkdownReport(result Result) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Assembly\n\n")
	fmt.Fprintf(&b, "- schema: `%s`\n", result.SchemaName)
	fmt.Fprintf(&b, "- version: `%s`\n", result.Version)
	if result.Source.DetectorPath != "" {
		fmt.Fprintf(&b, "- detector: `%s`\n", result.Source.DetectorPath)
	}
	fmt.Fprintf(&b, "- inputLeafCount: `%d`\n", result.Diagnostics.InputLeafCount)
	fmt.Fprintf(&b, "- detectorCandidateCount: `%d`\n", result.Diagnostics.DetectorCandidateCount)
	fmt.Fprintf(&b, "- outputNodeCount: `%d`\n", result.Diagnostics.OutputNodeCount)
	fmt.Fprintf(&b, "- consumed: `%d`\n", result.Diagnostics.ConsumedCount)
	fmt.Fprintf(&b, "- suppressed: `%d`\n", result.Diagnostics.SuppressedCount)
	fmt.Fprintf(&b, "- refined: `%d`\n", result.Diagnostics.RefinedCount)
	fmt.Fprintf(&b, "- hints: `%d`\n", result.Diagnostics.HintCount)

	writeCountTable(&b, "Output Roles", result.Diagnostics.RoleCounts)
	writeCountTable(&b, "Decisions", result.SourceCandidates.Summary.ByDecision)

	fmt.Fprintf(&b, "\n## Source Candidates\n\n")
	fmt.Fprintf(&b, "| id | kind | role | decision | score | authority | owner | bbox | reason |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |\n")
	for _, item := range result.SourceCandidates.Candidates {
		fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%s` | %.3f | `%s` | `%s` | `%d,%d,%d,%d` | `%s` |\n",
			item.ID, item.Kind, item.Role, item.Decision, item.Score, item.BBoxAuthority, item.OwnerID,
			item.BBox.X, item.BBox.Y, item.BBox.Width, item.BBox.Height, escapeCell(item.Reason))
	}

	if len(result.OwnershipGraph.Edges) > 0 {
		fmt.Fprintf(&b, "\n## Ownership Edges\n\n")
		fmt.Fprintf(&b, "| from | to | kind | score | reason |\n")
		fmt.Fprintf(&b, "| --- | --- | --- | ---: | --- |\n")
		for _, edge := range result.OwnershipGraph.Edges {
			fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | %.3f | `%s` |\n", edge.FromID, edge.ToID, edge.Kind, edge.Score, escapeCell(edge.Reason))
		}
	}
	return b.String()
}

func writeCountTable(b *strings.Builder, title string, counts map[string]int) {
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

func escapeCell(value string) string {
	value = strings.ReplaceAll(value, "\n", " ")
	value = strings.ReplaceAll(value, "|", "\\|")
	return strings.TrimSpace(value)
}
