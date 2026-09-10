package main

import (
	"io/fs"
	"strings"
	"testing"
)

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
