package server

import (
	"path/filepath"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

type Config struct {
	StorageRoot    string
	OCRProvider    string
	MaxUploadBytes int64
	VisionEnabled  bool
	VisionOptions  detector.Options
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
		out.StorageRoot = filepath.Join(".", "storage", "draft_server")
	}
	if out.MaxUploadBytes <= 0 {
		out.MaxUploadBytes = 10 * 1024 * 1024
	}
	return out
}
