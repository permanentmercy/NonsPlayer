# Bilibili 适配器 Android 随包发布子计划 (v1.0.0)

## 1. 需求与目标
- **目标**：将官方维护的 B 站适配器组件（`adapter.component.wasm` + `manifest.json`）内置随包发布到 Android APK 中。
- **业务效果**：在 Android 手机上安装 APK 后，开箱即支持 B 站歌曲搜索、各音质音频解析播放、扫码登录及 MV 关联播放，无需通过移动端商店或文件选择器动态导入。

## 2. 执行计划步骤
- [x] **阶段一：资产获取与就绪**
  - 下载官方 B 站适配器预编译产物 `adapter-bilibili-1.0.0-cc6d7dfec4eb99e3.zip` 并校验 SHA-256（`cc6d7dfec4eb99e3dd949530df09b0a38bfe9710b76308634d3d43591ae87778`）。
  - 解压部署至 `app/src-tauri/bundled-adapters/bilibili/`。
- [x] **阶段二：Android 端原生资源嵌入与物化接线**
  - 编写 `app/src-tauri/src/platform/android/bundled_adapters.rs` 中的资源物化逻辑（`materialize`），通过 `include_bytes!` 在 Android 二进制中固化 B 站适配器文件。
  - 在 `app/src-tauri/src/platform/android/mod.rs` 中导出 `bundled_adapters` 模块。
  - 在 `app/src-tauri/src/application/mod.rs` 启动链路中完成接线：Android 环境下启动时调用 `materialize` 物化释出到应用私有目录 `$APP_DATA/bundled-adapters/`，并无缝交由 `prepare_components` 与 `load_components` 自动发现注册。
- [x] **阶段三：构建环境检查与补全**
  - 补齐 Rust 目标工具链：`rustup target add aarch64-linux-android`。
  - 配置 `JAVA_HOME` 环境指向本地 Adoptium JDK 17。
  - 部署 Android commandline-tools (`sdkmanager.bat`)，补全 Platform 37、Build-Tools 37。
  - 安装并就位 Android NDK 27.2（`.local/android/sdk/ndk/27.2.12479018`）。
  - 安装前端依赖 `pnpm install` 并验证前端产物编译。
  - 执行 `cargo check --target aarch64-linux-android` 验证 Android 架构编译（0 错误通过）。
- [x] **阶段四：执行打包与 APK 验证**
  - 执行完整构建：`scripts/android.ps1 build` 构建 ARM64 APK。
  - 校验离线前端资源与 ARM64 原生库（`verify-android-apk.py` 通过）。
  - 校验 16 KB 页面对齐（`zipalign -c -P 16 4` 通过，满足 Android 15 要求）。
  - 校验数字签名（v2 / v3 签名验证通过）。
  - 二进制检查确认 `libnons_lib.so` 中已完整内置 B 站适配器元数据与 wasm 组件。
  - 产物与哈希就绪于 `.local/android/` 目录。

## 3. 当前状态
- **已全部完成 (Done)**。详细执行成果与产物说明参见同目录下 [result.md](result.md)。
