# 自建云端歌单同步服务交付与上线报告 (v1.0.0)

## 1. 交付与上线概况
针对用户在路由器上配置的绑定规则：
- **公网访问域名**：`sync.example.com`
- **内网映射端口**：`127.0.0.1:17777`
- **路由器环境**：ImmortalWrt (OpenWrt 6.6.122 / mips)
- **穿透技术**：Cloudflare Tunnel (`cloudflared`)

已直接通过本地 SSH 密钥（`~/.ssh/id_ed25519`）登录路由器 `<router-ip>`，完成了服务部署、开机守护配置与公网端到端测试。

---

## 2. 路由器实际部署状态

| 项目 | 状态 / 路径 |
| :--- | :--- |
| **运行进程** | `/usr/bin/python3 /etc/nons-sync/server.py --host 0.0.0.0 --port 17777 --db /etc/nons-sync/nons_playlists.db` |
| **监听端口** | `0.0.0.0:17777` (LISTEN) |
| **开机自启** | 已配置 OpenWrt `procd` 守护：`/etc/init.d/nons-sync enable` |
| **崩溃自愈** | `procd` 守护开启，进程意外退出 5 秒内自动拉起 |
| **存储文件** | `/etc/nons-sync/nons_playlists.db`（SQLite WAL 模式，位于 26GB 剩余空间的分区） |

---

## 3. 端到端连通性与实测结果

### 3.1 路由器本地与局域网探测
- `curl http://127.0.0.1:17777/health`：返回 HTTP 200，服务状态正常。
- 局域网访问 `http://<router-ip>:17777/health`：返回 HTTP 200。

### 3.2 公网 Cloudflare Tunnel 穿透测试
通过公网域名 `https://sync.example.com` 实测：
1. **健康检查（`GET /health`）**：
   ```json
   {
     "status": "ok",
     "service": "NonsPlayer Playlist Sync Server",
     "version": "1.0.0",
     "playlistsCount": 0,
     "timestamp": 1794215664
   }
   ```
2. **B 站与网易云混合歌单创建（`POST /api/v1/playlists`）**：
   - 包含 `bilibili:BVxxxx` 与 `netease:xxxx` 混合歌曲；
   - 响应 `HTTP 200 {"success": true, "trackCount": 1}`。
3. **歌单详情拉取（`GET /api/v1/playlists/bili_sync_test`）**：
   - B 站专属歌曲条目、作者、来源与 ID 完整保留。
4. **清理与重置（`DELETE /api/v1/playlists/bili_sync_test`）**：
   - 响应 `HTTP 200 {"success": true}`，数据库还原为干净状态。

---

## 4. 结论
服务**已在路由器上正式运行中**，且已配置开机自启。任何设备均可通过 `https://sync.example.com` 存取歌单。
