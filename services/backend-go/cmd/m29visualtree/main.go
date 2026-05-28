package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/visualtree"
)

func main() {
	tokenPath := flag.String("tokens", "", "path to evidence_tokens.v1.json")
	relationPath := flag.String("relations", "", "path to relation_graph.v1.json")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *tokenPath == "" || *relationPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := visualtree.Compile(visualtree.Options{
		TokenPath:    *tokenPath,
		RelationPath: *relationPath,
		OutputDir:    *outputDir,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "m29visualtree: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s/visual_tree.v1.json (%d nodes)\n", *outputDir, doc.Diagnostics.NodeCount)
}
