package assembly

import (
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

const (
	SchemaName = "CodiaAssembly"
	Version    = "1.0"

	SourceCandidatesArtifactName = "codia_source_candidates.v1.json"
	OwnershipGraphArtifactName   = "codia_ownership_graph.v1.json"
	ReportArtifactName           = "codia_assembly_report.md"
)

type Options struct {
	Leaf             ir.Document
	Physical         contract.Document
	Tokens           evidence.Document
	Detector         *detector.Document
	DetectorPath     string
	PhysicalPath     string
	TokenPath        string
	SourceOutputPath string
}

type Result struct {
	SchemaName       string                   `json:"schemaName"`
	Version          string                   `json:"version"`
	Source           Source                   `json:"source"`
	Document         ir.Document              `json:"-"`
	SourceCandidates SourceCandidatesDocument `json:"sourceCandidates"`
	OwnershipGraph   OwnershipGraphDocument   `json:"ownershipGraph"`
	Diagnostics      Diagnostics              `json:"diagnostics"`
}

type Source struct {
	LeafPath         string `json:"leafPath,omitempty"`
	PhysicalPath     string `json:"physicalPath,omitempty"`
	TokenPath        string `json:"tokenPath,omitempty"`
	DetectorPath     string `json:"detectorPath,omitempty"`
	SourceOutputPath string `json:"sourceOutputPath,omitempty"`
}

type SourceCandidatesDocument struct {
	SchemaName string            `json:"schemaName"`
	Version    string            `json:"version"`
	Source     Source            `json:"source"`
	Candidates []CandidateRecord `json:"candidates"`
	Summary    CandidateSummary  `json:"summary"`
}

type CandidateRecord struct {
	ID            string   `json:"id"`
	Kind          string   `json:"kind"`
	Role          ir.Role  `json:"role"`
	SourceIDs     []string `json:"sourceIds,omitempty"`
	BBox          ir.BBox  `json:"bbox"`
	Confidence    float64  `json:"confidence"`
	Decision      string   `json:"decision"`
	Score         float64  `json:"score"`
	Reason        string   `json:"reason"`
	BBoxAuthority string   `json:"bboxAuthority"`
	OwnerID       string   `json:"ownerId,omitempty"`
	PassID        string   `json:"passId,omitempty"`
	RawLabel      string   `json:"rawLabel,omitempty"`
}

type CandidateSummary struct {
	Total        int            `json:"total"`
	ByDecision   map[string]int `json:"byDecision"`
	ByRole       map[string]int `json:"byRole"`
	EmittedCount int            `json:"emittedCount"`
	HintCount    int            `json:"hintCount"`
}

type OwnershipGraphDocument struct {
	SchemaName string          `json:"schemaName"`
	Version    string          `json:"version"`
	Source     Source          `json:"source"`
	Nodes      []OwnershipNode `json:"nodes"`
	Edges      []OwnershipEdge `json:"edges"`
	Summary    GraphSummary    `json:"summary"`
}

type OwnershipNode struct {
	ID            string   `json:"id"`
	Role          ir.Role  `json:"role"`
	BBox          ir.BBox  `json:"bbox"`
	Decision      string   `json:"decision"`
	Reason        string   `json:"reason"`
	Score         float64  `json:"score"`
	BBoxAuthority string   `json:"bboxAuthority"`
	SourceIDs     []string `json:"sourceIds,omitempty"`
}

type OwnershipEdge struct {
	FromID string  `json:"fromId"`
	ToID   string  `json:"toId"`
	Kind   string  `json:"kind"`
	Score  float64 `json:"score"`
	Reason string  `json:"reason"`
}

type GraphSummary struct {
	NodeCount int            `json:"nodeCount"`
	EdgeCount int            `json:"edgeCount"`
	Decisions map[string]int `json:"decisions"`
}

type Diagnostics struct {
	InputLeafCount         int            `json:"inputLeafCount"`
	DetectorCandidateCount int            `json:"detectorCandidateCount"`
	OutputNodeCount        int            `json:"outputNodeCount"`
	ConsumedCount          int            `json:"consumedCount"`
	SuppressedCount        int            `json:"suppressedCount"`
	RefinedCount           int            `json:"refinedCount"`
	HintCount              int            `json:"hintCount"`
	RoleCounts             map[string]int `json:"roleCounts,omitempty"`
}
