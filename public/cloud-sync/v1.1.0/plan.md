# 客户端云端双向同步与多端自动同步集成计划 (v1.1.0)

## 1. 需求与目标
- **背景**：已在路由器成功部署并持续运行自建歌单同步服务（域名：`https://sync.example.com`）。
- **用户核心诉求**：“现在我的 PC 和移动端怎么自动同步”
- **核心目标**：
  1. 在 NonsPlayer 客户端（Rust Tauri 层）内置云端同步客户端引擎，支持将全量聚合歌单及条目（包括网易云、B 站二创歌曲、本地歌曲等）自动推拉并同步至本地 SQLite 数据库。
  2. 实现全自动静默对齐：PC 端与 Android 手机端在应用冷启动/就绪时，后台自动向路由器同步服务发起双向增量同步。
  3. 前端提供直观的配置与交互界面（“设置 → 网络与服务 → 路由器自建云端同步”），默认内置并预设域名 `https://sync.example.com`，支持一键“立即双向同步”与状态反馈。
  4. 重新编译生成全平台（重点为 Android ARM64 APK）产物，确保两端开箱即用。

## 2. 执行计划步骤
- [x] **步骤一：Rust 核心云同步模块实现与命令注册**
  - 在 `app/src-tauri/src/aggregate/` 下新增 `cloud.rs`，实现 `cloud_sync`、`cloud_sync_config`、`set_cloud_sync_config`。
  - 在 `store.rs` 补充 `all_playlist_tracks` 与 `apply_cloud_playlist`，实现双向歌单合并与原子写入，并发送 `aggregate-playlist-updated` / `local-library-updated` 事件。
  - 在 `application/mod.rs` 注册 Tauri 命令，并在应用启动 3 秒后自动触发后台静默同步。
- [x] **步骤二：前端交互界面开发**
  - 在 `features/settings/network-service/` 创建独立组件 `cloud-sync-card.tsx`。
  - 在 `network-service-page.tsx` 中嵌入卡片，支持查看同步状态、开启/关闭自动同步、自定义服务器地址以及手动双向同步。
- [x] **步骤三：产物编译与移动端打包**
  - 前端通过 TypeScript 校验与 Vite 生产构建。
  - Android 端交叉编译并打包最新 debug APK 到 `.local/android/Nons-1.12.1-android-arm64-debug.apk`。
- [x] **步骤四：产物交付与多端操作指引**
  - 编写详细操作手册与机制说明，向用户清晰解释 PC 和手机端的自动化同步流程与手动同步方法。

## 3. 当前状态
- **已全部完成 (Done)**。详细执行产物与操作说明参见同目录下 [result.md](result.md)。
