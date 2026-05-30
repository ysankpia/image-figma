package detector

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	ProviderOpenAIResponses = "openai-responses"
	ProviderOpenAIChat      = "openai-chat-completions"
)

type Options struct {
	InputPath   string
	OutputDir   string
	Provider    string
	WireAPI     string
	BaseURL     string
	APIKey      string
	Model       string
	Passes      []string
	MaxSide     int
	Timeout     time.Duration
	Temperature float64
	Stream      bool
}

type RunResult struct {
	Document  Document
	Artifacts Artifacts
}

type Artifacts struct {
	Candidates   string   `json:"candidates"`
	Report       string   `json:"report"`
	Overlay      string   `json:"overlay"`
	RawResponses []string `json:"rawResponses,omitempty"`
}

func OptionsFromEnv() Options {
	return Options{
		Provider:    firstEnv("CODIA_UI_DETECTOR_PROVIDER", "UI_DETECTOR_PROVIDER"),
		WireAPI:     firstEnv("CODIA_UI_DETECTOR_WIRE_API", "UI_DETECTOR_WIRE_API"),
		BaseURL:     firstEnv("CODIA_UI_DETECTOR_BASE_URL", "OPENAI_BASE_URL", "UI_DETECTOR_BASE_URL"),
		APIKey:      firstEnv("CODIA_UI_DETECTOR_API_KEY", "OPENAI_API_KEY", "UI_DETECTOR_API_KEY"),
		Model:       firstEnv("CODIA_UI_DETECTOR_MODEL", "UI_DETECTOR_MODEL"),
		Passes:      splitCSV(firstEnv("CODIA_UI_DETECTOR_PASSES", "UI_DETECTOR_PASSES")),
		MaxSide:     envInt("CODIA_UI_DETECTOR_MAX_IMAGE_SIDE", envInt("UI_DETECTOR_MAX_IMAGE_SIDE", 1280)),
		Timeout:     time.Duration(envInt("CODIA_UI_DETECTOR_TIMEOUT_SECONDS", envInt("UI_DETECTOR_TIMEOUT_SECONDS", 180))) * time.Second,
		Temperature: envFloat("CODIA_UI_DETECTOR_TEMPERATURE", envFloat("UI_DETECTOR_TEMPERATURE", 0)),
		Stream:      envBool("CODIA_UI_DETECTOR_STREAM", envBool("UI_DETECTOR_STREAM", false)),
	}
}

func (o Options) withDefaults() Options {
	if strings.TrimSpace(o.Provider) == "" {
		o.Provider = ProviderOpenAIResponses
	}
	if strings.TrimSpace(o.WireAPI) == "" {
		switch strings.ToLower(strings.TrimSpace(o.Provider)) {
		case ProviderOpenAIChat, "chat", "chat-completions":
			o.WireAPI = "chat.completions"
		default:
			o.WireAPI = "responses"
		}
	}
	if strings.TrimSpace(o.BaseURL) == "" {
		o.BaseURL = "https://api.openai.com"
	}
	o.BaseURL = strings.TrimRight(strings.TrimSpace(o.BaseURL), "/")
	if strings.TrimSpace(o.Model) == "" {
		o.Model = "gpt-5.5"
	}
	if len(o.Passes) == 0 {
		o.Passes = []string{"layout", "imageview", "background", "bottom_nav"}
	}
	if o.MaxSide <= 0 {
		o.MaxSide = 1280
	}
	if o.Timeout <= 0 {
		o.Timeout = 180 * time.Second
	}
	return o
}

func (o Options) validate() error {
	if strings.TrimSpace(o.InputPath) == "" {
		return fmt.Errorf("missing input path")
	}
	if strings.TrimSpace(o.OutputDir) == "" {
		return fmt.Errorf("missing output dir")
	}
	if strings.TrimSpace(o.APIKey) == "" {
		return fmt.Errorf("missing detector API key: set CODIA_UI_DETECTOR_API_KEY or OPENAI_API_KEY")
	}
	switch strings.ToLower(strings.TrimSpace(o.WireAPI)) {
	case "responses", "chat.completions", "chat-completions":
		return nil
	default:
		return fmt.Errorf("unsupported detector wire API %q", o.WireAPI)
	}
}

func providerMeta(o Options) ProviderMeta {
	host := ""
	if parsed, err := url.Parse(o.BaseURL); err == nil {
		host = parsed.Host
	}
	return ProviderMeta{
		Name:        o.Provider,
		WireAPI:     o.WireAPI,
		Model:       o.Model,
		BaseURLHost: host,
		Stream:      o.Stream,
	}
}

func firstEnv(keys ...string) string {
	for _, key := range keys {
		if value := strings.TrimSpace(os.Getenv(key)); value != "" {
			return value
		}
	}
	return ""
}

func splitCSV(raw string) []string {
	fields := strings.Split(raw, ",")
	out := make([]string, 0, len(fields))
	for _, field := range fields {
		value := strings.TrimSpace(field)
		if value != "" {
			out = append(out, value)
		}
	}
	return out
}

func envInt(key string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return value
}

func envFloat(key string, fallback float64) float64 {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return fallback
	}
	return value
}

func envBool(key string, fallback bool) bool {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseBool(raw)
	if err != nil {
		return fallback
	}
	return value
}
