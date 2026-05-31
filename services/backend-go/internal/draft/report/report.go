package report

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/validate"
)

const ValidationReportName = "draft_validation_report.md"

func WriteValidationReport(dir string, doc contract.Document, validation validate.Report) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	path := filepath.Join(dir, ValidationReportName)
	data := []byte(formatValidationReport(doc, validation))
	return os.WriteFile(path, data, 0o644)
}

func formatValidationReport(doc contract.Document, validation validate.Report) string {
	out := "# Draft Validation Report\n\n"
	out += fmt.Sprintf("- version: `%s`\n", validation.Version)
	out += fmt.Sprintf("- image: `%dx%d`\n", doc.Image.Width, doc.Image.Height)
	out += fmt.Sprintf("- layers: `%d`\n", len(doc.Layers))
	out += fmt.Sprintf("- groups: `%d`\n", len(doc.Groups))
	out += fmt.Sprintf("- assets: `%d`\n", len(doc.Assets))
	out += fmt.Sprintf("- errors: `%d`\n", validation.ErrorCount)
	out += fmt.Sprintf("- warnings: `%d`\n\n", validation.WarningCount)
	if len(validation.Findings) == 0 {
		out += "No findings.\n"
		return out
	}
	out += "| severity | code | layer | message |\n"
	out += "| --- | --- | --- | --- |\n"
	for _, finding := range validation.Findings {
		out += fmt.Sprintf("| %s | `%s` | `%s` | %s |\n", finding.Severity, finding.Code, finding.LayerID, finding.Message)
	}
	return out
}
