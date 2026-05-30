package canvasexport

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func WriteArtifacts(outputDir string, result Result) error {
	if outputDir == "" {
		return fmt.Errorf("missing output dir")
	}
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(result.Document, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, CanvasArtifactName), data, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, ReportArtifactName), []byte(MarkdownReport(result)), 0o644)
}

func MarkdownReport(result Result) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Canvas Export\n\n")
	fmt.Fprintf(&b, "- schema: `%s`\n", result.Report.SchemaName)
	fmt.Fprintf(&b, "- version: `%s`\n", result.Report.Version)
	fmt.Fprintf(&b, "- canvasVersion: `%d`\n", result.Report.CanvasVersion)
	fmt.Fprintf(&b, "- designFrameName: `%s`\n", result.Report.DesignFrameName)
	fmt.Fprintf(&b, "- rootName: `%s`\n", result.Report.RootName)
	fmt.Fprintf(&b, "- nodeCount: `%d`\n", result.Report.NodeCount)
	fmt.Fprintf(&b, "\n## Non-Replicated Figma Internals\n\n")
	for _, note := range result.Report.UnsupportedNotes {
		fmt.Fprintf(&b, "- %s\n", note)
	}
	return b.String()
}
