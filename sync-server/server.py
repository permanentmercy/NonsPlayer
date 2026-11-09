#!/usr/bin/env python3
"""
NonsPlayer Playlist Sync Server (路由器/轻量级歌单同步服务)
零第三方依赖，仅使用 Python 3 标准库（http.server + sqlite3）。
适用于 OpenWrt、Debian、Armbian、Docker 等路由器与嵌入式 Linux 环境。
"""

import argparse
import http.server
import json
import os
import sqlite3
import sys
import time
from urllib.parse import parse_qs, urlparse

VERSION = "1.0.0"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 17777
DEFAULT_DB = "nons_playlists.db"

# 全局配置
AUTH_TOKEN = os.environ.get("SYNC_TOKEN", "")


def init_db(db_path: str):
    """初始化 SQLite 数据库及 WAL 模式"""
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS playlists (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            playlist_type TEXT NOT NULL DEFAULT 'aggregate',
            covers_json TEXT NOT NULL DEFAULT '[]',
            track_count INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL,
            tracks_json TEXT NOT NULL DEFAULT '[]'
        );
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_playlists_updated ON playlists(updated_at DESC);
        """
    )
    conn.commit()
    conn.close()


def get_db(db_path: str):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


class SyncHandler(http.server.BaseHTTPRequestHandler):
    db_path = DEFAULT_DB

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Requested-With, X-Sync-Token",
        )
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        self._send_json(status, {"error": message, "success": False})

    def _check_auth(self) -> bool:
        if not AUTH_TOKEN:
            return True
        # 1. 检查 Authorization Header
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            if token == AUTH_TOKEN:
                return True
        # 2. 检查 X-Sync-Token Header
        token_hdr = self.headers.get("X-Sync-Token", "").strip()
        if token_hdr == AUTH_TOKEN:
            return True
        # 3. 检查 query 参数
        query = parse_qs(urlparse(self.path).query)
        token_param = query.get("token", [""])[0]
        return token_param == AUTH_TOKEN

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        # 健康检查（无需认证）
        if path in ("/health", "/api/v1/health"):
            with get_db(self.db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM playlists"
                ).fetchone()[0]
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "NonsPlayer Playlist Sync Server",
                    "version": VERSION,
                    "playlistsCount": count,
                    "timestamp": int(time.time()),
                },
            )
            return

        if not self._check_auth():
            self._send_error(401, "未授权：无效或缺失同步令牌")
            return

        # 歌单列表：GET /api/v1/playlists
        if path == "/api/v1/playlists":
            with get_db(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT id, name, playlist_type, covers_json, track_count, updated_at FROM playlists ORDER BY updated_at DESC"
                ).fetchall()
                items = []
                for r in rows:
                    items.append(
                        {
                            "id": r["id"],
                            "name": r["name"],
                            "playlistType": r["playlist_type"],
                            "covers": json.loads(r["covers_json"] or "[]"),
                            "trackCount": r["track_count"],
                            "updatedAt": r["updated_at"],
                        }
                    )
            self._send_json(200, {"playlists": items, "total": len(items)})
            return

        # 单个歌单详情（含歌曲完整数据）：GET /api/v1/playlists/<id>
        if path.startswith("/api/v1/playlists/"):
            playlist_id = path[len("/api/v1/playlists/") :]
            with get_db(self.db_path) as conn:
                row = conn.execute(
                    "SELECT id, name, playlist_type, covers_json, track_count, updated_at, tracks_json FROM playlists WHERE id = ?",
                    (playlist_id,),
                ).fetchone()
            if not row:
                self._send_error(404, f"歌单未找到：{playlist_id}")
                return
            self._send_json(
                200,
                {
                    "id": row["id"],
                    "name": row["name"],
                    "playlistType": row["playlist_type"],
                    "covers": json.loads(row["covers_json"] or "[]"),
                    "trackCount": row["track_count"],
                    "updatedAt": row["updated_at"],
                    "tracks": json.loads(row["tracks_json"] or "[]"),
                },
            )
            return

        self._send_error(404, "接口不存在")

    def do_POST(self):
        if not self._check_auth():
            self._send_error(401, "未授权：无效或缺失同步令牌")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        length = int(self.headers.get("Content-Length", 0))
        if length > 30 * 1024 * 1024:  # 30MB 上限
            self._send_error(413, "请求体过大（最多允许 30MB）")
            return

        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception as e:
            self._send_error(400, f"JSON 解析失败：{str(e)}")
            return

        now = int(time.time())

        # 保存或更新单个歌单：POST /api/v1/playlists
        if path == "/api/v1/playlists":
            pid = str(payload.get("id", "")).strip()
            name = str(payload.get("name", "")).strip()
            if not pid or not name:
                self._send_error(400, "缺少必要参数：id 或 name 不能为空")
                return

            ptype = payload.get("playlistType", "aggregate")
            covers = json.dumps(payload.get("covers", []), ensure_ascii=False)
            tracks = payload.get("tracks", [])
            tracks_json = json.dumps(tracks, ensure_ascii=False)
            track_count = len(tracks)
            updated_at = int(payload.get("updatedAt", now))

            with get_db(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO playlists (id, name, playlist_type, covers_json, track_count, updated_at, tracks_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        playlist_type = excluded.playlist_type,
                        covers_json = excluded.covers_json,
                        track_count = excluded.track_count,
                        updated_at = excluded.updated_at,
                        tracks_json = excluded.tracks_json
                    """,
                    (
                        pid,
                        name,
                        ptype,
                        covers,
                        track_count,
                        updated_at,
                        tracks_json,
                    ),
                )
                conn.commit()
            self._send_json(
                200,
                {
                    "success": True,
                    "id": pid,
                    "trackCount": track_count,
                    "updatedAt": updated_at,
                },
            )
            return

        # 批量双向同步接口：POST /api/v1/sync
        # 客户端上报自身歌单与版本，服务端根据时间戳进行合并与差异返回
        if path == "/api/v1/sync":
            client_playlists = payload.get("playlists", [])
            updated_ids = []

            with get_db(self.db_path) as conn:
                for p in client_playlists:
                    pid = str(p.get("id", "")).strip()
                    name = str(p.get("name", "")).strip()
                    if not pid or not name:
                        continue
                    ptype = p.get("playlistType", "aggregate")
                    covers = json.dumps(p.get("covers", []), ensure_ascii=False)
                    tracks = p.get("tracks", [])
                    tracks_json = json.dumps(tracks, ensure_ascii=False)
                    track_count = len(tracks)
                    client_updated = int(p.get("updatedAt", now))

                    # 检查服务端版本
                    curr = conn.execute(
                        "SELECT updated_at FROM playlists WHERE id = ?", (pid,)
                    ).fetchone()
                    if not curr or client_updated >= curr["updated_at"]:
                        conn.execute(
                            """
                            INSERT INTO playlists (id, name, playlist_type, covers_json, track_count, updated_at, tracks_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(id) DO UPDATE SET
                                name = excluded.name,
                                playlist_type = excluded.playlist_type,
                                covers_json = excluded.covers_json,
                                track_count = excluded.track_count,
                                updated_at = excluded.updated_at,
                                tracks_json = excluded.tracks_json
                            """,
                            (
                                pid,
                                name,
                                ptype,
                                covers,
                                track_count,
                                client_updated,
                                tracks_json,
                            ),
                        )
                        updated_ids.append(pid)

                conn.commit()

                # 返回服务端全量歌单供客户端比对更新
                all_rows = conn.execute(
                    "SELECT id, name, playlist_type, covers_json, track_count, updated_at, tracks_json FROM playlists"
                ).fetchall()
                server_playlists = []
                for r in all_rows:
                    server_playlists.append(
                        {
                            "id": r["id"],
                            "name": r["name"],
                            "playlistType": r["playlist_type"],
                            "covers": json.loads(r["covers_json"] or "[]"),
                            "trackCount": r["track_count"],
                            "updatedAt": r["updated_at"],
                            "tracks": json.loads(r["tracks_json"] or "[]"),
                        }
                    )

            self._send_json(
                200,
                {
                    "success": True,
                    "updatedIds": updated_ids,
                    "playlists": server_playlists,
                    "timestamp": now,
                },
            )
            return

        self._send_error(404, "接口不存在")

    def do_DELETE(self):
        if not self._check_auth():
            self._send_error(401, "未授权：无效或缺失同步令牌")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith("/api/v1/playlists/"):
            playlist_id = path[len("/api/v1/playlists/") :]
            with get_db(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM playlists WHERE id = ?", (playlist_id,)
                )
                conn.commit()
            self._send_json(200, {"success": True, "deletedId": playlist_id})
            return

        self._send_error(404, "接口不存在")

    def log_message(self, format, *args):
        # 简化日志输出至标准错误输出
        sys.stderr.write(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {args[0]} {args[1]} -> {args[2]}\n"
        )


def main():
    global AUTH_TOKEN
    parser = argparse.ArgumentParser(
        description="NonsPlayer 路由器轻量级歌单同步服务"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("SYNC_HOST", DEFAULT_HOST),
        help=f"监听 IP，默认 {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SYNC_PORT", DEFAULT_PORT)),
        help=f"监听端口，默认 {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("SYNC_DB", DEFAULT_DB),
        help=f"SQLite 数据库路径，默认 {DEFAULT_DB}",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("SYNC_TOKEN", ""),
        help="访问认证 Token（可选，默认无认证）",
    )
    args = parser.parse_args()

    AUTH_TOKEN = args.token
    SyncHandler.db_path = args.db

    init_db(args.db)

    server_address = (args.host, args.port)
    httpd = http.server.ThreadingHTTPServer(server_address, SyncHandler)

    print("=" * 60)
    print(f"  NonsPlayer 歌单同步服务已启动 (v{VERSION})")
    print(f"  监听地址: http://{args.host}:{args.port}")
    print(f"  数据存储: {os.path.abspath(args.db)}")
    print(f"  安全认证: {'已启用 Token 认证' if AUTH_TOKEN else '开放访问 (无密码)'}")
    print(f"  健康检查: http://{args.host}:{args.port}/health")
    print("=" * 60)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        httpd.server_close()
        print("服务已停止。")


if __name__ == "__main__":
    main()
