package compiler

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/assembly"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/audit"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/control"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	codiadiff "github.com/luqing-studio/image-figma/services/backend-go/internal/codia/diff"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
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
	var detectorManifest *DetectorManifest
	var detectorDoc *detector.Document
	if options.DetectorCandidates != "" {
		doc, err := detector.ReadDocument(options.DetectorCandidates)
		if err != nil {
			return Result{}, fmt.Errorf("read detector candidates: %w", err)
		}
		manifest, err := writeDetectorManifest(paths.detectorDir, options.DetectorCandidates, doc)
		if err != nil {
			return Result{}, fmt.Errorf("detector candidates report-only manifest: %w", err)
		}
		detectorManifest = &manifest
		detectorDoc = &doc
	}
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

	assemblyResult, err := assembly.Build(assembly.Options{
		Leaf:             leafIR,
		Physical:         physical,
		Tokens:           tokens,
		Detector:         detectorDoc,
		DetectorPath:     options.DetectorCandidates,
		PhysicalPath:     filepath.Join(paths.extractDir, "m29_physical_evidence.v1.json"),
		TokenPath:        filepath.Join(paths.tokensDir, "evidence_tokens.v1.json"),
		SourceOutputPath: filepath.Join(paths.assemblyDir, "codia_ir.v1.json"),
	})
	if err != nil {
		return Result{}, fmt.Errorf("codia assembly: %w", err)
	}
	if err := assembly.WriteArtifacts(paths.assemblyDir, assemblyResult); err != nil {
		return Result{}, fmt.Errorf("write assembly artifacts: %w", err)
	}
	if err := ir.WriteArtifact(paths.assemblyDir, assemblyResult.Document); err != nil {
		return Result{}, fmt.Errorf("write assembly ir: %w", err)
	}

	controlStage, err := control.Compile(control.Options{InputPath: filepath.Join(paths.assemblyDir, "codia_ir.v1.json")})
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
		Assembly:         assemblyResult,
		AssemblyIR:       assemblyResult.Document,
		ControlStage:     controlStage,
		ControlIR:        controlIR,
		TreeIR:           treeIR,
		FigmaLikeTree:    emitted,
		DetectorManifest: detectorManifest,
		Artifacts: Artifacts{
			PhysicalEvidence: filepath.ToSlash(filepath.Join("extract", "m29_physical_evidence.v1.json")),
			EvidenceTokens:   filepath.ToSlash(filepath.Join("tokens", "evidence_tokens.v1.json")),
			LeafIR:           filepath.ToSlash(filepath.Join("leaves", leaf.ArtifactName)),
			AssemblyIR:       filepath.ToSlash(filepath.Join("assembly", "codia_ir.v1.json")),
			SourceCandidates: filepath.ToSlash(filepath.Join("assembly", assembly.SourceCandidatesArtifactName)),
			OwnershipGraph:   filepath.ToSlash(filepath.Join("assembly", assembly.OwnershipGraphArtifactName)),
			AssemblyReport:   filepath.ToSlash(filepath.Join("assembly", assembly.ReportArtifactName)),
			ControlStage:     filepath.ToSlash(filepath.Join("controls", control.StageArtifactName)),
			ControlIR:        filepath.ToSlash(filepath.Join("controls", control.ArtifactName)),
			TreeIR:           tree.ArtifactName,
			FigmaLikeTree:    "codia_figma_like_tree.v1.json",
		},
	}
	if detectorManifest != nil {
		result.Artifacts.DetectorManifest = filepath.ToSlash(filepath.Join("detector", "detector_manifest.v1.json"))
		result.Artifacts.DetectorCandidates = options.DetectorCandidates
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
	assemblyDir string
	controlsDir string
	detectorDir string
	diffDir     string
	auditDir    string
}

func outputPaths(outputDir string) paths {
	return paths{
		extractDir:  filepath.Join(outputDir, "extract"),
		tokensDir:   filepath.Join(outputDir, "tokens"),
		leavesDir:   filepath.Join(outputDir, "leaves"),
		assemblyDir: filepath.Join(outputDir, "assembly"),
		controlsDir: filepath.Join(outputDir, "controls"),
		detectorDir: filepath.Join(outputDir, "detector"),
		diffDir:     filepath.Join(outputDir, "diff"),
		auditDir:    filepath.Join(outputDir, "audit"),
	}
}

func writeDetectorManifest(outputDir string, candidatesPath string, doc detector.Document) (DetectorManifest, error) {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return DetectorManifest{}, err
	}
	manifest := DetectorManifest{
		Version:        "detector_manifest.v1",
		Mode:           "report_only",
		CandidatesPath: candidatesPath,
		Summary: DetectorSummary{
			Total:      doc.Summary.Total,
			RoleCounts: doc.Summary.RoleCounts,
			PassCounts: doc.Summary.PassCounts,
		},
	}
	data, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return DetectorManifest{}, err
	}
	if err := os.WriteFile(filepath.Join(outputDir, "detector_manifest.v1.json"), data, 0o644); err != nil {
		return DetectorManifest{}, err
	}
	return manifest, nil
}
