package detector

import (
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func WriteArtifacts(outputDir string, src image.Image, doc Document, rawArtifacts []string) error {
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
	if err := os.WriteFile(filepath.Join(outputDir, "ui_detector_candidates.v1.json"), data, 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outputDir, "ui_detector_report.md"), []byte(MarkdownReport(doc, rawArtifacts)), 0o644); err != nil {
		return err
	}
	return WriteOverlay(filepath.Join(outputDir, "ui_detector_overlay.png"), src, doc.Candidates)
}

func MarkdownReport(doc Document, rawArtifacts []string) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# UI Detector Candidates\n\n")
	fmt.Fprintf(&b, "- version: `%s`\n", doc.Version)
	fmt.Fprintf(&b, "- image: `%s`\n", doc.Image.Path)
	fmt.Fprintf(&b, "- size: `%d x %d`\n", doc.Image.Width, doc.Image.Height)
	fmt.Fprintf(&b, "- provider: `%s`\n", doc.Provider.Name)
	fmt.Fprintf(&b, "- wireApi: `%s`\n", doc.Provider.WireAPI)
	fmt.Fprintf(&b, "- model: `%s`\n", doc.Provider.Model)
	if doc.Provider.BaseURLHost != "" {
		fmt.Fprintf(&b, "- baseUrlHost: `%s`\n", doc.Provider.BaseURLHost)
	}
	fmt.Fprintf(&b, "- candidates: `%d`\n", doc.Summary.Total)

	fmt.Fprintf(&b, "\n## Passes\n\n")
	fmt.Fprintf(&b, "| pass | kind | prompt | sourceBBox | sentSize | durationMs |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | --- | --- | ---: |\n")
	for _, pass := range doc.Preprocess.Passes {
		fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | `%.0f,%.0f,%.0f,%.0f` | `%d x %d` | %d |\n",
			pass.ID, pass.Kind, pass.PromptName, pass.SourceBBox.X, pass.SourceBBox.Y, pass.SourceBBox.Width, pass.SourceBBox.Height, pass.SentWidth, pass.SentHeight, pass.DurationMS)
	}

	writeCountTable(&b, "Role Counts", doc.Summary.RoleCounts)
	writeCountTable(&b, "Pass Counts", doc.Summary.PassCounts)

	fmt.Fprintf(&b, "\n## Candidates\n\n")
	fmt.Fprintf(&b, "| id | role | pass | conf | bbox | label | merge |\n")
	fmt.Fprintf(&b, "| --- | --- | --- | ---: | --- | --- | --- |\n")
	for _, item := range doc.Candidates {
		fmt.Fprintf(&b, "| `%s` | `%s` | `%s` | %.2f | `%.1f,%.1f,%.1f,%.1f` | `%s` | `%s` |\n",
			item.ID, item.Role, item.Source.PassID, item.Confidence,
			item.BBox.X, item.BBox.Y, item.BBox.Width, item.BBox.Height,
			escapeMarkdownCell(item.RawLabel), item.Merge.State)
	}

	if len(rawArtifacts) > 0 {
		fmt.Fprintf(&b, "\n## Raw Responses\n\n")
		for _, path := range rawArtifacts {
			fmt.Fprintf(&b, "- `%s`\n", path)
		}
	}
	return b.String()
}

func writeCountTable(b *strings.Builder, title string, values map[string]int) {
	if len(values) == 0 {
		return
	}
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.SliceStable(keys, func(i, j int) bool {
		if values[keys[i]] != values[keys[j]] {
			return values[keys[i]] > values[keys[j]]
		}
		return keys[i] < keys[j]
	})
	fmt.Fprintf(b, "\n## %s\n\n", title)
	fmt.Fprintf(b, "| key | count |\n")
	fmt.Fprintf(b, "| --- | ---: |\n")
	for _, key := range keys {
		fmt.Fprintf(b, "| `%s` | %d |\n", key, values[key])
	}
}

func WriteOverlay(path string, src image.Image, candidates []Candidate) error {
	bounds := src.Bounds()
	out := image.NewRGBA(image.Rect(0, 0, bounds.Dx(), bounds.Dy()))
	draw.Draw(out, out.Bounds(), src, bounds.Min, draw.Src)
	for _, candidate := range candidates {
		drawBBox(out, candidate.BBox, colorForRole(candidate.Role))
	}
	return imageio.WritePNG(path, out)
}

func drawBBox(img *image.RGBA, bbox BBox, c color.RGBA) {
	x1 := clampInt(int(bbox.X), 0, img.Bounds().Dx()-1)
	y1 := clampInt(int(bbox.Y), 0, img.Bounds().Dy()-1)
	x2 := clampInt(int(bbox.X+bbox.Width), x1, img.Bounds().Dx()-1)
	y2 := clampInt(int(bbox.Y+bbox.Height), y1, img.Bounds().Dy()-1)
	for x := x1; x <= x2; x++ {
		img.SetRGBA(x, y1, c)
		img.SetRGBA(x, y2, c)
	}
	for y := y1; y <= y2; y++ {
		img.SetRGBA(x1, y, c)
		img.SetRGBA(x2, y, c)
	}
}

func colorForRole(role Role) color.RGBA {
	switch role {
	case RoleImageView:
		return color.RGBA{R: 230, G: 60, B: 60, A: 255}
	case RoleTextView:
		return color.RGBA{R: 20, G: 110, B: 255, A: 255}
	case RoleBackground:
		return color.RGBA{R: 20, G: 190, B: 90, A: 255}
	case RoleBottomNavigation:
		return color.RGBA{R: 255, G: 160, B: 0, A: 255}
	case RoleStatusBar, RoleActionBar:
		return color.RGBA{R: 165, G: 65, B: 225, A: 255}
	case RoleButton, RoleEditText:
		return color.RGBA{R: 40, G: 210, B: 170, A: 255}
	default:
		return color.RGBA{R: 255, G: 255, B: 255, A: 255}
	}
}

func escapeMarkdownCell(value string) string {
	value = strings.ReplaceAll(value, "\n", " ")
	value = strings.ReplaceAll(value, "|", "\\|")
	return strings.TrimSpace(value)
}
