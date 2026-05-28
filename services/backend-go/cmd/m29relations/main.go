package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/relation"
)

func main() {
	inputPath := flag.String("input", "", "path to evidence_tokens.v1.json")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := relation.Compile(relation.Options{InputPath: *inputPath, OutputDir: *outputDir})
	if err != nil {
		fmt.Fprintf(os.Stderr, "m29relations: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s/relation_graph.v1.json (%d relations from %d tokens)\n", *outputDir, doc.Diagnostics.RelationCount, doc.Diagnostics.TokenCount)
}
