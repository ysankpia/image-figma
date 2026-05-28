package batch

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/pipeline"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/relation"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/visualtree"
)

type Options struct {
	InputDir    string
	OutputDir   string
	OCRProvider string
	Limit       int
}

type Summary struct {
	SchemaName     string        `json:"schemaName"`
	Version        string        `json:"version"`
	GeneratedAt    string        `json:"generatedAt"`
	InputDir       string        `json:"inputDir"`
	OutputDir      string        `json:"outputDir"`
	OCRProvider    string        `json:"ocrProvider,omitempty"`
	CaseCount      int           `json:"caseCount"`
	CompletedCount int           `json:"completedCount"`
	FailedCount    int           `json:"failedCount"`
	Cases          []CaseSummary `json:"cases"`
}

type CaseSummary struct {
	Slug                            string                  `json:"slug"`
	SourcePath                      string                  `json:"sourcePath"`
	OutputDir                       string                  `json:"outputDir"`
	Status                          string                  `json:"status"`
	Error                           string                  `json:"error,omitempty"`
	OCRBlockCount                   int                     `json:"ocrBlockCount,omitempty"`
	PrimitiveCount                  int                     `json:"primitiveCount,omitempty"`
	PrimitiveTypeCounts             map[string]int          `json:"primitiveTypeCounts,omitempty"`
	TokenCount                      int                     `json:"tokenCount,omitempty"`
	TokenTypeCounts                 map[string]int          `json:"tokenTypeCounts,omitempty"`
	TokenDiagnostics                *evidence.Diagnostics   `json:"tokenDiagnostics,omitempty"`
	RelationCount                   int                     `json:"relationCount,omitempty"`
	RelationTypeCounts              map[string]int          `json:"relationTypeCounts,omitempty"`
	RelationDiagnostics             *relation.Diagnostics   `json:"relationDiagnostics,omitempty"`
	VisualTreeNodeCount             int                     `json:"visualTreeNodeCount,omitempty"`
	VisualTreeNodeTypeCounts        map[string]int          `json:"visualTreeNodeTypeCounts,omitempty"`
	VisualTreeDiagnostics           *visualtree.Diagnostics `json:"visualTreeDiagnostics,omitempty"`
	TextMaskPixelCount              int                     `json:"textMaskPixelCount,omitempty"`
	ForegroundPixelCount            int                     `json:"foregroundPixelCount,omitempty"`
	DebugOverlayPath                string                  `json:"debugOverlayPath,omitempty"`
	PreviewSheetPath                string                  `json:"previewSheetPath,omitempty"`
	EvidencePath                    string                  `json:"evidencePath,omitempty"`
	TokenPath                       string                  `json:"tokenPath,omitempty"`
	TokenOverlayPath                string                  `json:"tokenOverlayPath,omitempty"`
	TokenPreviewSheetPath           string                  `json:"tokenPreviewSheetPath,omitempty"`
	RelationPath                    string                  `json:"relationPath,omitempty"`
	RelationOverlayPath             string                  `json:"relationOverlayPath,omitempty"`
	RelationPreviewSheetPath        string                  `json:"relationPreviewSheetPath,omitempty"`
	RelationReportPath              string                  `json:"relationReportPath,omitempty"`
	VisualTreePath                  string                  `json:"visualTreePath,omitempty"`
	VisualTreeOverlayPath           string                  `json:"visualTreeOverlayPath,omitempty"`
	VisualTreePreviewSheetPath      string                  `json:"visualTreePreviewSheetPath,omitempty"`
	VisualTreeReportPath            string                  `json:"visualTreeReportPath,omitempty"`
	VisualTreeContainmentReportPath string                  `json:"visualTreeContainmentReportPath,omitempty"`
	OCRPath                         string                  `json:"ocrPath,omitempty"`
}

func Run(options Options) (Summary, error) {
	if options.InputDir == "" {
		return Summary{}, fmt.Errorf("missing input dir")
	}
	if options.OutputDir == "" {
		return Summary{}, fmt.Errorf("missing output dir")
	}
	inputs, err := findPNGInputs(options.InputDir)
	if err != nil {
		return Summary{}, err
	}
	if options.Limit > 0 && len(inputs) > options.Limit {
		inputs = inputs[:options.Limit]
	}
	casesDir := filepath.Join(options.OutputDir, "cases")
	if err := os.MkdirAll(casesDir, 0o755); err != nil {
		return Summary{}, err
	}
	summary := Summary{
		SchemaName:  "M29BatchEvidenceReview",
		Version:     "1.0",
		GeneratedAt: time.Now().UTC().Format(time.RFC3339),
		InputDir:    options.InputDir,
		OutputDir:   options.OutputDir,
		OCRProvider: options.OCRProvider,
		CaseCount:   len(inputs),
		Cases:       make([]CaseSummary, 0, len(inputs)),
	}
	usedSlugs := map[string]int{}
	for _, input := range inputs {
		slug := uniqueSlug(input, usedSlugs)
		caseDir := filepath.Join(casesDir, slug)
		caseSummary := CaseSummary{
			Slug:       slug,
			SourcePath: input,
			OutputDir:  caseDir,
			Status:     "completed",
		}
		doc, err := pipeline.Run(pipeline.Options{
			InputPath:   input,
			OCRProvider: options.OCRProvider,
			OutputDir:   caseDir,
		})
		if err != nil {
			caseSummary.Status = "failed"
			caseSummary.Error = err.Error()
			summary.FailedCount++
			summary.Cases = append(summary.Cases, caseSummary)
			continue
		}
		applyDocumentStats(&caseSummary, doc)
		tokenDoc, err := evidence.Compile(evidence.Options{
			InputPath: filepath.Join(caseDir, "m29_physical_evidence.v1.json"),
			OutputDir: caseDir,
		})
		if err != nil {
			caseSummary.Status = "failed"
			caseSummary.Error = "evidence tokens: " + err.Error()
			summary.FailedCount++
			summary.Cases = append(summary.Cases, caseSummary)
			continue
		}
		caseSummary.TokenCount = tokenDoc.Diagnostics.TokenCount
		caseSummary.TokenTypeCounts = tokenDoc.Diagnostics.TokenTypeCounts
		tokenDiagnostics := tokenDoc.Diagnostics
		caseSummary.TokenDiagnostics = &tokenDiagnostics
		relationDoc, err := relation.Compile(relation.Options{
			InputPath: filepath.Join(caseDir, "evidence_tokens.v1.json"),
			OutputDir: caseDir,
		})
		if err != nil {
			caseSummary.Status = "failed"
			caseSummary.Error = "relation graph: " + err.Error()
			summary.FailedCount++
			summary.Cases = append(summary.Cases, caseSummary)
			continue
		}
		caseSummary.RelationCount = relationDoc.Diagnostics.RelationCount
		caseSummary.RelationTypeCounts = relationDoc.Diagnostics.RelationTypeCounts
		relationDiagnostics := relationDoc.Diagnostics
		caseSummary.RelationDiagnostics = &relationDiagnostics
		visualTreeDoc, err := visualtree.Compile(visualtree.Options{
			TokenPath:    filepath.Join(caseDir, "evidence_tokens.v1.json"),
			RelationPath: filepath.Join(caseDir, "relation_graph.v1.json"),
			OutputDir:    caseDir,
		})
		if err != nil {
			caseSummary.Status = "failed"
			caseSummary.Error = "visual tree: " + err.Error()
			summary.FailedCount++
			summary.Cases = append(summary.Cases, caseSummary)
			continue
		}
		caseSummary.VisualTreeNodeCount = visualTreeDoc.Diagnostics.NodeCount
		caseSummary.VisualTreeNodeTypeCounts = visualTreeDoc.Diagnostics.NodeTypeCounts
		visualTreeDiagnostics := visualTreeDoc.Diagnostics
		caseSummary.VisualTreeDiagnostics = &visualTreeDiagnostics
		caseSummary.DebugOverlayPath = filepath.Join(caseDir, "debug_overlay.png")
		caseSummary.PreviewSheetPath = filepath.Join(caseDir, "preview_sheet.png")
		caseSummary.EvidencePath = filepath.Join(caseDir, "m29_physical_evidence.v1.json")
		caseSummary.TokenPath = filepath.Join(caseDir, "evidence_tokens.v1.json")
		caseSummary.TokenOverlayPath = filepath.Join(caseDir, "token_overlay.png")
		caseSummary.TokenPreviewSheetPath = filepath.Join(caseDir, "token_preview_sheet.png")
		caseSummary.RelationPath = filepath.Join(caseDir, "relation_graph.v1.json")
		caseSummary.RelationOverlayPath = filepath.Join(caseDir, "relation_overlay.png")
		caseSummary.RelationPreviewSheetPath = filepath.Join(caseDir, "relation_preview_sheet.png")
		caseSummary.RelationReportPath = filepath.Join(caseDir, "relation_report.md")
		caseSummary.VisualTreePath = filepath.Join(caseDir, "visual_tree.v1.json")
		caseSummary.VisualTreeOverlayPath = filepath.Join(caseDir, "visual_tree_overlay.png")
		caseSummary.VisualTreePreviewSheetPath = filepath.Join(caseDir, "visual_tree_preview_sheet.png")
		caseSummary.VisualTreeReportPath = filepath.Join(caseDir, "visual_tree_report.md")
		caseSummary.VisualTreeContainmentReportPath = filepath.Join(caseDir, "visual_tree_containment_report.md")
		if doc.OCR.Provided {
			caseSummary.OCRPath = filepath.Join(caseDir, "ocr.json")
		}
		summary.CompletedCount++
		summary.Cases = append(summary.Cases, caseSummary)
	}
	if err := writeSummary(options.OutputDir, summary); err != nil {
		return Summary{}, err
	}
	if err := writeReview(options.OutputDir, summary); err != nil {
		return Summary{}, err
	}
	return summary, nil
}

func findPNGInputs(inputDir string) ([]string, error) {
	var out []string
	err := filepath.WalkDir(inputDir, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		name := strings.ToLower(entry.Name())
		if strings.HasSuffix(name, ".png") {
			out = append(out, path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Strings(out)
	return out, nil
}

func uniqueSlug(path string, used map[string]int) string {
	base := strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
	slug := sanitizeSlug(base)
	if slug == "" {
		slug = "case"
	}
	used[slug]++
	if used[slug] == 1 {
		return slug
	}
	return fmt.Sprintf("%s-%02d", slug, used[slug])
}

func sanitizeSlug(value string) string {
	value = strings.ToLower(value)
	var b strings.Builder
	lastDash := false
	for _, r := range value {
		ok := (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9')
		if ok {
			b.WriteRune(r)
			lastDash = false
			continue
		}
		if !lastDash {
			b.WriteByte('-')
			lastDash = true
		}
	}
	return strings.Trim(b.String(), "-")
}

func applyDocumentStats(caseSummary *CaseSummary, doc contract.Document) {
	counts := map[string]int{}
	for _, primitive := range doc.Primitives {
		counts[primitive.PrimitiveType]++
	}
	caseSummary.OCRBlockCount = doc.OCR.BlockCount
	caseSummary.PrimitiveCount = len(doc.Primitives)
	caseSummary.PrimitiveTypeCounts = counts
	caseSummary.TextMaskPixelCount = doc.Diagnostics.TextMaskPixelCount
	caseSummary.ForegroundPixelCount = doc.Diagnostics.ForegroundPixelCount
}

func writeSummary(outputDir string, summary Summary) error {
	data, err := json.MarshalIndent(summary, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "summary.json"), data, 0o644)
}

func writeReview(outputDir string, summary Summary) error {
	var b strings.Builder
	fmt.Fprintf(&b, "# M29 Batch Evidence Review\n\n")
	fmt.Fprintf(&b, "- inputDir: `%s`\n", summary.InputDir)
	fmt.Fprintf(&b, "- outputDir: `%s`\n", summary.OutputDir)
	if summary.OCRProvider != "" {
		fmt.Fprintf(&b, "- ocrProvider: `%s`\n", summary.OCRProvider)
	}
	fmt.Fprintf(&b, "- cases: %d completed, %d failed, %d total\n\n", summary.CompletedCount, summary.FailedCount, summary.CaseCount)
	fmt.Fprintf(&b, "| case | status | ocr | primitives | tokens | relations | visual nodes | main | review | suppressed | primitive types | token types | relation types | visual types | raw preview | token preview | relation preview | visual tree preview |\n")
	fmt.Fprintf(&b, "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- |\n")
	for _, item := range summary.Cases {
		types := formatCounts(item.PrimitiveTypeCounts)
		tokenTypes := formatCounts(item.TokenTypeCounts)
		relationTypes := formatCounts(item.RelationTypeCounts)
		visualTypes := formatCounts(item.VisualTreeNodeTypeCounts)
		mainTokens, reviewTokens, suppressedTokens := dispositionCounts(item.TokenDiagnostics)
		preview := item.PreviewSheetPath
		if preview == "" {
			preview = item.Error
		}
		tokenPreview := item.TokenPreviewSheetPath
		if tokenPreview == "" {
			tokenPreview = item.Error
		}
		relationPreview := item.RelationPreviewSheetPath
		if relationPreview == "" {
			relationPreview = item.Error
		}
		visualPreview := item.VisualTreePreviewSheetPath
		if visualPreview == "" {
			visualPreview = item.Error
		}
		fmt.Fprintf(&b, "| `%s` | %s | %d | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s | %s | `%s` | `%s` | `%s` | `%s` |\n", item.Slug, item.Status, item.OCRBlockCount, item.PrimitiveCount, item.TokenCount, item.RelationCount, item.VisualTreeNodeCount, mainTokens, reviewTokens, suppressedTokens, types, tokenTypes, relationTypes, visualTypes, preview, tokenPreview, relationPreview, visualPreview)
	}
	return os.WriteFile(filepath.Join(outputDir, "review.md"), []byte(b.String()), 0o644)
}

func dispositionCounts(diagnostics *evidence.Diagnostics) (int, int, int) {
	if diagnostics == nil {
		return 0, 0, 0
	}
	return diagnostics.MainTokenCount, diagnostics.ReviewTokenCount, diagnostics.SuppressedCount
}

func formatCounts(counts map[string]int) string {
	if len(counts) == 0 {
		return ""
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s:%d", key, counts[key]))
	}
	return strings.Join(parts, ", ")
}
