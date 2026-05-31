package compile

import (
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
)

const (
	GraphArtifactName = "editable_layer_graph.v1.json"
)

type Options struct {
	InputPath   string
	OutputDir   string
	TaskID      string
	OCRPath     string
	OCRProvider string
}

type Result struct {
	Graph      contract.Document
	Validation validate.Report
	DSL        exportdsl.Document
	Artifacts  Artifacts
}

type Artifacts struct {
	M29PhysicalEvidence string `json:"m29PhysicalEvidence"`
	EvidenceTokens      string `json:"evidenceTokens"`
	EditableLayerGraph  string `json:"editableLayerGraph"`
	ValidationReport    string `json:"validationReport"`
	AssetManifest       string `json:"assetManifest"`
	RuntimeDSL          string `json:"runtimeDsl"`
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

	graph, err := assemble.Build(assemble.Input{
		Image: contract.ImageMeta{
			Path:   options.InputPath,
			Width:  m29Doc.Image.Width,
			Height: m29Doc.Image.Height,
		},
		Tokens: tokenDoc,
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
			EditableLayerGraph:  filepath.ToSlash(filepath.Join("draft", GraphArtifactName)),
			ValidationReport:    filepath.ToSlash(filepath.Join("draft", report.ValidationReportName)),
			AssetManifest:       filepath.ToSlash(filepath.Join("assets", asset.ManifestName)),
			RuntimeDSL:          filepath.ToSlash(filepath.Join("draft", exportdsl.ArtifactName)),
		},
	}, nil
}

func writeGraph(path string, graph contract.Document) error {
	data, err := json.MarshalIndent(graph, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}
