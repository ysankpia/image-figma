package detector

import "github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"

const CandidatesVersion = "ui_detector_candidates.v1"

type Document struct {
	Version    string       `json:"version"`
	Image      ImageMeta    `json:"image"`
	Provider   ProviderMeta `json:"provider"`
	Preprocess Preprocess   `json:"preprocess"`
	Candidates []Candidate  `json:"candidates"`
	Summary    Summary      `json:"summary"`
}

type ImageMeta struct {
	Path   string `json:"path,omitempty"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
	SHA256 string `json:"sha256,omitempty"`
}

type ProviderMeta struct {
	Name        string `json:"name"`
	WireAPI     string `json:"wireApi"`
	Model       string `json:"model,omitempty"`
	BaseURLHost string `json:"baseUrlHost,omitempty"`
	Stream      bool   `json:"stream,omitempty"`
}

type Preprocess struct {
	Passes []PassRun `json:"passes"`
}

type PassRun struct {
	ID         string        `json:"id"`
	Kind       string        `json:"kind"`
	PromptName string        `json:"promptName"`
	SourceBBox geometry.Rect `json:"sourceBBox"`
	SentWidth  int           `json:"sentWidth"`
	SentHeight int           `json:"sentHeight"`
	MaxSide    int           `json:"maxSide,omitempty"`
	DurationMS int64         `json:"durationMs,omitempty"`
	Error      string        `json:"error,omitempty"`
}

type Candidate struct {
	ID                   string          `json:"id"`
	Role                 string          `json:"role"`
	RawLabel             string          `json:"rawLabel,omitempty"`
	Confidence           float64         `json:"confidence"`
	BBox                 geometry.Rect   `json:"bbox"`
	BBoxNormalizedInPass *NormalizedBBox `json:"bboxNormalizedInPass,omitempty"`
	Source               CandidateSource `json:"source"`
	Merge                MergeState      `json:"merge"`
}

type CandidateSource struct {
	Kind             string `json:"kind"`
	PassID           string `json:"passId"`
	ModelOutputIndex int    `json:"modelOutputIndex"`
	PreferredByPass  bool   `json:"preferredByPass"`
	Reason           string `json:"reason,omitempty"`
}

type MergeState struct {
	State  string `json:"state"`
	Reason string `json:"reason,omitempty"`
}

type NormalizedBBox struct {
	X      float64 `json:"x"`
	Y      float64 `json:"y"`
	Width  float64 `json:"width"`
	Height float64 `json:"height"`
}

type Summary struct {
	Total      int            `json:"total"`
	RoleCounts map[string]int `json:"roleCounts,omitempty"`
	PassCounts map[string]int `json:"passCounts,omitempty"`
}
