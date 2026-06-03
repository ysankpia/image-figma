package config

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type OCRConfig struct {
	Provider      string
	MinConfidence float64
	Baidu         BaiduPaddleOCRConfig
}

type BaiduPaddleOCRConfig struct {
	Token        string
	JobURL       string
	Model        string
	PollInterval time.Duration
	Timeout      time.Duration
}

func LoadLocalEnvFromAncestors() {
	if strings.EqualFold(os.Getenv("IMAGE_FIGMA_LOAD_LOCAL_ENV"), "false") {
		return
	}
	cwd, err := os.Getwd()
	if err != nil {
		return
	}
	for {
		path := filepath.Join(cwd, ".env.local")
		if _, err := os.Stat(path); err == nil {
			_ = loadEnvFile(path)
			return
		}
		parent := filepath.Dir(cwd)
		if parent == cwd {
			return
		}
		cwd = parent
	}
}

func OCRFromEnv(providerOverride string) OCRConfig {
	provider := strings.TrimSpace(strings.ToLower(providerOverride))
	if provider == "" {
		provider = strings.TrimSpace(strings.ToLower(os.Getenv("OCR_PROVIDER")))
	}
	minConfidence := envFloat("OCR_MIN_CONFIDENCE", 0.70)
	return OCRConfig{
		Provider:      provider,
		MinConfidence: minConfidence,
		Baidu: BaiduPaddleOCRConfig{
			Token:        os.Getenv("BAIDU_PADDLE_OCR_TOKEN"),
			JobURL:       strings.TrimRight(envString("BAIDU_PADDLE_OCR_JOB_URL", "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"), "/"),
			Model:        envString("BAIDU_PADDLE_OCR_MODEL", "PP-OCRv5"),
			PollInterval: time.Duration(envFloat("BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS", 5)) * time.Second,
			Timeout:      time.Duration(envFloat("BAIDU_PADDLE_OCR_TIMEOUT_SECONDS", 120)) * time.Second,
		},
	}
}

func loadEnvFile(path string) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		key, value, ok := parseEnvLine(scanner.Text())
		if !ok {
			continue
		}
		if _, exists := os.LookupEnv(key); !exists {
			_ = os.Setenv(key, value)
		}
	}
	return scanner.Err()
}

func parseEnvLine(raw string) (string, string, bool) {
	line := strings.TrimSpace(raw)
	if line == "" || strings.HasPrefix(line, "#") {
		return "", "", false
	}
	line = strings.TrimSpace(strings.TrimPrefix(line, "export "))
	key, value, ok := strings.Cut(line, "=")
	if !ok {
		return "", "", false
	}
	key = strings.TrimSpace(key)
	if key == "" {
		return "", "", false
	}
	value = strings.TrimSpace(value)
	if len(value) >= 2 {
		first := value[0]
		last := value[len(value)-1]
		if (first == '"' && last == '"') || (first == '\'' && last == '\'') {
			value = value[1 : len(value)-1]
		}
	}
	return key, value, true
}

func envString(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func envFloat(key string, fallback float64) float64 {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return fallback
	}
	return parsed
}

func (c OCRConfig) ValidateForProvider() error {
	switch c.Provider {
	case "", "none", "fake":
		return nil
	case "baidu_ppocrv5":
		if c.Baidu.Token == "" {
			return fmt.Errorf("BAIDU_PADDLE_OCR_TOKEN is required when OCR provider is baidu_ppocrv5")
		}
		if c.Baidu.JobURL == "" {
			return fmt.Errorf("BAIDU_PADDLE_OCR_JOB_URL is required when OCR provider is baidu_ppocrv5")
		}
		if c.Baidu.Model == "" {
			return fmt.Errorf("BAIDU_PADDLE_OCR_MODEL is required when OCR provider is baidu_ppocrv5")
		}
		return nil
	default:
		return fmt.Errorf("unsupported OCR provider %q", c.Provider)
	}
}
