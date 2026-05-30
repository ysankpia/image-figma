package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/compiler"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/config"
)

func main() {
	config.LoadLocalEnvFromAncestors()
	inputPath := flag.String("input", "", "path to input PNG")
	ocrPath := flag.String("ocr", "", "optional OCR JSON path")
	ocrProvider := flag.String("ocr-provider", os.Getenv("OCR_PROVIDER"), "optional OCR provider: baidu_ppocrv5")
	goldenPath := flag.String("golden", "", "optional golden codia_ir.v1.json for structural diff")
	outputDir := flag.String("out", "", "output directory")
	failOnDiff := flag.Bool("fail-on-diff", false, "exit non-zero when golden diff has extra or missed nodes")
	flag.Parse()
	if *inputPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	result, err := compiler.Compile(compiler.Options{
		InputPath:   *inputPath,
		OCRPath:     *ocrPath,
		OCRProvider: *ocrProvider,
		GoldenPath:  *goldenPath,
		OutputDir:   *outputDir,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiacompile: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"wrote %s/codia_tree_ir.v1.json and codia_figma_like_tree.v1.json (%d nodes)\n",
		*outputDir,
		result.TreeIR.Summary.NodeCount,
	)
	if result.StructureDiff != nil {
		fmt.Printf(
			"structure diff: matched %d, extra %d, missed %d\n",
			result.StructureDiff.Summary.MatchedNodeCount,
			result.StructureDiff.Summary.ExtraNodeCount,
			result.StructureDiff.Summary.MissedNodeCount,
		)
		if result.FailureAudit != nil {
			fmt.Printf(
				"failure audit: actions %d, groups %d\n",
				len(result.FailureAudit.Actions),
				len(result.FailureAudit.Groups),
			)
		}
		if *failOnDiff && (result.StructureDiff.Summary.ExtraNodeCount > 0 || result.StructureDiff.Summary.MissedNodeCount > 0 || !result.StructureDiff.Checks.VisibleVocabularyPass) {
			os.Exit(1)
		}
	}
}
