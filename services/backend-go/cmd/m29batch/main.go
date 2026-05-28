package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/batch"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	inputDir := flag.String("input-dir", "", "directory containing PNG files")
	outputDir := flag.String("out", "", "batch output directory")
	ocrProvider := flag.String("ocr-provider", os.Getenv("OCR_PROVIDER"), "optional OCR provider: baidu_ppocrv5")
	limit := flag.Int("limit", 0, "optional max number of images")
	flag.Parse()
	if *inputDir == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	summary, err := batch.Run(batch.Options{
		InputDir:    *inputDir,
		OutputDir:   *outputDir,
		OCRProvider: *ocrProvider,
		Limit:       *limit,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "m29batch: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s (%d completed, %d failed)\n", *outputDir, summary.CompletedCount, summary.FailedCount)
}
