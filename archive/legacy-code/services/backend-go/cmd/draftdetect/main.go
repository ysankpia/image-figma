package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	envOptions := detector.OptionsFromEnv()

	inputPath := flag.String("input", "", "path to input PNG")
	outputDir := flag.String("out", "", "output directory")
	provider := flag.String("provider", envOptions.Provider, "vision provider")
	wireAPI := flag.String("wire-api", envOptions.WireAPI, "wire API: responses or chat.completions")
	baseURL := flag.String("base-url", envOptions.BaseURL, "OpenAI-compatible base URL")
	apiKey := flag.String("api-key", "", "vision API key override; prefer env VISION_API_KEY")
	model := flag.String("model", envOptions.Model, "vision model id")
	passes := flag.String("passes", strings.Join(envOptions.Passes, ","), "comma-separated detector pass list")
	maxSide := flag.Int("max-side", envOptions.MaxSide, "maximum image side sent to provider")
	concurrency := flag.Int("concurrency", envOptions.Concurrency, "maximum concurrent detector passes")
	timeoutSeconds := flag.Int("timeout-seconds", int(envOptions.Timeout/time.Second), "per-pass provider timeout in seconds")
	temperature := flag.Float64("temperature", envOptions.Temperature, "optional model temperature")
	stream := flag.Bool("stream", envOptions.Stream, "request streaming provider responses")
	flag.Parse()

	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	options := detector.Options{
		InputPath:   *inputPath,
		OutputDir:   *outputDir,
		Provider:    *provider,
		WireAPI:     *wireAPI,
		BaseURL:     *baseURL,
		APIKey:      detectorAPIKey(*apiKey, envOptions.APIKey),
		Model:       *model,
		Passes:      splitCSV(*passes),
		MaxSide:     *maxSide,
		Concurrency: *concurrency,
		Timeout:     time.Duration(*timeoutSeconds) * time.Second,
		Temperature: *temperature,
		Stream:      *stream,
	}
	result, err := detector.Run(context.Background(), options)
	if err != nil {
		fmt.Fprintf(os.Stderr, "draftdetect: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"wrote %s/ui_detector_candidates.v1.json, ui_detector_report.md, and ui_detector_overlay.png (%d candidates)\n",
		*outputDir,
		result.Document.Summary.Total,
	)
}

func detectorAPIKey(override string, envValue string) string {
	if strings.TrimSpace(override) != "" {
		return strings.TrimSpace(override)
	}
	return strings.TrimSpace(envValue)
}

func splitCSV(raw string) []string {
	fields := strings.Split(raw, ",")
	out := make([]string, 0, len(fields))
	for _, field := range fields {
		value := strings.TrimSpace(field)
		if value != "" {
			out = append(out, value)
		}
	}
	return out
}
