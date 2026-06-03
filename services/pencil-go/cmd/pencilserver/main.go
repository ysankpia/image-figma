package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"strings"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/server"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	addr := envString("PENCIL_SERVER_ADDR", "127.0.0.1:8100")
	cfg := server.Config{
		StorageRoot:    envString("PENCIL_SERVER_STORAGE_ROOT", ""),
		OCRProvider:    envString("OCR_PROVIDER", ""),
		MaxUploadBytes: int64(server.EnvInt("PENCIL_SERVER_MAX_UPLOAD_BYTES", 10*1024*1024)),
		MaxFiles:       server.EnvInt("PENCIL_SERVER_MAX_FILES", 20),
	}
	log.Printf("pencil server listening on %s", addr)
	if err := server.ListenAndServe(ctx, addr, cfg); err != nil {
		log.Fatal(err)
	}
}

func envString(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
