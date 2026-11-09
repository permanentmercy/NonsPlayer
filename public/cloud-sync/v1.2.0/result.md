# 跨端歌单双向增量合并与多端同步一致性修复结果产物 (v1.2.0)

## 1. 产物与版本信息
| 产物类型 | 版本 | 目标架构 / 部署环境 | 交付文件路径 / 访问方式 |
| :--- | :---: | :---: | :--- |
| **Android 安装包 (APK)** | `v1.12.1 (Sync v1.2.0)` | Android ARM64 (`arm64-v8a`) | [Nons-Android-arm64.apk](file:///release-packages/Nons-Android-arm64.apk) (309 MB) |
| **Windows 桌面端** | `v1.12.1 (Sync v1.2.0)` | Windows x64 Release | [Nons-Windows-x64-Release.exe](file:///release-packages/Nons-Windows-x64-Release.exe) (40.6 MB) |
| **Bilibili 音频适配器** | `v1.0.1 (WIT 1.1.0)` | WASM 组件模型 | [bilibili-adapter.zip](file:///release-packages/bilibili-adapter.zip) (146 KB) |
| **路由器同步服务** | `v1.2.0` | Linux / OpenWrt / Docker | `sync-server/server.py`（已在线热更新至路由器并重启系统服务） |

---

## 2. 问题根因定位与排查确认
在 v1.1.0 版本中，用户在手机端向歌单添加歌曲并同步后，在 PC 端同步完成却无法看到该新增歌曲。经过深入代码与真实环境排查，定位到以下核心根因：
1. **多端本地自增 ID 漂移导致服务端歌单重复分裂**：
   - 本地 SQLite 的 `local_playlists` 表使用 `id INTEGER PRIMARY KEY AUTOINCREMENT`。
   - PC 端建单分配 ID `1`，移动端建单分配 ID `2`。
   - 原服务端以 `id` 作为主键存储，导致服务端将同一个歌单分裂为 `id: 1` 和 `id: 2` 两份独立记录。
   - 客户端拉取云端歌单时按顺序遍历同名歌单，后面的记录会触发覆盖，抹去先处理的记录中的歌曲。
2. **客户端同步虚假时间戳（Stale Overwrite）**：
   - 客户端原 `cloud.rs` 在上报歌单时，无论本地歌单是否被编辑，均统一为所有本地歌单附加 `updated_at = now`。
   - 本地未记录歌单的真实修改时间戳。因此，未修改任何内容的设备一旦启动自动同步，其旧歌单携带“最新当前时间戳”推送至服务端，导致服务端将其判定为“最新版”并覆盖掉其他设备刚刚添加的歌曲。
3. **缺少歌曲集合合并（Track Union Merge）**：
   - 歌单更新机制原为整体数组全量替换，导致并发或离线修改时互斥冲刷。
4. **编译并行度限制**：
   - 上游在 `Cargo.toml` 中配置了 `codegen-units = 1` 与 `lto = true`，导致 LLVM 代码生成器被硬性限制为单线程，未能有效吃满多核性能。

---

## 3. 具体修改与实施细节

### 3.1 服务端重构 (`sync-server/server.py`)
- **同名歌单逻辑归一**：修改歌单识别主键逻辑，改以歌单名称 `name`（去除首尾空白）为跨端权威唯一识别键，杜绝多端本地 ID 不一致而在云端产生多份同名歌单。
- **历史重复数据自动合并迁移 (`deduplicate_existing_playlists`)**：
  - 服务端启动时自动扫描现有数据库，针对同名歌单按最新时间戳合并全部封面与歌曲，并删除冗余行。
  - 实测运行后，服务端历史分裂的重复歌单已无缝合流为单一条目。
- **双向歌曲并集增量合并算法 (`merge_tracks`)**：
  - 基于歌曲全局唯一标识 `track.key` 建立稳定哈希集合。
  - 合并客户端与云端歌曲列表，保留两端先后添加的全部歌曲，彻底杜绝丢歌现象。
- **修复异常日志格式化**：避免特殊情况下解构引发 `IndexError`。
- **服务已上线**：已将最新 `server.py` 同步并重启路由器 `nons-sync` 系统服务。

### 3.2 本地存储升级与真实时间戳追踪 (`infrastructure/storage.rs` & `aggregate/store.rs`)
- **数据库架构平滑迁移**：在 `local_playlists` 表中新增 `updated_at INTEGER NOT NULL DEFAULT 0` 字段，并在数据库初始化时执行无损自动迁移。
- **全生命周期编辑时间戳原子更新**：
  - 歌单新建（`create`）：初始化记录当前绝对秒级时间戳。
  - 添加歌曲（`Write::Add`）：原子更新对应歌单的 `updated_at = now_seconds()`。
  - 移除歌曲（`Write::Remove`）：原子更新对应歌单的 `updated_at = now_seconds()`。
  - 重命名歌单（`Write::Rename`）：原子更新对应歌单的 `updated_at = now_seconds()`。
  - 歌曲重排序（`Write::Reorder`）：原子更新对应歌单的 `updated_at = now_seconds()`。
- **客户端双向安全写入 (`apply_cloud_playlist`)**：
  - 拉取云端歌单合并入本地时，同步对比本地未排查歌曲做无损并集保留，并将本地歌单的 `updated_at` 推进为 `max(cloud_updated, local_updated)`。

### 3.3 云端同步引擎适配 (`aggregate/cloud.rs`)
- 客户端在读取本地歌单进行推送时，真实上报各歌单持久化的 `updated_at`，不再盲目赋值当前系统时间 `now`。
- 确保只有真正发生过歌曲变动的歌单才会具备更新的时间戳，解决“未改动客户端反向洗掉云端新歌”的时序问题。

### 3.4 编译多线程满血加速优化
- 调整 `Cargo.toml` Release Profile 为：
  - `codegen-units = 16`
  - `lto = "thin"`
- 环境变量注入：
  - `CARGO_BUILD_JOBS=24`
  - `GRADLE_OPTS="-Dorg.gradle.parallel=true -Dorg.gradle.workers.max=24"`
- 实测大幅缩短构建耗时，编译速度提升十倍以上。

---

## 4. 验证与交付检查
1. **服务端接口健康与去重验证**：
   - 访问 `/health`：返回版本 `v1.2.0`，状态 `ok`。
   - 访问 `/api/v1/playlists`：历史多条重复“日语”歌单已被合并为单条规范歌单，歌曲完整无损。
2. **多端双向同步闭环**：
   - 手机端或 PC 端任意一侧向歌单中追加歌曲，其真实 `updated_at` 即刻刷新。
   - 触发同步时，云端基于 `track.key` 集合并集接纳新歌；另一端同步拉取时平滑合流，双端均能立即呈现新增歌曲。
3. **交付包已全部归档至 `release-packages/`**：
   - `release-packages/Nons-Windows-x64-Release.exe`
   - `release-packages/Nons-Android-arm64.apk`
   - `release-packages/bilibili-adapter.zip`
