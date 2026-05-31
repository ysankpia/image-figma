package unifiedvision

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

type Options struct {
	Enabled              bool
	OutputDir            string
	Provider             string
	WireAPI              string
	BaseURL              string
	APIKey               string
	Model                string
	Concurrency          int
	Timeout              time.Duration
	Temperature          float64
	TransportRetries     int
	RepairAttempts       int
	MaxItemsPerBatch     int
	HardMaxItemsPerBatch int
	MaxComplexity        float64
	MinConfidence        float64
	MaxFitRatio          float64
	MaxYSpreadFactor     float64
	MaxGap               int
	MaxGapVariance       int
	CropPadding          int
}

func OptionsFromEnv() Options {
	return Options{
		Enabled:              envBool("UNIFIED_VISION_ENABLED", false),
		Provider:             envString("UNIFIED_VISION_PROVIDER", "openai-compatible"),
		WireAPI:              envString("UNIFIED_VISION_WIRE_API", "responses"),
		BaseURL:              envString("UNIFIED_VISION_BASE_URL", "https://api.openai.com"),
		APIKey:               envString("UNIFIED_VISION_API_KEY", ""),
		Model:                envString("UNIFIED_VISION_MODEL", ""),
		Concurrency:          envInt("UNIFIED_VISION_CONCURRENCY", 3),
		Timeout:              time.Duration(envInt("UNIFIED_VISION_TIMEOUT_SECONDS", 180)) * time.Second,
		Temperature:          envFloat("UNIFIED_VISION_TEMPERATURE", 0),
		TransportRetries:     envInt("UNIFIED_VISION_TRANSPORT_RETRIES", 3),
		RepairAttempts:       envInt("UNIFIED_VISION_REPAIR_ATTEMPTS", 1),
		MaxItemsPerBatch:     envInt("UNIFIED_VISION_MAX_ITEMS_PER_BATCH", 30),
		HardMaxItemsPerBatch: envInt("UNIFIED_VISION_HARD_MAX_ITEMS_PER_BATCH", 45),
		MaxComplexity:        envFloat("UNIFIED_VISION_MAX_COMPLEXITY", 110),
		MinConfidence:        envFloat("UNIFIED_VISION_MIN_CONFIDENCE", 0.70),
		MaxFitRatio:          envFloat("UNIFIED_VISION_MAX_FIT_RATIO", 1.01),
		MaxYSpreadFactor:     envFloat("UNIFIED_VISION_MAX_Y_SPREAD_FACTOR", 1.60),
		MaxGap:               envInt("UNIFIED_VISION_MAX_GAP", 96),
		MaxGapVariance:       envInt("UNIFIED_VISION_MAX_GAP_VARIANCE", 4096),
		CropPadding:          envInt("UNIFIED_VISION_CROP_PADDING", 10),
	}
}

func (o Options) withDefaults() Options {
	if strings.TrimSpace(o.Provider) == "" {
		o.Provider = "openai-compatible"
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
	if o.Concurrency <= 0 {
		o.Concurrency = 3
	}
	if o.Timeout <= 0 {
		o.Timeout = 180 * time.Second
	}
	if o.TransportRetries <= 0 {
		o.TransportRetries = 3
	}
	if o.RepairAttempts < 0 {
		o.RepairAttempts = 0
	}
	if o.MaxItemsPerBatch <= 0 {
		o.MaxItemsPerBatch = 30
	}
	if o.HardMaxItemsPerBatch <= 0 {
		o.HardMaxItemsPerBatch = 45
	}
	if o.MaxItemsPerBatch > o.HardMaxItemsPerBatch {
		o.MaxItemsPerBatch = o.HardMaxItemsPerBatch
	}
	if o.MaxComplexity <= 0 {
		o.MaxComplexity = 110
	}
	if o.MinConfidence <= 0 {
		o.MinConfidence = 0.70
	}
	if o.MaxFitRatio <= 0 {
		o.MaxFitRatio = 1.01
	}
	if o.MaxYSpreadFactor <= 0 {
		o.MaxYSpreadFactor = 1.60
	}
	if o.MaxGap <= 0 {
		o.MaxGap = 96
	}
	if o.MaxGapVariance <= 0 {
		o.MaxGapVariance = 4096
	}
	if o.CropPadding < 0 {
		o.CropPadding = 0
	}
	return o
}

func (o Options) validateProvider() error {
	if strings.TrimSpace(o.APIKey) == "" {
		return fmt.Errorf("missing unified vision API key: set UNIFIED_VISION_API_KEY")
	}
	if strings.TrimSpace(o.Model) == "" {
		return fmt.Errorf("missing unified vision model: set UNIFIED_VISION_MODEL")
	}
	switch strings.ToLower(strings.TrimSpace(o.WireAPI)) {
	case "responses", "chat.completions", "chat-completions":
		return nil
	default:
		return fmt.Errorf("unsupported unified vision wire API %q", o.WireAPI)
	}
}

func (o Options) providerMeta() ProviderMeta {
	host := ""
	if parsed, err := url.Parse(o.BaseURL); err == nil {
		host = parsed.Host
	}
	return ProviderMeta{
		WireAPI:     o.WireAPI,
		Model:       o.Model,
		BaseURLHost: host,
	}
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
