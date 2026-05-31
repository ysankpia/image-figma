package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/compile"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	envOptions := detector.OptionsFromEnv()
	inputPath := flag.String("input", "", "path to input PNG")
	outputDir := flag.String("out", "", "output directory")
	taskID := flag.String("task-id", "draft_task", "task id written into runtime DSL")
	ocrPath := flag.String("ocr", "", "optional OCR JSON path")
	ocrProvider := flag.String("ocr-provider", os.Getenv("OCR_PROVIDER"), "optional OCR provider")
	vision := flag.Bool("vision", false, "run optional vision detector; failures continue with a warning")
	provider := flag.String("vision-provider", envOptions.Provider, "vision provider")
	wireAPI := flag.String("vision-wire-api", envOptions.WireAPI, "vision wire API: responses or chat.completions")
	baseURL := flag.String("vision-base-url", envOptions.BaseURL, "OpenAI-compatible vision base URL")
	apiKey := flag.String("vision-api-key", "", "vision API key override; prefer env VISION_API_KEY")
	model := flag.String("vision-model", envOptions.Model, "vision model id")
	passes := flag.String("vision-passes", strings.Join(envOptions.Passes, ","), "comma-separated vision detector pass list")
	maxSide := flag.Int("vision-max-side", envOptions.MaxSide, "maximum image side sent to provider")
	concurrency := flag.Int("vision-concurrency", envOptions.Concurrency, "maximum concurrent detector passes")
	timeoutSeconds := flag.Int("vision-timeout-seconds", int(envOptions.Timeout/time.Second), "per-pass provider timeout in seconds")
	temperature := flag.Float64("vision-temperature", envOptions.Temperature, "optional model temperature")
	stream := flag.Bool("vision-stream", envOptions.Stream, "request streaming provider responses")
	flag.Parse()

	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := compile.Run(compile.Options{
		InputPath:     *inputPath,
		OutputDir:     *outputDir,
		TaskID:        *taskID,
		OCRPath:       *ocrPath,
		OCRProvider:   *ocrProvider,
		VisionEnabled: *vision,
		VisionOptions: detector.Options{
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
		},
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "draftcompile: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"wrote %s, %s, %s, and %s (%d layers)\n",
		result.Artifacts.M29PhysicalEvidence,
		result.Artifacts.EditableLayerGraph,
		result.Artifacts.ValidationReport,
		result.Artifacts.RuntimeDSL,
		result.Graph.Summary.LayerCount,
	)
	for _, warning := range result.Warnings {
		fmt.Fprintf(os.Stderr, "warning %s: %s\n", warning.Code, warning.Message)
	}
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
