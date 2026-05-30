package diff

import "github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"

const (
	SchemaName = "CodiaStructureDiff"
	Version    = "1.0"
)

type Options struct {
	GeneratedPath string
	GoldenPath    string
}

type Document struct {
	SchemaName string      `json:"schemaName"`
	Version    string      `json:"version"`
	Source     Source      `json:"source"`
	Summary    Summary     `json:"summary"`
	Checks     Checks      `json:"checks"`
	Generated  []NodeMatch `json:"generatedNodes"`
	Golden     []NodeMatch `json:"goldenNodes"`
	Edges      EdgeSummary `json:"edges"`
}

type Source struct {
	GeneratedPath string `json:"generatedPath,omitempty"`
	GoldenPath    string `json:"goldenPath,omitempty"`
}

type Summary struct {
	GeneratedNodeCount int             `json:"generatedNodeCount"`
	GoldenNodeCount    int             `json:"goldenNodeCount"`
	MatchedNodeCount   int             `json:"matchedNodeCount"`
	ExtraNodeCount     int             `json:"extraNodeCount"`
	MissedNodeCount    int             `json:"missedNodeCount"`
	RoleMetrics        map[string]Role `json:"roleMetrics"`
	ExtraByEvidence    map[string]int  `json:"extraByEvidenceKind,omitempty"`
	MissedByEvidence   map[string]int  `json:"missedByEvidenceKind,omitempty"`
	AverageBestIoU     float64         `json:"averageBestIoU"`
}

type Role struct {
	Generated int     `json:"generated"`
	Golden    int     `json:"golden"`
	Matched   int     `json:"matched"`
	Extra     int     `json:"extra"`
	Missed    int     `json:"missed"`
	Precision float64 `json:"precision"`
	Recall    float64 `json:"recall"`
}

type Checks struct {
	VisibleVocabularyPass       bool     `json:"visibleVocabularyPass"`
	VisibleVocabularyViolations []string `json:"visibleVocabularyViolations,omitempty"`
	ButtonBackgroundLast        LastRole `json:"buttonBackgroundLast"`
	EditTextBackgroundLast      LastRole `json:"editTextBackgroundLast"`
	BackgroundLate              LastRole `json:"backgroundLate"`
}

type LastRole struct {
	Pass       bool     `json:"pass"`
	Total      int      `json:"total"`
	Passed     int      `json:"passed"`
	Violations []string `json:"violations,omitempty"`
}

type NodeMatch struct {
	ID                   string  `json:"id"`
	Role                 ir.Role `json:"role"`
	ParentID             string  `json:"parentId,omitempty"`
	Path                 string  `json:"path"`
	SchemaID             string  `json:"schemaId,omitempty"`
	EvidenceKind         string  `json:"evidenceKind,omitempty"`
	EvidenceSourceID     string  `json:"evidenceSourceId,omitempty"`
	EvidenceNotes        string  `json:"evidenceNotes,omitempty"`
	SourcePath           string  `json:"sourcePath,omitempty"`
	SourceGUID           string  `json:"sourceGuid,omitempty"`
	VisibleName          string  `json:"visibleName"`
	FigmaType            string  `json:"figmaType"`
	BBox                 ir.BBox `json:"bbox"`
	BestID               string  `json:"bestId,omitempty"`
	BestRole             ir.Role `json:"bestRole,omitempty"`
	BestParentID         string  `json:"bestParentId,omitempty"`
	BestPath             string  `json:"bestPath,omitempty"`
	BestSchemaID         string  `json:"bestSchemaId,omitempty"`
	BestEvidenceKind     string  `json:"bestEvidenceKind,omitempty"`
	BestEvidenceSourceID string  `json:"bestEvidenceSourceId,omitempty"`
	BestEvidenceNotes    string  `json:"bestEvidenceNotes,omitempty"`
	BestSourcePath       string  `json:"bestSourcePath,omitempty"`
	BestSourceGUID       string  `json:"bestSourceGuid,omitempty"`
	BestBBox             ir.BBox `json:"bestBBox,omitempty"`
	BestIoU              float64 `json:"bestIoU"`
	ParentMatched        bool    `json:"parentMatched"`
	Verdict              string  `json:"verdict"`
	FailureStage         string  `json:"failureStage,omitempty"`
	FailureReason        string  `json:"failureReason,omitempty"`
	ChildRoleCount       int     `json:"childRoleCount"`
}

type EdgeSummary struct {
	Compared         int           `json:"compared"`
	Matched          int           `json:"matched"`
	Precision        float64       `json:"precision"`
	Recall           float64       `json:"recall"`
	GeneratedSamples []EdgeVerdict `json:"generatedSamples,omitempty"`
	GoldenSamples    []EdgeVerdict `json:"goldenSamples,omitempty"`
}

type EdgeVerdict struct {
	ChildID        string  `json:"childId"`
	ChildRole      ir.Role `json:"childRole"`
	ParentID       string  `json:"parentId,omitempty"`
	ParentRole     ir.Role `json:"parentRole,omitempty"`
	BestID         string  `json:"bestId,omitempty"`
	BestParentID   string  `json:"bestParentId,omitempty"`
	BestParentRole ir.Role `json:"bestParentRole,omitempty"`
	Verdict        string  `json:"verdict"`
}

type nodeRecord struct {
	Node     ir.Node
	Parent   *nodeRecord
	Path     string
	Children []*nodeRecord
}
