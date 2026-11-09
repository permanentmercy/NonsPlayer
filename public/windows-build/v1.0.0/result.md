# Windows Release 构建与打包修复实施结果 (v1.0.0)

## 1. 任务背景与问题排查
用户在将 `release-packages/Nons-Windows-x64-Release.exe` 替换至本地安装目录 `D:\software\nons\Nons.exe` 后，反馈无法正常使用。

### 根本原因定位
1. **构建工具链脱节**：
   - 此前为了加速构建，直接调用了 `cargo build --manifest-path app/src-tauri/Cargo.toml --release`。
   - 直接调用 Cargo 不会触发 Tauri CLI 注入的前置构建钩子（`beforeBuildCommand: pnpm build`），且跳过了 Tauri v2 针对 Windows 平台的运行时资源清单与 Webview2 宿主资源协议绑定。
   - 导致生成的二进制在启动时，虽然后台进程存活，但 WebView2 无法正常装载前端资源，主窗口句柄未创建（`MainWindowHandle = 0`），前端关键初始化指令（如 `aggregate_playlists`）无法触发。
2. **正确构建路径**：
   - 必须通过 Tauri 包装构建脚本 `node scripts/tauri.mjs build --no-bundle --ci`，完整执行 Vite 生产打包及 Tauri 资源嵌入。

---

## 2. 优化与实施措施

1. **并行构建优化**：
   - 针对本机 24 个逻辑处理器核心，在 `app/src-tauri/Cargo.toml` 中配置 `codegen-units = 24`，并设定环境变量 `$env:CARGO_BUILD_JOBS = "24"`，充分发挥多核心吞吐能力。
2. **完整构建执行**：
   - 配置环境：`$env:LIBCLANG_PATH="D:\github\NonsPlayer\.local\llvm"`, `$env:CARGO_BUILD_JOBS="24"`。
   - 调用 `node scripts/tauri.mjs build --no-bundle --ci` 完成完整构建，耗时 12 分 41 秒，生成 48.25MB 的生产 Release 二进制文件。
3. **替换与实机验证**：
   - 将产物同步至 `release-packages/Nons-Windows-x64-Release.exe`，并同时覆盖至 `D:\software\nons\Nons.exe`。
   - 启动测试 `D:\software\nons\Nons.exe`，验证结果：
     - `MainWindowHandle`：正常分配并创建（如 `5246752`）。
     - `MainWindowTitle`：正常显示为音乐主窗口。
     - 运行日志：前端与 Rust 后端无缝建立通信，正常触发 `aggregate_playlists`、适配器 profile 获取、歌单列表渲染与自启动云同步检查。
     - 无任何阻塞崩溃异常。

---

## 3. 产物交付

| 产物名称 | 文件路径 | 文件大小 | 校验与状态 |
| :--- | :--- | :--- | :--- |
| **Windows x64 Release** | `release-packages/Nons-Windows-x64-Release.exe` | 48,257,024 字节 (~48.25MB) | 已实机测试验证，窗口与功能完全正常 |
| **Android ARM64 Release** | `release-packages/Nons-Android-arm64.apk` | 324,690,891 字节 (~309MB) | 完整集成 B 站适配器、云同步与移动端搜索 |
| **Bilibili Adapter** | `release-packages/bilibili-adapter.zip` | 146,095 字节 (~142KB) | WIT 1.1.0 契约对齐版 |
