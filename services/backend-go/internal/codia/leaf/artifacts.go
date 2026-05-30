package leaf

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
	return os.WriteFile(filepath.Join(outputDir, "codia_leaf_ir_report.md"), []byte(MarkdownReport(doc)), 0o644)
}

func MarkdownReport(doc ir.Document) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Leaf IR\n\n")
	fmt.Fprintf(&b, "- input: `%s`\n", doc.Source.InputPath)
	fmt.Fprintf(&b, "- nodeCount: `%d`\n", doc.Summary.NodeCount)
	fmt.Fprintf(&b, "- maxDepth: `%d`\n", doc.Summary.MaxDepth)
	fmt.Fprintf(&b, "- rootBBox: `%d,%d,%d,%d`\n", doc.Root.SourceBBox.X, doc.Root.SourceBBox.Y, doc.Root.SourceBBox.Width, doc.Root.SourceBBox.Height)
	writeCountsTable(&b, "Roles", doc.Summary.RoleCounts)
	writeCountsTable(&b, "Figma Types", doc.Summary.FigmaTypeCounts)
	fmt.Fprintf(&b, "\n## Root Children Samples\n\n")
	fmt.Fprintf(&b, "| id | role | schema | bbox | evidence |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | --- |\n")
	for i, child := range doc.Root.Children {
		if i >= 30 {
			break
		}
		evidenceKind := ""
		if len(child.Evidence) > 0 {
			evidenceKind = child.Evidence[0].Kind
		}
		fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%d,%d,%d,%d` | `%s` |\n", child.ID, child.Role, child.SchemaID, child.SourceBBox.X, child.SourceBBox.Y, child.SourceBBox.Width, child.SourceBBox.Height, evidenceKind)
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
