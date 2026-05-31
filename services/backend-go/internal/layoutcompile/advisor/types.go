package advisor

import (
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

const (
	InputVersion      = "layout_advisor_input.v1"
	ResultVersion     = "layout_advisor_result.v1"
	ValidationVersion = "layout_advisor_validation.v1"
)

type Input struct {
	Version      string              `json:"version"`
	GeneratedAt  string              `json:"generatedAt,omitempty"`
	SourceImage  contract.ImageMeta  `json:"sourceImage"`
	Evidence     []EvidenceItem      `json:"evidence"`
	Rows         []RowDiagnostic     `json:"rows"`
	BadRows      []RowDiagnostic     `json:"badRows,omitempty"`
	Instructions AdvisorInstructions `json:"instructions"`
}

type EvidenceItem struct {
	ID         string               `json:"id"`
	Kind       string               `json:"kind"`
	RoleHint   string               `json:"roleHint,omitempty"`
	BBox       geometry.Rect        `json:"bbox"`
	Text       string               `json:"text,omitempty"`
	Source     string               `json:"source,omitempty"`
	Confidence float64              `json:"confidence,omitempty"`
	SourceRefs []contract.SourceRef `json:"sourceRefs,omitempty"`
}

type RowDiagnostic struct {
	ID              string               `json:"id"`
	BBox            geometry.Rect        `json:"bbox"`
	FlowEvidence    []string             `json:"flowEvidence"`
	OverlayEvidence []string             `json:"overlayEvidence,omitempty"`
	FlowCount       int                  `json:"flowCount"`
	OverlayCount    int                  `json:"overlayCount"`
	Gap             int                  `json:"gap"`
	GapVariance     int                  `json:"gapVariance"`
	RequiredWidth   int                  `json:"requiredWidth"`
	FitRatio        float64              `json:"fitRatio"`
	YSpread         int                  `json:"ySpread"`
	MedianHeight    int                  `json:"medianHeight"`
	Reason          string               `json:"reason,omitempty"`
	SourceRefs      []contract.SourceRef `json:"sourceRefs,omitempty"`
}

type AdvisorInstructions struct {
	Task        string   `json:"task"`
	Must        []string `json:"must"`
	MustNot     []string `json:"mustNot"`
	OutputShape string   `json:"outputShape"`
}

type Result struct {
	Version             string   `json:"version"`
	Groups              []Group  `json:"groups"`
	FallbackEvidenceIDs []string `json:"fallbackEvidenceIds,omitempty"`
	Warnings            []string `json:"warnings,omitempty"`
}

type Group struct {
	ID          string   `json:"id,omitempty"`
	Type        string   `json:"type"`
	Direction   string   `json:"direction,omitempty"`
	EvidenceIDs []string `json:"evidenceIds"`
	ExpectedGap int      `json:"expectedGap,omitempty"`
	Confidence  float64  `json:"confidence,omitempty"`
	Reason      string   `json:"reason,omitempty"`
}

type Validation struct {
	Version        string            `json:"version"`
	GeneratedAt    string            `json:"generatedAt,omitempty"`
	InputVersion   string            `json:"inputVersion,omitempty"`
	ResultVersion  string            `json:"resultVersion,omitempty"`
	AcceptedGroups []AcceptedGroup   `json:"acceptedGroups,omitempty"`
	RejectedGroups []RejectedGroup   `json:"rejectedGroups,omitempty"`
	Warnings       []string          `json:"warnings,omitempty"`
	Summary        ValidationSummary `json:"summary"`
}

type AcceptedGroup struct {
	GroupID       string        `json:"groupId"`
	Type          string        `json:"type"`
	Direction     string        `json:"direction,omitempty"`
	EvidenceIDs   []string      `json:"evidenceIds"`
	BBox          geometry.Rect `json:"bbox"`
	ExpectedGap   int           `json:"expectedGap,omitempty"`
	RequiredWidth int           `json:"requiredWidth"`
	FitRatio      float64       `json:"fitRatio"`
	YSpread       int           `json:"ySpread"`
	MedianHeight  int           `json:"medianHeight"`
	Confidence    float64       `json:"confidence,omitempty"`
	Reason        string        `json:"reason,omitempty"`
}

type RejectedGroup struct {
	GroupID     string   `json:"groupId,omitempty"`
	Type        string   `json:"type,omitempty"`
	Direction   string   `json:"direction,omitempty"`
	EvidenceIDs []string `json:"evidenceIds,omitempty"`
	Reason      string   `json:"reason"`
}

type ValidationSummary struct {
	AcceptedCount int `json:"acceptedCount"`
	RejectedCount int `json:"rejectedCount"`
}

type ValidateOptions struct {
	MinConfidence    float64
	MaxFitRatio      float64
	MaxYSpreadFactor float64
	MaxGapVariance   int
	MaxGap           int
}

func defaultValidateOptions(options ValidateOptions) ValidateOptions {
	if options.MinConfidence <= 0 {
		options.MinConfidence = 0.70
	}
	if options.MaxFitRatio <= 0 {
		options.MaxFitRatio = 1.01
	}
	if options.MaxYSpreadFactor <= 0 {
		options.MaxYSpreadFactor = 1.60
	}
	if options.MaxGap <= 0 {
		options.MaxGap = 96
	}
	if options.MaxGapVariance <= 0 {
		options.MaxGapVariance = 4096
	}
	return options
}

func timestamp() string {
	return time.Now().UTC().Format(time.RFC3339)
}
