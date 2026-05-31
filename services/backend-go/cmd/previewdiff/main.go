package main

import (
	"flag"
	"fmt"
	"os"

	previewdiff "github.com/luqing-studio/image-figma/services/backend-go/internal/htmlpreview/diff"
)

func main() {
	sourcePath := flag.String("source", "", "source PNG path")
	screenshotPath := flag.String("screenshot", "", "preview screenshot PNG path")
	previewHTML := flag.String("preview-html", "", "optional preview.html path for asset checks")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *sourcePath == "" || *screenshotPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := previewdiff.Run(previewdiff.Options{
		SourcePath:     *sourcePath,
		ScreenshotPath: *screenshotPath,
		PreviewHTML:    *previewHTML,
		OutputDir:      *outputDir,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "previewdiff: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"wrote %s and %s (mean channel diff %.2f, missing assets %d)\n",
		result.DiffPNG,
		result.Report,
		result.Metrics.MeanChannelDiff,
		result.Metrics.MissingAssetCount,
	)
}
