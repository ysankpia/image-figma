package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/canvas"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/emitter"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/ir"
)

func main() {
	inputPath := flag.String("input", "", "path to Codia/Figma canvas JSON")
	outputDir := flag.String("out", "", "output directory")
	expectation := flag.String("expect", "", "optional expectation name, for example tencent-comic-018")
	flag.Parse()
	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	analysis, err := canvas.AnalyzeFile(*inputPath, *expectation)
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiaanalyze: %v\n", err)
		os.Exit(1)
	}
	if err := canvas.WriteArtifacts(*outputDir, analysis); err != nil {
		fmt.Fprintf(os.Stderr, "codiaanalyze: write artifacts: %v\n", err)
		os.Exit(1)
	}
	irDoc, err := ir.FromAnalysis(analysis)
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiaanalyze: build ir: %v\n", err)
		os.Exit(1)
	}
	if err := ir.WriteArtifact(*outputDir, irDoc); err != nil {
		fmt.Fprintf(os.Stderr, "codiaanalyze: write ir: %v\n", err)
		os.Exit(1)
	}
	emitted, err := emitter.Emit(irDoc)
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiaanalyze: emit figma-like tree: %v\n", err)
		os.Exit(1)
	}
	if err := emitter.WriteArtifact(*outputDir, emitted); err != nil {
		fmt.Fprintf(os.Stderr, "codiaanalyze: write emitted tree: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("wrote %s/codia_canvas_analysis.v1.json, codia_ir.v1.json, and codia_figma_like_tree.v1.json (%d nodes, root children %d)\n", *outputDir, analysis.NodeCount, analysis.RootChildCount)
	if *expectation != "" {
		if len(analysis.ExpectationFailures) > 0 {
			fmt.Fprintf(os.Stderr, "codiaanalyze: expectation %q failed (%d checks)\n", *expectation, len(analysis.ExpectationFailures))
			for _, failure := range analysis.ExpectationFailures {
				fmt.Fprintf(os.Stderr, "- %s: expected %s, actual %s\n", failure.Check, failure.Expected, failure.Actual)
			}
			os.Exit(1)
		}
		fmt.Printf("expectation %s passed\n", *expectation)
	}
}
