package layoutcompile

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image/png"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/validate"
)

const (
	LayoutIRFile         = "ui_layout_ir.v1.json"
	ValidationReportFile = "ui_layout_ir_validation.v1.json"
	CompileReportFile    = "layout_compile_report.md"
)

type Options struct {
	InputPath string
	OutputDir string
	TaskID    string
}

type Artifacts struct {
	LayoutIR         string
	ValidationReport string
	CompileReport    string
}

type Result struct {
	Document   contract.Document
	Validation validate.Report
	Artifacts  Artifacts
}

func Run(options Options) (Result, error) {
	if options.InputPath == "" {
		return Result{}, fmt.Errorf("input path is required")
	}
	if options.OutputDir == "" {
		return Result{}, fmt.Errorf("output directory is required")
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Result{}, err
	}
	imageMeta, err := readImageMeta(options.InputPath)
	if err != nil {
		return Result{}, err
	}
	doc := newEmptyDocument(imageMeta)
	validation := validate.Document(doc)

	artifacts := Artifacts{
		LayoutIR:         filepath.Join(options.OutputDir, LayoutIRFile),
		ValidationReport: filepath.Join(options.OutputDir, ValidationReportFile),
		CompileReport:    filepath.Join(options.OutputDir, CompileReportFile),
	}
	if err := writeJSON(artifacts.LayoutIR, doc); err != nil {
		return Result{}, err
	}
	if err := writeJSON(artifacts.ValidationReport, validation); err != nil {
		return Result{}, err
	}
	if err := os.WriteFile(artifacts.CompileReport, []byte(markdownReport(doc, validation)), 0o644); err != nil {
		return Result{}, err
	}

	return Result{Document: doc, Validation: validation, Artifacts: artifacts}, nil
}

func readImageMeta(path string) (contract.ImageMeta, error) {
	absPath, err := filepath.Abs(path)
	if err != nil {
		return contract.ImageMeta{}, err
	}
	bytes, err := os.ReadFile(absPath)
	if err != nil {
		return contract.ImageMeta{}, err
	}
	file, err := os.Open(absPath)
	if err != nil {
		return contract.ImageMeta{}, err
	}
	defer file.Close()
	img, err := png.Decode(file)
	if err != nil {
		return contract.ImageMeta{}, err
	}
	sum := sha256.Sum256(bytes)
	bounds := img.Bounds()
	return contract.ImageMeta{
		Path:   absPath,
		Width:  bounds.Dx(),
		Height: bounds.Dy(),
		SHA256: hex.EncodeToString(sum[:]),
	}, nil
}

func newEmptyDocument(image contract.ImageMeta) contract.Document {
	root := contract.Node{
		ID:   "node_0001",
		Type: contract.NodePage,
		BBox: geometry.Rect{Width: image.Width, Height: image.Height},
		Layout: contract.Layout{
			Mode: contract.LayoutColumn,
		},
		SourceRefs: []contract.SourceRef{{
			Kind: "source_image",
			ID:   "source_image",
			Role: "page_bounds",
		}},
		Confidence:     1,
		FallbackPolicy: "none",
	}
	doc := contract.Document{
		Version:     contract.Version,
		SourceImage: image,
		Root:        root,
		Decisions: []contract.Decision{{
			ID:     "decision_0001",
			State:  contract.DecisionEmit,
			NodeID: root.ID,
			Reason: "source_image_page_initialized",
			SourceRefs: []contract.SourceRef{{
				Kind: "source_image",
				ID:   "source_image",
				Role: "page_bounds",
			}},
			Score: 1,
		}},
	}
	doc.Summary = summarize(doc)
	return doc
}

func summarize(doc contract.Document) contract.Summary {
	typeCounts := map[string]int{}
	var countNodes func(contract.Node) int
	countNodes = func(node contract.Node) int {
		typeCounts[string(node.Type)]++
		total := 1
		for _, child := range node.Children {
			total += countNodes(child)
		}
		return total
	}
	return contract.Summary{
		NodeCount:     countNodes(doc.Root),
		AssetCount:    len(doc.Assets),
		EvidenceCount: len(doc.Evidence),
		DecisionCount: len(doc.Decisions),
		TypeCounts:    typeCounts,
	}
}

func writeJSON(path string, value any) error {
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	bytes = append(bytes, '\n')
	return os.WriteFile(path, bytes, 0o644)
}

func markdownReport(doc contract.Document, report validate.Report) string {
	return fmt.Sprintf(`# Layout Compile Report

- version: %s
- source: %s
- size: %dx%d
- nodes: %d
- assets: %d
- evidence: %d
- decisions: %d
- validation errors: %d
- validation warnings: %d

## Stage

Stage 1 contract skeleton only. Evidence normalization, segmentation, clustering, HTML preview, and Figma gateway are intentionally not active yet.
`,
		doc.Version,
		doc.SourceImage.Path,
		doc.SourceImage.Width,
		doc.SourceImage.Height,
		doc.Summary.NodeCount,
		doc.Summary.AssetCount,
		doc.Summary.EvidenceCount,
		doc.Summary.DecisionCount,
		report.ErrorCount,
		report.WarningCount,
	)
}
