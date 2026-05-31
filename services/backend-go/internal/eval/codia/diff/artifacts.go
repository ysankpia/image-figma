package diff

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func WriteArtifacts(outputDir string, doc Document) error {
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
	if err := os.WriteFile(filepath.Join(outputDir, "codia_structure_diff.v1.json"), data, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "codia_structure_diff_report.md"), []byte(MarkdownReport(doc)), 0o644)
}

func MarkdownReport(doc Document) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Structure Diff\n\n")
	fmt.Fprintf(&b, "- generated: `%s`\n", doc.Source.GeneratedPath)
	fmt.Fprintf(&b, "- golden: `%s`\n", doc.Source.GoldenPath)
	fmt.Fprintf(&b, "- generatedNodes: `%d`\n", doc.Summary.GeneratedNodeCount)
	fmt.Fprintf(&b, "- goldenNodes: `%d`\n", doc.Summary.GoldenNodeCount)
	fmt.Fprintf(&b, "- matched: `%d`\n", doc.Summary.MatchedNodeCount)
	fmt.Fprintf(&b, "- extra: `%d`\n", doc.Summary.ExtraNodeCount)
	fmt.Fprintf(&b, "- missed: `%d`\n", doc.Summary.MissedNodeCount)
	fmt.Fprintf(&b, "- averageBestIoU: `%.3f`\n", doc.Summary.AverageBestIoU)
	fmt.Fprintf(&b, "- visibleVocabularyPass: `%t`\n", doc.Checks.VisibleVocabularyPass)
	fmt.Fprintf(&b, "- buttonBgLast: `%d/%d`\n", doc.Checks.ButtonBackgroundLast.Passed, doc.Checks.ButtonBackgroundLast.Total)
	fmt.Fprintf(&b, "- editTextBgLast: `%d/%d`\n", doc.Checks.EditTextBackgroundLast.Passed, doc.Checks.EditTextBackgroundLast.Total)
	fmt.Fprintf(&b, "- backgroundLate: `%d/%d`\n", doc.Checks.BackgroundLate.Passed, doc.Checks.BackgroundLate.Total)
	fmt.Fprintf(&b, "- parentEdgePrecision: `%.3f`\n", doc.Edges.Precision)
	fmt.Fprintf(&b, "- parentEdgeRecall: `%.3f`\n", doc.Edges.Recall)

	fmt.Fprintf(&b, "\n## Role Metrics\n\n")
	fmt.Fprintf(&b, "| role | generated | golden | matched | extra | missed | precision | recall |\n")
	fmt.Fprintf(&b, "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n")
	for _, role := range sortedRoleKeys(doc.Summary.RoleMetrics) {
		item := doc.Summary.RoleMetrics[role]
		fmt.Fprintf(&b, "| `%s` | %d | %d | %d | %d | %d | %.3f | %.3f |\n", role, item.Generated, item.Golden, item.Matched, item.Extra, item.Missed, item.Precision, item.Recall)
	}

	writeCountsTable(&b, "Extra By Evidence Kind", doc.Summary.ExtraByEvidence)
	writeCountsTable(&b, "Missed By Evidence Kind", doc.Summary.MissedByEvidence)

	writeNodeTable(&b, "Extra Generated Nodes", doc.Generated, "extra")
	writeNodeTable(&b, "Missed Golden Nodes", doc.Golden, "missed")

	if len(doc.Checks.VisibleVocabularyViolations) > 0 {
		fmt.Fprintf(&b, "\n## Visible Vocabulary Violations\n\n")
		for _, id := range doc.Checks.VisibleVocabularyViolations {
			fmt.Fprintf(&b, "- `%s`\n", id)
		}
	}

	writeEdgeTable(&b, "Generated Parent Edge Mismatches", doc.Edges.GeneratedSamples)
	writeEdgeTable(&b, "Golden Parent Edge Mismatches", doc.Edges.GoldenSamples)
	return b.String()
}

func sortedRoleKeys(values map[string]Role) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func writeCountsTable(b *strings.Builder, title string, counts map[string]int) {
	if len(counts) == 0 {
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
	fmt.Fprintf(b, "\n## %s\n\n", title)
	fmt.Fprintf(b, "| evidence | count |\n")
	fmt.Fprintf(b, "| --- | ---: |\n")
	for _, key := range keys {
		fmt.Fprintf(b, "| `%s` | %d |\n", key, counts[key])
	}
}

func writeNodeTable(b *strings.Builder, title string, nodes []NodeMatch, verdict string) {
	fmt.Fprintf(b, "\n## %s\n\n", title)
	fmt.Fprintf(b, "| id | role | evidence | parent | bbox | best | iou | stage | reason |\n")
	fmt.Fprintf(b, "| --- | --- | --- | --- | --- | --- | ---: | --- | --- |\n")
	count := 0
	for _, node := range nodes {
		if node.Verdict != verdict {
			continue
		}
		if count >= 40 {
			break
		}
		fmt.Fprintf(b, "| `%s` | `%s` | `%s` | `%s` | `%d,%d,%d,%d` | `%s` | %.3f | `%s` | `%s` |\n",
			node.ID,
			node.Role,
			node.EvidenceKind,
			node.ParentID,
			node.BBox.X,
			node.BBox.Y,
			node.BBox.Width,
			node.BBox.Height,
			node.BestID,
			node.BestIoU,
			node.FailureStage,
			node.FailureReason,
		)
		count++
	}
	if count == 0 {
		fmt.Fprintf(b, "| none |  |  |  |  |  |  |  |  |\n")
	}
}

func writeEdgeTable(b *strings.Builder, title string, edges []EdgeVerdict) {
	if len(edges) == 0 {
		return
	}
	fmt.Fprintf(b, "\n## %s\n\n", title)
	fmt.Fprintf(b, "| child | childRole | parent | best | bestParent | verdict |\n")
	fmt.Fprintf(b, "| --- | --- | --- | --- | --- | --- |\n")
	for _, edge := range edges {
		fmt.Fprintf(b, "| `%s` | `%s` | `%s` | `%s` | `%s` | `%s` |\n", edge.ChildID, edge.ChildRole, edge.ParentID, edge.BestID, edge.BestParentID, edge.Verdict)
	}
}
