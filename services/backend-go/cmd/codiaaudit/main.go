package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/codia/audit"
)

func main() {
	diffPath := flag.String("diff", "", "path to codia_structure_diff.v1.json")
	tokenPath := flag.String("tokens", "", "optional path to evidence_tokens.v1.json")
	physicalPath := flag.String("physical", "", "optional path to m29_physical_evidence.v1.json")
	outputDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *diffPath == "" || *outputDir == "" {
		flag.Usage()
		os.Exit(2)
	}
	doc, err := audit.Compile(audit.Options{
		DiffPath:     *diffPath,
		TokenPath:    *tokenPath,
		PhysicalPath: *physicalPath,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "codiaaudit: %v\n", err)
		os.Exit(1)
	}
	if err := audit.WriteArtifacts(*outputDir, doc); err != nil {
		fmt.Fprintf(os.Stderr, "codiaaudit: write artifacts: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"wrote %s/codia_failure_audit.v1.json and codia_failure_audit_report.md (%d actions, %d groups)\n",
		*outputDir,
		len(doc.Actions),
		len(doc.Groups),
	)
}
