package unifiedvision

import (
	"bufio"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"image"
	"image/png"
	"io"
	"mime"
	"net/http"
	"strings"
	"time"
)

type providerClient struct {
	options Options
	http    *http.Client
}

type modelResponse struct {
	RawText string
	Text    string
}

func newProviderClient(options Options) providerClient {
	return providerClient{
		options: options,
		http:    &http.Client{Timeout: options.Timeout},
	}
}

func (c providerClient) call(ctx context.Context, prompt string, img image.Image) (modelResponse, error) {
	switch strings.ToLower(strings.TrimSpace(c.options.WireAPI)) {
	case "responses":
		return c.callResponses(ctx, prompt, img)
	case "chat.completions", "chat-completions":
		return c.callChatCompletions(ctx, prompt, img)
	default:
		return modelResponse{}, fmt.Errorf("unsupported unified vision wire API %q", c.options.WireAPI)
	}
}

func (c providerClient) callResponses(ctx context.Context, prompt string, img image.Image) (modelResponse, error) {
	dataURL, err := imageDataURL(img)
	if err != nil {
		return modelResponse{}, err
	}
	payload := map[string]any{
		"model": c.options.Model,
		"input": []any{
			map[string]any{
				"role": "user",
				"content": []any{
					map[string]any{"type": "input_text", "text": prompt},
					map[string]any{"type": "input_image", "image_url": dataURL},
				},
			},
		},
	}
	if c.options.Temperature > 0 {
		payload["temperature"] = c.options.Temperature
	}
	return c.postJSON(ctx, requestURL(c.options.BaseURL, "/responses"), payload)
}

func (c providerClient) callChatCompletions(ctx context.Context, prompt string, img image.Image) (modelResponse, error) {
	dataURL, err := imageDataURL(img)
	if err != nil {
		return modelResponse{}, err
	}
	payload := map[string]any{
		"model": c.options.Model,
		"messages": []any{
			map[string]any{
				"role": "user",
				"content": []any{
					map[string]any{"type": "text", "text": prompt},
					map[string]any{"type": "image_url", "image_url": map[string]any{"url": dataURL}},
				},
			},
		},
	}
	if c.options.Temperature > 0 {
		payload["temperature"] = c.options.Temperature
	}
	return c.postJSON(ctx, requestURL(c.options.BaseURL, "/chat/completions"), payload)
}

func (c providerClient) postJSON(ctx context.Context, endpoint string, payload any) (modelResponse, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return modelResponse{}, err
	}
	var lastErr error
	attempts := maxInt(1, c.options.TransportRetries)
	for attempt := 0; attempt < attempts; attempt++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
		if err != nil {
			return modelResponse{}, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")
		req.Header.Set("Authorization", "Bearer "+c.options.APIKey)
		req.Header.Set("User-Agent", "curl/8.7.1")
		resp, err := c.http.Do(req)
		if err != nil {
			lastErr = err
			if attempt < attempts-1 {
				time.Sleep(time.Duration(attempt+1) * 2 * time.Second)
				continue
			}
			break
		}
		raw, readErr := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
		closeErr := resp.Body.Close()
		if readErr != nil {
			return modelResponse{}, readErr
		}
		if closeErr != nil {
			return modelResponse{}, closeErr
		}
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			text := extractResponseText(raw)
			if strings.TrimSpace(text) == "" {
				return modelResponse{}, fmt.Errorf("unified vision provider returned no text")
			}
			return modelResponse{RawText: string(raw), Text: text}, nil
		}
		lastErr = fmt.Errorf("unified vision provider returned %s: %s", resp.Status, trimForError(string(raw)))
		if !retryableStatus(resp.StatusCode) {
			break
		}
		if attempt < attempts-1 {
			time.Sleep(time.Duration(attempt+1) * 2 * time.Second)
		}
	}
	return modelResponse{}, lastErr
}

func retryableStatus(status int) bool {
	return status == 408 || status == 409 || status == 425 || status == 429 || status == 520 || status == 522 || status == 524 || status >= 500
}

func requestURL(baseURL, apiPath string) string {
	base := strings.TrimRight(strings.TrimSpace(baseURL), "/")
	path := "/" + strings.TrimLeft(apiPath, "/")
	if strings.HasSuffix(base, "/v1") {
		return base + path
	}
	if strings.HasSuffix(base, path) || strings.Contains(base, "/v1/") {
		return base
	}
	return base + "/v1" + path
}

func imageDataURL(img image.Image) (string, error) {
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		return "", err
	}
	encoded := base64.StdEncoding.EncodeToString(buf.Bytes())
	return "data:" + mime.TypeByExtension(".png") + ";base64," + encoded, nil
}

func extractResponseText(raw []byte) string {
	var root any
	if err := json.Unmarshal(raw, &root); err != nil {
		return string(raw)
	}
	if m, ok := root.(map[string]any); ok {
		if value, ok := m["output_text"].(string); ok && strings.TrimSpace(value) != "" {
			return value
		}
		if choices, ok := m["choices"].([]any); ok {
			for _, choice := range choices {
				if text := extractChoiceText(choice); strings.TrimSpace(text) != "" {
					return text
				}
			}
		}
	}
	texts := []string{}
	collectTextFields(root, &texts)
	return strings.Join(texts, "\n")
}

func extractChoiceText(value any) string {
	choice, ok := value.(map[string]any)
	if !ok {
		return ""
	}
	message, ok := choice["message"].(map[string]any)
	if !ok {
		return ""
	}
	switch content := message["content"].(type) {
	case string:
		return content
	case []any:
		texts := []string{}
		collectTextFields(content, &texts)
		return strings.Join(texts, "\n")
	default:
		return ""
	}
}

func collectTextFields(value any, out *[]string) {
	switch item := value.(type) {
	case map[string]any:
		if text, ok := item["text"].(string); ok {
			*out = append(*out, text)
		}
		for _, child := range item {
			collectTextFields(child, out)
		}
	case []any:
		for _, child := range item {
			collectTextFields(child, out)
		}
	}
}

func trimForError(value string) string {
	value = strings.TrimSpace(value)
	if len(value) > 600 {
		return value[:600] + "..."
	}
	return value
}

func readStreamModelResponse(body io.Reader) (modelResponse, error) {
	scanner := bufio.NewScanner(io.LimitReader(body, 16<<20))
	scanner.Buffer(make([]byte, 0, 64*1024), 4<<20)
	var raw bytes.Buffer
	for scanner.Scan() {
		raw.WriteString(scanner.Text())
		raw.WriteByte('\n')
	}
	if err := scanner.Err(); err != nil {
		return modelResponse{}, err
	}
	text := extractResponseText(raw.Bytes())
	return modelResponse{RawText: raw.String(), Text: text}, nil
}
