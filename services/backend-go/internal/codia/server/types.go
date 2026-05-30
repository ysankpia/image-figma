package server

import (
	"path/filepath"
	"time"
)

type Config struct {
	StorageRoot        string
	OCRProvider        string
	DetectorEnabled    bool
	DetectorCandidates string
	MaxUploadBytes     int64
}

type Task struct {
	ID        string            `json:"taskId"`
	Status    string            `json:"status"`
	Stage     string            `json:"stage"`
	Progress  int               `json:"progress"`
	Message   string            `json:"message"`
	DSLPath   string            `json:"-"`
	OutputDir string            `json:"-"`
	Artifacts map[string]string `json:"artifacts,omitempty"`
	Error     *TaskError        `json:"error,omitempty"`
	CreatedAt time.Time         `json:"-"`
	UpdatedAt time.Time         `json:"-"`
}

type TaskError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type apiSuccess struct {
	Success bool `json:"success"`
	Data    any  `json:"data"`
}

type apiFailure struct {
	Success bool     `json:"success"`
	Error   apiError `json:"error"`
}

type apiError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Stage   string `json:"stage"`
	TaskID  string `json:"taskId,omitempty"`
}

func (c Config) normalized() Config {
	out := c
	if out.StorageRoot == "" {
		out.StorageRoot = filepath.Join(".", "storage", "codia_server")
	}
	if out.MaxUploadBytes <= 0 {
		out.MaxUploadBytes = 10 * 1024 * 1024
	}
	return out
}
