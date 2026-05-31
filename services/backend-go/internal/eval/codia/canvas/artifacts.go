package canvas

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func WriteArtifacts(outputDir string, analysis Analysis) error {
	if outputDir == "" {
		return fmt.Errorf("missing output dir")
	}
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(analysis, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, "codia_canvas_analysis.v1.json"), data, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "codia_canvas_analysis_report.md"), []byte(MarkdownReport(analysis)), 0o644)
}

func MarkdownReport(a Analysis) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Canvas Analysis\n\n")
	fmt.Fprintf(&b, "- input: `%s`\n", a.InputPath)
	fmt.Fprintf(&b, "- canvasVersion: `%d`\n", a.CanvasVersion)
	fmt.Fprintf(&b, "- designFrame: `%s` at `%s`\n", a.DesignFrameName, a.DesignFramePath)
	fmt.Fprintf(&b, "- root: `%s` at `%s`\n", a.RootName, a.RootPath)
	fmt.Fprintf(&b, "- rootBBox: `%d,%d,%d,%d`\n", a.RootBBox.X, a.RootBBox.Y, a.RootBBox.Width, a.RootBBox.Height)
	fmt.Fprintf(&b, "- nodeCount: `%d`\n", a.NodeCount)
	fmt.Fprintf(&b, "- maxDepth: `%d`\n", a.MaxDepth)
	fmt.Fprintf(&b, "- rootChildCount: `%d`\n", a.RootChildCount)
	fmt.Fprintf(&b, "- schemaCoverage: `%d/%d`\n", a.SchemaCoverage.Present, a.SchemaCoverage.Total)
	fmt.Fprintf(&b, "- guidCoverage: `%d/%d`\n", a.GUIDCoverage.Present, a.GUIDCoverage.Total)
	fmt.Fprintf(&b, "- suffix: `%d..%d`, present `%d`, missing `%d`, duplicates `%d`\n", a.Suffix.Min, a.Suffix.Max, a.Suffix.Present, len(a.Suffix.Missing), len(a.Suffix.Duplicates))
	fmt.Fprintf(&b, "- childSuffixDescending: `%d/%d`\n", a.ChildOrder.StrictDescendingParents, a.ChildOrder.MultiChildParents)
	fmt.Fprintf(&b, "- imageFills: `%d`, uniqueHashes `%d`\n", a.ImageFills.ImageFillCount, a.ImageFills.UniqueHashCount)
	fmt.Fprintf(&b, "- cornerRadiusNodes: `%d`\n", a.CornerRadius.NodeCount)
	fmt.Fprintf(&b, "- siblingOverlapPairs: `%d`\n", a.SiblingOverlap.PairCount)
	fmt.Fprintf(&b, "- overflowChildren: `%d`\n", a.Overflow.Count)

	if a.Expectation != "" {
		fmt.Fprintf(&b, "\n## Expectation\n\n")
		fmt.Fprintf(&b, "- expectation: `%s`\n", a.Expectation)
		if len(a.ExpectationFailures) == 0 {
			fmt.Fprintf(&b, "- status: `pass`\n")
		} else {
			fmt.Fprintf(&b, "- status: `fail`\n\n")
			fmt.Fprintf(&b, "| check | expected | actual |\n")
			fmt.Fprintf(&b, "| --- | --- | --- |\n")
			for _, failure := range a.ExpectationFailures {
				fmt.Fprintf(&b, "| `%s` | `%s` | `%s` |\n", failure.Check, failure.Expected, failure.Actual)
			}
		}
	}

	fmt.Fprintf(&b, "\n## Counts\n\n")
	writeCountsTable(&b, "Types", a.TypeCounts)
	writeCountsTable(&b, "Roles", a.RoleCounts)
	writeCountsTable(&b, "Names", a.NameCounts)

	fmt.Fprintf(&b, "\n## Background Last Child\n\n")
	fmt.Fprintf(&b, "| role | last | total | not last |\n")
	fmt.Fprintf(&b, "| --- | ---: | ---: | --- |\n")
	for _, role := range []string{"Background", "bg_Button", "bg_EditText"} {
		report := a.LastChild[role]
		fmt.Fprintf(&b, "| `%s` | %d | %d | `%s` |\n", role, report.Last, report.Total, strings.Join(report.NotLast, ", "))
	}

	fmt.Fprintf(&b, "\n## Control Modes\n\n")
	writeCountsTable(&b, "Button Modes", a.ButtonModes)
	writeCountsTable(&b, "EditText Modes", a.EditTextModes)

	fmt.Fprintf(&b, "\n## Corner Radius\n\n")
	writeCountsTable(&b, "Corner Radius By Role", a.CornerRadius.ByRole)

	fmt.Fprintf(&b, "\n## Text\n\n")
	fmt.Fprintf(&b, "- TextView count: `%d`\n", a.Text.TextViewCount)
	fmt.Fprintf(&b, "- name/characters match: `%d/%d`\n", a.Text.NameCharacterMatch, a.Text.TextViewCount)
	fmt.Fprintf(&b, "- fontSize min/median/max: `%d/%d/%d`\n", a.Text.FontSizeMin, a.Text.FontSizeMedian, a.Text.FontSizeMax)
	writeCountsTable(&b, "Fonts", a.Text.FontCounts)
	writeCountsTable(&b, "Auto Resize", a.Text.AutoResizeCounts)
	writeCountsTable(&b, "Line Height", a.Text.LineHeightCounts)

	if len(a.RoleMappingViolations) > 0 {
		fmt.Fprintf(&b, "\n## Role Mapping Violations\n\n")
		fmt.Fprintf(&b, "| path | schema | role | type | name | reason |\n")
		fmt.Fprintf(&b, "| --- | --- | --- | --- | --- | --- |\n")
		for _, item := range a.RoleMappingViolations {
			fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%s` | `%s` | `%s` |\n", item.Path, item.SchemaID, item.Role, item.Type, item.Name, item.Reason)
		}
	}

	if len(a.Overflow.Items) > 0 {
		fmt.Fprintf(&b, "\n## Overflow Samples\n\n")
		fmt.Fprintf(&b, "| path | schema | parent | deltas L/T/R/B |\n")
		fmt.Fprintf(&b, "| --- | --- | --- | --- |\n")
		for i, item := range a.Overflow.Items {
			if i >= 20 {
				break
			}
			fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%d/%d/%d/%d` |\n", item.Path, item.SchemaID, item.ParentSchemaID, item.DeltaLeft, item.DeltaTop, item.DeltaRight, item.DeltaBottom)
		}
	}

	fmt.Fprintf(&b, "\n## Root Children\n\n")
	fmt.Fprintf(&b, "| path | schema | role | type | name | bbox | children |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | --- | --- | ---: |\n")
	for _, node := range a.Nodes {
		if node.Depth == 1 {
			fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%s` | `%s` | `%d,%d,%d,%d` | %d |\n", node.Path, node.SchemaID, node.Role, node.Type, node.Name, node.BBox.X, node.BBox.Y, node.BBox.Width, node.BBox.Height, node.ChildCount)
		}
	}
	return b.String()
}

func writeCountsTable(b *strings.Builder, title string, counts map[string]int) {
	fmt.Fprintf(b, "\n### %s\n\n", title)
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
