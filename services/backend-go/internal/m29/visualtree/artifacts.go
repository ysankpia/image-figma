package visualtree

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func writeArtifacts(outputDir string, sourcePath string, doc Document) error {
	if err := writeReport(filepath.Join(outputDir, "visual_tree_report.md"), doc); err != nil {
		return err
	}
	if err := writeContainmentReport(filepath.Join(outputDir, "visual_tree_containment_report.md"), doc.ContainmentReport); err != nil {
		return err
	}
	if sourcePath == "" {
		return nil
	}
	img, err := imageio.ReadPNG(sourcePath)
	if err != nil {
		return err
	}
	overlayPath := filepath.Join(outputDir, "visual_tree_overlay.png")
	if err := WriteOverlay(overlayPath, img, doc.Root); err != nil {
		return err
	}
	return writePreviewSheet(filepath.Join(outputDir, "visual_tree_preview_sheet.png"), img, overlayPath)
}

func writeReport(path string, doc Document) error {
	var b strings.Builder
	fmt.Fprintf(&b, "# M29 Visual Tree Report\n\n")
	fmt.Fprintf(&b, "- nodes: %d\n", doc.Diagnostics.NodeCount)
	fmt.Fprintf(&b, "- bodyChildren: %d\n", doc.Diagnostics.BodyChildCount)
	fmt.Fprintf(&b, "- nodeTypes: %s\n", formatCounts(doc.Diagnostics.NodeTypeCounts))
	fmt.Fprintf(&b, "- parentRelations: %d\n", doc.Diagnostics.ParentRelationCount)
	fmt.Fprintf(&b, "- parentRelativeLayouts: %d\n", doc.Diagnostics.ParentRelativeLayoutCount)
	fmt.Fprintf(&b, "- syntheticGroups: %d\n", doc.Diagnostics.SyntheticGroupCount)
	fmt.Fprintf(&b, "- groupKinds: %s\n", formatCounts(doc.Diagnostics.GroupKindCounts))
	fmt.Fprintf(&b, "- containment: %d applied, relation=%d, bboxOnly=%d, bodyChildren %d -> %d\n", doc.Diagnostics.ContainmentAppliedCount, doc.Diagnostics.RelationParentCount, doc.Diagnostics.ContainmentOnlyParentCount, doc.Diagnostics.BodyChildCountBefore, doc.Diagnostics.BodyChildCountAfter)
	fmt.Fprintf(&b, "- backgroundLayers: %d\n\n", doc.Diagnostics.BackgroundLayerCount)
	writeNodeReport(&b, doc.Root, 0)
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func writeContainmentReport(path string, report ContainmentReport) error {
	var b strings.Builder
	fmt.Fprintf(&b, "# M29 Visual Tree Containment Report\n\n")
	fmt.Fprintf(&b, "- bodyChildren: %d -> %d\n", report.BodyChildCountBefore, report.BodyChildCountAfter)
	fmt.Fprintf(&b, "- candidates: %d\n", report.CandidateCount)
	fmt.Fprintf(&b, "- applied: %d\n", report.AppliedCount)
	fmt.Fprintf(&b, "- relationParents: %d\n", report.RelationParentCount)
	fmt.Fprintf(&b, "- bboxOnlyParents: %d\n\n", report.ContainmentOnlyParentCount)
	fmt.Fprintf(&b, "| decision | node | oldParent | newParent | parentKind | reason | coverage | relationIds |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | --- | --- | ---: | --- |\n")
	for _, decision := range report.Decisions {
		fmt.Fprintf(
			&b,
			"| %s | `%s` | `%s` | `%s` | `%s` | `%s` | %.4f | %s |\n",
			decision.Decision,
			decision.NodeID,
			decision.OldParentID,
			decision.NewParentID,
			decision.NewParentKind,
			decision.Reason,
			decision.BBoxCoverage,
			strings.Join(decision.RelationIDs, ","),
		)
	}
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func writeNodeReport(b *strings.Builder, node Node, depth int) {
	indent := strings.Repeat("  ", depth)
	fmt.Fprintf(
		b,
		"%s- `%s` `%s` bbox=(%d,%d,%d,%d) layout=(%d,%d,%d,%d) tokens=%s relations=%s background=%s\n",
		indent,
		node.Type,
		node.ID,
		node.BBox.X,
		node.BBox.Y,
		node.BBox.Width,
		node.BBox.Height,
		node.Layout.X,
		node.Layout.Y,
		node.Layout.Width,
		node.Layout.Height,
		strings.Join(node.SourceRefs.TokenIDs, ","),
		strings.Join(node.SourceRefs.RelationIDs, ","),
		node.Style.BackgroundRef,
	)
	if node.Meta.Synthetic {
		fmt.Fprintf(b, "%s  meta: synthetic groupKind=%s\n", indent, node.Meta.GroupKind)
	}
	if node.Meta.ParentReason != "" {
		fmt.Fprintf(b, "%s  parentReason: %s\n", indent, node.Meta.ParentReason)
	}
	for _, child := range node.Children {
		writeNodeReport(b, child, depth+1)
	}
}

func WriteOverlay(path string, src image.Image, root Node) error {
	b := src.Bounds()
	out := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
	draw.Draw(out, out.Bounds(), src, b.Min, draw.Src)
	var walk func(Node, int)
	walk = func(node Node, depth int) {
		if node.Type != "Body" {
			drawBBox(out, node.BBox, colorForNode(node.Type, depth))
		}
		for _, child := range node.Children {
			walk(child, depth+1)
		}
	}
	walk(root, 0)
	return imageio.WritePNG(path, out)
}

func writePreviewSheet(path string, src image.Image, overlayPath string) error {
	overlay, err := imageio.ReadPNG(overlayPath)
	if err != nil {
		return err
	}
	srcBounds := src.Bounds()
	overlayBounds := overlay.Bounds()
	width := srcBounds.Dx() + overlayBounds.Dx()
	height := max(srcBounds.Dy(), overlayBounds.Dy())
	out := image.NewRGBA(image.Rect(0, 0, width, height))
	draw.Draw(out, image.Rect(0, 0, srcBounds.Dx(), srcBounds.Dy()), src, srcBounds.Min, draw.Src)
	draw.Draw(out, image.Rect(srcBounds.Dx(), 0, width, overlayBounds.Dy()), overlay, overlayBounds.Min, draw.Src)
	return imageio.WritePNG(path, out)
}

func drawBBox(img *image.RGBA, b contract.BBox, c color.RGBA) {
	x1 := max(0, b.X)
	y1 := max(0, b.Y)
	x2 := min(img.Bounds().Dx()-1, b.X+b.Width-1)
	y2 := min(img.Bounds().Dy()-1, b.Y+b.Height-1)
	if x2 < x1 || y2 < y1 {
		return
	}
	for x := x1; x <= x2; x++ {
		img.SetRGBA(x, y1, c)
		img.SetRGBA(x, y2, c)
	}
	for y := y1; y <= y2; y++ {
		img.SetRGBA(x1, y, c)
		img.SetRGBA(x2, y, c)
	}
}

func colorForNode(nodeType string, depth int) color.RGBA {
	alpha := uint8(255)
	if depth > 2 {
		alpha = 220
	}
	switch nodeType {
	case "Layer":
		return color.RGBA{R: 30, G: 210, B: 120, A: alpha}
	case "Text":
		return color.RGBA{R: 30, G: 120, B: 255, A: alpha}
	case "Image":
		return color.RGBA{R: 230, G: 80, B: 60, A: alpha}
	default:
		return color.RGBA{R: 255, G: 255, B: 255, A: alpha}
	}
}

func formatCounts(counts map[string]int) string {
	if len(counts) == 0 {
		return ""
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s:%d", key, counts[key]))
	}
	return strings.Join(parts, ", ")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
