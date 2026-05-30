package compiler

import (
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/audit"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/control"
	codiadiff "github.com/luqing-studio/image-figma/services/backend-go/internal/codia/diff"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

type Options struct {
	InputPath          string
	OCRPath            string
	OCRProvider        string
	GoldenPath         string
	DetectorCandidates string
	OutputDir          string
}

type Result struct {
	PhysicalEvidence contract.Document `json:"-"`
	EvidenceTokens   evidence.Document `json:"-"`
	LeafIR           ir.Document       `json:"-"`
	ControlStage     control.Result    `json:"-"`
	ControlIR        ir.Document       `json:"-"`
	TreeIR           ir.Document       `json:"-"`
	FigmaLikeTree    emitter.Document  `json:"-"`
	StructureDiff    *codiadiff.Document
	FailureAudit     *audit.Document
	DetectorManifest *DetectorManifest
	Artifacts        Artifacts
}

type Artifacts struct {
	PhysicalEvidence   string `json:"physicalEvidence"`
	EvidenceTokens     string `json:"evidenceTokens"`
	LeafIR             string `json:"leafIR"`
	ControlStage       string `json:"controlStage"`
	ControlIR          string `json:"controlIR"`
	TreeIR             string `json:"treeIR"`
	FigmaLikeTree      string `json:"figmaLikeTree"`
	StructureDiff      string `json:"structureDiff,omitempty"`
	StructureReport    string `json:"structureReport,omitempty"`
	FailureAudit       string `json:"failureAudit,omitempty"`
	FailureReport      string `json:"failureReport,omitempty"`
	DetectorManifest   string `json:"detectorManifest,omitempty"`
	DetectorCandidates string `json:"detectorCandidates,omitempty"`
}

type DetectorManifest struct {
	Version        string          `json:"version"`
	Mode           string          `json:"mode"`
	CandidatesPath string          `json:"candidatesPath"`
	Summary        DetectorSummary `json:"summary"`
}

type DetectorSummary struct {
	Total      int            `json:"total"`
	RoleCounts map[string]int `json:"roleCounts"`
	PassCounts map[string]int `json:"passCounts,omitempty"`
}
