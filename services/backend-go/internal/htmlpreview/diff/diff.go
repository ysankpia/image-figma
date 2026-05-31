package diff

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const (
	ReportVersion            = "html_preview_diff.v1"
	NormalizedScreenshotFile = "preview_screenshot_normalized.png"
	DiffPNGFile              = "source_vs_html_diff.png"
	ReportFile               = "html_preview_diff_report.md"
)

type Options struct {
	SourcePath     string
	ScreenshotPath string
	PreviewHTML    string
	OutputDir      string
}

type Result struct {
	NormalizedScreenshot string
	DiffPNG              string
	Report               string
	Metrics              Metrics
}

type Metrics struct {
	SourceWidth          int
	SourceHeight         int
	ScreenshotWidth      int
	ScreenshotHeight     int
	NormalizedWidth      int
	NormalizedHeight     int
	Scale                float64
	MeanChannelDiff      float64
	MaxChannelDiff       int
	WhiteHolePixels      int
	WhiteHoleRatio       float64
	LargeWhiteHole       bool
	ReferencedAssetCount int
	MissingAssetCount    int
}

func Run(options Options) (Result, error) {
	if options.SourcePath == "" {
		return Result{}, fmt.Errorf("source path is required")
	}
	if options.ScreenshotPath == "" {
		return Result{}, fmt.Errorf("screenshot path is required")
	}
	if options.OutputDir == "" {
		return Result{}, fmt.Errorf("output dir is required")
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Result{}, err
	}
	source, err := readPNG(options.SourcePath)
	if err != nil {
		return Result{}, fmt.Errorf("read source png: %w", err)
	}
	screenshot, err := readPNG(options.ScreenshotPath)
	if err != nil {
		return Result{}, fmt.Errorf("read screenshot png: %w", err)
	}
	normalizedPath := filepath.Join(options.OutputDir, NormalizedScreenshotFile)
	diffPath := filepath.Join(options.OutputDir, DiffPNGFile)
	metrics, err := compare(source, screenshot, normalizedPath, diffPath)
	if err != nil {
		return Result{}, err
	}
	if options.PreviewHTML != "" {
		metrics.ReferencedAssetCount = countReferencedAssets(options.PreviewHTML)
		metrics.MissingAssetCount = countMissingAssets(options.PreviewHTML)
	}
	reportPath := filepath.Join(options.OutputDir, ReportFile)
	if err := os.WriteFile(reportPath, []byte(markdownReport(options, metrics)), 0o644); err != nil {
		return Result{}, err
	}
	return Result{NormalizedScreenshot: normalizedPath, DiffPNG: diffPath, Report: reportPath, Metrics: metrics}, nil
}

func compare(source image.Image, screenshot image.Image, normalizedPath string, diffPath string) (Metrics, error) {
	metrics := Metrics{
		SourceWidth:      source.Bounds().Dx(),
		SourceHeight:     source.Bounds().Dy(),
		ScreenshotWidth:  screenshot.Bounds().Dx(),
		ScreenshotHeight: screenshot.Bounds().Dy(),
	}
	normalized := normalizeScreenshot(screenshot, metrics.SourceWidth, metrics.SourceHeight)
	metrics.NormalizedWidth = normalized.Bounds().Dx()
	metrics.NormalizedHeight = normalized.Bounds().Dy()
	if metrics.SourceHeight > 0 {
		metrics.Scale = float64(metrics.ScreenshotHeight) / float64(metrics.SourceHeight)
	}
	if err := writePNG(normalizedPath, normalized); err != nil {
		return Metrics{}, err
	}
	diff := image.NewRGBA(image.Rect(0, 0, metrics.SourceWidth, metrics.SourceHeight))
	draw.Draw(diff, diff.Bounds(), &image.Uniform{C: color.White}, image.Point{}, draw.Src)
	commonWidth := min(metrics.SourceWidth, metrics.NormalizedWidth)
	commonHeight := min(metrics.SourceHeight, metrics.NormalizedHeight)
	totalDiff := 0
	totalChannels := max(1, commonWidth*commonHeight*3)
	maxDiff := 0
	whiteHolePixels := 0
	for y := 0; y < commonHeight; y++ {
		for x := 0; x < commonWidth; x++ {
			sr, sg, sb := rgb8(source.At(source.Bounds().Min.X+x, source.Bounds().Min.Y+y))
			pr, pg, pb := rgb8(normalized.At(normalized.Bounds().Min.X+x, normalized.Bounds().Min.Y+y))
			dr := absInt(sr - pr)
			dg := absInt(sg - pg)
			db := absInt(sb - pb)
			totalDiff += dr + dg + db
			maxDiff = max(maxDiff, dr, dg, db)
			if previewWhite(pr, pg, pb) && !sourceNearWhite(sr, sg, sb) {
				whiteHolePixels++
			}
			intensity := uint8(min(255, (dr+dg+db)*2/3))
			diff.Set(x, y, color.RGBA{R: intensity, A: 255})
		}
	}
	markDimensionMismatch(diff, commonWidth, commonHeight)
	metrics.MeanChannelDiff = float64(totalDiff) / float64(totalChannels)
	metrics.MaxChannelDiff = maxDiff
	metrics.WhiteHolePixels = whiteHolePixels
	metrics.WhiteHoleRatio = float64(whiteHolePixels) / float64(max(1, metrics.SourceWidth*metrics.SourceHeight))
	metrics.LargeWhiteHole = metrics.WhiteHoleRatio >= 0.05
	if err := writePNG(diffPath, diff); err != nil {
		return Metrics{}, err
	}
	return metrics, nil
}

func markdownReport(options Options, metrics Metrics) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# HTML Preview Diff Report\n\n")
	fmt.Fprintf(&b, "- version: `%s`\n", ReportVersion)
	fmt.Fprintf(&b, "- source: `%s`\n", options.SourcePath)
	fmt.Fprintf(&b, "- screenshot: `%s`\n", options.ScreenshotPath)
	if options.PreviewHTML != "" {
		fmt.Fprintf(&b, "- preview html: `%s`\n", options.PreviewHTML)
	}
	fmt.Fprintf(&b, "- source size: `%dx%d`\n", metrics.SourceWidth, metrics.SourceHeight)
	fmt.Fprintf(&b, "- screenshot size: `%dx%d`\n", metrics.ScreenshotWidth, metrics.ScreenshotHeight)
	fmt.Fprintf(&b, "- normalized screenshot size: `%dx%d`\n", metrics.NormalizedWidth, metrics.NormalizedHeight)
	fmt.Fprintf(&b, "- inferred screenshot scale: `%.2f`\n", metrics.Scale)
	fmt.Fprintf(&b, "- mean channel diff: `%.2f`\n", metrics.MeanChannelDiff)
	fmt.Fprintf(&b, "- max channel diff: `%d`\n", metrics.MaxChannelDiff)
	fmt.Fprintf(&b, "- white hole pixels: `%d`\n", metrics.WhiteHolePixels)
	fmt.Fprintf(&b, "- white hole ratio: `%.4f`\n", metrics.WhiteHoleRatio)
	fmt.Fprintf(&b, "- large white hole: `%t`\n", metrics.LargeWhiteHole)
	fmt.Fprintf(&b, "- referenced assets: `%d`\n", metrics.ReferencedAssetCount)
	fmt.Fprintf(&b, "- missing assets: `%d`\n", metrics.MissingAssetCount)
	fmt.Fprintf(&b, "\n## Artifacts\n\n")
	fmt.Fprintf(&b, "- `%s`\n", NormalizedScreenshotFile)
	fmt.Fprintf(&b, "- `%s`\n", DiffPNGFile)
	return b.String()
}

func normalizeScreenshot(screenshot image.Image, targetWidth int, targetHeight int) image.Image {
	if targetWidth <= 0 || targetHeight <= 0 {
		return screenshot
	}
	bounds := screenshot.Bounds()
	scale := 1.0
	if bounds.Dy() > 0 {
		scale = float64(bounds.Dy()) / float64(targetHeight)
	}
	if scale <= 0 {
		scale = 1
	}
	cropWidth := min(bounds.Dx(), max(1, int(float64(targetWidth)*scale+0.5)))
	cropHeight := min(bounds.Dy(), max(1, int(float64(targetHeight)*scale+0.5)))
	out := image.NewRGBA(image.Rect(0, 0, targetWidth, targetHeight))
	for y := 0; y < targetHeight; y++ {
		for x := 0; x < targetWidth; x++ {
			sx := bounds.Min.X + min(cropWidth-1, int(float64(x)*float64(cropWidth)/float64(targetWidth)))
			sy := bounds.Min.Y + min(cropHeight-1, int(float64(y)*float64(cropHeight)/float64(targetHeight)))
			out.Set(x, y, screenshot.At(sx, sy))
		}
	}
	return out
}

func readPNG(path string) (image.Image, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	return png.Decode(file)
}

func writePNG(path string, img image.Image) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, img)
}

func rgb8(c color.Color) (int, int, int) {
	r, g, b, _ := c.RGBA()
	return int(r >> 8), int(g >> 8), int(b >> 8)
}

func previewWhite(r int, g int, b int) bool {
	return r >= 248 && g >= 248 && b >= 248
}

func sourceNearWhite(r int, g int, b int) bool {
	return r >= 235 && g >= 235 && b >= 235
}

func markDimensionMismatch(img *image.RGBA, commonWidth int, commonHeight int) {
	for y := commonHeight; y < img.Bounds().Dy(); y++ {
		for x := 0; x < img.Bounds().Dx(); x++ {
			img.Set(x, y, color.RGBA{R: 255, B: 255, A: 255})
		}
	}
	for y := 0; y < commonHeight; y++ {
		for x := commonWidth; x < img.Bounds().Dx(); x++ {
			img.Set(x, y, color.RGBA{R: 255, B: 255, A: 255})
		}
	}
}

func countReferencedAssets(previewPath string) int {
	return len(assetRefs(previewPath))
}

func countMissingAssets(previewPath string) int {
	refs := assetRefs(previewPath)
	base := filepath.Dir(previewPath)
	missing := 0
	for _, ref := range refs {
		if strings.HasPrefix(ref, "http://") || strings.HasPrefix(ref, "https://") || strings.HasPrefix(ref, "data:") || filepath.IsAbs(ref) {
			continue
		}
		if _, err := os.Stat(filepath.Join(base, filepath.FromSlash(ref))); err != nil {
			missing++
		}
	}
	return missing
}

func assetRefs(previewPath string) []string {
	data, err := os.ReadFile(previewPath)
	if err != nil {
		return nil
	}
	matches := regexp.MustCompile(`\bsrc="([^"]+)"`).FindAllStringSubmatch(string(data), -1)
	out := make([]string, 0, len(matches))
	for _, match := range matches {
		if len(match) == 2 {
			out = append(out, match[1])
		}
	}
	return out
}

func absInt(value int) int {
	if value < 0 {
		return -value
	}
	return value
}
