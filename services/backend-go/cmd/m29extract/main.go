package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/pipeline"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	inputPath := flag.String("input", "", "path to input PNG")
	ocrPath := flag.String("ocr", "", "optional OCR JSON path")
	ocrProvider := flag.String("ocr-provider", os.Getenv("OCR_PROVIDER"), "optional OCR provider: baidu_ppocrv5")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()

	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := pipeline.Run(pipeline.Options{
		InputPath:   *inputPath,
		OCRPath:     *ocrPath,
		OCRProvider: *ocrProvider,
		OutputDir:   *outputDir,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "m29extract: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s (%d primitives)\n", *outputDir, len(doc.Primitives))
}
