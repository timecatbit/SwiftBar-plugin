# OpenCodex Token 面板

SwiftBar 菜单栏插件，以原生 AppKit 面板汇总 OpenCodex 和本机 Claude Code 的使用情况。维护基线为 **4.10.2**。

## 功能

- Summary 汇总费用估算、Token、请求数；OpenCodex 和 Claude Code 分开显示。
- 范围默认为当天，可下拉选择近 24 小时、近 7 天、近 30 天、本周、本月、全部。
- 共用趋势图显示总量和两个来源；当天从首次调用前的短零线开始。
- 主页显示 DeepSeek 余额、Codex 账户可用量、Komari 状态与应用更新数量。
- 侧栏按内容宽度展示，悬停展开；右键保留 SwiftBar 原生管理菜单。
- OpenCodex 每小时检查稳定版，有更新时自动安装并重启，确认健康后通知；失败延后重试。
- Claude 桌面版、ChatGPT 桌面版和 Claude Code 每 6 小时检查，只提醒，不自动安装。

费用是 Token 的 API 等值估算，不代表订阅账单。没有定价的数据保留未计价标记。

## 环境

- macOS 13 或更新版本、SwiftBar、Python 3.9+、Xcode Command Line Tools（含 `swiftc`）。
- 本机 OpenCodex 管理接口；认证令牌从现有 `~/.opencodex/admin-api-token` 读取。
- Claude Code 用量来自 `~/.claude/projects`，只索引用量元数据，不复制对话正文。
- 本机已验证 SwiftBar 2.1.2 build 623 的标题点击修复。macOS 26 上请使用包含该修复的版本。

## 安装与更新

克隆仓库并进入 `opencodex/` 插件目录：

```sh
git clone https://github.com/timecatbit/swiftbar-token-monitor.git
cd swiftbar-token-monitor/opencodex
cp config.example.sh config.local.sh
# 编辑 config.local.sh，填写自己的 Komari 地址。
# 不使用 Komari 时，删除或注释该配置行。
python3 scripts/check.py
python3 scripts/install.py --plugin-dir '/你的/SwiftBar插件目录'
```

安装脚本会编译并本地签名原生面板，备份上一版，再刷新 SwiftBar。只替换本插件的文件，不改动其他插件。再次安装时重复后两个命令即可。

运行目录结构：

```text
opencodex.30s.sh
assets/deepseek-logo.svg
.opencodex-panel/
  OpenCodexPanel.app/
  config.local.sh
```

`config.local.sh` 不上传 Git，也不写入构建产物。安装时复制到运行目录；未提供新配置时保留原配置。其他可选配置见 `config.example.sh`。

只构建、不安装：

```sh
python3 scripts/build.py
```

产物位于 `build/OpenCodexPanel.app`。备份位于本机 `~/Library/Application Support/SwiftBarToken/backups/`。

## 日常维护

源码入口为 `opencodex.30s.sh`（采集、缓存、菜单、动作）及 `panel/Panel.swift`（原生界面）。`tests/` 保存回归检查；CI 在 macOS 上运行检查和编译。

建议流程：修改 → `scripts/check.py` → `scripts/install.py` → 实际点星星检查 → 提交和推送。

界面验证应覆盖浅色/深色、范围下拉框、悬停侧栏、更新徽标、长版本号、左右键菜单互斥。设置仍从“右键星星 → SwiftBar”进入。

## 数据范围

- 当天、本周、本月及日历日范围采用 Asia/Taipei 时区；周从周一开始。
- 近 24 小时为滚动窗口；近 7/30 天含当天。
- “全部”费用覆盖现有记录；图表受后端历史日期桶范围限制，受限时显示说明。
- DeepSeek 余额和 Codex 额度始终表示当前状态，与费用筛选范围无关。

## 插件目录内容

本目录只保存源码、图标、示例配置、文档和测试。凭据、本机配置、缓存、日志、数据库、个人截图及编译产物均不提交。
