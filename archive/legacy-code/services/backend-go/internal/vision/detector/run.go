package detector

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"image"
	"os"
	"path/filepath"
	"sort"
	"sync"
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
	results := runPasses(ctx, client, passes, options)
	all := []Candidate{}
	rawArtifacts := []string{}
	passRuns := make([]PassRun, 0, len(results))
	for _, result := range results {
		run := result.Run
		passRuns = append(passRuns, run)
		if result.RawArtifact != "" {
			rawArtifacts = append(rawArtifacts, result.RawArtifact)
		}
		if result.Err != nil {
			if result.ErrorArtifact != "" {
				rawArtifacts = append(rawArtifacts, result.ErrorArtifact)
			}
			continue
		}
		all = append(all, result.Candidates...)
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

type passResult struct {
	Index         int
	Run           PassRun
	Candidates    []Candidate
	RawArtifact   string
	ErrorArtifact string
	Err           error
}

func runPasses(ctx context.Context, client providerClient, passes []preparedPass, options Options) []passResult {
	results := make([]passResult, len(passes))
	sem := make(chan struct{}, options.Concurrency)
	var wg sync.WaitGroup
	for i, pass := range passes {
		i := i
		pass := pass
		wg.Add(1)
		go func() {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[i] = runOnePass(ctx, client, pass, options, i)
		}()
	}
	wg.Wait()
	sort.SliceStable(results, func(i, j int) bool {
		return results[i].Index < results[j].Index
	})
	return results
}

func runOnePass(ctx context.Context, client providerClient, pass preparedPass, options Options, index int) passResult {
	passCtx, cancel := context.WithTimeout(ctx, options.Timeout)
	defer cancel()
	started := time.Now()
	result := passResult{Index: index, Run: pass.Run}
	response, err := client.detect(passCtx, pass)
	result.Run.DurationMS = time.Since(started).Milliseconds()
	if err != nil {
		result.Err = err
		result.Run.Error = err.Error()
		result.ErrorArtifact = writePassError(options.OutputDir, pass.Spec.ID, err)
		return result
	}
	rawName := filepath.Join("raw_model_response", pass.Spec.ID+".json")
	if err := os.WriteFile(filepath.Join(options.OutputDir, rawName), []byte(response.RawText), 0o644); err != nil {
		result.Err = err
		result.Run.Error = err.Error()
		return result
	}
	result.RawArtifact = filepath.ToSlash(rawName)
	candidates, err := parseCandidates(response.Text, pass, 0)
	if err != nil {
		result.Err = err
		result.Run.Error = err.Error()
		result.ErrorArtifact = writePassError(options.OutputDir, pass.Spec.ID, err)
		return result
	}
	result.Candidates = candidates
	return result
}

func writePassError(outputDir, passID string, err error) string {
	name := filepath.Join("raw_model_response", passID+".error.txt")
	path := filepath.Join(outputDir, name)
	if writeErr := os.WriteFile(path, []byte(err.Error()), 0o644); writeErr != nil {
		return ""
	}
	return filepath.ToSlash(name)
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
