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
	ProviderOpenAICompatible = "openai-compatible"
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
	Concurrency int
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
		Provider:    envString("VISION_PROVIDER", ProviderOpenAICompatible),
		WireAPI:     envString("VISION_WIRE_API", "responses"),
		BaseURL:     envString("VISION_BASE_URL", "https://api.openai.com"),
		APIKey:      envString("VISION_API_KEY", ""),
		Model:       envString("VISION_MODEL", ""),
		Passes:      splitCSV(envString("VISION_DETECTOR_PASSES", "")),
		MaxSide:     envInt("VISION_MAX_IMAGE_SIDE", 1280),
		Concurrency: envInt("VISION_DETECTOR_CONCURRENCY", 3),
		Timeout:     time.Duration(envInt("VISION_TIMEOUT_SECONDS", 90)) * time.Second,
		Temperature: envFloat("VISION_TEMPERATURE", 0),
		Stream:      envBool("VISION_STREAM", false),
	}
}

func (o Options) withDefaults() Options {
	if strings.TrimSpace(o.Provider) == "" {
		o.Provider = ProviderOpenAICompatible
	}
	if strings.TrimSpace(o.WireAPI) == "" {
		o.WireAPI = "responses"
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
	if o.Concurrency <= 0 {
		o.Concurrency = 3
	}
	if o.Timeout <= 0 {
		o.Timeout = 90 * time.Second
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
		return fmt.Errorf("missing detector API key: set VISION_API_KEY")
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

func envString(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
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
