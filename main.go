package main

import (
	"context"
	"embed"
	"fmt"
	"io/fs"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// web contains the same offline-first frontend used by the Android build.
//
//go:embed web
var web embed.FS

func main() {
	assets, err := fs.Sub(web, "web")
	if err != nil {
		panic(err)
	}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		panic(err)
	}
	server := &http.Server{Handler: http.FileServer(http.FS(assets))}
	serverDone := make(chan struct{})
	go func() {
		_ = server.Serve(listener)
		close(serverDone)
	}()

	url := fmt.Sprintf("http://127.0.0.1:%d/", listener.Addr().(*net.TCPAddr).Port)
	if err := waitForReady(url); err != nil {
		shutdown(server, listener, serverDone)
		return
	}

	if runtime.GOOS == "windows" {
		if edge := findEdge(); edge != "" {
			// A separate profile prevents an already-running Edge instance from
			// handing off the --app request and exiting our child process early.
			profile, profileErr := os.MkdirTemp("", "vibration-analyzer-edge-")
			if profileErr == nil {
				args := []string{"--app=" + url, "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check"}
				command := exec.Command(edge, args...)
				if startErr := command.Start(); startErr == nil {
					_ = command.Wait()
					shutdown(server, listener, serverDone)
					_ = os.RemoveAll(profile)
					return
				}
				_ = os.RemoveAll(profile)
			}
		}
		// Edge is installed on supported Windows versions; this fallback keeps
		// the portable launcher useful on machines where its path is unusual.
		_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
		// A default-browser fallback has no reliable child-process lifetime.
		// Keep the local server available rather than closing it immediately.
		<-time.After(24 * time.Hour)
		shutdown(server, listener, serverDone)
		return
	}
	_ = exec.Command(browserCommand(), url).Start()
	select {}
}

func waitForReady(target string) error {
	client := &http.Client{Timeout: 200 * time.Millisecond}
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		response, err := client.Get(target)
		if err == nil {
			_ = response.Body.Close()
			if response.StatusCode < http.StatusInternalServerError {
				return nil
			}
		}
		time.Sleep(25 * time.Millisecond)
	}
	return fmt.Errorf("local app server did not become ready")
}

func shutdown(server *http.Server, listener net.Listener, done <-chan struct{}) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	_ = server.Shutdown(ctx)
	_ = listener.Close()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
	}
}

func findEdge() string {
	candidates := []string{
		`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`,
		`C:\Program Files\Microsoft\Edge\Application\msedge.exe`,
		`C:\Program Files (x86)\Microsoft\Edge Beta\Application\msedge.exe`,
		`C:\Program Files\Microsoft\Edge Beta\Application\msedge.exe`,
	}
	if local := os.Getenv("LOCALAPPDATA"); local != "" {
		candidates = append(candidates, filepath.Join(local, `Microsoft\Edge\Application\msedge.exe`))
	}
	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	if path, err := exec.LookPath("msedge.exe"); err == nil {
		return path
	}
	return ""
}

func browserCommand() string {
	if strings.EqualFold(runtime.GOOS, "darwin") {
		return "open"
	}
	return "xdg-open"
}
