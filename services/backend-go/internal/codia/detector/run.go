package detector

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"image"
	"os"
	"path/filepath"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func Run(ctx context.Context, options Options) (RunResult, error) {
	options = options.withDefaults()
	if err := options.validate(); err != nil {
		return RunResult{}, err
	}
	if err := os.MkdirAll(options.OutputDir, 0o755); err != nil {
		return RunResult{}, err
	}
	src, err := imageio.ReadPNG(options.InputPath)
	if err != nil {
		return RunResult{}, fmt.Errorf("read input PNG: %w", err)
	}
	passes, err := preparePasses(src, options.Passes, options.MaxSide)
	if err != nil {
		return RunResult{}, err
	}
	client := newProviderClient(options)
	rawDir := filepath.Join(options.OutputDir, "raw_model_response")
	if err := os.MkdirAll(rawDir, 0o755); err != nil {
		return RunResult{}, err
	}
	all := []Candidate{}
	rawArtifacts := []string{}
	passRuns := []PassRun{}
	for _, pass := range passes {
		passCtx, cancel := context.WithTimeout(ctx, options.Timeout)
		started := time.Now()
		response, err := client.detect(passCtx, pass)
		cancel()
		if err != nil {
			return RunResult{}, fmt.Errorf("pass %s: %w", pass.Spec.ID, err)
		}
		rawName := filepath.Join("raw_model_response", pass.Spec.ID+".json")
		if err := os.WriteFile(filepath.Join(options.OutputDir, rawName), []byte(response.RawText), 0o644); err != nil {
			return RunResult{}, err
		}
		rawArtifacts = append(rawArtifacts, filepath.ToSlash(rawName))
		candidates, err := parseCandidates(response.Text, pass, len(all))
		if err != nil {
			return RunResult{}, fmt.Errorf("pass %s: %w", pass.Spec.ID, err)
		}
		run := pass.Run
		run.DurationMS = time.Since(started).Milliseconds()
		passRuns = append(passRuns, run)
		all = append(all, candidates...)
	}
	all = dedupeCandidates(all)
	b := src.Bounds()
	doc := Document{
		Version: CandidatesVersion,
		Image: ImageMeta{
			Path:   options.InputPath,
			Width:  b.Dx(),
			Height: b.Dy(),
			SHA256: fileSHA256(options.InputPath),
		},
		Provider:   providerMeta(options),
		Preprocess: Preprocess{Passes: passRuns},
		Candidates: all,
		Summary:    summarize(all),
	}
	if err := WriteArtifacts(options.OutputDir, src, doc, rawArtifacts); err != nil {
		return RunResult{}, err
	}
	return RunResult{
		Document: doc,
		Artifacts: Artifacts{
			Candidates:   "ui_detector_candidates.v1.json",
			Report:       "ui_detector_report.md",
			Overlay:      "ui_detector_overlay.png",
			RawResponses: rawArtifacts,
		},
	}, nil
}

func summarize(candidates []Candidate) Summary {
	out := Summary{
		Total:      len(candidates),
		RoleCounts: map[string]int{},
		PassCounts: map[string]int{},
	}
	for _, candidate := range candidates {
		out.RoleCounts[string(candidate.Role)]++
		out.PassCounts[candidate.Source.PassID]++
	}
	return out
}

func fileSHA256(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func imageSize(img image.Image) (int, int) {
	b := img.Bounds()
	return b.Dx(), b.Dy()
}
