package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"
)

type Track struct {
	Key        string                 `json:"key"`
	Title      string                 `json:"title"`
	Artists    []map[string]any       `json:"artists,omitempty"`
	Album      map[string]any         `json:"album,omitempty"`
	DurationMs uint32                 `json:"durationMs,omitempty"`
	Source     map[string]any         `json:"source"`
	Cover      map[string]any         `json:"cover,omitempty"`
	Extra      map[string]any         `json:"-"`
}

type Playlist struct {
	ID           string   `json:"id"`
	Name         string   `json:"name"`
	PlaylistType string   `json:"playlistType"`
	Covers       []string `json:"covers"`
	TrackCount   int      `json:"trackCount"`
	UpdatedAt    int64    `json:"updatedAt"`
	Tracks       []any    `json:"tracks,omitempty"`
}

type Store struct {
	mu        sync.RWMutex
	filePath  string
	playlists map[string]Playlist
}

func newStore(path string) *Store {
	s := &Store{
		filePath:  path,
		playlists: make(map[string]Playlist),
	}
	s.load()
	return s
}

func (s *Store) load() {
	s.mu.Lock()
	defer s.mu.Unlock()
	data, err := os.ReadFile(s.filePath)
	if err != nil {
		return
	}
	_ = json.Unmarshal(data, &s.playlists)
}

func (s *Store) save() error {
	data, err := json.MarshalIndent(s.playlists, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.filePath, data, 0644)
}

func main() {
	host := flag.String("host", "0.0.0.0", "监听 IP")
	port := flag.Int("port", 17777, "监听端口")
	dataFile := flag.String("data", "nons_playlists.json", "歌单持久化文件路径")
	token := flag.String("token", os.Getenv("SYNC_TOKEN"), "认证 Token")
	flag.Parse()

	store := newStore(*dataFile)

	cors := func(w http.ResponseWriter) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, X-Sync-Token")
	}

	checkAuth := func(r *http.Request) bool {
		if *token == "" {
			return true
		}
		auth := r.Header.Get("Authorization")
		if len(auth) > 7 && auth[:7] == "Bearer " && auth[7:] == *token {
			return true
		}
		if r.Header.Get("X-Sync-Token") == *token {
			return true
		}
		if r.URL.Query().Get("token") == *token {
			return true
		}
		return false
	}

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		store.mu.RLock()
		count := len(store.playlists)
		store.mu.RUnlock()
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status":         "ok",
			"service":        "NonsPlayer Playlist Sync (Go)",
			"version":        "1.0.0",
			"playlistsCount": count,
			"timestamp":      time.Now().Unix(),
		})
	})

	http.HandleFunc("/api/v1/playlists", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if !checkAuth(r) {
			http.Error(w, `{"error":"未授权"}`, http.StatusUnauthorized)
			return
		}

		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		if r.Method == http.MethodGet {
			store.mu.RLock()
			items := make([]Playlist, 0, len(store.playlists))
			for _, p := range store.playlists {
				summary := p
				summary.Tracks = nil
				items = append(items, summary)
			}
			store.mu.RUnlock()
			_ = json.NewEncoder(w).Encode(map[string]any{"playlists": items, "total": len(items)})
			return
		}

		if r.Method == http.MethodPost {
			var p Playlist
			if err := json.NewDecoder(r.Body).Decode(&p); err != nil || p.ID == "" || p.Name == "" {
				http.Error(w, `{"error":"参数无效"}`, http.StatusBadRequest)
				return
			}
			p.TrackCount = len(p.Tracks)
			if p.UpdatedAt == 0 {
				p.UpdatedAt = time.Now().Unix()
			}
			store.mu.Lock()
			store.playlists[p.ID] = p
			_ = store.save()
			store.mu.Unlock()
			_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "id": p.ID, "updatedAt": p.UpdatedAt})
			return
		}
	})

	http.HandleFunc("/api/v1/playlists/", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if !checkAuth(r) {
			http.Error(w, `{"error":"未授权"}`, http.StatusUnauthorized)
			return
		}

		id := r.URL.Path[len("/api/v1/playlists/"):]
		w.Header().Set("Content-Type", "application/json; charset=utf-8")

		if r.Method == http.MethodGet {
			store.mu.RLock()
			p, ok := store.playlists[id]
			store.mu.RUnlock()
			if !ok {
				http.Error(w, `{"error":"歌单未找到"}`, http.StatusNotFound)
				return
			}
			_ = json.NewEncoder(w).Encode(p)
			return
		}

		if r.Method == http.MethodDelete {
			store.mu.Lock()
			delete(store.playlists, id)
			_ = store.save()
			store.mu.Unlock()
			_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "deletedId": id})
			return
		}
	})

	http.HandleFunc("/api/v1/sync", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if !checkAuth(r) {
			http.Error(w, `{"error":"未授权"}`, http.StatusUnauthorized)
			return
		}

		var req struct {
			Playlists []Playlist `json:"playlists"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, `{"error":"参数解析失败"}`, http.StatusBadRequest)
			return
		}

		now := time.Now().Unix()
		store.mu.Lock()
		updatedIDs := make([]string, 0)
		for _, p := range req.Playlists {
			if p.ID == "" || p.Name == "" {
				continue
			}
			p.TrackCount = len(p.Tracks)
			if p.UpdatedAt == 0 {
				p.UpdatedAt = now
			}
			curr, exists := store.playlists[p.ID]
			if !exists || p.UpdatedAt >= curr.UpdatedAt {
				store.playlists[p.ID] = p
				updatedIDs = append(updatedIDs, p.ID)
			}
		}
		_ = store.save()

		all := make([]Playlist, 0, len(store.playlists))
		for _, p := range store.playlists {
			all = append(all, p)
		}
		store.mu.Unlock()

		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"success":    true,
			"updatedIds": updatedIDs,
			"playlists":  all,
			"timestamp":  now,
		})
	})

	addr := fmt.Sprintf("%s:%d", *host, *port)
	log.Printf("NonsPlayer 歌单同步服务 (Go版) 启动在 http://%s\n", addr)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("启动失败: %v", err)
	}
}
