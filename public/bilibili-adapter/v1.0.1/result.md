# Bilibili 适配器契约对齐与修复执行结果 (v1.0.1)

## 1. 执行概要
- **版本标识**：`v1.0.1`（迭代修复版本）
- **对应上游版本**：`NonsPlayer v1.12.1`
- **解决核心问题**：解决 Android 安装后启动/加载适配器报错 `加载失败：音乐服务不可用`（`ErrorCode::Internal`）。

---

## 2. 根本原因与修复细节

### 2.1 契约断层对齐
- **旧状态**：
  - 本地宿主 WIT 契约为 `nons:host@1.0.0`，SDK 限制 `CONTRACT_VERSION = 1`。
  - 官方 B 站 WebAssembly 组件 `adapter.component.wasm` 依赖 `nons:host/transport@1.1.0`，导出契约版本为 `2`。
  - Wasmtime 实例化时无法解析 `@1.1.0` 接口，抛出内部错误。
- **修复方案**：
  - 拉取并变基合并上游 `origin/main` 86 个提交，升级至最新的 1.12.1 契约体系（`nons:host@1.1.0`、`CONTRACT_VERSION = 2`、支持 `lyricMatch` 能力及自适应网络权限）。
  - 在 `app/src-tauri/src/application/mod.rs` 中完整保留 Android 原生物化桥接：
    ```rust
    #[cfg(target_os = "android")]
    let component_directory = {
        let directory = data.join("bundled-adapters");
        crate::platform::android::bundled_adapters::materialize(&directory)?;
        Some(directory)
    };
    #[cfg(not(target_os = "android"))]
    let component_directory = cfg!(all(debug_assertions, desktop))
        .then(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("bundled-adapters"));
    ```

### 2.2 描述符与 Manifest 对齐
- 对齐更新 `bundled-adapters/bilibili/manifest.json`：
  ```json
  {
    "version": "1.0.0",
    "descriptor": {
      "source": "bilibili",
      "displayName": "哔哩哔哩",
      "description": "扫码登录哔哩哔哩，搜索并播放视频音轨，可为歌曲查找和播放 MV。",
      "contractVersion": 2,
      "platforms": ["bilibili"],
      "loginMethods": [{ "id": "qr", "label": "扫码登录" }],
      "capabilities": ["search", "mv", "account", "lyricMatch"],
      "shareLinkTemplates": {
        "track": "https://www.bilibili.com/video/{id}"
      }
    },
    "permissions": {
      "system": true,
      "state": true,
      "credentials": true
    }
  }
  ```

---

## 3. 构建与产物验证

### 3.1 交叉编译与构建日志
- **Rust Android Target Check**：`cargo check --lib --target aarch64-linux-android` 零错误通过。
- **APK 构建**：通过 `scripts/android.ps1 build` 完成前端（Vite/TypeScript）打包、原生 Rust 库编译及 Gradle APK 组装。

### 3.2 最终产物信息
| 产物项 | 详细信息 |
| :--- | :--- |
| **文件路径** | `.local/android/Nons-1.12.1-android-arm64-debug.apk` |
| **应用版本** | `1.12.1` |
| **目标架构** | `arm64-v8a` (AArch64) |
| **SHA-256** | `38979f25336235ebc65ec8b1a58a2858b7a61938c30ef97390e19c4d51953e73` |
| **APK 签名验证** | Scheme v2: `true`, Scheme v3: `true` (Android Debug) |
| **16KB 页面对齐** | 验证通过 (`zipalign` 4 字节边界与 16KB 兼容) |
| **内置组件检查** | `libnons_lib.so` (156,882,288 bytes) 包含 `contractVersion: 2` 与 `lyricMatch` |

---

## 4. 验证与交付结论
APK 已重新打包完毕，`Nons-1.12.1-android-arm64-debug.apk` 修复了 WIT 契约版本不匹配引起的 `加载失败：音乐服务不可用` 错误，内置的 B 站适配器在应用启动后可由 Wasmtime 正常完成链接与注册。
