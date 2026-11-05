# OpenCodex Token 面板

SwiftBar 菜单栏插件，使用原生 macOS 面板查看多个 AI 客户端的用量、余额、额度与 Komari 监控。当前版本 **5.1.1**。

## 主页与模块

左键星星打开主页。右键星星提供“主页模块…”、“自动检测”和 SwiftBar 自身管理入口，不重复主页的操作。

“主页模块…”会打开 280pt 宽的紧凑面板：修改自动保存，支持快速连续点击，点击“完成”或面板外部才关闭。也可以直接在主页内右键进入模块管理。数据目录和外观设置收在列表底部的悬停侧栏。

“允许折叠”默认开启：Summary 保持完整，各客户端收为两行，保留名称、状态、费用和 Token；点击标题独立展开或收起模型明细，可同时展开多个客户端。各自状态自动保存，刷新、重新打开面板或隐藏再启用模块后保持。关闭开关即可显示全部明细，再开启时恢复原有展开状态；折叠不改变统计结果。内容能完整显示时不滚动、不回弹；只有超出可见高度时才允许双指滚动。

| 模块 | 数据来源与边界 |
| --- | --- |
| Summary | 汇总当前显示的用量来源；共用趋势图显示总量及各来源 |
| OpenCodex | 本机或自定义管理接口的 Token、请求、费用、模型分布；附代理管理 |
| Claude Code | 本机 JSONL 中的用量字段；兼容第三方模型，未知价格显示未计价 |
| Codex 本机用量 | Codex 会话与归档会话的用量事件；不会把缓存或 reasoning 再加一次 |
| OpenCode | 只读 `opencode.db` 中的 assistant 用量与已记录费用 |
| DeepSeek Harness | 用户指定的会话目录；支持 v2–v4 JSONL 和 Zstandard 压缩日志 |
| WorkBuddy | 当前与旧版 `projects` JSONL；按响应 ID 去重，缓存与 reasoning 不重复计数，Credit 不视作美元 |
| Gemini CLI | 本机 JSON / JSONL 会话用量；兼容迁移与重放记录，包含思考 Token |
| DeepSeek API 余额 | 官方 `/user/balance`；可独立配置 API key 文件，也可复用 OpenCodex 已配置的官方 DeepSeek 凭据 |
| ChatGPT / Codex 额度 | 官方 Codex App Server 返回的 ChatGPT 登录账户额度；不是网页聊天次数或订阅账单 |
| OpenCodex 账户额度 | OpenCodex 管理的 Codex 账户可用量 |
| Grok API 余额 | xAI 官方 Management API 的团队预付余额，需管理密钥和 Team ID；不是 SuperGrok 订阅额度 |
| MiniMax 套餐额度 | 官方 Token Plan / M Plan 查询接口；显示滚动和本周剩余百分比 |
| Komari 监控 | 已配置的 Komari 面板、在线状态与服务器详情 |
| 应用更新 | OpenCodex 稳定版自动更新；Claude、ChatGPT、Claude Code 只提示 |

首次安装自动检测常见客户端命令、WorkBuddy 应用、记录目录和已配置 API 凭据，勾选找到的模块。升级保留已有选择，不会重新打开手动关闭的模块；悬停右键“自动检测”可在旁边查看说明，也可从“外观与设置 → 自动检测”进入。点击“开始检测…”后先扫描，再列出将启用和取消的模块，并提醒会覆盖当前模块选择；默认按钮是“取消”，只有点击“覆盖当前选项”才按检测结果替换勾选。取消保持原设置。未安装、未配置、日志格式不支持或无权限时会显示状态，不会当成零用量。

统计默认当天，可下拉选择近 24 小时、近 7 天、近 30 天、本周、本月或全部。其他子菜单悬停在旁边展开，判定延迟为 80 毫秒。打开 Grok、MiniMax、ChatGPT 额度、Komari 或应用更新侧栏时立即检查对应来源，结果就地更新；5 秒内重复打开会去重。启用账户模块后也会立即检查，不必等待 30 秒轮询。

## 外观

macOS 26+ 使用原生 `NSGlassEffectView` 的 regular 玻璃材质；旧系统使用 `NSVisualEffectView`。界面跟随深浅色和系统“降低透明度”，也可在模块面板中改用实色背景。概览不可选中，不显示悬停提示；左右键菜单互斥。

## 安装与更新

需要 macOS 13+、SwiftBar、Python 3.9+ 和 Xcode Command Line Tools。OpenCodex、Claude Code 等是可选数据源，不是所有模块的共同依赖。macOS 26 上需使用含标题点击修复的 SwiftBar（已验证 2.1.2 build 623）。

```sh
git clone https://github.com/timecatbit/SwiftBar-plugin.git
cd SwiftBar-plugin/opencodex
python3 scripts/check.py
python3 scripts/install.py
```

安装脚本自动读取 SwiftBar 当前的插件目录，也可以显式指定：

```sh
python3 scripts/install.py --plugin-dir '/你的/SwiftBar插件目录'
```

脚本会编译、签名、备份并复制运行所需文件，首次安装自动选择模块，然后刷新 SwiftBar。**安装后可移动或删除源码仓库，插件不依赖仓库路径。** 没有写死用户名或个人 Documents 目录。

SwiftBar 只执行一个入口，但完整的原生界面需要配套运行文件：

```text
SwiftBar 插件目录/
  opencodex.30s.sh
  assets/deepseek-logo.svg
  .opencodex-panel/
    OpenCodexPanel.app/
    lib/
    config.local.sh       # 可选，旧版配置兼容
```

仓库中的 `panel/`、`tests/`、`scripts/` 和文档用于开发维护，不需要全部放入 SwiftBar 插件目录。安装器会保留其他插件以及本机设置。

## 本机配置

模块面板“外观与设置”中的“打开本机配置”会打开当前用户的：

```text
~/Library/Application Support/SwiftBarToken/config.local.sh
```

这里的配置优先于插件旁边旧版 `config.local.sh`。模块选择、折叠状态和材质偏好单独保存在同目录的 `preferences.json`，不会随源码移动或缓存清除而丢失。安装前也可复制 `config.example.sh` 为仓库内忽略的 `config.local.sh`，随安装复制到运行目录。

```sh
export KOMARI_BASE_URL="https://your-komari.example"
export DEEPSEEK_API_KEY_FILE="$HOME/.config/deepseek/api-key"
# key 文件只放 API key，建议权限 600；不要提交到 Git。
```

Claude Code、Codex、OpenCode、Gemini CLI 按各客户端的标准目录自动检测。WorkBuddy 同时检测 `~/.workbuddy-ai/projects` 和旧版 `~/.workbuddy/projects`，按响应 ID 去重。自定义目录可在“数据来源”旁边的子菜单中选择，或用 `config.example.sh` 中的环境变量指定。DeepSeek Harness 的存储目录由部署决定，请选择实际的会话日志根目录。读取其压缩日志需要 `zstd`，或支持 Zstandard 的 Node.js；不支持的旧格式会明确标记。

Grok 需设置 `XAI_MANAGEMENT_API_KEY_FILE` 和 `XAI_TEAM_ID`，使用具备账单读取权限的管理密钥；普通推理 API key 不适用。MiniMax 需设置 `MINIMAX_API_KEY_FILE`（套餐密钥），可选 `MINIMAX_REGION=china`，默认国际区。只发送读取请求，不调用模型或充值；未配置的模块会给出提示。

自动检测只查看客户端安装状态、标准目录中的记录文件是否存在，以及当前环境变量、插件本机配置、OpenCodex 官方 DeepSeek 配置与 Codex 登录状态。不扫描对话内容、浏览器或钥匙串，不复制凭据、不发送验证请求；检测到配置不代表凭据一定有效，实际状态在打开模块时查询。刚安装但尚无记录的客户端会显示暂无数据；DeepSeek Harness 可能还需要指定记录目录。

## 统计口径与隐私

- 费用是已知价格的 API 等值估算，或客户端记录的费用，不是订阅账单。没有价格的数据会保留 Token 并标记未计价。
- 同时显示 OpenCodex 和 Codex 本机用量时，OpenCodex 有可用数据则作为 Summary 的统计来源；Codex 保留独立明细，避免同一调用跨代理和客户端重复相加。关闭 OpenCodex 后，Codex 会计入 Summary。
- 其他客户端会排除明确标记为 `opencodex`/`ocx` 的代理记录。自定义路由名及跨工具导入的历史可能仍重叠，使用共享代理时应选择合适的统计来源。
- 按系统时区统计，可通过 `OCX_TIMEZONE` 覆盖。周从周一开始；近 24 小时为滚动窗口，近 7/30 天含当天。
- 本机日志只索引用量元数据，不保存对话正文；数据库只读，增量索引和设置仅当前用户可读。余额和订阅额度不加入费用汇总。
- ChatGPT 额度通过客户端已有的 ChatGPT 登录查询，不自动登录、不调用模型；API-key-only 登录不能提供该订阅额度。此模块不声称覆盖 ChatGPT 网页所有聊天限额。
- OpenCodex、Claude、ChatGPT、Claude Code 的版本检查沿用原有更新策略。隐藏用量模块会停止对应的范围统计；OpenCodex 自动更新策略独立保留。

接口与格式依据：[Apple 原生玻璃](https://developer.apple.com/documentation/appkit/nsglasseffectview)、[Codex App Server](https://learn.chatgpt.com/docs/app-server)、[DeepSeek 余额](https://api-docs.deepseek.com/api/get-user-balance/)、[DeepSeek Harness 存储](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/session/session-persistence-jsonl)、[OpenCode 数据目录](https://opencode.ai/docs/troubleshooting/)、[Gemini 会话格式](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/services/chatRecordingTypes.ts)、[xAI 账单接口](https://docs.x.ai/developers/rest-api-reference/management/billing)、[MiniMax 官方额度解析](https://github.com/MiniMax-AI/cli/blob/main/src/utils/quota.ts)。

## 开发维护

`opencodex.30s.sh` 负责采集协调、缓存与 SwiftBar 入口；`lib/` 负责独立采集器与偏好设置；`panel/Panel.swift` 负责原生界面。

```sh
python3 scripts/check.py   # 隔离测试，不运行实际插件
python3 scripts/build.py   # 仅构建到忽略的 build/
python3 scripts/install.py # 安装、保留备份、刷新
```

备份位于 `~/Library/Application Support/SwiftBarToken/backups/`。界面修改安装后需实际点星星验证深浅色、下拉范围、多选持久化、悬停侧栏及左右键互斥；不能只凭编译通过判断视觉效果。
