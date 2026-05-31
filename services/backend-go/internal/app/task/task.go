package task

import "time"

type Status string

const (
	StatusQueued    Status = "queued"
	StatusRunning   Status = "running"
	StatusCompleted Status = "completed"
	StatusFailed    Status = "failed"
)

type Stage string

const (
	StageDraftQueued         Stage = "draft_queued"
	StageOCR                 Stage = "ocr"
	StageM29PhysicalEvidence Stage = "m29_physical_evidence"
	StageVisionDetector      Stage = "vision_detector"
	StageVisionReview        Stage = "vision_review"
	StageDraftAssemble       Stage = "draft_assemble"
	StageDraftAssets         Stage = "draft_assets"
	StageDraftValidate       Stage = "draft_validate"
	StageDraftExport         Stage = "draft_export"
	StageDraftCompleted      Stage = "draft_completed"
	StageDraftFailed         Stage = "draft_failed"
	StageDraftPanic          Stage = "draft_panic"
)

type Task struct {
	ID        string            `json:"taskId"`
	Status    Status            `json:"status"`
	Stage     Stage             `json:"stage"`
	Progress  int               `json:"progress"`
	Message   string            `json:"message"`
	DSLPath   string            `json:"-"`
	OutputDir string            `json:"-"`
	Artifacts map[string]string `json:"artifacts,omitempty"`
	Error     *Error            `json:"error,omitempty"`
	Warnings  []Warning         `json:"warnings,omitempty"`
	CreatedAt time.Time         `json:"-"`
	UpdatedAt time.Time         `json:"-"`
}

type Error struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type Warning struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Stage   Stage  `json:"stage,omitempty"`
}
