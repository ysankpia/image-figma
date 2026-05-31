package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutcompile"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	inputPath := flag.String("input", "", "path to input PNG")
	outputDir := flag.String("out", "", "output directory")
	taskID := flag.String("task-id", "layout_task", "task id for future reports")
	flag.Parse()

	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := layoutcompile.Run(layoutcompile.Options{
		InputPath: *inputPath,
		OutputDir: *outputDir,
		TaskID:    *taskID,
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
}
