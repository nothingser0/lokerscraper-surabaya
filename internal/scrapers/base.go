package scrapers

import (
	"crypto/tls"
	"io"
	"net/http"
	"sync"
	"time"

	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

const DefaultUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

type Scraper interface {
	SourceName() string
	FetchJobs() ([]model.Job, error)
	SetSeenIDs(seen map[string]bool)
}

type BaseClient struct {
	Client        *http.Client
	RequestDelay  time.Duration
	lastRequestTs time.Time
	mu            sync.Mutex
	SeenIDs       map[string]bool
}

func NewBaseClient(timeout time.Duration, delay time.Duration) *BaseClient {
	transport := &http.Transport{
		MaxIdleConns:        10,
		MaxIdleConnsPerHost: 5,
		IdleConnTimeout:     30 * time.Second,
		TLSHandshakeTimeout: 10 * time.Second,
		DisableCompression:  false,
		ForceAttemptHTTP2:   true,
		TLSClientConfig:     &tls.Config{InsecureSkipVerify: false},
	}
	return &BaseClient{
		Client: &http.Client{
			Transport: transport,
			Timeout:   timeout,
		},
		RequestDelay: delay,
		SeenIDs:      make(map[string]bool),
	}
}

func (b *BaseClient) Throttle() {
	if b.RequestDelay <= 0 {
		return
	}
	b.mu.Lock()
	defer b.mu.Unlock()

	elapsed := time.Since(b.lastRequestTs)
	if elapsed < b.RequestDelay {
		time.Sleep(b.RequestDelay - elapsed)
	}
	b.lastRequestTs = time.Now()
}

func (b *BaseClient) DoRequest(req *http.Request) (*http.Response, error) {
	b.Throttle()
	return b.Client.Do(req)
}

func (b *BaseClient) IsSeen(sourceName, rawID string) bool {
	if len(b.SeenIDs) == 0 {
		return false
	}
	jobID := utils.GenerateJobID(sourceName, rawID)
	return b.SeenIDs[jobID]
}

func ReadBody(resp *http.Response) ([]byte, error) {
	defer resp.Body.Close()
	return io.ReadAll(resp.Body)
}
