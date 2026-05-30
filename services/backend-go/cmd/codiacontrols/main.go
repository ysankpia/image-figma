package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/control"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
)

func main() {
	inputPath := flag.String("input", "", "path to codia_leaf_ir.v1.json")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := control.Compile(control.Options{InputPath: *inputPath})
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiacontrols: %v\n", err)
		os.Exit(1)
	}
	if err := control.WriteArtifacts(*outputDir, result); err != nil {
		fmt.Fprintf(os.Stderr, "codiacontrols: write artifacts: %v\n", err)
		os.Exit(1)
	}
	doc := control.ToDocument(result)
	emitted, err := emitter.Emit(doc)
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiacontrols: emit figma-like tree: %v\n", err)
		os.Exit(1)
	}
	if err := emitter.WriteArtifact(*outputDir, emitted); err != nil {
		fmt.Fprintf(os.Stderr, "codiacontrols: write emitted tree: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s/%s and codia_figma_like_tree.v1.json (%d nodes)\n", *outputDir, control.ArtifactName, doc.Summary.NodeCount)
}
