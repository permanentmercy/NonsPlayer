# Windows Release 构建与打包修复实施方案 (v1.0.0)

## 1. 背景与目标
在替换 `D:\software\nons\Nons.exe` 为 `release-packages\Nons-Windows-x64-Release.exe` 之后，应用程序无法正常展现主窗口界面（无 UI，无法正常使用）。
经诊断：
1. 直接使用 `cargo build --release` 编译只会生成原生 Rust 二进制，不会经由 Tauri 完整工具链调用 `pnpm build` 打包前端，也不会注入 Tauri 所需的运行时资源映射表。
2. 在 Tauri v2 架构下，脱离 Tauri CLI 工具链（`scripts/tauri.mjs`）构建会导致 WebView 宿主初始化异常与资源挂载失效。
3. 验证发现，使用 `node scripts/tauri.mjs build` 完整构建的二进制能够正常唤起主窗口（`MainWindowHandle` 正常，窗口与页面完全正常交互）。

**目标**：
1. 启用本机 24 核心并行构建优化（`codegen-units = 24`，`CARGO_BUILD_JOBS = 24`）。
2. 使用 `node scripts/tauri.mjs build` 重新完成包含云同步（v1.2.0）与移动端搜索优化的完整 Windows 发行版构建（含独立 `.exe` 与安装包）。
3. 替换并验证 `D:\software\nons\Nons.exe` 能正常启动、显示窗口并建立云同步。
4. 同步更新 `release-packages/` 目录下的 Windows 构建包。

## 2. 实施步骤
1. **构建配置调优**：
   - 确认 `app/src-tauri/Cargo.toml` 中 `codegen-units = 24` 与 `lto = "thin"`。
   - 配置环境：`$env:LIBCLANG_PATH="D:\github\NonsPlayer\.local\llvm"`, `$env:CARGO_BUILD_JOBS="24"`。
2. **执行正式构建**：
   - 执行 `node scripts/tauri.mjs build --ci --bundles nsis`，同步生成最新可执行文件及安装程序。
3. **验证与测试**：
   - 替换 `D:\software\nons\Nons.exe`，启动进程并检查 `MainWindowHandle`、窗口标题及运行日志。
   - 验证无异常崩溃，确认 WebView 与云同步服务连接正常。
4. **统一分发与归档**：
   - 将验证通过的最新 Windows Release 可执行文件和安装包放置于 `release-packages/` 目录下。
   - 记录执行产物 `result.md`，更新全局 `public/plan.md`。
