package ocr

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"mime/multipart"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/config"
	"github.com/luqing-studio/image-figma/services/pencil-go/internal/m29/contract"
)

const BaiduProvider = "baidu_ppocrv5"

var transientStatusCodes = map[int]bool{
	http.StatusRequestTimeout:      true,
	http.StatusTooEarly:            true,
	http.StatusTooManyRequests:     true,
	http.StatusInternalServerError: true,
	http.StatusBadGateway:          true,
	http.StatusServiceUnavailable:  true,
	http.StatusGatewayTimeout:      true,
}

func ExtractBaiduPPOCRV5(ctx context.Context, sourcePath string, image ImageInfo, cfg config.OCRConfig) (Document, error) {
	if err := cfg.ValidateForProvider(); err != nil {
		return Document{}, err
	}
	start := time.Now()
	jobID, submitSeconds, err := submitJob(ctx, sourcePath, cfg.Baidu)
	if err != nil {
		return Document{}, err
	}
	resultURL, pollSeconds, pollCount, err := pollJob(ctx, jobID, cfg.Baidu)
	if err != nil {
		return Document{}, err
	}
	rows, err := downloadJSONL(ctx, resultURL, cfg.Baidu)
	if err != nil {
		return Document{}, err
	}
	blocks, warnings := ParsePPOCRV5Rows(rows, cfg.MinConfidence)
	blocks, normalizeWarnings := normalizeBlocks(blocks, image)
	warnings = append(warnings, normalizeWarnings...)
	doc := Document{
		Image:    image,
		Provider: BaiduProvider,
		Model:    cfg.Baidu.Model,
		Status:   "completed",
		Blocks:   blocks,
		Warnings: warnings,
		Meta: map[string]any{
			"remoteJobId":                jobID,
			"submitSeconds":              round3(submitSeconds),
			"pollSeconds":                round3(pollSeconds),
			"pollCount":                  pollCount,
			"totalSeconds":               round3(time.Since(start).Seconds()),
			"filteredLowConfidenceCount": countWarnings(warnings, "OCR_LOW_CONFIDENCE"),
		},
	}
	return doc, nil
}

func submitJob(ctx context.Context, sourcePath string, cfg config.BaiduPaddleOCRConfig) (string, float64, error) {
	fileBytes, err := os.ReadFile(sourcePath)
	if err != nil {
		return "", 0, err
	}
	payload := map[string]any{
		"useDocOrientationClassify": false,
		"useDocUnwarping":           false,
		"useTextlineOrientation":    false,
	}
	payloadData, err := json.Marshal(payload)
	if err != nil {
		return "", 0, err
	}
	start := time.Now()
	response, err := requestWithTransientRetry(ctx, http.MethodPost, cfg.JobURL, cfg, func() (*http.Request, error) {
		var body bytes.Buffer
		writer := multipart.NewWriter(&body)
		if err := writer.WriteField("model", cfg.Model); err != nil {
			return nil, err
		}
		if err := writer.WriteField("optionalPayload", string(payloadData)); err != nil {
			return nil, err
		}
		part, err := writer.CreateFormFile("file", sourcePath)
		if err != nil {
			return nil, err
		}
		if _, err := part.Write(fileBytes); err != nil {
			return nil, err
		}
		if err := writer.Close(); err != nil {
			return nil, err
		}
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, cfg.JobURL, &body)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "bearer "+cfg.Token)
		req.Header.Set("Content-Type", writer.FormDataContentType())
		return req, nil
	})
	if err != nil {
		return "", 0, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return "", 0, fmt.Errorf("Baidu PP-OCRv5 submit failed with status %d", response.StatusCode)
	}
	var body map[string]any
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		return "", 0, err
	}
	data, _ := body["data"].(map[string]any)
	jobID, _ := data["jobId"].(string)
	if jobID == "" {
		return "", 0, fmt.Errorf("Baidu PP-OCRv5 submit response does not contain data.jobId")
	}
	return jobID, time.Since(start).Seconds(), nil
}

func pollJob(ctx context.Context, jobID string, cfg config.BaiduPaddleOCRConfig) (string, float64, int, error) {
	start := time.Now()
	pollCount := 0
	for {
		pollCount++
		url := cfg.JobURL + "/" + jobID
		response, err := requestWithTransientRetry(ctx, http.MethodGet, url, cfg, func() (*http.Request, error) {
			req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
			if err != nil {
				return nil, err
			}
			req.Header.Set("Authorization", "bearer "+cfg.Token)
			return req, nil
		})
		if err != nil {
			return "", 0, pollCount, err
		}
		if response.StatusCode != http.StatusOK {
			response.Body.Close()
			return "", 0, pollCount, fmt.Errorf("Baidu PP-OCRv5 poll failed with status %d", response.StatusCode)
		}
		var body map[string]any
		if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
			response.Body.Close()
			return "", 0, pollCount, err
		}
		response.Body.Close()
		data, _ := body["data"].(map[string]any)
		state, _ := data["state"].(string)
		switch state {
		case "done":
			resultURL, ok := resultJSONURL(data)
			if !ok {
				return "", 0, pollCount, fmt.Errorf("Baidu PP-OCRv5 response does not contain resultUrl.jsonUrl")
			}
			return resultURL, time.Since(start).Seconds(), pollCount, nil
		case "failed":
			msg, _ := data["errorMsg"].(string)
			if msg == "" {
				msg = "unknown error"
			}
			return "", 0, pollCount, fmt.Errorf("Baidu PP-OCRv5 job failed: %s", msg)
		}
		if cfg.Timeout > 0 && time.Since(start) >= cfg.Timeout {
			return "", 0, pollCount, fmt.Errorf("Baidu PP-OCRv5 job timed out")
		}
		if cfg.PollInterval > 0 {
			select {
			case <-ctx.Done():
				return "", 0, pollCount, ctx.Err()
			case <-time.After(cfg.PollInterval):
			}
		}
	}
}

func downloadJSONL(ctx context.Context, url string, cfg config.BaiduPaddleOCRConfig) ([]map[string]any, error) {
	response, err := requestWithTransientRetry(ctx, http.MethodGet, url, cfg, func() (*http.Request, error) {
		return http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	})
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Baidu PP-OCRv5 JSONL download failed with status %d", response.StatusCode)
	}
	var rows []map[string]any
	scanner := bufio.NewScanner(response.Body)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var row map[string]any
		if err := json.Unmarshal([]byte(line), &row); err != nil {
			return nil, err
		}
		rows = append(rows, row)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, fmt.Errorf("Baidu PP-OCRv5 JSONL response is empty")
	}
	return rows, nil
}

func requestWithTransientRetry(ctx context.Context, method, url string, cfg config.BaiduPaddleOCRConfig, build func() (*http.Request, error)) (*http.Response, error) {
	client := &http.Client{Timeout: cfg.Timeout}
	var lastErr error
	for attempt := 1; attempt <= 3; attempt++ {
		req, err := build()
		if err != nil {
			return nil, err
		}
		response, err := client.Do(req)
		if err != nil {
			lastErr = err
			if attempt == 3 {
				return nil, err
			}
			sleepRetry(ctx, attempt, cfg)
			continue
		}
		if transientStatusCodes[response.StatusCode] && attempt < 3 {
			io.Copy(io.Discard, response.Body)
			response.Body.Close()
			sleepRetry(ctx, attempt, cfg)
			continue
		}
		return response, nil
	}
	return nil, lastErr
}

func sleepRetry(ctx context.Context, attempt int, cfg config.BaiduPaddleOCRConfig) {
	delay := time.Duration(500*(1<<(attempt-1))) * time.Millisecond
	if cfg.PollInterval > 0 && delay > cfg.PollInterval {
		delay = cfg.PollInterval
	}
	select {
	case <-ctx.Done():
	case <-time.After(delay):
	}
}

func resultJSONURL(data map[string]any) (string, bool) {
	resultURL, _ := data["resultUrl"].(map[string]any)
	jsonURL, _ := resultURL["jsonUrl"].(string)
	return jsonURL, jsonURL != ""
}

func ParsePPOCRV5Rows(rows []map[string]any, minConfidence float64) ([]Block, []Warning) {
	var blocks []Block
	var warnings []Warning
	nextIndex := 1
	for _, row := range rows {
		result, ok := row["result"].(map[string]any)
		if !ok {
			warnings = append(warnings, Warning{Code: "BAIDU_OCR_RESULT_MISSING", Message: "JSONL row does not contain result."})
			continue
		}
		ocrResults, ok := result["ocrResults"].([]any)
		if !ok {
			warnings = append(warnings, Warning{Code: "BAIDU_OCR_RESULTS_MISSING", Message: "result.ocrResults is missing or invalid."})
			continue
		}
		for _, item := range ocrResults {
			ocrResult, ok := item.(map[string]any)
			if !ok {
				continue
			}
			parsedBlocks, parsedWarnings, count := parseOCRResult(ocrResult, nextIndex, minConfidence)
			nextIndex += count
			blocks = append(blocks, parsedBlocks...)
			warnings = append(warnings, parsedWarnings...)
		}
	}
	return blocks, warnings
}

func parseOCRResult(ocrResult map[string]any, startIndex int, minConfidence float64) ([]Block, []Warning, int) {
	pruned, ok := ocrResult["prunedResult"].(map[string]any)
	if !ok {
		return nil, []Warning{{Code: "BAIDU_PRUNED_RESULT_MISSING", Message: "ocrResults item has no prunedResult."}}, 0
	}
	texts, ok := pruned["rec_texts"].([]any)
	if !ok {
		return nil, []Warning{{Code: "BAIDU_REC_TEXTS_MISSING", Message: "prunedResult.rec_texts is missing."}}, 0
	}
	scores, _ := pruned["rec_scores"].([]any)
	boxes, _ := pruned["rec_boxes"].([]any)
	polys, _ := pruned["rec_polys"].([]any)
	var blocks []Block
	var warnings []Warning
	for index, rawText := range texts {
		blockNumber := startIndex + index
		blockID := fmt.Sprintf("ocr_text_%03d", blockNumber)
		text := strings.TrimSpace(fmt.Sprint(rawText))
		if text == "" {
			warnings = append(warnings, Warning{Code: "OCR_TEXT_EMPTY", Message: "Empty OCR text was dropped.", BlockID: blockID})
			continue
		}
		confidence := parseScore(valueAt(scores, index))
		if confidence < minConfidence {
			warnings = append(warnings, Warning{Code: "OCR_LOW_CONFIDENCE", Message: fmt.Sprintf("OCR text was dropped because confidence %.3f is below threshold.", confidence), BlockID: blockID})
			continue
		}
		bbox, ok := RecBoxToBBox(valueAt(boxes, index))
		polyRaw := valueAt(polys, index)
		if !ok && polyRaw != nil {
			bbox, ok = PolygonToBBox(polyRaw)
		}
		if !ok {
			warnings = append(warnings, Warning{Code: "INVALID_OCR_BBOX", Message: "OCR bbox is missing.", BlockID: blockID})
			continue
		}
		blocks = append(blocks, Block{
			ID:         blockID,
			Text:       text,
			BBox:       bbox,
			Confidence: confidence,
			Source:     BaiduProvider,
		})
	}
	return blocks, warnings, len(texts)
}

func RecBoxToBBox(value any) (contract.BBox, bool) {
	items, ok := value.([]any)
	if !ok || len(items) != 4 {
		return contract.BBox{}, false
	}
	x1, ok1 := toFloat(items[0])
	y1, ok2 := toFloat(items[1])
	x2, ok3 := toFloat(items[2])
	y2, ok4 := toFloat(items[3])
	if !ok1 || !ok2 || !ok3 || !ok4 {
		return contract.BBox{}, false
	}
	width := x2 - x1
	height := y2 - y1
	if width <= 1 || height <= 1 {
		return contract.BBox{}, false
	}
	return contract.BBox{X: int(math.Round(x1)), Y: int(math.Round(y1)), Width: int(math.Round(width)), Height: int(math.Round(height))}, true
}

func PolygonToBBox(value any) (contract.BBox, bool) {
	items, ok := value.([]any)
	if !ok || len(items) == 0 {
		return contract.BBox{}, false
	}
	minX, minY := math.Inf(1), math.Inf(1)
	maxX, maxY := math.Inf(-1), math.Inf(-1)
	for _, item := range items {
		point, ok := item.([]any)
		if !ok || len(point) < 2 {
			return contract.BBox{}, false
		}
		x, ok1 := toFloat(point[0])
		y, ok2 := toFloat(point[1])
		if !ok1 || !ok2 {
			return contract.BBox{}, false
		}
		minX = math.Min(minX, x)
		minY = math.Min(minY, y)
		maxX = math.Max(maxX, x)
		maxY = math.Max(maxY, y)
	}
	width := maxX - minX
	height := maxY - minY
	if width <= 1 || height <= 1 {
		return contract.BBox{}, false
	}
	return contract.BBox{X: int(math.Round(minX)), Y: int(math.Round(minY)), Width: int(math.Round(width)), Height: int(math.Round(height))}, true
}

func normalizeBlocks(blocks []Block, image ImageInfo) ([]Block, []Warning) {
	out := make([]Block, 0, len(blocks))
	var warnings []Warning
	seen := map[string]bool{}
	for _, block := range blocks {
		if seen[block.ID] {
			warnings = append(warnings, Warning{Code: "DUPLICATE_OCR_BLOCK_ID", Message: "Duplicate OCR block id dropped.", BlockID: block.ID})
			continue
		}
		seen[block.ID] = true
		bbox, ok := clampBBox(block.BBox, image)
		if !ok {
			warnings = append(warnings, Warning{Code: "INVALID_OCR_BBOX", Message: "OCR bbox is outside image.", BlockID: block.ID})
			continue
		}
		block.BBox = bbox
		if block.Confidence < 0 {
			block.Confidence = 0
		}
		if block.Confidence > 1 {
			block.Confidence = 1
		}
		out = append(out, block)
	}
	return out, warnings
}

func clampBBox(b contract.BBox, image ImageInfo) (contract.BBox, bool) {
	x1 := max(0, b.X)
	y1 := max(0, b.Y)
	x2 := min(image.Width, b.X+b.Width)
	y2 := min(image.Height, b.Y+b.Height)
	if x2 <= x1 || y2 <= y1 {
		return contract.BBox{}, false
	}
	return contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1}, true
}

func parseScore(value any) float64 {
	score, ok := toFloat(value)
	if !ok {
		return 0
	}
	return score
}

func valueAt(items []any, index int) any {
	if index < 0 || index >= len(items) {
		return nil
	}
	return items[index]
}

func toFloat(value any) (float64, bool) {
	switch v := value.(type) {
	case float64:
		return v, true
	case float32:
		return float64(v), true
	case int:
		return float64(v), true
	case int64:
		return float64(v), true
	case json.Number:
		parsed, err := v.Float64()
		return parsed, err == nil
	default:
		return 0, false
	}
}

func countWarnings(warnings []Warning, code string) int {
	count := 0
	for _, warning := range warnings {
		if warning.Code == code {
			count++
		}
	}
	return count
}

func round3(value float64) float64 {
	return math.Round(value*1000) / 1000
}
