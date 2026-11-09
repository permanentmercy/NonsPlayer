# 项目总体开发与演进计划 (Plan)

## 1. 项目概述
NonsPlayer 是一款基于 Tauri v2 (Rust + React) 的高音质流媒体与本地音乐播放器。支持桌面端（Windows/Linux/macOS）以及移动端（Android ARM64）。

## 2. 当前阶段目标
1. 解决跨平台（特别是 B 站独占二创音频）多端同步痛点，开发配套部署于路由器/私有服务器（`sync.example.com:17777`）的极轻量歌单同步服务。
2. 规范数据协议，支持无损同步包含 B 站专属音频的全平台聚合歌单。

## 3. 功能模块规划与进度追踪

| 功能模块 | 版本 | 目标与范围 | 状态 | 文档路径 | 结果产物 |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `bilibili-adapter` | `v1.0.0` | 预编译 B 站适配器资产引入、Android 原生资源随包物化挂载、环境构建与 APK 打包 | **已完成** | [bilibili-adapter/v1.0.0/plan.md](bilibili-adapter/v1.0.0/plan.md) | [bilibili-adapter/v1.0.0/result.md](bilibili-adapter/v1.0.0/result.md) |
| `bilibili-adapter` | `v1.0.1` | 同步上游契约（WIT 1.1.0 / Contract v2）、修复 `音乐服务不可用` 运行时链接错误并重构建 | **已完成** | [bilibili-adapter/v1.0.1/plan.md](bilibili-adapter/v1.0.1/plan.md) | [bilibili-adapter/v1.0.1/result.md](bilibili-adapter/v1.0.1/result.md) |
| `cloud-sync` | `v1.0.0` | 路由器专用轻量级歌单同步服务（Python/Go/Docker）及接口协议、部署配置规范 | **已完成** | [cloud-sync/v1.0.0/plan.md](cloud-sync/v1.0.0/plan.md) | [cloud-sync/v1.0.0/result.md](cloud-sync/v1.0.0/result.md) |
| `cloud-sync` | `v1.1.0` | 客户端云端双向同步引擎（PC & Android）、启动自动静默对齐、设置控制面板集成与 APK 打包 | **已完成** | [cloud-sync/v1.1.0/plan.md](cloud-sync/v1.1.0/plan.md) | [cloud-sync/v1.1.0/result.md](cloud-sync/v1.1.0/result.md) |
| `cloud-sync` | `v1.2.0` | 跨端歌单双向增量合并修复（歌曲去重合并、真实更新时间戳、多端 ID 漂移归一与服务端去重） | **已完成** | [cloud-sync/v1.2.0/plan.md](cloud-sync/v1.2.0/plan.md) | [cloud-sync/v1.2.0/result.md](cloud-sync/v1.2.0/result.md) |
| `windows-build` | `v1.0.0` | Windows Release 构建与打包修复（24核全开、Tauri工具链完整打包、替换验证与统一分发） | **已完成** | [windows-build/v1.0.0/plan.md](windows-build/v1.0.0/plan.md) | [windows-build/v1.0.0/result.md](windows-build/v1.0.0/result.md) |

---
*注：本项目开发计划与各版本执行产物依据团队规范持续同步更新于 `public/` 目录下。*
