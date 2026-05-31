package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/draft/compile"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	inputPath := flag.String("input", "", "path to input PNG")
	outputDir := flag.String("out", "", "output directory")
	taskID := flag.String("task-id", "draft_task", "task id written into runtime DSL")
	ocrPath := flag.String("ocr", "", "optional OCR JSON path")
	ocrProvider := flag.String("ocr-provider", os.Getenv("OCR_PROVIDER"), "optional OCR provider")
	flag.Parse()

	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := compile.Run(compile.Options{
		InputPath:   *inputPath,
		OutputDir:   *outputDir,
		TaskID:      *taskID,
		OCRPath:     *ocrPath,
		OCRProvider: *ocrProvider,
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
}
