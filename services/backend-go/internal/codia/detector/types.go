package detector

const (
	CandidatesVersion = "ui_detector_candidates.v1"
	EvalVersion       = "ui_detector_eval.v1"
)

type Role string

const (
	RoleImageView        Role = "ImageView"
	RoleTextView         Role = "TextView"
	RoleBackground       Role = "Background"
	RoleStatusBar        Role = "StatusBar"
	RoleActionBar        Role = "ActionBar"
	RoleBottomNavigation Role = "BottomNavigation"
	RoleListView         Role = "ListView"
	RoleViewGroup        Role = "ViewGroup"
	RoleButton           Role = "Button"
	RoleEditText         Role = "EditText"
)

type Document struct {
	Version    string       `json:"version"`
	Image      ImageMeta    `json:"image"`
	Provider   ProviderMeta `json:"provider"`
	Preprocess Preprocess   `json:"preprocess"`
	Candidates []Candidate  `json:"candidates"`
	Summary    Summary      `json:"summary"`
}

type ImageMeta struct {
	Path   string `json:"path"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
	SHA256 string `json:"sha256,omitempty"`
}

type ProviderMeta struct {
	Name        string `json:"name"`
	WireAPI     string `json:"wireApi"`
	Model       string `json:"model"`
	BaseURLHost string `json:"baseUrlHost,omitempty"`
	Stream      bool   `json:"stream,omitempty"`
}

type Preprocess struct {
	Passes []PassRun `json:"passes"`
}

type PassRun struct {
	ID         string `json:"id"`
	Kind       string `json:"kind"`
	PromptName string `json:"promptName"`
	SourceBBox BBox   `json:"sourceBBox"`
	SentWidth  int    `json:"sentWidth"`
	SentHeight int    `json:"sentHeight"`
	MaxSide    int    `json:"maxSide,omitempty"`
	DurationMS int64  `json:"durationMs,omitempty"`
}

type Candidate struct {
	ID                   string          `json:"id"`
	Role                 Role            `json:"role"`
	RawLabel             string          `json:"rawLabel,omitempty"`
	Confidence           float64         `json:"confidence"`
	BBox                 BBox            `json:"bbox"`
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

type BBox struct {
	X      float64 `json:"x"`
	Y      float64 `json:"y"`
	Width  float64 `json:"width"`
	Height float64 `json:"height"`
}

type NormalizedBBox struct {
	X      float64 `json:"x"`
	Y      float64 `json:"y"`
	Width  float64 `json:"width"`
	Height float64 `json:"height"`
}

type Summary struct {
	Total      int            `json:"total"`
	RoleCounts map[string]int `json:"roleCounts"`
	PassCounts map[string]int `json:"passCounts,omitempty"`
}

type EvalDocument struct {
	Version string      `json:"version"`
	Source  EvalSource  `json:"source"`
	Summary EvalSummary `json:"summary"`
	Roles   []RoleEval  `json:"roles"`
	Missed  []EvalNode  `json:"missed,omitempty"`
	Extra   []EvalNode  `json:"extra,omitempty"`
}

type EvalSource struct {
	CandidatesPath string `json:"candidatesPath,omitempty"`
	GoldenPath     string `json:"goldenPath,omitempty"`
}

type EvalSummary struct {
	GoldenCount    int `json:"goldenCount"`
	DetectorCount  int `json:"detectorCount"`
	MatchedAt05    int `json:"matchedAt0_5"`
	MatchedAt06    int `json:"matchedAt0_6"`
	ExtraAt05      int `json:"extraAt0_5"`
	MissedAt05     int `json:"missedAt0_5"`
	MatchedRoleNum int `json:"matchedRoleNum"`
}

type RoleEval struct {
	Role        Role    `json:"role"`
	Golden      int     `json:"golden"`
	Detector    int     `json:"detector"`
	MatchedAt05 int     `json:"matchedAt0_5"`
	MatchedAt06 int     `json:"matchedAt0_6"`
	Precision05 float64 `json:"precisionAt0_5"`
	Recall05    float64 `json:"recallAt0_5"`
	F105        float64 `json:"f1At0_5"`
	Precision06 float64 `json:"precisionAt0_6"`
	Recall06    float64 `json:"recallAt0_6"`
	F106        float64 `json:"f1At0_6"`
}

type EvalNode struct {
	ID       string  `json:"id"`
	Role     Role    `json:"role"`
	BBox     BBox    `json:"bbox"`
	BestID   string  `json:"bestId,omitempty"`
	BestBBox BBox    `json:"bestBBox,omitempty"`
	BestIoU  float64 `json:"bestIoU"`
	PassID   string  `json:"passId,omitempty"`
	Label    string  `json:"label,omitempty"`
}
