package server

import (
	"context"
	"encoding/json"
	"net/http"
	"time"
)

type Server struct {
	config Config
}

func New(config Config) *Server {
	return &Server{config: config.normalized()}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/health", s.handleHealth)
	mux.HandleFunc("/api/draft-preview", s.handleDraftPreview)
	mux.HandleFunc("/api/draft-preview/", s.handleDraftPreviewTask)
	return withCORS(mux)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "health", "")
		return
	}
	writeJSON(w, http.StatusOK, apiSuccess{Success: true, Data: map[string]any{
		"status":  "ok",
		"version": "draft-server-v0.1",
		"time":    time.Now().UTC().Format(time.RFC3339),
	}})
}

func (s *Server) handleDraftPreview(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "METHOD_NOT_ALLOWED", "Method not allowed.", "draft_preview_upload", "")
		return
	}
	writeError(w, http.StatusNotImplemented, "DRAFT_PIPELINE_NOT_IMPLEMENTED", "Draft pipeline route is reserved but not wired yet.", "draft_preview_upload", "")
}

func (s *Server) handleDraftPreviewTask(w http.ResponseWriter, r *http.Request) {
	writeError(w, http.StatusNotImplemented, "DRAFT_PIPELINE_NOT_IMPLEMENTED", "Draft task route is reserved but not wired yet.", "draft_preview_lookup", "")
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
