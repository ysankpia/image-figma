package server

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image/png"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/pencil"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/project"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/storage"
)

type Config struct {
	StorageRoot    string
	OCRProvider    string
	MaxUploadBytes int64
	MaxFiles       int
}

func (c Config) normalized() Config {
	out := c
	if out.StorageRoot == "" {
		out.StorageRoot = storage.DefaultRoot
	}
	if out.MaxUploadBytes <= 0 {
		out.MaxUploadBytes = 10 * 1024 * 1024
	}
	if out.MaxFiles <= 0 {
		out.MaxFiles = 20
	}
	return out
}

type Status string

const (
	StatusQueued    Status = "queued"
	StatusRunning   Status = "running"
	StatusCompleted Status = "completed"
	StatusFailed    Status = "failed"
)

type Task struct {
	ID          string                  `json:"taskId"`
	Status      Status                  `json:"status"`
	Progress    int                     `json:"progress"`
	Message     string                  `json:"message"`
	PageCount   int                     `json:"pageCount,omitempty"`
	Modes       []pencil.Mode           `json:"modes,omitempty"`
	DownloadURL string                  `json:"downloadUrl,omitempty"`
	Error       string                  `json:"error,omitempty"`
	OutputDir   string                  `json:"-"`
	ZipPath     string                  `json:"-"`
	Manifest    *pencil.ProjectManifest `json:"-"`
	CreatedAt   time.Time               `json:"-"`
	UpdatedAt   time.Time               `json:"-"`
}

type Server struct {
	config Config
	paths  storage.Paths
	mu     sync.RWMutex
	tasks  map[string]*Task
}

func New(config Config) *Server {
	normalized := config.normalized()
	return &Server{
		config: normalized,
		paths:  storage.New(normalized.StorageRoot),
		tasks:  map[string]*Task{},
	}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/health", s.handleHealth)
	mux.HandleFunc("/api/pencil/projects", s.handleProjects)
	mux.HandleFunc("/api/pencil/projects/", s.handleProjectTask)
	return withCORS(mux)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": map[string]any{"status": "ok", "version": "pencil-server-v0.1", "time": time.Now().UTC().Format(time.RFC3339)}})
}

func (s *Server) handleProjects(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.")
		return
	}
	files, options, err := s.readProjectUpload(w, r)
	if err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_PROJECT_UPLOAD", err.Error())
		return
	}
	taskID := newTaskID()
	root := s.paths.TaskRoot(taskID)
	uploads := s.paths.UploadsDir(taskID)
	if err := os.MkdirAll(uploads, 0o755); err != nil {
		writeError(w, http.StatusInternalServerError, "STORAGE_CREATE_FAILED", err.Error())
		return
	}
	var inputPaths []string
	for i, file := range files {
		name := fmt.Sprintf("page_%04d_%s", i+1, safeFileName(file.name))
		path := filepath.Join(uploads, name)
		if err := os.WriteFile(path, file.data, 0o644); err != nil {
			writeError(w, http.StatusInternalServerError, "UPLOAD_SAVE_FAILED", err.Error())
			return
		}
		inputPaths = append(inputPaths, path)
	}
	now := time.Now().UTC()
	task := &Task{ID: taskID, Status: StatusQueued, Progress: 1, Message: "Pencil project queued.", OutputDir: filepath.Join(root, "output"), CreatedAt: now, UpdatedAt: now}
	s.storeTask(task)
	go s.runTask(taskID, inputPaths, options)
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": map[string]any{"taskId": taskID, "status": task.Status}})
}

type uploadFile struct {
	name string
	data []byte
}

type uploadOptions struct {
	projectName  string
	mode         pencil.Mode
	columns      string
	includeDebug bool
}

func (s *Server) readProjectUpload(w http.ResponseWriter, r *http.Request) ([]uploadFile, uploadOptions, error) {
	r.Body = http.MaxBytesReader(w, r.Body, s.config.MaxUploadBytes*int64(s.config.MaxFiles))
	if err := r.ParseMultipartForm(s.config.MaxUploadBytes * int64(s.config.MaxFiles)); err != nil {
		return nil, uploadOptions{}, fmt.Errorf("upload is too large or invalid")
	}
	headers := append([]*multipart.FileHeader{}, r.MultipartForm.File["files[]"]...)
	headers = append(headers, r.MultipartForm.File["files"]...)
	if len(headers) == 0 {
		return nil, uploadOptions{}, fmt.Errorf("files[] field is required")
	}
	if len(headers) > s.config.MaxFiles {
		return nil, uploadOptions{}, fmt.Errorf("maximum %d files per project", s.config.MaxFiles)
	}
	out := make([]uploadFile, 0, len(headers))
	for _, header := range headers {
		file, err := header.Open()
		if err != nil {
			return nil, uploadOptions{}, fmt.Errorf("open %s: %w", header.Filename, err)
		}
		data, err := io.ReadAll(io.LimitReader(file, s.config.MaxUploadBytes+1))
		file.Close()
		if err != nil {
			return nil, uploadOptions{}, fmt.Errorf("read %s: %w", header.Filename, err)
		}
		if int64(len(data)) > s.config.MaxUploadBytes {
			return nil, uploadOptions{}, fmt.Errorf("%s is too large", header.Filename)
		}
		if !bytes.HasPrefix(data, []byte("\x89PNG\r\n\x1a\n")) {
			return nil, uploadOptions{}, fmt.Errorf("%s is not a PNG", header.Filename)
		}
		if _, err := png.DecodeConfig(bytes.NewReader(data)); err != nil {
			return nil, uploadOptions{}, fmt.Errorf("%s dimensions are invalid", header.Filename)
		}
		out = append(out, uploadFile{name: header.Filename, data: data})
	}
	mode := pencil.Mode(strings.TrimSpace(r.FormValue("mode")))
	if mode == "" {
		mode = pencil.ModeAll
	}
	if len(pencil.ExpandModes(mode)) == 0 {
		return nil, uploadOptions{}, fmt.Errorf("unsupported mode %q", mode)
	}
	includeDebug := true
	if raw := strings.TrimSpace(r.FormValue("includeDebug")); raw != "" {
		includeDebug = raw == "true" || raw == "1"
	}
	return out, uploadOptions{
		projectName:  firstNonEmpty(strings.TrimSpace(r.FormValue("projectName")), "Pencil Project"),
		mode:         mode,
		columns:      firstNonEmpty(strings.TrimSpace(r.FormValue("columns")), "auto"),
		includeDebug: includeDebug,
	}, nil
}

func (s *Server) handleProjectTask(w http.ResponseWriter, r *http.Request) {
	taskID, suffix := splitTaskPath(strings.TrimPrefix(r.URL.Path, "/api/pencil/projects/"))
	task := s.getTask(taskID)
	if task == nil {
		writeError(w, http.StatusNotFound, "TASK_NOT_FOUND", "Task not found.")
		return
	}
	switch suffix {
	case "":
		if r.Method != http.MethodGet {
			writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.")
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": taskPublic(task)})
	case "manifest":
		if r.Method != http.MethodGet {
			writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.")
			return
		}
		if task.Status != StatusCompleted || task.Manifest == nil {
			writeError(w, http.StatusConflict, "MANIFEST_NOT_READY", "Manifest is not ready.")
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": map[string]any{"manifest": task.Manifest}})
	case "download.zip":
		if r.Method != http.MethodGet {
			writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.")
			return
		}
		if task.Status != StatusCompleted || task.ZipPath == "" {
			writeError(w, http.StatusConflict, "ZIP_NOT_READY", "Project ZIP is not ready.")
			return
		}
		http.ServeFile(w, r, task.ZipPath)
	default:
		writeError(w, http.StatusNotFound, "NOT_FOUND", "Endpoint not found.")
	}
}

func (s *Server) runTask(taskID string, inputs []string, options uploadOptions) {
	defer s.recoverTask(taskID)
	s.updateTask(taskID, StatusRunning, 20, "Running M29 and Pencil project export.", "")
	task := s.getTask(taskID)
	result, err := project.Export(project.Options{
		Inputs:       inputs,
		OutputDir:    task.OutputDir,
		ProjectName:  options.projectName,
		Mode:         options.mode,
		Columns:      options.columns,
		IncludeDebug: options.includeDebug,
		OCRProvider:  s.config.OCRProvider,
	})
	if err != nil {
		s.updateTask(taskID, StatusFailed, 100, "Pencil project export failed.", err.Error())
		return
	}
	s.mu.Lock()
	if task := s.tasks[taskID]; task != nil {
		task.Status = StatusCompleted
		task.Progress = 100
		task.Message = "Pencil project ZIP is ready."
		task.PageCount = result.Manifest.PageCount
		task.Modes = result.Manifest.Modes
		task.DownloadURL = "/api/pencil/projects/" + taskID + "/download.zip"
		task.ZipPath = result.ZipPath
		task.Manifest = &result.Manifest
		task.UpdatedAt = time.Now().UTC()
		s.persistTaskLocked(task)
	}
	s.mu.Unlock()
}

func (s *Server) recoverTask(taskID string) {
	if value := recover(); value != nil {
		log.Printf("pencil task panic task=%s: %v\n%s", taskID, value, debug.Stack())
		s.updateTask(taskID, StatusFailed, 100, "Pencil project export panicked.", fmt.Sprint(value))
	}
}

func (s *Server) storeTask(task *Task) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tasks[task.ID] = task
	s.persistTaskLocked(task)
}

func (s *Server) getTask(taskID string) *Task {
	s.mu.RLock()
	defer s.mu.RUnlock()
	task := s.tasks[taskID]
	if task == nil {
		return nil
	}
	copy := *task
	return &copy
}

func (s *Server) updateTask(taskID string, status Status, progress int, message, errMsg string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	task := s.tasks[taskID]
	if task == nil {
		return
	}
	task.Status = status
	task.Progress = progress
	task.Message = message
	task.Error = errMsg
	task.UpdatedAt = time.Now().UTC()
	s.persistTaskLocked(task)
}

func (s *Server) persistTaskLocked(task *Task) {
	path := filepath.Join(s.paths.TaskRoot(task.ID), "task.json")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		log.Printf("persist pencil task %s: %v", task.ID, err)
		return
	}
	data, err := json.MarshalIndent(taskPublic(task), "", "  ")
	if err != nil {
		log.Printf("marshal pencil task %s: %v", task.ID, err)
		return
	}
	data = append(data, '\n')
	if err := os.WriteFile(path, data, 0o644); err != nil {
		log.Printf("write pencil task %s: %v", task.ID, err)
	}
}

func taskPublic(task *Task) map[string]any {
	out := map[string]any{
		"taskId":   task.ID,
		"status":   task.Status,
		"progress": task.Progress,
		"message":  task.Message,
	}
	if task.Error != "" {
		out["error"] = task.Error
	}
	if task.PageCount > 0 {
		out["pageCount"] = task.PageCount
	}
	if len(task.Modes) > 0 {
		out["modes"] = task.Modes
	}
	if task.DownloadURL != "" {
		out["downloadUrl"] = task.DownloadURL
	}
	return out
}

func ListenAndServe(ctx context.Context, addr string, config Config) error {
	srv := &http.Server{Addr: addr, Handler: New(config).Handler(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdownCtx)
	}()
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}

func newTaskID() string {
	var buf [6]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return fmt.Sprintf("pencil_%d", time.Now().UnixNano())
	}
	return "pencil_" + hex.EncodeToString(buf[:])
}

func safeFileName(name string) string {
	base := filepath.Base(strings.TrimSpace(name))
	if base == "" || base == "." {
		return "upload.png"
	}
	var b strings.Builder
	for _, r := range base {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '.' || r == '_' || r == '-' {
			b.WriteRune(r)
		} else {
			b.WriteByte('_')
		}
	}
	out := strings.Trim(b.String(), "._-")
	if out == "" {
		return "upload.png"
	}
	if !strings.HasSuffix(strings.ToLower(out), ".png") {
		out += ".png"
	}
	return out
}

func splitTaskPath(path string) (string, string) {
	first, rest, ok := strings.Cut(strings.Trim(path, "/"), "/")
	if !ok {
		return first, ""
	}
	return first, rest
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, map[string]any{"success": false, "error": map[string]any{"code": code, "message": message}})
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func EnvInt(key string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return value
}
