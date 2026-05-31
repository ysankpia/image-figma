package unifiedvision

import (
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

const (
	InputVersion      = "unified_vision_input.v1"
	ResultVersion     = "unified_vision_result.v1"
	ValidationVersion = "unified_vision_validation.v1"
)

type Input struct {
	Version      string             `json:"version"`
	GeneratedAt  string             `json:"generatedAt,omitempty"`
	SourceImage  contract.ImageMeta `json:"sourceImage"`
	Provider     ProviderMeta       `json:"provider,omitempty"`
	Batches      []BatchInput       `json:"batches"`
	Instructions Instructions       `json:"instructions"`
}

type ProviderMeta struct {
	WireAPI     string `json:"wireApi,omitempty"`
	Model       string `json:"model,omitempty"`
	BaseURLHost string `json:"baseUrlHost,omitempty"`
}

type Instructions struct {
	Task        string   `json:"task"`
	Must        []string `json:"must"`
	MustNot     []string `json:"mustNot"`
	OutputShape string   `json:"outputShape"`
}

type BatchInput struct {
	ID          string               `json:"id"`
	SectionID   string               `json:"sectionId"`
	SectionBBox geometry.Rect        `json:"sectionBBox"`
	CropBBox    geometry.Rect        `json:"cropBBox"`
	Complexity  Complexity           `json:"complexity"`
	Evidence    []EvidenceItem       `json:"evidence"`
	SourceRefs  []contract.SourceRef `json:"sourceRefs,omitempty"`
}

type Complexity struct {
	ItemCount        int     `json:"itemCount"`
	YBandCount       int     `json:"yBandCount"`
	RoleMixCount     int     `json:"roleMixCount"`
	Density          float64 `json:"density"`
	OverlapPairs     int     `json:"overlapPairs"`
	ContainmentPairs int     `json:"containmentPairs"`
	GapVariance      int     `json:"gapVariance"`
	LargeGapCount    int     `json:"largeGapCount"`
	VerticalSpan     int     `json:"verticalSpan"`
	NeighborDensity  float64 `json:"neighborDensity"`
	Score            float64 `json:"score"`
}

type EvidenceItem struct {
	ID         string               `json:"id"`
	Kind       string               `json:"kind"`
	RoleHint   string               `json:"roleHint,omitempty"`
	BBox       geometry.Rect        `json:"bbox"`
	BBoxLocal  geometry.Rect        `json:"bboxLocal"`
	Text       string               `json:"text,omitempty"`
	Source     string               `json:"source,omitempty"`
	Confidence float64              `json:"confidence,omitempty"`
	SourceRefs []contract.SourceRef `json:"sourceRefs,omitempty"`
}

type Result struct {
	Version     string        `json:"version"`
	GeneratedAt string        `json:"generatedAt,omitempty"`
	Batches     []BatchResult `json:"batches,omitempty"`
	Warnings    []string      `json:"warnings,omitempty"`
}

type BatchResult struct {
	BatchID        string      `json:"batchId"`
	SectionID      string      `json:"sectionId"`
	Attempt        int         `json:"attempt"`
	Result         ModelResult `json:"result,omitempty"`
	RawArtifact    string      `json:"rawArtifact,omitempty"`
	ErrorArtifact  string      `json:"errorArtifact,omitempty"`
	Error          string      `json:"error,omitempty"`
	RepairAttempt  bool        `json:"repairAttempt,omitempty"`
	DurationMillis int64       `json:"durationMillis,omitempty"`
}

type ModelResult struct {
	Version       string                  `json:"version"`
	Groups        []Group                 `json:"groups,omitempty"`
	ElementStyles map[string]ElementStyle `json:"elementStyles,omitempty"`
	Ungrouped     []string                `json:"ungrouped,omitempty"`
	Warnings      []string                `json:"warnings,omitempty"`
}

type Group struct {
	ID         string     `json:"id,omitempty"`
	Name       string     `json:"name,omitempty"`
	Direction  string     `json:"direction,omitempty"`
	Gap        int        `json:"gap,omitempty"`
	Members    []string   `json:"members"`
	Confidence float64    `json:"confidence,omitempty"`
	Reason     string     `json:"reason,omitempty"`
	Style      GroupStyle `json:"style,omitempty"`
}

type GroupStyle struct {
	Background   string  `json:"background,omitempty"`
	BorderRadius float64 `json:"borderRadius,omitempty"`
	Shadow       string  `json:"shadow,omitempty"`
}

type ElementStyle struct {
	FontSize   float64 `json:"fontSize,omitempty"`
	FontWeight any     `json:"fontWeight,omitempty"`
	Color      string  `json:"color,omitempty"`
}

type Validation struct {
	Version        string                  `json:"version"`
	GeneratedAt    string                  `json:"generatedAt,omitempty"`
	InputVersion   string                  `json:"inputVersion,omitempty"`
	ResultVersion  string                  `json:"resultVersion,omitempty"`
	Batches        []BatchValidation       `json:"batches,omitempty"`
	AcceptedGroups []AcceptedGroup         `json:"acceptedGroups,omitempty"`
	RejectedGroups []RejectedGroup         `json:"rejectedGroups,omitempty"`
	AcceptedStyles map[string]ElementStyle `json:"acceptedStyles,omitempty"`
	RejectedStyles []RejectedStyle         `json:"rejectedStyles,omitempty"`
	Summary        ValidationSummary       `json:"summary"`
}

type BatchValidation struct {
	BatchID         string `json:"batchId"`
	SectionID       string `json:"sectionId,omitempty"`
	AcceptedCount   int    `json:"acceptedCount"`
	RejectedCount   int    `json:"rejectedCount"`
	Fallback        bool   `json:"fallback,omitempty"`
	Reason          string `json:"reason,omitempty"`
	RepairAttempted bool   `json:"repairAttempted,omitempty"`
}

type AcceptedGroup struct {
	GroupID      string        `json:"groupId"`
	Name         string        `json:"name,omitempty"`
	Direction    string        `json:"direction"`
	BatchID      string        `json:"batchId"`
	SectionID    string        `json:"sectionId"`
	EvidenceIDs  []string      `json:"evidenceIds"`
	BBox         geometry.Rect `json:"bbox"`
	Gap          int           `json:"gap,omitempty"`
	RequiredSize int           `json:"requiredSize"`
	FitRatio     float64       `json:"fitRatio"`
	CrossSpread  int           `json:"crossSpread"`
	MedianCross  int           `json:"medianCross"`
	MaxGap       int           `json:"maxGap"`
	GapVariance  int           `json:"gapVariance"`
	Confidence   float64       `json:"confidence,omitempty"`
	Reason       string        `json:"reason,omitempty"`
}

type RejectedGroup struct {
	BatchID     string   `json:"batchId,omitempty"`
	GroupID     string   `json:"groupId,omitempty"`
	Name        string   `json:"name,omitempty"`
	Direction   string   `json:"direction,omitempty"`
	EvidenceIDs []string `json:"evidenceIds,omitempty"`
	Reason      string   `json:"reason"`
}

type RejectedStyle struct {
	BatchID    string `json:"batchId,omitempty"`
	EvidenceID string `json:"evidenceId,omitempty"`
	Reason     string `json:"reason"`
}

type ValidationSummary struct {
	BatchCount              int     `json:"batchCount"`
	AcceptedGroupCount      int     `json:"acceptedGroupCount"`
	RejectedGroupCount      int     `json:"rejectedGroupCount"`
	AcceptedStyleCount      int     `json:"acceptedStyleCount"`
	RejectedStyleCount      int     `json:"rejectedStyleCount"`
	FallbackBatchCount      int     `json:"fallbackBatchCount"`
	AcceptedEvidenceCount   int     `json:"acceptedEvidenceCount"`
	TotalEvidenceCount      int     `json:"totalEvidenceCount"`
	Coverage                float64 `json:"coverage"`
	DuplicateOwnershipCount int     `json:"duplicateOwnershipCount"`
	BBoxDriftCount          int     `json:"bboxDriftCount"`
	OCRMismatchCount        int     `json:"ocrMismatchCount"`
}

type Output struct {
	Input      Input
	Result     Result
	Validation Validation
	Experiment contract.Document
	Artifacts  Artifacts
	Warnings   []string
}

type Artifacts struct {
	Input          string   `json:"input,omitempty"`
	Result         string   `json:"result,omitempty"`
	Validation     string   `json:"validation,omitempty"`
	LayoutIR       string   `json:"layoutIr,omitempty"`
	PreviewHTML    string   `json:"previewHtml,omitempty"`
	DebugHTML      string   `json:"debugHtml,omitempty"`
	PreviewReport  string   `json:"previewReport,omitempty"`
	RawResponses   []string `json:"rawResponses,omitempty"`
	ErrorArtifacts []string `json:"errorArtifacts,omitempty"`
}

func timestamp() string {
	return time.Now().UTC().Format(time.RFC3339)
}
