package provider

import (
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	DefaultProvider    = "openai-compatible"
	DefaultWireAPI     = "responses"
	DefaultBaseURL     = "https://api.openai.com"
	DefaultMaxSide     = 1280
	DefaultConcurrency = 3
	DefaultTimeout     = 90 * time.Second
)

type Config struct {
	Provider    string
	WireAPI     string
	BaseURL     string
	APIKey      string
	Model       string
	MaxSide     int
	Concurrency int
	Timeout     time.Duration
	Temperature float64
	Stream      bool
}

func FromEnv() Config {
	return Config{
		Provider:    envString("VISION_PROVIDER", DefaultProvider),
		WireAPI:     envString("VISION_WIRE_API", DefaultWireAPI),
		BaseURL:     strings.TrimRight(envString("VISION_BASE_URL", DefaultBaseURL), "/"),
		APIKey:      envString("VISION_API_KEY", ""),
		Model:       envString("VISION_MODEL", ""),
		MaxSide:     envInt("VISION_MAX_IMAGE_SIDE", DefaultMaxSide),
		Concurrency: envInt("VISION_DETECTOR_CONCURRENCY", DefaultConcurrency),
		Timeout:     time.Duration(envInt("VISION_TIMEOUT_SECONDS", int(DefaultTimeout/time.Second))) * time.Second,
		Temperature: envFloat("VISION_TEMPERATURE", 0),
		Stream:      envBool("VISION_STREAM", false),
	}.Normalized()
}

func (c Config) Normalized() Config {
	if strings.TrimSpace(c.Provider) == "" {
		c.Provider = DefaultProvider
	}
	if strings.TrimSpace(c.WireAPI) == "" {
		c.WireAPI = DefaultWireAPI
	}
	if strings.TrimSpace(c.BaseURL) == "" {
		c.BaseURL = DefaultBaseURL
	}
	c.BaseURL = strings.TrimRight(strings.TrimSpace(c.BaseURL), "/")
	if c.MaxSide <= 0 {
		c.MaxSide = DefaultMaxSide
	}
	if c.Concurrency <= 0 {
		c.Concurrency = DefaultConcurrency
	}
	if c.Timeout <= 0 {
		c.Timeout = DefaultTimeout
	}
	return c
}

func envString(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
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
