package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"strconv"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/app/server"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

func main() {
	config.LoadLocalEnvFromAncestors()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	addr := envString("DRAFT_SERVER_ADDR", "127.0.0.1:8000")
	config := server.Config{
		StorageRoot:    envString("DRAFT_SERVER_STORAGE_ROOT", ""),
		OCRProvider:    envString("OCR_PROVIDER", ""),
		MaxUploadBytes: int64(envInt("DRAFT_SERVER_MAX_UPLOAD_BYTES", 10*1024*1024)),
		VisionEnabled:  envBool("DRAFT_SERVER_VISION_ENABLED", true),
		VisionOptions:  detector.OptionsFromEnv(),
	}
	log.Printf("draft server listening on %s", addr)
	if err := server.ListenAndServe(ctx, addr, config); err != nil {
		log.Fatal(err)
	}
}

func envString(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func envInt(key string, fallback int) int {
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

func envBool(key string, fallback bool) bool {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseBool(raw)
	if err != nil {
		return fallback
	}
	return value
}
