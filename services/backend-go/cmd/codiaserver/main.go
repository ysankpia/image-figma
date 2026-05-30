package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/server"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	addr := envString("CODIA_SERVER_ADDR", "127.0.0.1:8000")
	storageRoot := envString("CODIA_SERVER_STORAGE_ROOT", filepath.Join(".", "storage", "codia_server"))
	maxUploadBytes := envInt64("CODIA_SERVER_MAX_UPLOAD_BYTES", 10*1024*1024)
	detectorEnabled := envBool("CODIA_SERVER_DETECTOR_ENABLED", false)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	log.Printf("codia server listening on http://%s", addr)
	log.Printf("storage root: %s", storageRoot)
	if detectorEnabled {
		log.Printf("ui detector: enabled")
	}
	if err := server.ListenAndServe(ctx, addr, server.Config{
		StorageRoot:        storageRoot,
		OCRProvider:        os.Getenv("OCR_PROVIDER"),
		DetectorEnabled:    detectorEnabled,
		DetectorCandidates: strings.TrimSpace(os.Getenv("CODIA_SERVER_DETECTOR_CANDIDATES")),
		MaxUploadBytes:     maxUploadBytes,
	}); err != nil {
		log.Fatal(err)
	}
}

func envString(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func envInt64(key string, fallback int64) int64 {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseInt(value, 10, 64)
	if err != nil || parsed <= 0 {
		fmt.Fprintf(os.Stderr, "invalid %s=%q, using %d\n", key, value, fallback)
		return fallback
	}
	return parsed
}

func envBool(key string, fallback bool) bool {
	value := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if value == "" {
		return fallback
	}
	switch value {
	case "1", "true", "yes", "on", "enabled":
		return true
	case "0", "false", "no", "off", "disabled":
		return false
	default:
		fmt.Fprintf(os.Stderr, "invalid %s=%q, using %t\n", key, value, fallback)
		return fallback
	}
}
