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

VERSION = "1.2.0"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 17777
DEFAULT_DB = "nons_playlists.db"

# 全局配置
AUTH_TOKEN = os.environ.get("SYNC_TOKEN", "")


def get_track_key(track: dict) -> str:
    """提取歌曲的唯一标识键"""
    key = track.get("key")
    if key:
        return str(key)
    src = track.get("source", {})
    if isinstance(src, dict):
        t_info = src.get("track", {})
        ref = t_info.get("reference", {})
        if ref:
            return f"{ref.get('source')}:{ref.get('kind')}:{ref.get('id')}"
    return json.dumps(track, sort_keys=True)


def merge_tracks(primary_tracks: list, secondary_tracks: list) -> list:
    """保持优先顺序的歌曲集合合并（基于唯一键去重）"""
    result = []
    seen = set()
    for t in primary_tracks:
        k = get_track_key(t)
        if k not in seen:
            seen.add(k)
            result.append(t)
    for t in secondary_tracks:
        k = get_track_key(t)
        if k not in seen:
            seen.add(k)
            result.append(t)
    return result


def merge_covers(primary_covers: list, secondary_covers: list) -> list:
    """封面合并去重"""
    seen = set()
    result = []
    for c in primary_covers + secondary_covers:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result[:4]


def deduplicate_existing_playlists(conn):
    """将同名歌单的歌曲合并并删除因多端本地自增 ID 产生的重复记录"""
    rows = conn.execute(
        "SELECT id, name, playlist_type, covers_json, track_count, updated_at, tracks_json FROM playlists"
    ).fetchall()
    grouped = {}
    for r in rows:
        norm_name = r["name"].strip()
        grouped.setdefault(norm_name, []).append(r)
    for name, plist in grouped.items():
        if len(plist) <= 1:
            continue
        # 按 updated_at 降序排序，最新更新的作为 primary
        plist.sort(key=lambda x: x["updated_at"], reverse=True)
        primary = plist[0]
        all_tracks = json.loads(primary["tracks_json"] or "[]")
        all_covers = json.loads(primary["covers_json"] or "[]")
        for other in plist[1:]:
            other_tracks = json.loads(other["tracks_json"] or "[]")
            other_covers = json.loads(other["covers_json"] or "[]")
            all_tracks = merge_tracks(all_tracks, other_tracks)
            all_covers = merge_covers(all_covers, other_covers)
            conn.execute("DELETE FROM playlists WHERE id = ?", (other["id"],))
        conn.execute(
            """
            UPDATE playlists SET
                covers_json = ?,
                track_count = ?,
                tracks_json = ?
            WHERE id = ?
            """,
            (
                json.dumps(all_covers, ensure_ascii=False),
                len(all_tracks),
                json.dumps(all_tracks, ensure_ascii=False),
                primary["id"],
            ),
        )
    conn.commit()


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
    conn.row_factory = sqlite3.Row
    deduplicate_existing_playlists(conn)
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
            if not name:
                self._send_error(400, "缺少必要参数：name 不能为空")
                return

            ptype = payload.get("playlistType", "aggregate")
            covers = payload.get("covers", [])
            tracks = payload.get("tracks", [])
            updated_at = int(payload.get("updatedAt", now))

            with get_db(self.db_path) as conn:
                existing = conn.execute(
                    "SELECT id, covers_json, updated_at, tracks_json FROM playlists WHERE LOWER(TRIM(name)) = LOWER(?)",
                    (name,),
                ).fetchone()
                if not existing:
                    target_id = pid if pid else str(int(time.time() * 1000))
                    conn.execute(
                        """
                        INSERT INTO playlists (id, name, playlist_type, covers_json, track_count, updated_at, tracks_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            target_id,
                            name,
                            ptype,
                            json.dumps(covers, ensure_ascii=False),
                            len(tracks),
                            updated_at,
                            json.dumps(tracks, ensure_ascii=False),
                        ),
                    )
                else:
                    target_id = existing["id"]
                    srv_tracks = json.loads(existing["tracks_json"] or "[]")
                    srv_covers = json.loads(existing["covers_json"] or "[]")
                    merged_t = merge_tracks(tracks, srv_tracks)
                    merged_c = merge_covers(covers, srv_covers)
                    conn.execute(
                        """
                        UPDATE playlists SET
                            name = ?,
                            playlist_type = ?,
                            covers_json = ?,
                            track_count = ?,
                            updated_at = ?,
                            tracks_json = ?
                        WHERE id = ?
                        """,
                        (
                            name,
                            ptype,
                            json.dumps(merged_c, ensure_ascii=False),
                            len(merged_t),
                            max(updated_at, existing["updated_at"]),
                            json.dumps(merged_t, ensure_ascii=False),
                            target_id,
                        ),
                    )
                conn.commit()

            self._send_json(
                200,
                {
                    "success": True,
                    "id": target_id,
                    "updatedAt": updated_at,
                },
            )
            return

        # 批量双向同步接口：POST /api/v1/sync
        # 客户端上报自身歌单与版本，服务端根据歌单名归一并做歌曲全量并集增量合并
        if path == "/api/v1/sync":
            client_playlists = payload.get("playlists", [])
            updated_ids = []

            with get_db(self.db_path) as conn:
                for p in client_playlists:
                    pid = str(p.get("id", "")).strip()
                    name = str(p.get("name", "")).strip()
                    if not name:
                        continue
                    ptype = p.get("playlistType", "aggregate")
                    client_covers = p.get("covers", [])
                    client_tracks = p.get("tracks", [])
                    client_updated = int(p.get("updatedAt", now))

                    # 通过歌单名称查找服务端现有同名歌单（忽略大小写与首尾空格）
                    existing = conn.execute(
                        "SELECT id, name, playlist_type, covers_json, track_count, updated_at, tracks_json FROM playlists WHERE LOWER(TRIM(name)) = LOWER(?)",
                        (name,),
                    ).fetchone()

                    if not existing:
                        # 服务端不存在，以客户端 ID 或时间戳新建
                        server_id = pid if pid else str(int(time.time() * 1000))
                        conn.execute(
                            """
                            INSERT INTO playlists (id, name, playlist_type, covers_json, track_count, updated_at, tracks_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                server_id,
                                name,
                                ptype,
                                json.dumps(client_covers, ensure_ascii=False),
                                len(client_tracks),
                                client_updated,
                                json.dumps(client_tracks, ensure_ascii=False),
                            ),
                        )
                        updated_ids.append(server_id)
                    else:
                        server_id = existing["id"]
                        server_updated = existing["updated_at"]
                        server_tracks = json.loads(existing["tracks_json"] or "[]")
                        server_covers = json.loads(existing["covers_json"] or "[]")

                        # 双向歌曲并集合并（保留两端添加的新歌，绝不丢失）
                        if client_updated >= server_updated:
                            merged_tracks = merge_tracks(client_tracks, server_tracks)
                            merged_covers = merge_covers(client_covers, server_covers)
                            final_updated = client_updated
                        else:
                            merged_tracks = merge_tracks(server_tracks, client_tracks)
                            merged_covers = merge_covers(server_covers, client_covers)
                            final_updated = server_updated

                        conn.execute(
                            """
                            UPDATE playlists SET
                                name = ?,
                                playlist_type = ?,
                                covers_json = ?,
                                track_count = ?,
                                updated_at = ?,
                                tracks_json = ?
                            WHERE id = ?
                            """,
                            (
                                name,
                                ptype,
                                json.dumps(merged_covers, ensure_ascii=False),
                                len(merged_tracks),
                                final_updated,
                                json.dumps(merged_tracks, ensure_ascii=False),
                                server_id,
                            ),
                        )
                        updated_ids.append(server_id)

                conn.commit()

                # 返回服务端全量归一后的歌单供客户端比对更新
                all_rows = conn.execute(
                    "SELECT id, name, playlist_type, covers_json, track_count, updated_at, tracks_json FROM playlists ORDER BY updated_at DESC"
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
        # 简化日志输出至标准错误输出，避免 IndexError
        try:
            msg = format % args
        except Exception:
            msg = " ".join(str(a) for a in args)
        sys.stderr.write(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {self.address_string()} - {msg}\n"
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
