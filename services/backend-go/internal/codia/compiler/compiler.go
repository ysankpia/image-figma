package compiler

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/audit"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/control"
	codiadiff "github.com/luqing-studio/image-figma/services/backend-go/internal/codia/diff"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/leaf"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/tree"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	m29pipeline "github.com/luqing-studio/image-figma/services/backend-go/internal/m29/pipeline"
)

func Compile(options Options) (Result, error) {
	if options.InputPath == "" {
		return Result{}, fmt.Errorf("missing input path")
	}
	if options.OutputDir == "" {
		return Result{}, fmt.Errorf("missing output dir")
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Result{}, err
	}

	paths := outputPaths(options.OutputDir)
	physical, err := m29pipeline.Run(m29pipeline.Options{
		InputPath:   options.InputPath,
		OCRPath:     options.OCRPath,
		OCRProvider: options.OCRProvider,
		OutputDir:   paths.extractDir,
	})
	if err != nil {
		return Result{}, fmt.Errorf("m29 physical evidence: %w", err)
	}

	tokens, err := evidence.Compile(evidence.Options{
		InputPath: filepath.Join(paths.extractDir, "m29_physical_evidence.v1.json"),
		OutputDir: paths.tokensDir,
	})
	if err != nil {
		return Result{}, fmt.Errorf("m29 evidence tokens: %w", err)
	}

	leafIR, err := leaf.Compile(leaf.Options{TokenPath: filepath.Join(paths.tokensDir, "evidence_tokens.v1.json")})
	if err != nil {
		return Result{}, fmt.Errorf("codia leaves: %w", err)
	}
	if err := leaf.WriteArtifacts(paths.leavesDir, leafIR); err != nil {
		return Result{}, fmt.Errorf("write leaf artifacts: %w", err)
	}

	controlStage, err := control.Compile(control.Options{InputPath: filepath.Join(paths.leavesDir, leaf.ArtifactName)})
	if err != nil {
		return Result{}, fmt.Errorf("codia controls: %w", err)
	}
	if err := control.WriteArtifacts(paths.controlsDir, controlStage); err != nil {
		return Result{}, fmt.Errorf("write control artifacts: %w", err)
	}
	controlIR := control.ToDocument(controlStage)

	treeIR, err := tree.BuildFromControl(controlStage)
	if err != nil {
		return Result{}, fmt.Errorf("codia tree: %w", err)
	}
	treeIR.Source.InputPath = options.InputPath
	if err := tree.WriteArtifacts(options.OutputDir, treeIR); err != nil {
		return Result{}, fmt.Errorf("write tree ir: %w", err)
	}

	emitted, err := emitter.Emit(treeIR)
	if err != nil {
		return Result{}, fmt.Errorf("emit figma-like tree: %w", err)
	}
	if err := emitter.WriteArtifact(options.OutputDir, emitted); err != nil {
		return Result{}, fmt.Errorf("write emitted tree: %w", err)
	}

	result := Result{
		PhysicalEvidence: physical,
		EvidenceTokens:   tokens,
		LeafIR:           leafIR,
		ControlStage:     controlStage,
		ControlIR:        controlIR,
		TreeIR:           treeIR,
		FigmaLikeTree:    emitted,
		Artifacts: Artifacts{
			PhysicalEvidence: filepath.ToSlash(filepath.Join("extract", "m29_physical_evidence.v1.json")),
			EvidenceTokens:   filepath.ToSlash(filepath.Join("tokens", "evidence_tokens.v1.json")),
			LeafIR:           filepath.ToSlash(filepath.Join("leaves", leaf.ArtifactName)),
			ControlStage:     filepath.ToSlash(filepath.Join("controls", control.StageArtifactName)),
			ControlIR:        filepath.ToSlash(filepath.Join("controls", control.ArtifactName)),
			TreeIR:           tree.ArtifactName,
			FigmaLikeTree:    "codia_figma_like_tree.v1.json",
		},
	}

	if options.GoldenPath != "" {
		diffDoc, err := codiadiff.Compile(codiadiff.Options{
			GeneratedPath: filepath.Join(options.OutputDir, "codia_tree_ir.v1.json"),
			GoldenPath:    options.GoldenPath,
		})
		if err != nil {
			return Result{}, fmt.Errorf("codia structure diff: %w", err)
		}
		if err := codiadiff.WriteArtifacts(paths.diffDir, diffDoc); err != nil {
			return Result{}, fmt.Errorf("write diff artifacts: %w", err)
		}
		auditDoc, err := audit.Compile(audit.Options{
			DiffPath:     filepath.Join(paths.diffDir, "codia_structure_diff.v1.json"),
			TokenPath:    filepath.Join(paths.tokensDir, "evidence_tokens.v1.json"),
			PhysicalPath: filepath.Join(paths.extractDir, "m29_physical_evidence.v1.json"),
		})
		if err != nil {
			return Result{}, fmt.Errorf("codia failure audit: %w", err)
		}
		auditDoc.Source.DiffPath = filepath.Join(paths.diffDir, "codia_structure_diff.v1.json")
		if err := audit.WriteArtifacts(paths.auditDir, auditDoc); err != nil {
			return Result{}, fmt.Errorf("write failure audit artifacts: %w", err)
		}
		result.StructureDiff = &diffDoc
		result.FailureAudit = &auditDoc
		result.Artifacts.StructureDiff = filepath.ToSlash(filepath.Join("diff", "codia_structure_diff.v1.json"))
		result.Artifacts.StructureReport = filepath.ToSlash(filepath.Join("diff", "codia_structure_diff_report.md"))
		result.Artifacts.FailureAudit = filepath.ToSlash(filepath.Join("audit", "codia_failure_audit.v1.json"))
		result.Artifacts.FailureReport = filepath.ToSlash(filepath.Join("audit", "codia_failure_audit_report.md"))
	}

	return result, nil
}

type paths struct {
	extractDir  string
	tokensDir   string
	leavesDir   string
	controlsDir string
	diffDir     string
	auditDir    string
}

func outputPaths(outputDir string) paths {
	return paths{
		extractDir:  filepath.Join(outputDir, "extract"),
		tokensDir:   filepath.Join(outputDir, "tokens"),
		leavesDir:   filepath.Join(outputDir, "leaves"),
		controlsDir: filepath.Join(outputDir, "controls"),
		diffDir:     filepath.Join(outputDir, "diff"),
		auditDir:    filepath.Join(outputDir, "audit"),
	}
}
