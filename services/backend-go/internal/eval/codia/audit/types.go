package audit

import "github.com/luqing-studio/image-figma/services/backend-go/internal/eval/codia/ir"

const (
	SchemaName = "CodiaFailureAudit"
	Version    = "1.0"
)

type Options struct {
	DiffPath     string
	TokenPath    string
	PhysicalPath string
}

type Document struct {
	SchemaName string        `json:"schemaName"`
	Version    string        `json:"version"`
	Source     Source        `json:"source"`
	Summary    Summary       `json:"summary"`
	Groups     []Group       `json:"groups"`
	Actions    []ActionItem  `json:"actions"`
	LeafDebug  []DebugSample `json:"leafDebugSamples,omitempty"`
}

type Source struct {
	DiffPath             string `json:"diffPath,omitempty"`
	GeneratedPath        string `json:"generatedPath,omitempty"`
	GoldenPath           string `json:"goldenPath,omitempty"`
	EvidenceTokenPath    string `json:"evidenceTokenPath,omitempty"`
	PhysicalEvidencePath string `json:"physicalEvidencePath,omitempty"`
}

type Summary struct {
	GeneratedNodeCount int            `json:"generatedNodeCount"`
	GoldenNodeCount    int            `json:"goldenNodeCount"`
	MatchedNodeCount   int            `json:"matchedNodeCount"`
	ExtraNodeCount     int            `json:"extraNodeCount"`
	MissedNodeCount    int            `json:"missedNodeCount"`
	ByStage            map[string]int `json:"byStage"`
	ByDiagnosis        map[string]int `json:"byDiagnosis"`
	ByRole             map[string]int `json:"byRole"`
	ByEvidenceKind     map[string]int `json:"byEvidenceKind"`
	ByIoUBucket        map[string]int `json:"byIoUBucket"`
}

type Group struct {
	Key          string   `json:"key"`
	Stage        string   `json:"stage"`
	Diagnosis    string   `json:"diagnosis"`
	Role         string   `json:"role,omitempty"`
	EvidenceKind string   `json:"evidenceKind,omitempty"`
	Count        int      `json:"count"`
	SampleIDs    []string `json:"sampleIds,omitempty"`
}

type ActionItem struct {
	Rank         int      `json:"rank"`
	OwnerLayer   string   `json:"ownerLayer"`
	Diagnosis    string   `json:"diagnosis"`
	Role         string   `json:"role,omitempty"`
	EvidenceKind string   `json:"evidenceKind,omitempty"`
	Count        int      `json:"count"`
	Rationale    string   `json:"rationale"`
	SampleIDs    []string `json:"sampleIds,omitempty"`
}

type DebugSample struct {
	ID                   string           `json:"id"`
	Verdict              string           `json:"verdict"`
	Diagnosis            string           `json:"diagnosis"`
	Role                 string           `json:"role"`
	EvidenceKind         string           `json:"evidenceKind,omitempty"`
	EvidenceSourceID     string           `json:"evidenceSourceId,omitempty"`
	EvidenceNotes        string           `json:"evidenceNotes,omitempty"`
	SourcePath           string           `json:"sourcePath,omitempty"`
	SourceGUID           string           `json:"sourceGuid,omitempty"`
	ParentID             string           `json:"parentId,omitempty"`
	BBox                 ir.BBox          `json:"bbox"`
	BestID               string           `json:"bestId,omitempty"`
	BestEvidenceKind     string           `json:"bestEvidenceKind,omitempty"`
	BestEvidenceSourceID string           `json:"bestEvidenceSourceId,omitempty"`
	BestEvidenceNotes    string           `json:"bestEvidenceNotes,omitempty"`
	BestSourcePath       string           `json:"bestSourcePath,omitempty"`
	BestSourceGUID       string           `json:"bestSourceGuid,omitempty"`
	BestParentID         string           `json:"bestParentId,omitempty"`
	BestBBox             ir.BBox          `json:"bestBBox,omitempty"`
	BestIoU              float64          `json:"bestIoU"`
	FailureReason        string           `json:"failureReason,omitempty"`
	NearbyTokens         []NearbyEvidence `json:"nearbyTokens,omitempty"`
	NearbyPrimitives     []NearbyEvidence `json:"nearbyPrimitives,omitempty"`
}

type NearbyEvidence struct {
	ID                 string   `json:"id"`
	Kind               string   `json:"kind"`
	Disposition        string   `json:"disposition,omitempty"`
	BBox               ir.BBox  `json:"bbox"`
	IoU                float64  `json:"iou"`
	OverlapRatio       float64  `json:"overlapRatio"`
	CenterDistance     float64  `json:"centerDistance"`
	Contained          bool     `json:"contained,omitempty"`
	ContainsTarget     bool     `json:"containsTarget,omitempty"`
	Reasons            []string `json:"reasons,omitempty"`
	SourcePrimitiveIDs []string `json:"sourcePrimitiveIds,omitempty"`
	MeanColor          string   `json:"meanColor,omitempty"`
	TextureScore       float64  `json:"textureScore,omitempty"`
	EdgeDensity        float64  `json:"edgeDensity,omitempty"`
	ColorCount         int      `json:"colorCount,omitempty"`
}

type failureRecord struct {
	ID                   string
	Role                 ir.Role
	Stage                string
	Diagnosis            string
	EvidenceKind         string
	EvidenceSourceID     string
	EvidenceNotes        string
	SourcePath           string
	SourceGUID           string
	IoUBucket            string
	Verdict              string
	FailureReason        string
	ParentMatched        bool
	BestIoU              float64
	ChildRoleCount       int
	BestID               string
	BestEvidenceKind     string
	BestEvidenceSourceID string
	BestEvidenceNotes    string
	BestSourcePath       string
	BestSourceGUID       string
	BestBBox             ir.BBox
	BestParentID         string
	ParentID             string
	BBox                 ir.BBox
}
