package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/leaf"
)

func main() {
	tokenPath := flag.String("tokens", "", "path to evidence_tokens.v1.json")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *tokenPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := leaf.Compile(leaf.Options{TokenPath: *tokenPath})
	if err != nil {
		fmt.Fprintf(os.Stderr, "codialeaves: %v\n", err)
		os.Exit(1)
	}
	if err := leaf.WriteArtifacts(*outputDir, doc); err != nil {
		fmt.Fprintf(os.Stderr, "codialeaves: write artifacts: %v\n", err)
		os.Exit(1)
	}
	emitted, err := emitter.Emit(doc)
	if err != nil {
		fmt.Fprintf(os.Stderr, "codialeaves: emit figma-like tree: %v\n", err)
		os.Exit(1)
	}
	if err := emitter.WriteArtifact(*outputDir, emitted); err != nil {
		fmt.Fprintf(os.Stderr, "codialeaves: write emitted tree: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s/%s and codia_figma_like_tree.v1.json (%d nodes, %d leaf children)\n", *outputDir, leaf.ArtifactName, doc.Summary.NodeCount, len(doc.Root.Children))
}
