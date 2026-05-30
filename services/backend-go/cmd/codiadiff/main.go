package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/diff"
)

func main() {
	generatedPath := flag.String("generated", "", "path to generated codia_ir.v1.json")
	goldenPath := flag.String("golden", "", "path to golden codia_ir.v1.json")
	outputDir := flag.String("out", "", "output directory")
	failOnDiff := flag.Bool("fail-on-diff", false, "exit non-zero when extra or missed nodes are present")
	flag.Parse()
	if *generatedPath == "" || *goldenPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := diff.Compile(diff.Options{GeneratedPath: *generatedPath, GoldenPath: *goldenPath})
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiadiff: %v\n", err)
		os.Exit(1)
	}
	if err := diff.WriteArtifacts(*outputDir, doc); err != nil {
		fmt.Fprintf(os.Stderr, "codiadiff: write artifacts: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"wrote %s/codia_structure_diff.v1.json and codia_structure_diff_report.md (matched %d, extra %d, missed %d)\n",
		*outputDir,
		doc.Summary.MatchedNodeCount,
		doc.Summary.ExtraNodeCount,
		doc.Summary.MissedNodeCount,
	)
	if *failOnDiff && (doc.Summary.ExtraNodeCount > 0 || doc.Summary.MissedNodeCount > 0 || !doc.Checks.VisibleVocabularyPass) {
		os.Exit(1)
	}
}
