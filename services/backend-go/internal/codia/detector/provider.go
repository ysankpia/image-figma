package detector

import (
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

func (c providerClient) detect(ctx context.Context, pass preparedPass) (modelResponse, error) {
	switch strings.ToLower(strings.TrimSpace(c.options.WireAPI)) {
	case "responses":
		return c.detectResponses(ctx, pass)
	case "chat.completions", "chat-completions":
		return c.detectChatCompletions(ctx, pass)
	default:
		return modelResponse{}, fmt.Errorf("unsupported detector wire API %q", c.options.WireAPI)
	}
}

func (c providerClient) detectResponses(ctx context.Context, pass preparedPass) (modelResponse, error) {
	dataURL, err := imageDataURL(pass.Image)
	if err != nil {
		return modelResponse{}, err
	}
	payload := map[string]any{
		"model": c.options.Model,
		"input": []any{
			map[string]any{
				"role": "user",
				"content": []any{
					map[string]any{"type": "input_text", "text": pass.Prompt},
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

func (c providerClient) detectChatCompletions(ctx context.Context, pass preparedPass) (modelResponse, error) {
	dataURL, err := imageDataURL(pass.Image)
	if err != nil {
		return modelResponse{}, err
	}
	payload := map[string]any{
		"model": c.options.Model,
		"messages": []any{
			map[string]any{
				"role": "user",
				"content": []any{
					map[string]any{"type": "text", "text": pass.Prompt},
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
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return modelResponse{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.options.APIKey)
	resp, err := c.http.Do(req)
	if err != nil {
		return modelResponse{}, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	if err != nil {
		return modelResponse{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return modelResponse{}, fmt.Errorf("detector provider returned %s: %s", resp.Status, trimForError(string(raw)))
	}
	text := extractResponseText(raw)
	if strings.TrimSpace(text) == "" {
		return modelResponse{}, fmt.Errorf("detector provider returned no text")
	}
	return modelResponse{RawText: string(raw), Text: text}, nil
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

func collectTextFields(value any, texts *[]string) {
	switch item := value.(type) {
	case []any:
		for _, child := range item {
			collectTextFields(child, texts)
		}
	case map[string]any:
		if text, ok := item["text"].(string); ok && strings.TrimSpace(text) != "" {
			*texts = append(*texts, text)
		}
		for _, child := range item {
			collectTextFields(child, texts)
		}
	}
}

func trimForError(raw string) string {
	raw = strings.TrimSpace(raw)
	if len(raw) > 1000 {
		return raw[:1000] + "..."
	}
	return raw
}
