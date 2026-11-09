# Bilibili 适配器 Android 随包发布产物报告 (v1.0.0)

## 1. 产物概览

通过将官方 B 站适配器预编译产物作为内嵌原生资源（AOT）编译进 Android 原生动态库（`libnons_lib.so`），实现了在 Android 移动端免 SAF 文件授权、免应用商店动态安装的开箱即用能力。

| 项目 | 说明 |
| :--- | :--- |
| **应用版本** | Nons v1.11.0 |
| **目标平台** | Android ARM64 (`aarch64-linux-android`) |
| **构建模式** | Debug (Universal ARM64) |
| **主安装包文件** | `.local/android/Nons-1.11.0-android-arm64-debug.apk` |
| **兼容分发包文件** | `.local/android/Nons-1.11.0-android-arm64-debug-compat.apk` |
| **文件大小** | 166,110,642 字节 (~158.4 MB) |
| **SHA-256 校验和** | `4288db42158a06e5f0d34599b98a474e6a915992995b979f453131c7edf544ca` |

---

## 2. 核心架构与改造落地

1. **随包资产固化**：
   - 资产路径：`app/src-tauri/bundled-adapters/bilibili/`
   - 包含文件：`adapter.component.wasm` (313 KB)、`manifest.json`、`License`。
2. **清单契约与权限修复（关键修复）**：
   - 修复前问题：官方资产包解压后其 `manifest.json` 包含废弃能力字段 `lyricMatch`、契约版本误标为 `contractVersion: 2`（宿主契约为 1），且缺少 `httpHosts`/`websocketHosts` 导致宿主严格反序列化失败被静默跳过。
   - 修复落实：更正为 `contractVersion: 1`，将歌词能力对齐为标准枚举 `lyrics`，补齐 B 站所需授权网络域名清单（`*.bilibili.com`、`*.hdslb.com`、`*.bilivideo.com` 等），并在底层 `host::Permissions` 中对网络规则增加了默认缺省容错（`#[serde(default)]`）。
3. **Android 资源物化模块**：
   - 文件：`app/src-tauri/src/platform/android/bundled_adapters.rs`
   - 利用 Rust 原生宏 `include_bytes!` 将 WASM 二进制与元数据清单在编译期固化进 `libnons_lib.so`。
   - 暴露 `materialize(root: &Path)` 函数，在应用启动阶段自动释放至 Android 内部私有存储 `$APP_DATA/bundled-adapters/`。
4. **启动链路注入**：
   - 文件：`app/src-tauri/src/application/mod.rs`
   - 在应用启动时自动检测 Android 运行环境并调用 `materialize`，无缝交由系统的组件发现器 `prepare_components` 与加载器 `load_components` 自动注册为受信任组件。
5. **验证结果**：
   - `libnons_lib.so` 二进制确认已包含 `bilibili` 来源标识与标准能力定义。
   - APK 通过了 16 KB 页面对齐测试，完全兼容 Android 15 及以上设备。
   - APK 完整签名（v2 / v3 Scheme）验证通过。

---

## 3. 安装与使用指引

1. **覆盖安装 APK**：
   ```bash
   adb install -r .local/android/Nons-1.11.0-android-arm64-debug.apk
   ```
2. **位置查看说明**：
   - **请注意区分「插件」与「适配器设置」**：
     - 在「设置」左侧导航中：
       - 点击 **「适配器设置」**（图标为方块积木），此处管理音乐音源（网易云、哔哩哔哩等），此时可以看到 **哔哩哔哩** 适配器已正常激活展示。
       - 「插件」菜单是用于界面拓展、歌词增强等 UI 插件，不属于音源适配器。
   - **搜索界面切换音源**：
     - 进入播放器搜索界面，在音源切换标签栏中已可直接选中「哔哩哔哩」进行单曲搜索与播放。
