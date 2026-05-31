package layoutcompile

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image/png"
	"os"
	"path/filepath"
	"sort"
	"strings"

	htmlrender "github.com/luqing-studio/image-figma/services/backend-go/internal/htmlpreview/render"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutcompile/cluster"
	layoutevidence "github.com/luqing-studio/image-figma/services/backend-go/internal/layoutcompile/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutcompile/materialize"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutcompile/segment"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/validate"
	m29evidence "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/pipeline"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

const (
	LayoutIRFile         = "ui_layout_ir.v1.json"
	ValidationReportFile = "ui_layout_ir_validation.v1.json"
	CompileReportFile    = "layout_compile_report.md"
)

type Options struct {
	InputPath                 string
	OutputDir                 string
	TaskID                    string
	OCRPath                   string
	OCRProvider               string
	VisionEnabled             bool
	VisionCandidatesPath      string
	VisionOptions             detector.Options
	SkipEvidenceNormalization bool
}

type Artifacts struct {
	LayoutIR            string
	ValidationReport    string
	CompileReport       string
	M29PhysicalEvidence string
	EvidenceTokens      string
	VisionCandidates    string
	VisionFallback      string
	PreviewHTML         string
	DebugHTML           string
	PreviewReport       string
}

type Result struct {
	Document   contract.Document
	Validation validate.Report
	Artifacts  Artifacts
	Warnings   []Warning
}

type Warning struct {
	Code     string `json:"code"`
	Message  string `json:"message"`
	Stage    string `json:"stage,omitempty"`
	Artifact string `json:"artifact,omitempty"`
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
	artifacts := Artifacts{
		LayoutIR:            filepath.Join(options.OutputDir, LayoutIRFile),
		ValidationReport:    filepath.Join(options.OutputDir, ValidationReportFile),
		CompileReport:       filepath.Join(options.OutputDir, CompileReportFile),
		M29PhysicalEvidence: filepath.ToSlash(filepath.Join("m29", "m29_physical_evidence.v1.json")),
		EvidenceTokens:      filepath.ToSlash(filepath.Join("tokens", "evidence_tokens.v1.json")),
	}
	var warnings []Warning
	var normalized []contract.Evidence
	if !options.SkipEvidenceNormalization {
		tokenDoc, err := runM29(options)
		if err != nil {
			return Result{}, err
		}
		var detectorDoc *detector.Document
		detectorDoc, artifacts, warnings, err = loadOrRunVision(options, artifacts)
		if err != nil {
			return Result{}, err
		}
		normalized = layoutevidence.Normalize(layoutevidence.Input{
			Bounds:   geometry.Rect{Width: imageMeta.Width, Height: imageMeta.Height},
			Tokens:   tokenDoc,
			Detector: detectorDoc,
		})
	}
	doc := newEmptyDocument(imageMeta)
	doc.Evidence = normalized
	if len(normalized) > 0 {
		segmentation := segment.Build(geometry.Rect{Width: imageMeta.Width, Height: imageMeta.Height}, normalized, segment.Options{})
		sections := make([]contract.Node, 0, len(segmentation.Sections))
		for _, section := range segmentation.Sections {
			withRows, rowDecisions := cluster.BuildRows(section, normalized, cluster.Options{})
			sections = append(sections, withRows)
			doc.Decisions = append(doc.Decisions, rowDecisions...)
		}
		doc.Root.Children = sections
		doc.Decisions = append(doc.Decisions, segmentation.Decisions...)
		doc = materialize.Build(doc, materialize.Options{})
	}
	doc.Summary = summarize(doc)
	validation := validate.Document(doc)

	if err := writeJSON(artifacts.LayoutIR, doc); err != nil {
		return Result{}, err
	}
	if err := writeJSON(artifacts.ValidationReport, validation); err != nil {
		return Result{}, err
	}
	htmlArtifacts, err := htmlrender.Write(doc, htmlrender.Options{OutputDir: options.OutputDir})
	if err != nil {
		return Result{}, fmt.Errorf("html preview: %w", err)
	}
	artifacts.PreviewHTML = htmlArtifacts.PreviewHTML
	artifacts.DebugHTML = htmlArtifacts.DebugHTML
	artifacts.PreviewReport = htmlArtifacts.PreviewReport
	for _, warning := range htmlArtifacts.Warnings {
		warnings = append(warnings, Warning{
			Code:     warning.Code,
			Message:  warning.Message,
			Stage:    "html_preview",
			Artifact: htmlArtifacts.PreviewReport,
		})
	}
	if err := os.WriteFile(artifacts.CompileReport, []byte(markdownReport(doc, validation)), 0o644); err != nil {
		return Result{}, err
	}

	return Result{Document: doc, Validation: validation, Artifacts: artifacts, Warnings: warnings}, nil
}

func runM29(options Options) (m29evidence.Document, error) {
	m29Dir := filepath.Join(options.OutputDir, "m29")
	tokensDir := filepath.Join(options.OutputDir, "tokens")
	if _, err := pipeline.Run(pipeline.Options{
		InputPath:   options.InputPath,
		OCRPath:     options.OCRPath,
		OCRProvider: options.OCRProvider,
		OutputDir:   m29Dir,
	}); err != nil {
		return m29evidence.Document{}, fmt.Errorf("m29 physical evidence: %w", err)
	}
	tokenDoc, err := m29evidence.Compile(m29evidence.Options{
		InputPath: filepath.Join(m29Dir, "m29_physical_evidence.v1.json"),
		OutputDir: tokensDir,
	})
	if err != nil {
		return m29evidence.Document{}, fmt.Errorf("m29 evidence tokens: %w", err)
	}
	return tokenDoc, nil
}

func loadOrRunVision(options Options, artifacts Artifacts) (*detector.Document, Artifacts, []Warning, error) {
	if options.VisionCandidatesPath != "" {
		doc, err := readVisionCandidates(options.VisionCandidatesPath)
		if err != nil {
			return nil, artifacts, nil, err
		}
		artifacts.VisionCandidates = options.VisionCandidatesPath
		return &doc, artifacts, nil, nil
	}
	if !options.VisionEnabled {
		return nil, artifacts, nil, nil
	}
	visionDir := filepath.Join(options.OutputDir, "vision")
	visionOptions := options.VisionOptions
	visionOptions.InputPath = options.InputPath
	visionOptions.OutputDir = visionDir
	result, err := detector.Run(context.Background(), visionOptions)
	if err == nil {
		artifacts.VisionCandidates = filepath.ToSlash(filepath.Join("vision", result.Artifacts.Candidates))
		return &result.Document, artifacts, nil, nil
	}
	fallback := filepath.Join(visionDir, "vision_detector_fallback.v1.json")
	if writeErr := writeVisionFallback(fallback, err); writeErr != nil {
		err = fmt.Errorf("%v; fallback write failed: %w", err, writeErr)
	}
	artifacts.VisionFallback = filepath.ToSlash(filepath.Join("vision", "vision_detector_fallback.v1.json"))
	return nil, artifacts, []Warning{{
		Code:     "LAYOUT_VISION_FALLBACK",
		Message:  err.Error(),
		Stage:    "vision_detector",
		Artifact: artifacts.VisionFallback,
	}}, nil
}

func readVisionCandidates(path string) (detector.Document, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return detector.Document{}, err
	}
	var doc detector.Document
	if err := json.Unmarshal(data, &doc); err != nil {
		return detector.Document{}, err
	}
	if doc.Version != detector.CandidatesVersion {
		return detector.Document{}, fmt.Errorf("expected %s, got %q", detector.CandidatesVersion, doc.Version)
	}
	return doc, nil
}

func writeVisionFallback(path string, cause error) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload := map[string]any{
		"version": "layout_vision_fallback.v1",
		"stage":   "vision_detector",
		"reason":  cause.Error(),
		"policy":  "continue_with_m29_ocr_layout",
	}
	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
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
	var b strings.Builder
	fmt.Fprintf(&b, `# Layout Compile Report

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

Stage 8A visible leaf materialization is active. Figma gateway is intentionally not active yet.

## HTML Preview

- preview: %s
- debug preview: %s
- report: %s
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
		htmlrender.PreviewHTMLFile,
		htmlrender.DebugHTMLFile,
		htmlrender.PreviewReportFile,
	)
	writeCountTable(&b, "Evidence By Kind", countEvidenceByKind(doc.Evidence))
	writeCountTable(&b, "Evidence By Role Hint", countEvidenceByRoleHint(doc.Evidence))
	return b.String()
}

func countEvidenceByKind(items []contract.Evidence) map[string]int {
	out := map[string]int{}
	for _, item := range items {
		out[item.Kind]++
	}
	return out
}

func countEvidenceByRoleHint(items []contract.Evidence) map[string]int {
	out := map[string]int{}
	for _, item := range items {
		key := item.RoleHint
		if key == "" {
			key = "(none)"
		}
		out[key]++
	}
	return out
}

func writeCountTable(b *strings.Builder, title string, values map[string]int) {
	if len(values) == 0 {
		return
	}
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		if values[keys[i]] != values[keys[j]] {
			return values[keys[i]] > values[keys[j]]
		}
		return keys[i] < keys[j]
	})
	fmt.Fprintf(b, "\n## %s\n\n", title)
	fmt.Fprintf(b, "| key | count |\n")
	fmt.Fprintf(b, "| --- | ---: |\n")
	for _, key := range keys {
		fmt.Fprintf(b, "| `%s` | %d |\n", key, values[key])
	}
}
