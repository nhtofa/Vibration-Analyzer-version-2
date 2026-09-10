package main

import (
	"io/fs"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestWaitForReady(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		response.WriteHeader(http.StatusOK)
	}))
	defer server.Close()
	if err := waitForReady(server.URL); err != nil {
		t.Fatalf("waitForReady returned an error for a live server: %v", err)
	}
}

func TestEmbeddedWebAssets(t *testing.T) {
	for _, name := range []string{"web/index.html", "web/app.js", "web/style.css", "web/vendor/xlsx.full.min.js"} {
		content, err := fs.ReadFile(web, name)
		if err != nil {
			t.Fatalf("embedded asset %s: %v", name, err)
		}
		if len(content) == 0 {
			t.Fatalf("embedded asset %s is empty", name)
		}
	}
	index, err := fs.ReadFile(web, "web/index.html")
	if err != nil || !strings.Contains(string(index), "Vibration Analyzer") {
		t.Fatal("embedded index does not contain the application title")
	}
}
