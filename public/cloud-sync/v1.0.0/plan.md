# 自建云端歌单同步服务与多端接入计划 (v1.0.0)

## 1. 需求与目标
- **用户环境配置**：
  - 域名：`sync.example.com`
  - 目标端口：`127.0.0.1:17777`（路由器已完成反向代理/内网绑定）
- **核心目标**：
  1. 编写运行在路由器上的高可用、极低资源占用的专用歌单同步服务（支持 OpenWrt、Docker、Linux Systemd、Python3、Node、Go 等多种部署形态）。
  2. 服务提供标准 REST API，能够完整持久化包含跨平台音源（网易云、哔哩哔哩 B 站专属音频、本地歌曲条目等）的聚合歌单及完整曲目元数据。
  3. 提供多端接入方案与 API 使用指南，使 PC 与手机端的聚合歌单能够直接通过路由器完成无缝多端同步。

## 2. 执行计划步骤
- [x] **步骤一：路由器同步服务端实现 (`sync-server/`)**
  - 设计 REST API 规范（`GET /health`、`GET /api/v1/playlists`、`GET /api/v1/playlists/:id`、`POST /api/v1/playlists`、`POST /api/v1/sync`、`DELETE /api/v1/playlists/:id`）。
  - 实现零依赖 Python 3 服务端（`sync-server/server.py`，内置 SQLite 存储，单文件免安装，内存占用 < 15MB，适配 OpenWrt）。
  - 实现单静态二进制 Go 服务端（`sync-server/main.go`，内存占用 < 5MB，适合无 Python 环境的路由器）。
  - 配套部署配置：Docker 镜像定义（`Dockerfile`、`docker-compose.yml`）、OpenWrt init.d 脚本与 Systemd 服务文件。
  - 编写详细部署与运行指南（`sync-server/README.md`）。
- [x] **步骤二：服务端端到端集成测试**
  - 编写并执行自动化测试套件（`test_server.py`），验证 CORS 跨域、Token 认证、歌单增删改查、以及 B 站二创歌曲与网易云混合歌曲的无损存储与读取。全部通过（100% 测试通过）。
- [x] **步骤三：产物归档与交付文档编写**
  - 在 `result.md` 中完整记录服务端使用与部署指南、接口协议格式及路由器上线命令。

## 3. 当前状态
- **已全部完成 (Done)**。详细产物与使用说明参见同目录下 [result.md](result.md)。
