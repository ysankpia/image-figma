package review

import "github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"

const Version = "ui_candidate_review.v1"

type Action string

const (
	ActionPromoteM29Candidate  Action = "promote_m29_candidate"
	ActionSuppressVLMCandidate Action = "suppress_vlm_candidate"
	ActionRefineBBox           Action = "refine_bbox"
	ActionMergeCandidates      Action = "merge_candidates"
	ActionKeepCandidate        Action = "keep_candidate"
	ActionClassifySemanticTag  Action = "classify_semantic_tag"
)

type Document struct {
	Version   string     `json:"version"`
	Decisions []Decision `json:"decisions"`
	Summary   Summary    `json:"summary"`
}

type Decision struct {
	ID            string         `json:"id"`
	Action        Action         `json:"action"`
	TargetID      string         `json:"targetId"`
	Role          string         `json:"role,omitempty"`
	SemanticTags  []string       `json:"semanticTags,omitempty"`
	Confidence    float64        `json:"confidence,omitempty"`
	Reason        string         `json:"reason"`
	BBox          *geometry.Rect `json:"bbox,omitempty"`
	BBoxAuthority string         `json:"bboxAuthority,omitempty"`
	SourceIDs     []string       `json:"sourceIds,omitempty"`
}

type Summary struct {
	Total        int            `json:"total"`
	ActionCounts map[string]int `json:"actionCounts,omitempty"`
}
