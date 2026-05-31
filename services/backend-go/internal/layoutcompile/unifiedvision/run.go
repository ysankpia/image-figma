package unifiedvision

import (
	"context"
	"fmt"
	"image"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/imageio"
)

func Run(ctx context.Context, doc contract.Document, options Options) (Output, error) {
	options = options.withDefaults()
	input := BuildInput(doc, options)
	output := Output{
		Input: input,
		Result: Result{
			Version:     ResultVersion,
			GeneratedAt: timestamp(),
		},
		Experiment: doc,
	}
	if len(input.Batches) == 0 {
		output.Validation = Validate(input, output.Result, options)
		return output, nil
	}
	rawDir := filepath.Join(options.OutputDir, "unified_vision", "raw_model_response")
	if err := os.MkdirAll(rawDir, 0o755); err != nil {
		return output, err
	}
	src, err := imageio.ReadPNG(doc.SourceImage.Path)
	if err != nil {
		output.Result.Batches = fallbackBatchResults(input.Batches, "read_source_image:"+err.Error())
		output.Validation = Validate(input, output.Result, options)
		output.Experiment = Apply(doc, output.Validation)
		return output, nil
	}
	if err := options.validateProvider(); err != nil {
		output.Result.Batches = fallbackBatchResults(input.Batches, err.Error())
		output.Validation = Validate(input, output.Result, options)
		output.Experiment = Apply(doc, output.Validation)
		output.Warnings = append(output.Warnings, err.Error())
		return output, nil
	}
	client := newProviderClient(options)
	results := runBatches(ctx, client, src, input, options, rawDir)
	output.Result.Batches = results
	sort.SliceStable(output.Result.Batches, func(i, j int) bool {
		return output.Result.Batches[i].BatchID < output.Result.Batches[j].BatchID
	})
	for _, result := range output.Result.Batches {
		if result.RawArtifact != "" {
			output.Artifacts.RawResponses = append(output.Artifacts.RawResponses, result.RawArtifact)
		}
		if result.ErrorArtifact != "" {
			output.Artifacts.ErrorArtifacts = append(output.Artifacts.ErrorArtifacts, result.ErrorArtifact)
		}
	}
	output.Validation = Validate(input, output.Result, options)
	output.Experiment = Apply(doc, output.Validation)
	return output, nil
}

func runBatches(ctx context.Context, client providerClient, src image.Image, input Input, options Options, rawDir string) []BatchResult {
	results := make([]BatchResult, len(input.Batches))
	sem := make(chan struct{}, options.Concurrency)
	var wg sync.WaitGroup
	for i, batch := range input.Batches {
		i := i
		batch := batch
		wg.Add(1)
		go func() {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[i] = runOneBatch(ctx, client, src, input, batch, options, rawDir)
		}()
	}
	wg.Wait()
	return results
}

func runOneBatch(ctx context.Context, client providerClient, src image.Image, input Input, batch BatchInput, options Options, rawDir string) BatchResult {
	attempts := 1 + maxInt(0, options.RepairAttempts)
	var previous *BatchValidation
	var last BatchResult
	for attempt := 1; attempt <= attempts; attempt++ {
		result := callOneBatch(ctx, client, src, batch, options, rawDir, attempt, previous)
		last = result
		if result.Error != "" {
			if attempt < attempts && semanticRetryable(result.Error) {
				previous = &BatchValidation{BatchID: batch.ID, SectionID: batch.SectionID, RejectedCount: 1, Reason: result.Error}
				continue
			}
			return result
		}
		validation := Validate(Input{
			Version:     input.Version,
			SourceImage: input.SourceImage,
			Batches:     []BatchInput{batch},
		}, Result{
			Version: ResultVersion,
			Batches: []BatchResult{result},
		}, options)
		if len(validation.RejectedGroups) == 0 {
			return result
		}
		if attempt < attempts {
			batchValidation := validation.Batches[0]
			batchValidation.Reason = batchRejectSummary(validation.RejectedGroups, batch.ID)
			previous = &batchValidation
			continue
		}
	}
	return last
}

func callOneBatch(ctx context.Context, client providerClient, src image.Image, batch BatchInput, options Options, rawDir string, attempt int, repair *BatchValidation) BatchResult {
	started := time.Now()
	result := BatchResult{
		BatchID:       batch.ID,
		SectionID:     batch.SectionID,
		Attempt:       attempt,
		RepairAttempt: repair != nil,
	}
	callCtx, cancel := context.WithTimeout(ctx, options.Timeout)
	defer cancel()
	response, err := client.call(callCtx, buildPrompt(batch, repair), cropImage(src, batch.CropBBox))
	result.DurationMillis = time.Since(started).Milliseconds()
	if err != nil {
		result.Error = err.Error()
		result.ErrorArtifact = writeBatchError(rawDir, batch.ID, attempt, err)
		return result
	}
	result.RawArtifact = writeBatchRaw(rawDir, batch.ID, attempt, response.RawText)
	parsed, err := parseModelResult(response.Text)
	if err != nil {
		result.Error = err.Error()
		result.ErrorArtifact = writeBatchError(rawDir, batch.ID, attempt, err)
		return result
	}
	result.Result = parsed
	return result
}

func semanticRetryable(reason string) bool {
	reason = strings.ToLower(reason)
	return strings.Contains(reason, "parse") || strings.Contains(reason, "json") || strings.Contains(reason, "schema")
}

func fallbackBatchResults(batches []BatchInput, reason string) []BatchResult {
	out := make([]BatchResult, 0, len(batches))
	for _, batch := range batches {
		out = append(out, BatchResult{
			BatchID:   batch.ID,
			SectionID: batch.SectionID,
			Attempt:   0,
			Error:     reason,
		})
	}
	return out
}

func writeBatchRaw(rawDir string, batchID string, attempt int, raw string) string {
	name := fmt.Sprintf("%s_attempt%d.json", batchID, attempt)
	path := filepath.Join(rawDir, name)
	if err := os.WriteFile(path, []byte(raw), 0o644); err != nil {
		return ""
	}
	return filepath.ToSlash(filepath.Join("unified_vision", "raw_model_response", name))
}

func writeBatchError(rawDir string, batchID string, attempt int, err error) string {
	name := fmt.Sprintf("%s_attempt%d.error.txt", batchID, attempt)
	path := filepath.Join(rawDir, name)
	if writeErr := os.WriteFile(path, []byte(err.Error()), 0o644); writeErr != nil {
		return ""
	}
	return filepath.ToSlash(filepath.Join("unified_vision", "raw_model_response", name))
}
