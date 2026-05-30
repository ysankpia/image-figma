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
	"net/http"
	"os"
	"path/filepath"
	"runtime/debug"
	"strings"
	"sync"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/compiler"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/dsl02"
)

type CompileFunc func(compiler.Options) (compiler.Result, error)
type DetectorFunc func(context.Context, detector.Options) (detector.RunResult, error)

type Server struct {
	config  Config
	compile CompileFunc
	detect  DetectorFunc
	mu      sync.RWMutex
	tasks   map[string]*Task
}

func New(config Config) *Server {
	return NewWithCompiler(config, compiler.Compile)
}

func NewWithCompiler(config Config, compile CompileFunc) *Server {
	return NewWithCompilerAndDetector(config, compile, detector.Run)
}

func NewWithCompilerAndDetector(config Config, compile CompileFunc, detect DetectorFunc) *Server {
	if compile == nil {
		compile = compiler.Compile
	}
	if detect == nil {
		detect = detector.Run
	}
	return &Server{
		config:  config.normalized(),
		compile: compile,
		detect:  detect,
		tasks:   map[string]*Task{},
	}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/health", s.handleHealth)
	mux.HandleFunc("/api/codia-preview", s.handleCodiaPreview)
	mux.HandleFunc("/api/codia-preview/", s.handleCodiaPreviewTask)
	return withCORS(mux)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "health", "")
		return
	}
	writeJSON(w, http.StatusOK, apiSuccess{Success: true, Data: map[string]any{
		"status":  "ok",
		"version": "codia-server-v0.1",
		"time":    time.Now().UTC().Format(time.RFC3339),
	}})
}

func (s *Server) handleCodiaPreview(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "codia_preview_upload", "")
		return
	}
	fileName, data, err := readMultipartPNG(w, r, s.config.MaxUploadBytes)
	if err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_PNG_UPLOAD", err.Error(), "codia_preview_upload", "")
		return
	}
	if _, err := png.DecodeConfig(bytes.NewReader(data)); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_IMAGE_DIMENSIONS", "PNG image dimensions could not be read.", "codia_preview_upload", "")
		return
	}

	taskID := newTaskID()
	taskRoot := filepath.Join(s.config.StorageRoot, "codia_previews", taskID)
	if err := os.MkdirAll(taskRoot, 0o755); err != nil {
		writeError(w, http.StatusInternalServerError, "STORAGE_CREATE_FAILED", err.Error(), "codia_preview_upload", taskID)
		return
	}
	inputPath := filepath.Join(taskRoot, safeFileName(fileName))
	if err := os.WriteFile(inputPath, data, 0o644); err != nil {
		writeError(w, http.StatusInternalServerError, "UPLOAD_SAVE_FAILED", err.Error(), "codia_preview_upload", taskID)
		return
	}

	now := time.Now().UTC()
	task := &Task{
		ID:        taskID,
		Status:    "processing",
		Stage:     "codia_queued",
		Progress:  1,
		Message:   "Go Codia compiler queued.",
		OutputDir: filepath.Join(taskRoot, "compile"),
		CreatedAt: now,
		UpdatedAt: now,
	}
	s.storeTask(task)
	go s.runTask(taskID, inputPath, task.OutputDir)

	writeJSON(w, http.StatusOK, apiSuccess{Success: true, Data: map[string]any{
		"taskId":   task.ID,
		"status":   task.Status,
		"stage":    task.Stage,
		"progress": task.Progress,
		"file": map[string]any{
			"filename": fileName,
			"mimeType": "image/png",
			"size":     len(data),
		},
	}})
}

func (s *Server) handleCodiaPreviewTask(w http.ResponseWriter, r *http.Request) {
	taskID, suffix := splitTaskPath(strings.TrimPrefix(r.URL.Path, "/api/codia-preview/"))
	if taskID == "" {
		writeError(w, http.StatusNotFound, "TASK_NOT_FOUND", "Task not found.", "codia_preview_lookup", "")
		return
	}
	task := s.getTask(taskID)
	if task == nil {
		writeError(w, http.StatusNotFound, "TASK_NOT_FOUND", "Task not found.", "codia_preview_lookup", taskID)
		return
	}
	switch suffix {
	case "":
		if r.Method != http.MethodGet {
			writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "codia_preview_lookup", taskID)
			return
		}
		writeJSON(w, http.StatusOK, apiSuccess{Success: true, Data: task.toPublic()})
	case "dsl":
		s.handleDSL(w, r, task)
	case "artifacts":
		s.handleArtifacts(w, r, task)
	default:
		if strings.HasPrefix(suffix, "assets/") {
			s.handleAsset(w, r, task, strings.TrimPrefix(suffix, "assets/"))
			return
		}
		writeError(w, http.StatusNotFound, "NOT_FOUND", "Endpoint not found.", "codia_preview_lookup", taskID)
	}
}

func (s *Server) handleDSL(w http.ResponseWriter, r *http.Request, task *Task) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "codia_preview_dsl", task.ID)
		return
	}
	if task.Status != "completed" {
		writeError(w, http.StatusConflict, "DSL_NOT_READY", "Codia Runtime DSL is not ready.", "codia_preview_dsl", task.ID)
		return
	}
	data, err := os.ReadFile(task.DSLPath)
	if err != nil {
		writeError(w, http.StatusNotFound, "DSL_NOT_FOUND", "Codia Runtime DSL file not found.", "codia_preview_dsl", task.ID)
		return
	}
	var dsl any
	if err := json.Unmarshal(data, &dsl); err != nil {
		writeError(w, http.StatusInternalServerError, "DSL_INVALID_JSON", err.Error(), "codia_preview_dsl", task.ID)
		return
	}
	writeJSON(w, http.StatusOK, apiSuccess{Success: true, Data: map[string]any{"dsl": dsl}})
}

func (s *Server) handleArtifacts(w http.ResponseWriter, r *http.Request, task *Task) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "codia_preview_artifacts", task.ID)
		return
	}
	writeJSON(w, http.StatusOK, apiSuccess{Success: true, Data: map[string]any{
		"taskId":    task.ID,
		"status":    task.Status,
		"stage":     task.Stage,
		"outputDir": task.OutputDir,
		"artifacts": task.Artifacts,
		"warnings":  task.Warnings,
	}})
}

func (s *Server) handleAsset(w http.ResponseWriter, r *http.Request, task *Task, name string) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "codia_preview_asset", task.ID)
		return
	}
	fileName := safeAssetFileName(name)
	if fileName == "" {
		writeError(w, http.StatusNotFound, "ASSET_NOT_FOUND", "Asset not found.", "codia_preview_asset", task.ID)
		return
	}
	file, err := os.Open(filepath.Join(task.OutputDir, dsl02.AssetDirName, fileName))
	if err != nil {
		writeError(w, http.StatusNotFound, "ASSET_NOT_FOUND", "Asset not found.", "codia_preview_asset", task.ID)
		return
	}
	defer file.Close()
	w.Header().Set("Content-Type", "image/png")
	w.Header().Set("Cache-Control", "no-store")
	_, _ = io.Copy(w, file)
}

func (s *Server) runTask(taskID, inputPath, outputDir string) {
	defer s.recoverTask(taskID)

	detectorCandidates := strings.TrimSpace(s.config.DetectorCandidates)
	detectorFallback := ""
	if detectorCandidates == "" && s.config.DetectorEnabled {
		s.updateTask(taskID, "processing", "codia_detector", 20, "Running UI detector.", nil)
		candidatePath, err := s.runDetector(inputPath, filepath.Join(outputDir, "detector"))
		if err != nil {
			detectorFallback = err.Error()
			log.Printf("codia detector fallback task=%s: %v", taskID, err)
			_ = writeDetectorFallback(filepath.Join(outputDir, "detector"), err)
			s.addTaskWarning(taskID, TaskWarning{
				Code:    "CODIA_DETECTOR_FALLBACK",
				Message: detectorFallback,
				Stage:   "codia_detector",
			})
		} else {
			detectorCandidates = candidatePath
		}
	}
	compileMessage := "Running Go Codia compiler."
	if detectorFallback != "" {
		compileMessage = "Running Go Codia compiler without detector candidates after detector fallback."
	}
	s.updateTask(taskID, "processing", "codia_compile", 40, compileMessage, nil)
	result, err := s.compile(compiler.Options{
		InputPath:          inputPath,
		OCRProvider:        s.config.OCRProvider,
		TaskID:             taskID,
		DetectorCandidates: detectorCandidates,
		OutputDir:          outputDir,
	})
	if err != nil {
		s.updateTask(taskID, "failed", "codia_compile", 100, err.Error(), &TaskError{Code: "CODIA_COMPILE_FAILED", Message: err.Error()})
		return
	}
	dslPath := filepath.Join(outputDir, dsl02.ArtifactName)
	s.mu.Lock()
	if task := s.tasks[taskID]; task != nil {
		task.Status = "completed"
		task.Stage = "codia_completed"
		task.Progress = 100
		task.Message = "Codia Runtime DSL 0.2 is ready."
		if detectorFallback != "" {
			task.Message = "Codia Runtime DSL 0.2 is ready. UI detector fallback was used."
		}
		task.DSLPath = dslPath
		task.Artifacts = artifactsToMap(result.Artifacts)
		task.UpdatedAt = time.Now().UTC()
	}
	s.mu.Unlock()
}

func (s *Server) runDetector(inputPath, outputDir string) (string, error) {
	options := detector.OptionsFromEnv()
	options.InputPath = inputPath
	options.OutputDir = outputDir
	if _, err := s.detect(context.Background(), options); err != nil {
		return "", err
	}
	return filepath.Join(outputDir, "ui_detector_candidates.v1.json"), nil
}

func (s *Server) recoverTask(taskID string) {
	value := recover()
	if value == nil {
		return
	}
	message := fmt.Sprintf("Codia task panicked: %v", value)
	log.Printf("codia task panic task=%s: %v\n%s", taskID, value, debug.Stack())
	s.updateTask(taskID, "failed", "codia_panic", 100, message, &TaskError{
		Code:    "CODIA_TASK_PANIC",
		Message: message,
	})
}

func writeDetectorFallback(outputDir string, err error) error {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	doc := map[string]any{
		"version": "codia_detector_fallback.v1",
		"error":   err.Error(),
	}
	data, marshalErr := json.MarshalIndent(doc, "", "  ")
	if marshalErr != nil {
		return marshalErr
	}
	return os.WriteFile(filepath.Join(outputDir, "detector_fallback.v1.json"), data, 0o644)
}

func (s *Server) storeTask(task *Task) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.tasks[task.ID] = task
}

func (s *Server) getTask(taskID string) *Task {
	s.mu.RLock()
	defer s.mu.RUnlock()
	task := s.tasks[taskID]
	if task == nil {
		return nil
	}
	copy := *task
	if task.Artifacts != nil {
		copy.Artifacts = map[string]string{}
		for key, value := range task.Artifacts {
			copy.Artifacts[key] = value
		}
	}
	if len(task.Warnings) > 0 {
		copy.Warnings = append([]TaskWarning(nil), task.Warnings...)
	}
	return &copy
}

func (s *Server) updateTask(taskID, status, stage string, progress int, message string, taskErr *TaskError) {
	s.mu.Lock()
	defer s.mu.Unlock()
	task := s.tasks[taskID]
	if task == nil {
		return
	}
	task.Status = status
	task.Stage = stage
	task.Progress = progress
	task.Message = message
	task.Error = taskErr
	task.UpdatedAt = time.Now().UTC()
}

func (s *Server) addTaskWarning(taskID string, warning TaskWarning) {
	s.mu.Lock()
	defer s.mu.Unlock()
	task := s.tasks[taskID]
	if task == nil {
		return
	}
	task.Warnings = append(task.Warnings, warning)
	task.UpdatedAt = time.Now().UTC()
}

func (task Task) toPublic() map[string]any {
	out := map[string]any{
		"taskId":   task.ID,
		"status":   task.Status,
		"stage":    task.Stage,
		"progress": task.Progress,
		"message":  task.Message,
	}
	if task.Error != nil {
		out["error"] = task.Error
	}
	if len(task.Warnings) > 0 {
		out["warnings"] = task.Warnings
	}
	return out
}

func safeAssetFileName(name string) string {
	base := filepath.Base(strings.TrimSpace(name))
	if base == "" || base == "." || !strings.HasSuffix(strings.ToLower(base), ".png") {
		return ""
	}
	for _, r := range base {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '.' || r == '_' || r == '-' {
			continue
		}
		return ""
	}
	return base
}

func readMultipartPNG(w http.ResponseWriter, r *http.Request, maxBytes int64) (string, []byte, error) {
	r.Body = http.MaxBytesReader(w, r.Body, maxBytes)
	if err := r.ParseMultipartForm(maxBytes); err != nil {
		return "", nil, fmt.Errorf("PNG upload is too large or invalid")
	}
	file, header, err := r.FormFile("file")
	if err != nil {
		return "", nil, fmt.Errorf("file field is required")
	}
	defer file.Close()
	data, err := io.ReadAll(io.LimitReader(file, maxBytes+1))
	if err != nil {
		return "", nil, fmt.Errorf("read PNG upload: %w", err)
	}
	if int64(len(data)) > maxBytes {
		return "", nil, fmt.Errorf("PNG file is too large")
	}
	if !bytes.HasPrefix(data, []byte("\x89PNG\r\n\x1a\n")) {
		return "", nil, fmt.Errorf("only PNG uploads are supported")
	}
	return header.Filename, data, nil
}

func splitTaskPath(path string) (string, string) {
	first, rest, ok := strings.Cut(strings.Trim(path, "/"), "/")
	if !ok {
		return first, ""
	}
	return first, rest
}

func newTaskID() string {
	var buf [6]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return fmt.Sprintf("task_%d", time.Now().UnixNano())
	}
	return "task_" + hex.EncodeToString(buf[:])
}

func safeFileName(name string) string {
	base := filepath.Base(strings.TrimSpace(name))
	if base == "" || base == "." || base == string(filepath.Separator) {
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

func artifactsToMap(artifacts compiler.Artifacts) map[string]string {
	data, err := json.Marshal(artifacts)
	if err != nil {
		return map[string]string{}
	}
	out := map[string]string{}
	_ = json.Unmarshal(data, &out)
	return out
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func writeError(w http.ResponseWriter, status int, code, message, stage, taskID string) {
	writeJSON(w, status, apiFailure{
		Success: false,
		Error: apiError{
			Code:    code,
			Message: message,
			Stage:   stage,
			TaskID:  taskID,
		},
	})
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

func ListenAndServe(ctx context.Context, addr string, config Config) error {
	server := &http.Server{
		Addr:              addr,
		Handler:           New(config).Handler(),
		ReadHeaderTimeout: 10 * time.Second,
	}
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdownCtx)
	}()
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}
