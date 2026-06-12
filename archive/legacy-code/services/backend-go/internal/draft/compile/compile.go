package compile

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/assemble"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/asset"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/exportdsl"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/report"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/validate"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/pipeline"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

const (
	GraphArtifactName = "editable_layer_graph.v1.json"
)

type Options struct {
	InputPath     string
	OutputDir     string
	TaskID        string
	OCRPath       string
	OCRProvider   string
	VisionEnabled bool
	VisionOptions detector.Options
}

type Result struct {
	Graph      contract.Document
	Validation validate.Report
	DSL        exportdsl.Document
	Artifacts  Artifacts
	Warnings   []Warning
}

type Artifacts struct {
	M29PhysicalEvidence string `json:"m29PhysicalEvidence"`
	EvidenceTokens      string `json:"evidenceTokens"`
	VisionCandidates    string `json:"visionCandidates,omitempty"`
	VisionReport        string `json:"visionReport,omitempty"`
	VisionOverlay       string `json:"visionOverlay,omitempty"`
	VisionRawResponses  string `json:"visionRawResponses,omitempty"`
	VisionFallback      string `json:"visionFallback,omitempty"`
	EditableLayerGraph  string `json:"editableLayerGraph"`
	ValidationReport    string `json:"validationReport"`
	AssetManifest       string `json:"assetManifest"`
	RuntimeDSL          string `json:"runtimeDsl"`
}

type Warning struct {
	Code     string `json:"code"`
	Message  string `json:"message"`
	Stage    string `json:"stage,omitempty"`
	Artifact string `json:"artifact,omitempty"`
}

func Run(options Options) (Result, error) {
	if options.InputPath == "" {
		return Result{}, fmt.Errorf("missing input path")
	}
	if options.OutputDir == "" {
		return Result{}, fmt.Errorf("missing output dir")
	}
	taskID := options.TaskID
	if taskID == "" {
		taskID = "draft_task"
	}

	m29Dir := filepath.Join(options.OutputDir, "m29")
	tokensDir := filepath.Join(options.OutputDir, "tokens")
	visionDir := filepath.Join(options.OutputDir, "vision")
	draftDir := filepath.Join(options.OutputDir, "draft")
	assetsDir := filepath.Join(options.OutputDir, "assets")
	if err := os.MkdirAll(draftDir, 0o755); err != nil {
		return Result{}, err
	}

	m29Doc, err := pipeline.Run(pipeline.Options{
		InputPath:   options.InputPath,
		OCRPath:     options.OCRPath,
		OCRProvider: options.OCRProvider,
		OutputDir:   m29Dir,
	})
	if err != nil {
		return Result{}, fmt.Errorf("m29 physical evidence: %w", err)
	}
	tokenDoc, err := evidence.Compile(evidence.Options{
		InputPath: filepath.Join(m29Dir, "m29_physical_evidence.v1.json"),
		OutputDir: tokensDir,
	})
	if err != nil {
		return Result{}, fmt.Errorf("m29 evidence tokens: %w", err)
	}

	var detectorDoc *detector.Document
	var warnings []Warning
	visionArtifacts := visionArtifactPaths{}
	if options.VisionEnabled {
		visionResult, warning := runVision(options, visionDir)
		if warning != nil {
			warnings = append(warnings, *warning)
			visionArtifacts.Fallback = warning.Artifact
		} else {
			detectorDoc = &visionResult.Document
			visionArtifacts.Candidates = filepath.ToSlash(filepath.Join("vision", visionResult.Artifacts.Candidates))
			visionArtifacts.Report = filepath.ToSlash(filepath.Join("vision", visionResult.Artifacts.Report))
			visionArtifacts.Overlay = filepath.ToSlash(filepath.Join("vision", visionResult.Artifacts.Overlay))
			if len(visionResult.Artifacts.RawResponses) > 0 {
				visionArtifacts.RawResponses = filepath.ToSlash(filepath.Join("vision", "raw_model_response"))
			}
		}
	}

	graph, err := assemble.Build(assemble.Input{
		Image: contract.ImageMeta{
			Path:            options.InputPath,
			Width:           m29Doc.Image.Width,
			Height:          m29Doc.Image.Height,
			BackgroundColor: m29Doc.Diagnostics.BackgroundColor,
		},
		Tokens:   tokenDoc,
		Detector: detectorDoc,
	})
	if err != nil {
		return Result{}, fmt.Errorf("draft assemble: %w", err)
	}
	if err := writeGraph(filepath.Join(draftDir, GraphArtifactName), graph); err != nil {
		return Result{}, err
	}

	validation := validate.Graph(graph)
	if err := report.WriteValidationReport(draftDir, graph, validation); err != nil {
		return Result{}, err
	}
	if validation.ErrorCount > 0 {
		return Result{}, fmt.Errorf("draft validation failed with %d errors", validation.ErrorCount)
	}

	if err := asset.WriteLayerAssets(assetsDir, options.InputPath, graph); err != nil {
		return Result{}, err
	}
	manifest := asset.FromGraph(graph)
	if err := asset.WriteManifest(assetsDir, manifest); err != nil {
		return Result{}, err
	}

	dsl := exportdsl.Export(taskID, graph)
	if err := exportdsl.WriteArtifact(draftDir, dsl); err != nil {
		return Result{}, err
	}

	return Result{
		Graph:      graph,
		Validation: validation,
		DSL:        dsl,
		Artifacts: Artifacts{
			M29PhysicalEvidence: filepath.ToSlash(filepath.Join("m29", "m29_physical_evidence.v1.json")),
			EvidenceTokens:      filepath.ToSlash(filepath.Join("tokens", "evidence_tokens.v1.json")),
			VisionCandidates:    visionArtifacts.Candidates,
			VisionReport:        visionArtifacts.Report,
			VisionOverlay:       visionArtifacts.Overlay,
			VisionRawResponses:  visionArtifacts.RawResponses,
			VisionFallback:      visionArtifacts.Fallback,
			EditableLayerGraph:  filepath.ToSlash(filepath.Join("draft", GraphArtifactName)),
			ValidationReport:    filepath.ToSlash(filepath.Join("draft", report.ValidationReportName)),
			AssetManifest:       filepath.ToSlash(filepath.Join("assets", asset.ManifestName)),
			RuntimeDSL:          filepath.ToSlash(filepath.Join("draft", exportdsl.ArtifactName)),
		},
		Warnings: warnings,
	}, nil
}

type visionArtifactPaths struct {
	Candidates   string
	Report       string
	Overlay      string
	RawResponses string
	Fallback     string
}

func runVision(options Options, outputDir string) (detector.RunResult, *Warning) {
	visionOptions := options.VisionOptions
	visionOptions.InputPath = options.InputPath
	visionOptions.OutputDir = outputDir
	result, err := detector.Run(context.Background(), visionOptions)
	if err == nil {
		return result, nil
	}
	artifact := filepath.ToSlash(filepath.Join("vision", "vision_detector_fallback.v1.json"))
	if writeErr := writeVisionFallback(filepath.Join(outputDir, "vision_detector_fallback.v1.json"), err); writeErr != nil {
		err = fmt.Errorf("%v; fallback write failed: %w", err, writeErr)
	}
	return detector.RunResult{}, &Warning{
		Code:     "DRAFT_VISION_FALLBACK",
		Message:  err.Error(),
		Stage:    "vision_detector",
		Artifact: artifact,
	}
}

func writeVisionFallback(path string, cause error) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	payload := map[string]any{
		"version": "vision_detector_fallback.v1",
		"stage":   "vision_detector",
		"reason":  cause.Error(),
		"policy":  "continue_with_m29_ocr_draft",
	}
	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}

func writeGraph(path string, graph contract.Document) error {
	data, err := json.MarshalIndent(graph, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}
