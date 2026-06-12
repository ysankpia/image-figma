package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
)

func main() {
	inputPath := flag.String("input", "", "path to m29_physical_evidence.v1.json")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := evidence.Compile(evidence.Options{InputPath: *inputPath, OutputDir: *outputDir})
	if err != nil {
		fmt.Fprintf(os.Stderr, "m29tokens: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s/evidence_tokens.v1.json (%d tokens from %d primitives)\n", *outputDir, doc.Diagnostics.TokenCount, doc.Diagnostics.PrimitiveCount)
}
