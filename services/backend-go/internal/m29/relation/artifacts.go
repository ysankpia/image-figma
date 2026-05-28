package relation

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func writeRelationArtifacts(outputDir string, sourcePath string, tokens []evidence.Token, relations []Relation, diagnostics Diagnostics) error {
	if err := writeRelationReport(filepath.Join(outputDir, "relation_report.md"), diagnostics, relations); err != nil {
		return err
	}
	if sourcePath == "" {
		return nil
	}
	img, err := imageio.ReadPNG(sourcePath)
	if err != nil {
		return err
	}
	overlayPath := filepath.Join(outputDir, "relation_overlay.png")
	if err := WriteRelationOverlay(overlayPath, img, tokens, relations); err != nil {
		return err
	}
	return writeRelationPreviewSheet(filepath.Join(outputDir, "relation_preview_sheet.png"), img, overlayPath)
}

func WriteRelationOverlay(path string, src image.Image, tokens []evidence.Token, relations []Relation) error {
	b := src.Bounds()
	out := image.NewRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
	draw.Draw(out, out.Bounds(), src, b.Min, draw.Src)
	tokenByID := map[string]evidence.Token{}
	for _, token := range tokens {
		if token.Disposition == "suppressed" {
			continue
		}
		tokenByID[token.ID] = token
	}
	for _, relation := range relations {
		if relation.Strength == "weak" {
			continue
		}
		from, okFrom := tokenByID[relation.FromID]
		to, okTo := tokenByID[relation.ToID]
		if !okFrom || !okTo {
			continue
		}
		if !drawnRelationType(relation.RelationType) {
			continue
		}
		drawBBox(out, from.BBox, colorForRelation(relation.RelationType))
		drawBBox(out, to.BBox, colorForRelation(relation.RelationType))
	}
	return imageio.WritePNG(path, out)
}

func drawnRelationType(relationType string) bool {
	switch relationType {
	case "inside_surface", "raster_parts_same_region":
		return true
	default:
		return false
	}
}

func drawBBox(img *image.RGBA, b bbox, c color.RGBA) {
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

func writeRelationPreviewSheet(path string, src image.Image, overlayPath string) error {
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

func writeRelationReport(path string, diagnostics Diagnostics, relations []Relation) error {
	var b strings.Builder
	fmt.Fprintf(&b, "# M29 Relation Graph Report\n\n")
	fmt.Fprintf(&b, "- tokens: %d eligible, %d total\n", diagnostics.EligibleTokenCount, diagnostics.TokenCount)
	fmt.Fprintf(&b, "- relations: %d total, %d weak\n", diagnostics.RelationCount, diagnostics.WeakRelationCount)
	fmt.Fprintf(&b, "- relationCategories: %s\n", formatCounts(diagnostics.RelationCategoryCounts))
	fmt.Fprintf(&b, "- relationTypes: %s\n\n", formatCounts(diagnostics.RelationTypeCounts))
	writeRelationReportSection(&b, "Structural Relations", relations, "structural", 80)
	writeRelationReportSection(&b, "Grouping Relations", relations, "grouping", 80)
	writeRelationReportSection(&b, "Layout Hints", relations, "layout_hint", 40)
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func writeRelationReportSection(b *strings.Builder, title string, relations []Relation, category string, limit int) {
	fmt.Fprintf(b, "## %s\n\n", title)
	fmt.Fprintf(b, "| relation | from | to | confidence | strength | reasons |\n")
	fmt.Fprintf(b, "| --- | --- | --- | ---: | --- | --- |\n")
	count := 0
	for _, relation := range relations {
		if relation.Category != category {
			continue
		}
		if count >= limit {
			break
		}
		fmt.Fprintf(b, "| `%s` | `%s` | `%s` | %.2f | %s | %s |\n", relation.RelationType, relation.FromID, relation.ToID, relation.Confidence, relation.Strength, strings.Join(relation.Reasons, ", "))
		count++
	}
	if count == 0 {
		fmt.Fprintf(b, "|  |  |  |  |  |  |\n")
	}
	fmt.Fprintf(b, "\n")
}

func colorForRelation(relationType string) color.RGBA {
	switch relationType {
	case "contains":
		return color.RGBA{R: 20, G: 210, B: 80, A: 255}
	case "inside_surface":
		return color.RGBA{R: 40, G: 210, B: 210, A: 255}
	case "foreground_inside_background":
		return color.RGBA{R: 180, G: 180, B: 180, A: 255}
	case "same_band":
		return color.RGBA{R: 255, G: 180, B: 0, A: 255}
	case "raster_parts_same_region":
		return color.RGBA{R: 255, G: 80, B: 40, A: 255}
	default:
		return color.RGBA{R: 255, G: 255, B: 255, A: 255}
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
