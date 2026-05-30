package audit

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func WriteArtifacts(outputDir string, doc Document) error {
	if outputDir == "" {
		return fmt.Errorf("missing output dir")
	}
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, "codia_failure_audit.v1.json"), data, 0o644); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outputDir, "codia_failure_audit_report.md"), []byte(MarkdownReport(doc)), 0o644)
}

func MarkdownReport(doc Document) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Codia Failure Audit\n\n")
	fmt.Fprintf(&b, "- diff: `%s`\n", doc.Source.DiffPath)
	fmt.Fprintf(&b, "- generated: `%s`\n", doc.Source.GeneratedPath)
	fmt.Fprintf(&b, "- golden: `%s`\n", doc.Source.GoldenPath)
	fmt.Fprintf(&b, "- generatedNodes: `%d`\n", doc.Summary.GeneratedNodeCount)
	fmt.Fprintf(&b, "- goldenNodes: `%d`\n", doc.Summary.GoldenNodeCount)
	fmt.Fprintf(&b, "- matched: `%d`\n", doc.Summary.MatchedNodeCount)
	fmt.Fprintf(&b, "- extra: `%d`\n", doc.Summary.ExtraNodeCount)
	fmt.Fprintf(&b, "- missed: `%d`\n", doc.Summary.MissedNodeCount)

	writeCountsTable(&b, "By Stage", doc.Summary.ByStage)
	writeCountsTable(&b, "By Diagnosis", doc.Summary.ByDiagnosis)
	writeCountsTable(&b, "By Role", doc.Summary.ByRole)
	writeCountsTable(&b, "By Evidence Kind", doc.Summary.ByEvidenceKind)
	writeCountsTable(&b, "By IoU Bucket", doc.Summary.ByIoUBucket)

	fmt.Fprintf(&b, "\n## Action Items\n\n")
	fmt.Fprintf(&b, "| rank | ownerLayer | diagnosis | role | evidence | count | samples | rationale |\n")
	fmt.Fprintf(&b, "| ---: | --- | --- | --- | --- | ---: | --- | --- |\n")
	if len(doc.Actions) == 0 {
		fmt.Fprintf(&b, "| 0 | none | none |  |  | 0 |  |  |\n")
	} else {
		for _, item := range doc.Actions {
			fmt.Fprintf(&b, "| %d | `%s` | `%s` | `%s` | `%s` | %d | `%s` | %s |\n",
				item.Rank,
				item.OwnerLayer,
				item.Diagnosis,
				item.Role,
				item.EvidenceKind,
				item.Count,
				strings.Join(item.SampleIDs, ", "),
				item.Rationale,
			)
		}
	}

	fmt.Fprintf(&b, "\n## Leaf Debug Samples\n\n")
	fmt.Fprintf(&b, "| id | verdict | diagnosis | role | evidence | source | notes | parent | bbox | best | bestEvidence | bestSource | bestNotes | bestParent | bestBBox | iou | reason | nearbyTokens | nearbyPrimitives |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- |\n")
	if len(doc.LeafDebug) == 0 {
		fmt.Fprintf(&b, "| none |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |\n")
	} else {
		for _, sample := range doc.LeafDebug {
			fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%s` | `%s` | `%s` | `%s` | `%s` | `%d,%d,%d,%d` | `%s` | `%s` | `%s` | `%s` | `%s` | `%d,%d,%d,%d` | %.3f | `%s` | `%s` | `%s` |\n",
				sample.ID,
				sample.Verdict,
				sample.Diagnosis,
				sample.Role,
				sample.EvidenceKind,
				nonEmpty(sample.EvidenceSourceID, sample.SourcePath),
				sample.EvidenceNotes,
				sample.ParentID,
				sample.BBox.X,
				sample.BBox.Y,
				sample.BBox.Width,
				sample.BBox.Height,
				sample.BestID,
				sample.BestEvidenceKind,
				nonEmpty(sample.BestEvidenceSourceID, sample.BestSourcePath),
				sample.BestEvidenceNotes,
				sample.BestParentID,
				sample.BestBBox.X,
				sample.BestBBox.Y,
				sample.BestBBox.Width,
				sample.BestBBox.Height,
				sample.BestIoU,
				sample.FailureReason,
				formatNearby(sample.NearbyTokens),
				formatNearby(sample.NearbyPrimitives),
			)
		}
	}

	fmt.Fprintf(&b, "\n## Failure Groups\n\n")
	fmt.Fprintf(&b, "| stage | diagnosis | role | evidence | count | samples |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | ---: | --- |\n")
	if len(doc.Groups) == 0 {
		fmt.Fprintf(&b, "| none | none |  |  | 0 |  |\n")
	} else {
		limit := min(40, len(doc.Groups))
		for _, group := range doc.Groups[:limit] {
			fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%s` | %d | `%s` |\n",
				group.Stage,
				group.Diagnosis,
				group.Role,
				group.EvidenceKind,
				group.Count,
				strings.Join(group.SampleIDs, ", "),
			)
		}
	}
	return b.String()
}

func writeCountsTable(b *strings.Builder, title string, counts map[string]int) {
	if len(counts) == 0 {
		return
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		if counts[keys[i]] != counts[keys[j]] {
			return counts[keys[i]] > counts[keys[j]]
		}
		return keys[i] < keys[j]
	})
	fmt.Fprintf(b, "\n## %s\n\n", title)
	fmt.Fprintf(b, "| key | count |\n")
	fmt.Fprintf(b, "| --- | ---: |\n")
	for _, key := range keys {
		fmt.Fprintf(b, "| `%s` | %d |\n", key, counts[key])
	}
}

func formatNearby(items []NearbyEvidence) string {
	if len(items) == 0 {
		return ""
	}
	limit := min(3, len(items))
	parts := make([]string, 0, limit)
	for _, item := range items[:limit] {
		reasons := strings.Join(item.Reasons, "+")
		if reasons == "" {
			reasons = "-"
		}
		parts = append(parts, fmt.Sprintf(
			"%s/%s/%s/iou=%.3f/ov=%.3f/d=%.1f/b=%d,%d,%d,%d/r=%s",
			item.ID,
			item.Kind,
			nonEmpty(item.Disposition, "-"),
			item.IoU,
			item.OverlapRatio,
			item.CenterDistance,
			item.BBox.X,
			item.BBox.Y,
			item.BBox.Width,
			item.BBox.Height,
			reasons,
		))
	}
	return strings.Join(parts, "; ")
}

func min(a int, b int) int {
	if a < b {
		return a
	}
	return b
}
