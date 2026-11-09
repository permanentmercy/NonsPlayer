# Bilibili 适配器契约版本对齐与加载修复计划 (v1.0.1)

## 1. 问题背景与分析
- **问题现象**：在手机上安装 v1.0.0 打包出的 APK 后，打开适配器设置或启动时报错提示 `加载失败：音乐服务不可用`。
- **根本原因排查**：
  1. `加载失败：音乐服务不可用` 映射自 Rust 内部抛出的 `ErrorCode::Internal`。
  2. 官方预编译的 `adapter.component.wasm` 编译于 `nons:host/transport@1.1.0` 体系，其内部导出的元数据声明了 `contractVersion: 2`、能力声明为 `["search", "mv", "account", "lyricMatch"]`。
  3. 此前本地分支落后上游 `origin/main` 86 个提交，本地代码库仍处于旧版契约 `nons:host@1.0.0` 及 `CONTRACT_VERSION = 1`。
  4. Wasmtime 在运行时尝试链接 `@1.1.0` 导入接口时失败，并被捕获为 `ErrorCode::Internal`。
  5. 此外，旧 `manifest.json` 写为了 `contractVersion: 1` 和 `capabilities: ["lyrics"]`，导致与 WASM 内部声明冲突。

## 2. 执行计划步骤
- [x] **步骤一：同步上游契约与代码库升级**
  - 同步变基上游最新提交至 `origin/main`（包含 1.12.1 契约升级、`nons:host@1.1.0` 接口支持、网络权限简化、歌词匹配 `lyricMatch` 等）。
  - 合并本地 Android 随包资源释放（`materialize`）逻辑至 `app/src-tauri/src/application/mod.rs` 与 `platform/android/`。
- [x] **步骤二：适配器元数据精准对齐**
  - 根据 `adapter.component.wasm` 提取出的真实元数据更新 `bundled-adapters/bilibili/manifest.json`：
    - `contractVersion: 2`
    - `capabilities: ["search", "mv", "account", "lyricMatch"]`
    - 清理冗余字段，适配上游简化的权限模型。
- [x] **步骤三：交叉编译与 Rust 单元验证**
  - 验证 Android aarch64 交叉编译：`scripts/android.ps1 -Task check` 零错误通过。
  - 验证 `libnons_lib.so` 原生库中各字段与契约完全对齐。
- [x] **步骤四：Android 重新打包与产物校验**
  - 使用 Adoptium JDK 17、Android SDK 37、NDK 27.2 执行 `scripts/android.ps1 build` 重新打包。
  - 校验离线前端资源与 ARM64 原生库。
  - 校验 16 KB 页面对齐与 APK v2/v3 签名。
  - 输出产物至 `.local/android/Nons-1.12.1-android-arm64-debug.apk`。

## 3. 当前状态
- **已全部完成 (Done)**。详细执行成果与产物说明参见同目录下 [result.md](result.md)。
