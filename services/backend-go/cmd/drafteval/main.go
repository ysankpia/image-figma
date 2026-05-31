package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/eval/codia/audit"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/eval/codia/canvas"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/eval/codia/diff"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/eval/codia/ir"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	var err error
	switch os.Args[1] {
	case "analyze":
		err = runAnalyze(os.Args[2:])
	case "diff":
		err = runDiff(os.Args[2:])
	case "audit":
		err = runAudit(os.Args[2:])
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "drafteval %s: %v\n", os.Args[1], err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, "usage: drafteval <analyze|diff|audit> [flags]\n")
}

func runAnalyze(args []string) error {
	fs := flag.NewFlagSet("analyze", flag.ExitOnError)
	inputPath := fs.String("input", "", "path to Codia/Figma canvas JSON")
	outputDir := fs.String("out", "", "output directory")
	expectation := fs.String("expect", "", "optional expectation name, for example tencent-comic-018")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *inputPath == "" || *outputDir == "" {
		fs.Usage()
		return fmt.Errorf("missing required flags")
	}
	analysis, err := canvas.AnalyzeFile(*inputPath, *expectation)
	if err != nil {
		return err
	}
	if err := canvas.WriteArtifacts(*outputDir, analysis); err != nil {
		return fmt.Errorf("write canvas artifacts: %w", err)
	}
	irDoc, err := ir.FromAnalysis(analysis)
	if err != nil {
		return fmt.Errorf("build ir: %w", err)
	}
	if err := ir.WriteArtifact(*outputDir, irDoc); err != nil {
		return fmt.Errorf("write ir: %w", err)
	}
	fmt.Printf("wrote %s/codia_canvas_analysis.v1.json and codia_ir.v1.json (%d nodes, root children %d)\n", *outputDir, analysis.NodeCount, analysis.RootChildCount)
	if *expectation != "" {
		if len(analysis.ExpectationFailures) > 0 {
			for _, failure := range analysis.ExpectationFailures {
				fmt.Fprintf(os.Stderr, "- %s: expected %s, actual %s\n", failure.Check, failure.Expected, failure.Actual)
			}
			return fmt.Errorf("expectation %q failed (%d checks)", *expectation, len(analysis.ExpectationFailures))
		}
		fmt.Printf("expectation %s passed\n", *expectation)
	}
	return nil
}

func runDiff(args []string) error {
	fs := flag.NewFlagSet("diff", flag.ExitOnError)
	generatedPath := fs.String("generated", "", "path to generated codia_ir.v1.json")
	goldenPath := fs.String("golden", "", "path to golden codia_ir.v1.json")
	outputDir := fs.String("out", "", "output directory")
	failOnDiff := fs.Bool("fail-on-diff", false, "exit non-zero when extra or missed nodes are present")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *generatedPath == "" || *goldenPath == "" || *outputDir == "" {
		fs.Usage()
		return fmt.Errorf("missing required flags")
	}
	doc, err := diff.Compile(diff.Options{GeneratedPath: *generatedPath, GoldenPath: *goldenPath})
	if err != nil {
		return err
	}
	if err := diff.WriteArtifacts(*outputDir, doc); err != nil {
		return fmt.Errorf("write artifacts: %w", err)
	}
	fmt.Printf(
		"wrote %s/codia_structure_diff.v1.json and codia_structure_diff_report.md (matched %d, extra %d, missed %d)\n",
		*outputDir,
		doc.Summary.MatchedNodeCount,
		doc.Summary.ExtraNodeCount,
		doc.Summary.MissedNodeCount,
	)
	if *failOnDiff && (doc.Summary.ExtraNodeCount > 0 || doc.Summary.MissedNodeCount > 0 || !doc.Checks.VisibleVocabularyPass) {
		return fmt.Errorf("diff gate failed: extra=%d missed=%d visibleVocabulary=%t", doc.Summary.ExtraNodeCount, doc.Summary.MissedNodeCount, doc.Checks.VisibleVocabularyPass)
	}
	return nil
}

func runAudit(args []string) error {
	fs := flag.NewFlagSet("audit", flag.ExitOnError)
	diffPath := fs.String("diff", "", "path to codia_structure_diff.v1.json")
	tokenPath := fs.String("tokens", "", "optional path to evidence_tokens.v1.json")
	physicalPath := fs.String("physical", "", "optional path to m29_physical_evidence.v1.json")
	outputDir := fs.String("out", "", "output directory")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *diffPath == "" || *outputDir == "" {
		fs.Usage()
		return fmt.Errorf("missing required flags")
	}
	doc, err := audit.Compile(audit.Options{
		DiffPath:     *diffPath,
		TokenPath:    *tokenPath,
		PhysicalPath: *physicalPath,
	})
	if err != nil {
		return err
	}
	if err := audit.WriteArtifacts(*outputDir, doc); err != nil {
		return fmt.Errorf("write artifacts: %w", err)
	}
	fmt.Printf(
		"wrote %s/codia_failure_audit.v1.json and codia_failure_audit_report.md (%d actions, %d groups)\n",
		*outputDir,
		len(doc.Actions),
		len(doc.Groups),
	)
	return nil
}
