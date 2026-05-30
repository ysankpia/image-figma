package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/detector"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	envOptions := detector.OptionsFromEnv()

	inputPath := flag.String("input", "", "path to input PNG")
	outputDir := flag.String("out", "", "output directory")
	provider := flag.String("provider", envOptions.Provider, "detector provider: openai-responses or openai-chat-completions")
	wireAPI := flag.String("wire-api", envOptions.WireAPI, "wire API: responses or chat.completions")
	baseURL := flag.String("base-url", envOptions.BaseURL, "OpenAI-compatible base URL")
	apiKey := flag.String("api-key", "", "detector API key override; prefer env CODIA_UI_DETECTOR_API_KEY or OPENAI_API_KEY")
	model := flag.String("model", envOptions.Model, "detector model id")
	passes := flag.String("passes", strings.Join(envOptions.Passes, ","), "comma-separated pass list")
	maxSide := flag.Int("max-side", envOptions.MaxSide, "maximum image side sent to provider")
	timeoutSeconds := flag.Int("timeout-seconds", int(envOptions.Timeout/time.Second), "per-pass provider timeout in seconds")
	temperature := flag.Float64("temperature", envOptions.Temperature, "optional model temperature")
	stream := flag.Bool("stream", envOptions.Stream, "request streaming provider responses")

	evalMode := flag.Bool("eval", false, "evaluate existing ui_detector_candidates.v1.json against golden CodiaIR")
	candidatesPath := flag.String("candidates", "", "path to ui_detector_candidates.v1.json for -eval")
	goldenPath := flag.String("golden", "", "path to golden codia_ir.v1.json for -eval")
	flag.Parse()

	if *evalMode {
		if *candidatesPath == "" || *goldenPath == "" || *outputDir == "" {
			flag.Usage()
			os.Exit(2)
		}
		doc, err := detector.Eval(detector.EvalOptions{
			CandidatesPath: *candidatesPath,
			GoldenPath:     *goldenPath,
			OutputDir:      *outputDir,
		})
		if err != nil {
			fmt.Fprintf(os.Stderr, "codiadetector eval: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf(
			"wrote %s/ui_detector_eval.v1.json and ui_detector_eval_report.md (matched@0.5 %d, extra@0.5 %d, missed@0.5 %d)\n",
			*outputDir,
			doc.Summary.MatchedAt05,
			doc.Summary.ExtraAt05,
			doc.Summary.MissedAt05,
		)
		return
	}

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
		Timeout:     time.Duration(*timeoutSeconds) * time.Second,
		Temperature: *temperature,
		Stream:      *stream,
	}
	result, err := detector.Run(context.Background(), options)
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiadetector: %v\n", err)
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
