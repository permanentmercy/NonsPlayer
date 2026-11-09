# NonsPlayer 路由器轻量级歌单同步服务

本服务专为部署在路由器（如 OpenWrt、iStoreOS、Padavan）、软路由或局域网 NAS 上设计，提供高可靠、低内存（< 15MB）的歌单同步接口。

它能够将 NonsPlayer 的**聚合歌单（包含网易云歌曲、哔哩哔哩 B 站特有音频/MV、本地歌曲等全平台歌曲及封面元数据）**持久化存储并提供多端双向同步，彻底摆脱单一平台云端无法存储第三方歌曲的限制。

---

## 快速配置参考

- **域名映射**：`sync.example.com` → `127.0.0.1:17777`
- **监听端口**：`17777`
- **数据格式**：标准 JSON RESTful API，带 CORS 支持

---

## 部署方式一：OpenWrt 路由器（推荐原生 Python 3）

OpenWrt 官方软件源自带 Python 3 和 SQLite3，无需编译即可运行。

### 1. 安装 Python 环境（若尚未安装）
登录路由器终端（SSH）：
```sh
opkg update
opkg install python3 python3-sqlite3
```

### 2. 拷贝脚本
将 `server.py` 拷贝至路由器目录 `/etc/nons-sync/server.py`：
```sh
mkdir -p /etc/nons-sync
# 上传 server.py 到 /etc/nons-sync/
chmod +x /etc/nons-sync/server.py
```

### 3. 开机自启服务配置
将 `nons-sync.init` 拷贝为 `/etc/init.d/nons-sync` 并赋予执行权限：
```sh
chmod +x /etc/init.d/nons-sync
/etc/init.d/nons-sync enable
/etc/init.d/nons-sync start
```

检查运行状态：
```sh
/etc/init.d/nons-sync status
curl http://127.0.0.1:17777/health
```

---

## 部署方式二：Docker / Docker Compose

如果你的路由器（如 iStoreOS、Armbian 或软路由）支持 Docker：

```sh
cd sync-server
docker compose up -d
```

数据将保存在当前目录下的 `./data/nons_playlists.db` 中。

---

## 部署方式三：Linux Systemd（Debian / Armbian / Ubuntu）

```sh
mkdir -p /opt/nons-sync
cp server.py /opt/nons-sync/
cp nons-sync.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now nons-sync
systemctl status nons-sync
```

---

## 接口测试验证

服务启动后，可在任意终端执行以下测试：

### 1. 服务健康检查
```bash
curl http://127.0.0.1:17777/health
# 或者通过你的外网域名测试
curl https://sync.example.com/health
```
响应示例：
```json
{
  "status": "ok",
  "service": "NonsPlayer Playlist Sync Server",
  "version": "1.0.0",
  "playlistsCount": 0,
  "timestamp": 1731145200
}
```

### 2. 获取所有同步歌单
```bash
curl https://sync.example.com/api/v1/playlists
```

### 3. 保存/更新歌单
```bash
curl -X POST https://sync.example.com/api/v1/playlists \
  -H "Content-Type: application/json" \
  -d '{
    "id": "aggregate_test_1",
    "name": "我的全平台歌单",
    "tracks": [
      {
        "key": "bilibili:BV1xx411c7mD:0",
        "title": "B站独占二创曲",
        "artists": [{"name": "UP主"}],
        "source": {"kind": "track", "track": {"source": "bilibili", "id": "BV1xx411c7mD"}}
      }
    ]
  }'
```

---

## 安全认证（可选）

如需给同步服务增加密码保护，防止未授权访问：
- 启动时指定参数 `--token 你的自定义密钥`，或设置环境变量 `SYNC_TOKEN=你的自定义密钥`；
- 开启后，客户端在请求头中携带 `Authorization: Bearer 你的自定义密钥` 或 `X-Sync-Token: 你的自定义密钥` 即可完成认证。
