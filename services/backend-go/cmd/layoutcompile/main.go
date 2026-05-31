package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutcompile"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutcompile/unifiedvision"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/vision/detector"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	envOptions := detector.OptionsFromEnv()
	unifiedEnv := unifiedvision.OptionsFromEnv()
	inputPath := flag.String("input", "", "path to input PNG")
	outputDir := flag.String("out", "", "output directory")
	taskID := flag.String("task-id", "layout_task", "task id for future reports")
	ocrPath := flag.String("ocr", "", "optional OCR JSON path")
	ocrProvider := flag.String("ocr-provider", os.Getenv("OCR_PROVIDER"), "optional OCR provider")
	skipEvidence := flag.Bool("skip-evidence", false, "write only the empty layout IR page skeleton")
	vision := flag.Bool("vision", false, "run optional vision detector; failures continue with a warning")
	visionCandidates := flag.String("vision-candidates", "", "optional ui_detector_candidates.v1.json path")
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
	advisorInputOut := flag.String("advisor-input-out", "", "optional path to write layout_advisor_input.v1.json")
	advisorResult := flag.String("advisor-result", "", "optional layout_advisor_result.v1.json path to build advisor experiment artifacts")
	unified := flag.Bool("unified-vision", unifiedEnv.Enabled, "run optional Unified Vision layout experiment; baseline artifacts remain unchanged")
	unifiedWireAPI := flag.String("unified-vision-wire-api", unifiedEnv.WireAPI, "Unified Vision wire API: responses or chat.completions")
	unifiedBaseURL := flag.String("unified-vision-base-url", unifiedEnv.BaseURL, "OpenAI-compatible Unified Vision base URL")
	unifiedAPIKey := flag.String("unified-vision-api-key", "", "Unified Vision API key override; prefer env UNIFIED_VISION_API_KEY")
	unifiedModel := flag.String("unified-vision-model", unifiedEnv.Model, "Unified Vision model id")
	unifiedConcurrency := flag.Int("unified-vision-concurrency", unifiedEnv.Concurrency, "maximum concurrent Unified Vision section/batch calls")
	unifiedTimeoutSeconds := flag.Int("unified-vision-timeout-seconds", int(unifiedEnv.Timeout/time.Second), "per-batch Unified Vision timeout in seconds")
	unifiedTransportRetries := flag.Int("unified-vision-transport-retries", unifiedEnv.TransportRetries, "transport retry count for Unified Vision provider calls")
	unifiedRepairAttempts := flag.Int("unified-vision-repair-attempts", unifiedEnv.RepairAttempts, "semantic repair attempts for rejected Unified Vision batches")
	unifiedMaxItems := flag.Int("unified-vision-max-items", unifiedEnv.MaxItemsPerBatch, "soft max evidence items per Unified Vision batch")
	unifiedHardMaxItems := flag.Int("unified-vision-hard-max-items", unifiedEnv.HardMaxItemsPerBatch, "hard max evidence items per Unified Vision batch")
	unifiedMaxComplexity := flag.Float64("unified-vision-max-complexity", unifiedEnv.MaxComplexity, "max complexity score per Unified Vision batch before splitting")
	flag.Parse()

	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := layoutcompile.Run(layoutcompile.Options{
		InputPath:                 *inputPath,
		OutputDir:                 *outputDir,
		TaskID:                    *taskID,
		OCRPath:                   *ocrPath,
		OCRProvider:               *ocrProvider,
		VisionEnabled:             *vision,
		VisionCandidatesPath:      *visionCandidates,
		SkipEvidenceNormalization: *skipEvidence,
		AdvisorInputPath:          *advisorInputOut,
		AdvisorResultPath:         *advisorResult,
		UnifiedVisionEnabled:      *unified,
		UnifiedVisionOptions: unifiedvision.Options{
			Enabled:              *unified,
			Provider:             unifiedEnv.Provider,
			WireAPI:              *unifiedWireAPI,
			BaseURL:              *unifiedBaseURL,
			APIKey:               detectorAPIKey(*unifiedAPIKey, unifiedEnv.APIKey),
			Model:                *unifiedModel,
			Concurrency:          *unifiedConcurrency,
			Timeout:              time.Duration(*unifiedTimeoutSeconds) * time.Second,
			Temperature:          unifiedEnv.Temperature,
			TransportRetries:     *unifiedTransportRetries,
			RepairAttempts:       *unifiedRepairAttempts,
			MaxItemsPerBatch:     *unifiedMaxItems,
			HardMaxItemsPerBatch: *unifiedHardMaxItems,
			MaxComplexity:        *unifiedMaxComplexity,
			MinConfidence:        unifiedEnv.MinConfidence,
			MaxFitRatio:          unifiedEnv.MaxFitRatio,
			MaxYSpreadFactor:     unifiedEnv.MaxYSpreadFactor,
			MaxGap:               unifiedEnv.MaxGap,
			MaxGapVariance:       unifiedEnv.MaxGapVariance,
			CropPadding:          unifiedEnv.CropPadding,
		},
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
		fmt.Fprintf(os.Stderr, "layoutcompile: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"wrote %s, %s, and %s (%d nodes, %d validation errors)\n",
		result.Artifacts.LayoutIR,
		result.Artifacts.ValidationReport,
		result.Artifacts.CompileReport,
		result.Document.Summary.NodeCount,
		result.Validation.ErrorCount,
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
