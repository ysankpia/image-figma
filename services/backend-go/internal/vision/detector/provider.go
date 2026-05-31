package detector

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
	if c.options.Stream {
		payload["stream"] = true
		return c.postStreamJSON(ctx, requestURL(c.options.BaseURL, "/responses"), payload)
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
	if c.options.Stream {
		payload["stream"] = true
		return c.postStreamJSON(ctx, requestURL(c.options.BaseURL, "/chat/completions"), payload)
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

func (c providerClient) postStreamJSON(ctx context.Context, endpoint string, payload any) (modelResponse, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return modelResponse{}, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return modelResponse{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")
	req.Header.Set("Authorization", "Bearer "+c.options.APIKey)
	resp, err := c.http.Do(req)
	if err != nil {
		return modelResponse{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		raw, readErr := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
		if readErr != nil {
			return modelResponse{}, readErr
		}
		return modelResponse{}, fmt.Errorf("detector provider returned %s: %s", resp.Status, trimForError(string(raw)))
	}
	response, err := readStreamModelResponse(resp.Body)
	if err != nil {
		return modelResponse{}, err
	}
	if strings.TrimSpace(response.Text) == "" {
		return modelResponse{}, fmt.Errorf("detector provider returned no text")
	}
	return response, nil
}

func readStreamModelResponse(body io.Reader) (modelResponse, error) {
	scanner := bufio.NewScanner(io.LimitReader(body, 16<<20))
	scanner.Buffer(make([]byte, 0, 64*1024), 4<<20)
	var raw bytes.Buffer
	dataLines := []string{}
	var streamed strings.Builder
	fallbacks := []string{}

	flush := func() {
		if len(dataLines) == 0 {
			return
		}
		data := strings.TrimSpace(strings.Join(dataLines, "\n"))
		dataLines = dataLines[:0]
		if data == "" || data == "[DONE]" {
			return
		}
		if delta := extractStreamDelta([]byte(data)); strings.TrimSpace(delta) != "" {
			streamed.WriteString(delta)
			return
		}
		if finalText := extractStreamFinalText([]byte(data)); strings.TrimSpace(finalText) != "" {
			fallbacks = append(fallbacks, finalText)
		}
	}

	for scanner.Scan() {
		line := scanner.Text()
		raw.WriteString(line)
		raw.WriteByte('\n')
		if line == "" {
			flush()
			continue
		}
		if strings.HasPrefix(line, "data:") {
			dataLines = append(dataLines, strings.TrimSpace(strings.TrimPrefix(line, "data:")))
		}
	}
	flush()
	if err := scanner.Err(); err != nil {
		return modelResponse{}, err
	}

	text := streamed.String()
	if strings.TrimSpace(text) == "" && len(fallbacks) > 0 {
		text = fallbacks[len(fallbacks)-1]
	}
	if strings.TrimSpace(text) == "" {
		trimmed := strings.TrimSpace(raw.String())
		if strings.HasPrefix(trimmed, "{") || strings.HasPrefix(trimmed, "[") {
			text = extractResponseText([]byte(trimmed))
		}
	}
	return modelResponse{RawText: raw.String(), Text: text}, nil
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

func extractStreamDelta(raw []byte) string {
	var root any
	if err := json.Unmarshal(raw, &root); err != nil {
		return ""
	}
	return strings.Join(collectStreamDeltas(root), "")
}

func collectStreamDeltas(value any) []string {
	switch item := value.(type) {
	case []any:
		out := []string{}
		for _, child := range item {
			out = append(out, collectStreamDeltas(child)...)
		}
		return out
	case map[string]any:
		out := []string{}
		if choices, ok := item["choices"].([]any); ok {
			for _, choice := range choices {
				if text := extractChoiceDelta(choice); text != "" {
					out = append(out, text)
				}
			}
			return out
		}
		if delta, ok := item["delta"].(string); ok {
			out = append(out, delta)
		}
		if delta, ok := item["delta"].(map[string]any); ok {
			if text := extractContentText(delta["text"]); text != "" {
				out = append(out, text)
			}
			if text := extractContentText(delta["content"]); text != "" {
				out = append(out, text)
			}
		}
		return out
	default:
		return nil
	}
}

func extractChoiceDelta(value any) string {
	choice, ok := value.(map[string]any)
	if !ok {
		return ""
	}
	delta, ok := choice["delta"].(map[string]any)
	if !ok {
		return ""
	}
	if text := extractContentText(delta["content"]); text != "" {
		return text
	}
	return extractContentText(delta["text"])
}

func extractContentText(value any) string {
	switch content := value.(type) {
	case string:
		return content
	case []any:
		texts := []string{}
		collectTextFields(content, &texts)
		return strings.Join(texts, "")
	default:
		return ""
	}
}

func extractStreamFinalText(raw []byte) string {
	var root any
	if err := json.Unmarshal(raw, &root); err != nil {
		return ""
	}
	if item, ok := root.(map[string]any); ok {
		if response, ok := item["response"]; ok {
			data, err := json.Marshal(response)
			if err == nil {
				return extractResponseText(data)
			}
		}
	}
	return extractResponseText(raw)
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
