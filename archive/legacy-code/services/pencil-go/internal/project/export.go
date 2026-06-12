package project

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/pipeline"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/pencil"
)

type Options struct {
	Inputs       []string
	OutputDir    string
	ProjectName  string
	Mode         pencil.Mode
	Columns      string
	IncludeDebug bool
	OCRProvider  string
}

type Result struct {
	OutputDir string
	ZipPath   string
	Manifest  pencil.ProjectManifest
}

type pageResult struct {
	ID       string
	Name     string
	Source   string
	M29Dir   string
	Width    int
	Height   int
	X        int
	Y        int
	Evidence contract.Document
	ByMode   map[pencil.Mode]pencil.Result
}

func Export(options Options) (Result, error) {
	if len(options.Inputs) == 0 {
		return Result{}, fmt.Errorf("missing input")
	}
	if options.OutputDir == "" {
		return Result{}, fmt.Errorf("missing output dir")
	}
	if options.ProjectName == "" {
		options.ProjectName = "M29 Pencil Project"
	}
	modes := pencil.ExpandModes(options.Mode)
	if len(modes) == 0 {
		return Result{}, fmt.Errorf("unsupported mode %q", options.Mode)
	}
	inputs, err := expandInputs(options.Inputs)
	if err != nil {
		return Result{}, err
	}
	if len(inputs) == 0 {
		return Result{}, fmt.Errorf("no PNG inputs found")
	}
	if err := os.RemoveAll(options.OutputDir); err != nil {
		return Result{}, err
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return Result{}, err
	}

	config.LoadLocalEnvFromAncestors()
	pageResults := make([]pageResult, 0, len(inputs))
	for i, input := range inputs {
		pageID := fmt.Sprintf("page_%04d", i+1)
		pageName := fmt.Sprintf("%02d - %s", i+1, strings.TrimSuffix(filepath.Base(input), filepath.Ext(input)))
		m29Root := filepath.Join(options.OutputDir, "debug", "pages")
		if !options.IncludeDebug {
			m29Root = filepath.Join(options.OutputDir, ".work", "pages")
		}
		m29Dir := filepath.Join(m29Root, pageID)
		doc, err := pipeline.Run(pipeline.Options{
			InputPath:   input,
			OCRProvider: options.OCRProvider,
			OutputDir:   m29Dir,
		})
		if err != nil {
			return Result{}, fmt.Errorf("%s m29: %w", pageID, err)
		}
		pageResults = append(pageResults, pageResult{
			ID:       pageID,
			Name:     pageName,
			Source:   input,
			M29Dir:   m29Dir,
			Width:    doc.Image.Width,
			Height:   doc.Image.Height,
			Evidence: doc,
			ByMode:   map[pencil.Mode]pencil.Result{},
		})
		if options.IncludeDebug {
			_ = copyFile(input, filepath.Join(options.OutputDir, "debug", "pages", pageID, "source.png"))
		}
	}
	layoutPages(pageResults, options.Columns)

	for pi := range pageResults {
		page := &pageResults[pi]
		for _, mode := range modes {
			result, err := pencil.ExportMode(pencil.ExportOptions{
				InputDir:     page.M29Dir,
				OutputDir:    options.OutputDir,
				Name:         page.Name,
				Mode:         mode,
				IDPrefix:     page.ID,
				AssetPageDir: page.ID,
				X:            page.X,
				Y:            page.Y,
			}, page.Evidence, mode)
			if err != nil {
				return Result{}, fmt.Errorf("%s %s export: %w", page.ID, mode, err)
			}
			page.ByMode[mode] = result
		}
	}

	modeOutputs := map[pencil.Mode]pencil.ModeOutput{}
	for _, mode := range modes {
		policy, _ := pencil.PolicyForMode(mode)
		children := make([]pencil.Node, 0, len(pageResults))
		combined := pencil.Summary{}
		for _, page := range pageResults {
			result := page.ByMode[mode]
			children = append(children, result.Document.Children...)
			combined.TextNodes += result.Summary.TextNodes
			combined.CropNodes += result.Summary.CropNodes
			combined.TextKnockoutCropNodes += result.Summary.TextKnockoutCropNodes
			combined.ArtTextCropNodes += result.Summary.ArtTextCropNodes
			combined.CropTextNodes += result.Summary.CropTextNodes
			combined.SuppressedDuplicateCropNodes += result.Summary.SuppressedDuplicateCropNodes
			combined.SuppressedInternalCropNodes += result.Summary.SuppressedInternalCropNodes
			combined.AssetCount += result.Summary.AssetCount
		}
		doc := pencil.Document{Version: pencil.PenVersion, Children: children}
		modeDir := filepath.Join(options.OutputDir, policy.DirName)
		if err := pencil.WriteJSON(filepath.Join(modeDir, "design.pen"), doc); err != nil {
			return Result{}, err
		}
		modeManifest := map[string]any{
			"schema":      "m29.pencil.project_mode_manifest.v1",
			"projectName": options.ProjectName,
			"mode":        mode,
			"pageCount":   len(pageResults),
			"summary":     combined,
		}
		if err := pencil.WriteJSON(filepath.Join(modeDir, "manifest.json"), modeManifest); err != nil {
			return Result{}, err
		}
		modeOutputs[mode] = pencil.ModeOutput{
			Pen:      filepath.ToSlash(filepath.Join(policy.DirName, "design.pen")),
			Manifest: filepath.ToSlash(filepath.Join(policy.DirName, "manifest.json")),
			Summary:  combined,
		}
	}

	pages := make([]pencil.ProjectPage, 0, len(pageResults))
	for _, page := range pageResults {
		summaries := map[pencil.Mode]pencil.Summary{}
		for _, mode := range modes {
			summaries[mode] = page.ByMode[mode].Summary
		}
		pages = append(pages, pencil.ProjectPage{
			PageID:     page.ID,
			Name:       page.Name,
			SourcePath: page.Source,
			Width:      page.Width,
			Height:     page.Height,
			X:          page.X,
			Y:          page.Y,
			Summaries:  summaries,
		})
	}
	manifest := pencil.ProjectManifest{
		Schema:      "m29.pencil.project_manifest.v1",
		ProjectName: options.ProjectName,
		PageCount:   len(pageResults),
		Modes:       modes,
		Pages:       pages,
		ModeOutputs: modeOutputs,
	}
	if err := pencil.WriteJSON(filepath.Join(options.OutputDir, "manifest.json"), manifest); err != nil {
		return Result{}, err
	}
	if options.IncludeDebug {
		if err := writeDebugReport(options.OutputDir, manifest); err != nil {
			return Result{}, err
		}
	}
	zipPath := filepath.Join(options.OutputDir, "project.zip")
	if err := zipDirectory(options.OutputDir, zipPath); err != nil {
		return Result{}, err
	}
	return Result{OutputDir: options.OutputDir, ZipPath: zipPath, Manifest: manifest}, nil
}

func layoutPages(pages []pageResult, columnsOpt string) {
	columns := parseColumns(columnsOpt, pages)
	gap := 200
	colWidths := make([]int, columns)
	rowHeights := []int{}
	for i, page := range pages {
		col := i % columns
		row := i / columns
		for len(rowHeights) <= row {
			rowHeights = append(rowHeights, 0)
		}
		if page.Width > colWidths[col] {
			colWidths[col] = page.Width
		}
		if page.Height > rowHeights[row] {
			rowHeights[row] = page.Height
		}
	}
	xOffsets := make([]int, columns)
	for i := 1; i < columns; i++ {
		xOffsets[i] = xOffsets[i-1] + colWidths[i-1] + gap
	}
	yOffsets := make([]int, len(rowHeights))
	for i := 1; i < len(rowHeights); i++ {
		yOffsets[i] = yOffsets[i-1] + rowHeights[i-1] + gap
	}
	for i := range pages {
		col := i % columns
		row := i / columns
		pages[i].X = xOffsets[col]
		pages[i].Y = yOffsets[row]
	}
}

func parseColumns(raw string, pages []pageResult) int {
	raw = strings.TrimSpace(strings.ToLower(raw))
	if raw == "" || raw == "auto" {
		if len(pages) == 0 {
			return 1
		}
		webLike := pages[0].Width >= pages[0].Height || float64(pages[0].Width)/float64(maxInt(1, pages[0].Height)) >= 0.85
		if webLike {
			return 2
		}
		return 5
	}
	var value int
	_, _ = fmt.Sscanf(raw, "%d", &value)
	if value < 1 {
		return 1
	}
	if value > 12 {
		return 12
	}
	return value
}

func expandInputs(inputs []string) ([]string, error) {
	seen := map[string]bool{}
	var out []string
	for _, input := range inputs {
		path := filepath.Clean(input)
		info, err := os.Stat(path)
		if err != nil {
			return nil, err
		}
		if info.IsDir() {
			var files []string
			err := filepath.WalkDir(path, func(p string, d os.DirEntry, err error) error {
				if err != nil {
					return err
				}
				if d.IsDir() {
					return nil
				}
				if strings.EqualFold(filepath.Ext(p), ".png") {
					files = append(files, p)
				}
				return nil
			})
			if err != nil {
				return nil, err
			}
			sort.Strings(files)
			for _, file := range files {
				if !seen[file] {
					seen[file] = true
					out = append(out, file)
				}
			}
			continue
		}
		if strings.EqualFold(filepath.Ext(path), ".json") {
			items, err := readManifestInputs(path)
			if err != nil {
				return nil, err
			}
			for _, item := range items {
				if !seen[item] {
					seen[item] = true
					out = append(out, item)
				}
			}
			continue
		}
		if !strings.EqualFold(filepath.Ext(path), ".png") {
			return nil, fmt.Errorf("unsupported input %s", path)
		}
		if !seen[path] {
			seen[path] = true
			out = append(out, path)
		}
	}
	return out, nil
}

func readManifestInputs(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var payload struct {
		Pages []string `json:"pages"`
		Files []string `json:"files"`
		Cases []struct {
			SourcePath string `json:"sourcePath"`
		} `json:"cases"`
	}
	if err := json.Unmarshal(data, &payload); err != nil {
		return nil, err
	}
	var out []string
	base := filepath.Dir(path)
	for _, item := range append(payload.Pages, payload.Files...) {
		out = append(out, resolveRelative(base, item))
	}
	for _, item := range payload.Cases {
		out = append(out, resolveRelative(base, item.SourcePath))
	}
	return out, nil
}

func resolveRelative(base, path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(base, path)
}

func writeDebugReport(outDir string, manifest pencil.ProjectManifest) error {
	var b strings.Builder
	b.WriteString("# Pencil Project Export\n\n")
	b.WriteString(fmt.Sprintf("- project: %s\n", manifest.ProjectName))
	b.WriteString(fmt.Sprintf("- pages: %d\n", manifest.PageCount))
	b.WriteString(fmt.Sprintf("- modes: %v\n", manifest.Modes))
	for _, page := range manifest.Pages {
		b.WriteString(fmt.Sprintf("- %s %dx%d at %d,%d\n", page.PageID, page.Width, page.Height, page.X, page.Y))
	}
	path := filepath.Join(outDir, "debug", "report.md")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func zipDirectory(root, zipPath string) error {
	temp := zipPath + ".tmp"
	_ = os.Remove(temp)
	out, err := os.Create(temp)
	if err != nil {
		return err
	}
	zw := zip.NewWriter(out)
	err = filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if d.Name() == ".work" {
				return filepath.SkipDir
			}
			return nil
		}
		if path == temp || path == zipPath {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		w, err := zw.Create(filepath.ToSlash(rel))
		if err != nil {
			return err
		}
		f, err := os.Open(path)
		if err != nil {
			return err
		}
		defer f.Close()
		_, err = io.Copy(w, f)
		return err
	})
	closeErr := zw.Close()
	fileErr := out.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if fileErr != nil {
		return fileErr
	}
	return os.Rename(temp, zipPath)
}

func copyFile(src, dst string) error {
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
