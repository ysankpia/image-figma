package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/luqing-studio/image-figma/tools/go-m29-physical-evidence/internal/m29/locator"
)

func main() {
	inputPath := flag.String("input", "", "path to input PNG")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()

	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := locator.Run(locator.Options{InputPath: *inputPath, OutputDir: *outputDir})
	if err != nil {
		fmt.Fprintf(os.Stderr, "m29locate: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s (%d items)\n", filepath.Join(*outputDir, locator.OutputName), len(doc.Items))
}
