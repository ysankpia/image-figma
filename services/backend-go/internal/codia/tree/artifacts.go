package tree

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func WriteArtifacts(outputDir string, doc ir.Document) error {
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
	if err := os.WriteFile(filepath.Join(outputDir, ArtifactName), data, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "codia_tree_ir_report.md"), []byte(MarkdownReport(doc)), 0o644)
}

func MarkdownReport(doc ir.Document) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Tree IR\n\n")
	fmt.Fprintf(&b, "- input: `%s`\n", doc.Source.InputPath)
	fmt.Fprintf(&b, "- nodeCount: `%d`\n", doc.Summary.NodeCount)
	fmt.Fprintf(&b, "- maxDepth: `%d`\n", doc.Summary.MaxDepth)
	writeCountsTable(&b, "Roles", doc.Summary.RoleCounts)
	writeCountsTable(&b, "Tree Evidence", treeEvidenceCounts(doc.Root))
	fmt.Fprintf(&b, "\n## Root Children\n\n")
	fmt.Fprintf(&b, "| id | role | evidence | bbox | children |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | ---: |\n")
	for _, child := range doc.Root.Children {
		fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%d,%d,%d,%d` | %d |\n", child.ID, child.Role, firstEvidenceKind(child), child.SourceBBox.X, child.SourceBBox.Y, child.SourceBBox.Width, child.SourceBBox.Height, len(child.Children))
	}
	return b.String()
}

func treeEvidenceCounts(root ir.Node) map[string]int {
	out := map[string]int{}
	var walk func(ir.Node)
	walk = func(node ir.Node) {
		if kind := firstEvidenceKind(node); strings.HasSuffix(kind, "_candidate") || strings.HasSuffix(kind, "_owner") || strings.Contains(kind, "navigation") || strings.Contains(kind, "row") || strings.Contains(kind, "section") || strings.Contains(kind, "category") {
			out[kind]++
		}
		for _, child := range node.Children {
			walk(child)
		}
	}
	walk(root)
	return out
}

func firstEvidenceKind(node ir.Node) string {
	if len(node.Evidence) == 0 {
		return ""
	}
	return node.Evidence[0].Kind
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
	fmt.Fprintf(b, "| role | count |\n")
	fmt.Fprintf(b, "| --- | ---: |\n")
	for _, key := range keys {
		fmt.Fprintf(b, "| `%s` | %d |\n", key, counts[key])
	}
}
