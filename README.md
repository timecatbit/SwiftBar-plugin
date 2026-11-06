# SwiftBar Token Monitor

SwiftBar 菜单栏插件，使用原生 macOS 面板查看多个 AI 客户端的用量、余额、额度与 Komari 监控。当前版本 **5.10.1**。

<p align="center">
  <img src="preview.png" width="360" alt="SwiftBar Token Monitor：全部范围 Summary、OpenCodex 与 Claude 用量、账户余额和更新提示">
</p>

实际运行截图，Summary 选择「全部」，客户端明细折叠，使用实色外观；也支持系统玻璃外观。费用为 API 等值估算，不代表订阅账单。

## 主页与模块

左键星星打开主页。Summary 保留在最上方，下方依次为 **Harness Token 用量、订阅用量、API 余额、其他**；未启用的类别不占位。模块管理也使用相同分类。右键星星提供“主页模块…”、“自动检测”和 SwiftBar 自身管理入口，不重复主页的操作。

“主页模块…”会打开 280pt 宽的紧凑面板：修改自动保存，支持快速连续点击，点击“完成”或面板外部才关闭。也可以直接在主页内右键进入模块管理。悬停模块名称配置数据来源；“外观与设置”紧接顶部的“允许折叠”，之后才是模块分类列表。

“允许折叠”默认开启：Summary 保持完整，各客户端收为两行，保留名称、状态、费用和 Token；点击标题独立展开或收起模型明细，可同时展开多个客户端。各自状态自动保存，刷新、重新打开面板或隐藏再启用模块后保持。关闭开关即可显示全部明细，再开启时恢复原有展开状态；折叠不改变统计结果。内容能完整显示时不滚动、不回弹；只有超出可见高度时才允许双指滚动。

| 模块 | 数据来源与边界 |
| --- | --- |
| Summary | 汇总当前显示的用量来源；共用趋势图显示总量及各来源 |
| OpenCodex | 本机或自定义管理接口的 Token、请求、费用、模型分布；附代理管理 |
| Claude | Claude 桌面 App 登记的可读取会话用量；排除未登记的独立 CLI 会话，未知价格显示未计价 |
| ChatGPT 本机用量 | Codex 普通/归档会话，支持 `.jsonl` 和 `.jsonl.zst`；优先单次用量，兼容仅累计计数，不重复加缓存或 reasoning |
| OpenCode | 只读 `opencode.db` 中的 assistant 用量与已记录费用 |
| DeepSeek Harness | 用户指定的会话目录；支持 v2–v4 JSONL 和 Zstandard 压缩日志 |
| WorkBuddy | 当前与旧版 `projects` JSONL；按响应 ID 去重，缓存与 reasoning 不重复计数，Credit 不视作美元 |
| Gemini CLI | 本机 JSON / JSONL 会话用量；兼容迁移与重放记录，包含思考 Token |
| DeepSeek API 余额 | 官方 `/user/balance`；可独立配置 API key 文件，也可复用 OpenCodex 已配置的官方 DeepSeek 凭据 |
| ChatGPT 订阅 | 本机 ChatGPT 登录的编程工具额度，或 OpenCodex 管理的 ChatGPT 账户额度；支持选择来源，不代表网页聊天全部限额 |
| Claude 订阅 | 可复用 Claude Code 登录主动查询最新订阅用量，无需 Cookie 或模型调用；也可只读本机快照。仅显示用量与重置时间 |
| Gemini / Grok / Kimi 订阅 | 独立模块、手动配置标记与官网入口；尚未接入自动额度查询，不读取浏览器登录 |
| Grok API 余额 | xAI 官方 Management API 的团队预付余额，需管理密钥和 Team ID；不是 SuperGrok 订阅额度 |
| MiniMax 订阅 | 官方 Token Plan / M Plan 查询接口；显示滚动和本周剩余百分比 |
| ChatGPT / Claude / MiniMax / Gemini / Kimi API | 识别已有 API 密钥配置或引用用户选择的密钥文件；本版仅提供官网账单入口，未接入余额自动查询 |
| Komari 监控 | 已配置的 Komari 面板、在线状态与服务器详情 |
| 应用更新 | 跟随已勾选的 Harness；OpenCodex 联动 ChatGPT 与 Codex CLI，Claude 联动 Claude Code。OpenCodex 自动更新，其他应用提示并提供更新入口 |

订阅顺序为 **ChatGPT、Claude、MiniMax、Gemini、Grok、Kimi**；API 顺序为 **ChatGPT、Claude、DeepSeek、MiniMax、Gemini、Grok、Kimi**。两组单独勾选、单独配置，安装客户端或存在 API Key 不代表已订阅。模块选择与连接设置合并在同一列表，分类与主页一致。

“已配置”旁为绿色实心圆点，“未配置”旁为灰色空心圆点，文字始终保留。圆点只说明存在配置引用或用户保存的手动标记，不代表已验证凭据或付费状态。尚未接入查询的模块显示“官网查看”，不显示伪造的零余额；未设置则显示“未配置”。订阅手动标记保存在本机偏好文件，不复制登录信息。API 官网入口模块不会发送密钥请求。MiniMax API 使用独立的 `MINIMAX_PLATFORM_API_KEY_FILE`，不复用订阅的 `MINIMAX_API_KEY_FILE`。

升级会把原来的 OpenCodex 账户额度迁入 ChatGPT 订阅，并继续使用原有代理来源，不改变已选择的主页模块。界面统一使用 ChatGPT 名称；`codex` 命令、`~/.codex` 路径、内部数据 ID 与模型原名保持兼容。OpenCodex 是独立产品名称。

首次安装自动检测常见客户端命令、WorkBuddy 应用、记录目录和已配置 API 凭据，勾选找到的模块。升级保留已有选择，不会重新打开手动关闭的模块；悬停右键“自动检测”可在旁边查看说明，也可从“外观与设置 → 自动检测”进入。点击“开始检测…”后先扫描，再列出将启用和取消的模块，并提醒会覆盖当前模块选择；默认按钮是“取消”，只有点击“覆盖当前选项”才按检测结果替换勾选。取消保持原设置。未安装、未配置、日志格式不支持或无权限时会显示状态，不会当成零用量。

统计默认当天，可下拉选择近 24 小时、近 7 天、近 30 天、本周、本月或全部。其他子菜单悬停在旁边展开，判定延迟为 80 毫秒。打开 Grok、MiniMax、ChatGPT 额度、Komari 或应用更新侧栏时立即检查对应来源，结果就地更新；5 秒内重复打开会去重。启用账户模块后也会立即检查，不必等待 30 秒轮询。

## 外观

macOS 26+ 使用原生 `NSGlassEffectView` 的 regular 玻璃材质；旧系统使用 `NSVisualEffectView`。界面跟随深浅色和系统“降低透明度”，也可在模块面板中改用实色背景。概览不可选中，不显示悬停提示；左右键菜单互斥。

## 安装与更新

需要 macOS 13+、SwiftBar、Python 3.9+ 和 Xcode Command Line Tools。OpenCodex、Claude App 等是可选数据源，不是所有模块的共同依赖。macOS 26 上需使用含标题点击修复的 SwiftBar（已验证 2.1.2 build 623）。

```sh
git clone https://github.com/timecatbit/swiftbar-token-monitor.git
cd swiftbar-token-monitor
python3 scripts/check.py
python3 scripts/install.py
```

安装脚本自动读取 SwiftBar 当前的插件目录，也可以显式指定：

```sh
python3 scripts/install.py --plugin-dir '/你的/SwiftBar插件目录'
```

脚本会编译、签名、备份并复制运行所需文件，首次安装自动选择模块，然后刷新 SwiftBar。**安装后可移动或删除源码仓库，插件不依赖仓库路径。** 没有写死用户名或个人 Documents 目录。

安装会从 PyPI 下载固定版本的 `curl_cffi` 及依赖，放在插件自己的 `.opencodex-panel/python/` 中，不修改系统 Python 包；后续安装复用已验证的构建缓存。该组件用于 Claude 官方网站兼容的 HTTPS 连接，菜单刷新不会运行 pip。需要 Python 自带的 pip 和首次安装时的网络连接；更换 `OCX_PYTHON` 或 Python 主/次版本后重新运行安装脚本。

SwiftBar 只执行一个入口，但完整的原生界面需要配套运行文件：

```text
SwiftBar 插件目录/
  opencodex.30s.sh
  assets/deepseek-logo.svg
  .opencodex-panel/
    OpenCodexPanel.app/
    lib/
```

仓库中的 `panel/`、`tests/`、`scripts/` 和文档用于开发维护，不需要全部放入 SwiftBar 插件目录。安装器会保留其他插件以及本机设置。

## 本机配置

**右键星星 → 主页模块** 同时管理显示与连接，按 **Harness Token 用量、订阅用量、API 余额、其他** 分组。左侧勾选决定是否显示，右侧圆点与文字表示配置状态；悬停名称或点击箭头直接展开该模块的连接设置，取消勾选后仍可配置。点击复选框或名称可连续多选，鼠标停在复选框上不会弹出侧栏。

每项连接明确显示“已配置”或“未配置”；配置状态不等于连接验证结果。通用外观、自动检测、高级配置文件和恢复默认集中放在“允许折叠”下方的“外观与设置”：

- 本机客户端自动读取标准记录目录；已配置项在下一级显示实际读取目录，可在 Finder 中打开、手动选择或恢复自动查找。API 只显示配置/密钥文件路径，不显示密钥内容。
- ChatGPT 订阅支持自动、本机登录和 OpenCodex 账户三种来源选择；支持选择含 `auth.json` 的配置目录、恢复自动读取及在 Finder 中打开；默认使用 `CODEX_HOME` 或 `~/.codex`。只改变插件读取位置，不修改客户端登录文件，也不影响 ChatGPT 本机用量目录。
- OpenCodex 位于 Harness 分组：可选择配置目录、修改管理地址、选择管理令牌文件及恢复自动读取。选择配置目录时改为读取该目录内的端口和令牌，不保留上一个目录的连接覆盖。
- DeepSeek 优先使用明确指定的密钥文件，否则读取 OpenCodex 的官方 DeepSeek 连接。
- Komari 必须明确提供实际面板地址；空值、注释和示例地址不算配置，不会自动启用。
- Grok 选择管理密钥文件并填写 Team ID；MiniMax 选择套餐密钥文件和地区。全部确认后才保存，任一步取消都不改变设置。
- 配置成功会启用对应模块；清除连接会关闭它，原始密钥文件不会删除。模块也可独立隐藏。

文件各有用途：

| 文件 | 何时写入 |
| --- | --- |
| `~/Library/Application Support/SwiftBarToken/preferences.json` | 模块选择、目录覆盖、材质、各模块展开状态改变时 |
| 同目录 `config.local.sh` | 明确设置地址或密钥文件引用时；也可通过“高级配置文件”编辑 |
| 系统临时目录中的插件缓存 | 数据同步时；连接变更会清除对应旧数据，清缓存不丢偏好 |
| 客户端日志和密钥原文件 | 仅只读访问；插件不修改、不复制密钥 |

项目代码直接位于仓库根目录：`opencodex.30s.sh`、`lib/`、`panel/`、`scripts/`、`tests/`。入口文件名保留，升级后 SwiftBar 不会出现第二个插件。

`config.local.sh` 是唯一的插件用户配置。注释只作说明，不是已启用的设置。安装器不会再自动复制仓库中的私有配置；旧运行目录配置仅在用户配置不存在时迁移一次，已存在的用户配置（即使只有注释）始终优先，旧文件备份后移出。首次安装需要显式导入时可传 `--config /path/to/config.local.sh`；已有用户配置时拒绝覆盖。

Claude App、ChatGPT 编程客户端、OpenCode、Gemini CLI 按各客户端的标准目录自动检测。WorkBuddy 同时检测 `~/.workbuddy-ai/projects` 和旧版 `~/.workbuddy/projects`，按响应 ID 去重。自定义目录可在“主页模块”中悬停对应客户端后选择，或用 `config.example.sh` 中的环境变量指定。DeepSeek Harness 的存储目录由部署决定，请选择实际的会话日志根目录。读取其压缩日志需要 `zstd`，或支持 Zstandard 的 Node.js；不支持的旧格式会明确标记。

Grok 需设置 `XAI_MANAGEMENT_API_KEY_FILE` 和 `XAI_TEAM_ID`，使用具备账单读取权限的管理密钥；普通推理 API key 不适用。MiniMax 需设置 `MINIMAX_API_KEY_FILE`（套餐密钥），可选 `MINIMAX_REGION=china`，默认国际区。只发送读取请求，不调用模型或充值；未配置的模块会给出提示。

Claude App 的会话仍由桌面 App 登记决定；用量记录同时查找 `~/.claude/projects` 和 `${XDG_CONFIG_HOME:-~/.config}/claude/projects`，或 `CLAUDE_CONFIG_DIR` 指定的逗号分隔目录（配置根目录或 `projects` 目录均可）。不同目录的副本会去重，独立 CLI 会话不会因此混入 App 模块。

自动检测只查看客户端安装状态、标准目录中的记录文件是否存在，以及当前环境变量、插件本机配置、OpenCodex 官方 DeepSeek 配置与 ChatGPT 编程客户端登录状态；也保留已手动配置的订阅入口。自动检测本身不扫描对话内容、浏览器或钥匙串，不复制凭据、不发送验证请求；检测到配置不代表凭据一定有效；已接入自动查询的模块在打开时检查，官网入口模块不发请求。刚安装但尚无记录的客户端会显示暂无数据；DeepSeek Harness 可能还需要指定记录目录。

## 后台开销

SwiftBar 的 30 秒入口保留，但复用缓存：面板关闭时短周期数据改为约 3 分钟检查，电池供电时约 5 分钟；余额等低频来源保持自身较长间隔。打开面板立即按正常刷新时效检查，资源侧栏和手动刷新仍可主动更新。电源状态最多每 5 分钟读取一次。

原生面板通过目录变化事件接收快照和动作回执，关闭时不运行每秒计时器，也不监听全局鼠标移动。相同快照不重复写入；一次后台同步只触发一次 SwiftBar 刷新。未配置的 Komari、Grok、MiniMax 和未登录的 ChatGPT 不发起查询。

## 统计口径与隐私

- 费用是已知价格的 API 等值估算，或客户端记录的费用，不是订阅账单。没有价格的数据会保留 Token 并标记未计价。
- Claude 缓存写入区分 5 分钟/1 小时时长，存在明细时以明细为准。有效 `costUSD` 优先作为客户端记录费用，缺失时再按已知价格估算；未知价格不伪造零费用。`advisor_message` 按自身模型单独计入，普通迭代不重复相加。
- 响应优先按 message/request ID 去重；缺少 request ID 时限制到会话和时间，真实响应 ID 跨流式内容块合并。侧链重放保留父响应，独立侧链回答正常统计。文件替换、删减、压缩或归档迁移会更新索引，避免残留旧统计。去重先于范围过滤，切换日期范围不重复解析日志。
- 同时显示 OpenCodex 和 ChatGPT 本机用量时，OpenCodex 有可用数据则作为 Summary 的统计来源；ChatGPT 保留独立明细，避免同一调用跨代理和客户端重复相加。关闭 OpenCodex 后，ChatGPT 会计入 Summary。
- 其他客户端会排除明确标记为 `opencodex`/`ocx` 的代理记录。自定义路由名及跨工具导入的历史可能仍重叠，使用共享代理时应选择合适的统计来源。
- 按系统时区统计，可通过 `OCX_TIMEZONE` 覆盖。周从周一开始；近 24 小时为滚动窗口，近 7/30 天含当天。
- 本机日志只索引用量元数据，不保存对话正文；数据库只读，增量索引和设置仅当前用户可读。余额和订阅额度不加入费用汇总。
- ChatGPT 额度通过客户端已有的 ChatGPT 登录查询，不自动登录、不调用模型；API-key-only 登录不能提供该订阅额度。此模块不声称覆盖 ChatGPT 网页所有聊天限额。
- 应用更新跟随 Harness 勾选：**Claude → Claude 桌面 App + Claude Code**，**ChatGPT → ChatGPT 桌面客户端 + Codex CLI**，**OpenCodex → OpenCodex + ChatGPT + Codex CLI**。已配置 OpenCodex 时，即使其模块隐藏，也联动检查 ChatGPT 和 Codex CLI；不改变主页勾选，重复来源只检查一次。订阅/API 勾选不触发应用更新，移出范围立即移除条目和更新数量。
- Claude Code 和 Codex CLI 有更新时，点击条目在终端分别运行 `claude update`、`codex update`；先确认本机版本支持命令，未安装不会自动安装，更新后自动刷新。优先直接在 iTerm 新标签或 Terminal 新窗口执行，显示真实命令、更新器输出、前后版本和最终结果，完成后保留窗口。系统不允许自动控制终端时才降级为独立 `.command` 文件，结果仍保留。
- CLI 更新日志仅保存在本机 `~/Library/Application Support/SwiftBarToken/logs/updates/`，每个 CLI 保留最近 20 次，文件权限为 600；“应用更新”中可打开已勾选客户端最近的日志。退出码非零明确显示失败；命令成功但版本没变时显示“检查完成，版本未变化”，不误报升级成功。其他桌面客户端仍只提示和打开官方入口。
- Claude Harness 默认读取 `~/Library/Application Support/Claude` 的会话登记，再读取对应的共享用量记录；只统计 App 登记的可读取会话，并不声称覆盖所有 Chat/Cowork 调用。旧版指定的 CLI 日志目录不会被误用为 App 目录。
- Claude 订阅只显示已用百分比与重置时间，不查询或展示额度余额。有效用量低于 70% 使用正常文字色（浅色为黑、深色为浅色），70–89% 为系统橙色，90% 起为系统红色；旧数据不套用当前用量的警示颜色。
- 推荐在 Claude 订阅侧栏启用 **Claude Code 登录查询**：只读复用当前 Code 登录，通过 `GET https://api.anthropic.com/api/oauth/usage` 主动获取用量，无需浏览器 Cookie，也不用等待模型响应。默认约 5 分钟更新，打开侧栏和手动刷新会主动检查，30 秒内复用成功结果；429 按服务端 `Retry-After` 退避，缺失时至少等 5 分钟，手动刷新也不会绕过限流。接口属于客户端内部接口，服务端变更可能影响可用性。
- OAuth 凭据只在内存中使用，只发送到固定的 Anthropic 用量地址，不跟随重定向、不查询余额。缓存仅含解析后的用量、不可逆的登录指纹和重试状态。令牌过期时由 Claude Code 的启动自检自行续期；插件不提交提示词，不调用模型，不直接轮换或写回令牌。自检在临时空目录运行，禁用工具、MCP、钩子和自动更新，完成后关闭自己的进程组。续期失败不反复启动 CLI，等待登录变化或用户明确重试。钥匙串读取失败后暂停自动读取，直到用户在侧栏重新授权。
- 未启用 OAuth 时只读取 App 历史快照或已启用的 Code 本机回传，比较新鲜程度并标出来源和时间；超过 10 分钟或已过重置时间标记待更新，不将旧值当当前值。OAuth 启用后失败也不会悄悄拼入 App 数据，以免不同客户端登录的账号不同。
- 在 Claude 订阅侧栏启用“本机用量回传…”会配置官方状态栏回调，仅写入 Claude 的 `settings.json` 中 `statusLine` 一项，原状态栏备份并继续执行，关闭后恢复；用户后来自行替换的状态栏不会被覆盖。桥接脚本存于插件的用户应用支持目录，独立于仓库路径。只保存百分比、重置时间与采样时间，不保存完整输入、对话、身份或凭据；回调按事件运行并节流，不自行调用模型或联网。客户端产生响应后才可能提供订阅数据，尚无回传时显示等待更新。
- 模块连接设置里的“使用 App 登录查询一次…”是独立的可选方式，只有主动点击并授权才读取 App Cookie，向 `https://claude.ai/api/organizations/{组织}/usage` 发出一次只读请求。后台不使用 Cookie，不将它作为 OAuth 的自动兜底。OAuth 开启时主页仍只使用 Code 账户数据；切回本机来源后才显示 App 手动查询快照。
- Codex CLI 的“最新版本”跟随实际安装渠道：官方 Homebrew Cask / Formula 使用对应 Homebrew 元数据，npm 安装使用 npm 版本。不拿 npm 发布抢先提示 Homebrew 用户更新；未知或自定义安装渠道明确显示待确认。执行仍为 `codex update`，终端保留完整日志和前后版本。
- DeepSeek 余额刷新期间保留主页金额，不追加“上次”；刷新进度、成功更新时间与失败状态放在余额侧栏。失败时明确说明正在保留最近余额。
- OpenCode、DeepSeek Harness、WorkBuddy、Gemini CLI 已选中时显示官网更新入口，明确标记尚未接入自动版本检查；不会声称已是最新。关闭“应用更新”停止提醒和非 OpenCodex 检查；OpenCodex 仅在其 Harness 被选中时自动检查与更新。已启动的安装仅继续确认结果，不重复启动。

接口与格式依据：[Apple 原生玻璃](https://developer.apple.com/documentation/appkit/nsglasseffectview)、[Codex App Server](https://learn.chatgpt.com/docs/app-server)、[DeepSeek 余额](https://api-docs.deepseek.com/api/get-user-balance/)、[DeepSeek Harness 存储](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/session/session-persistence-jsonl)、[OpenCode 数据目录](https://opencode.ai/docs/troubleshooting/)、[Gemini 会话格式](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/services/chatRecordingTypes.ts)、[xAI 账单接口](https://docs.x.ai/developers/rest-api-reference/management/billing)、[MiniMax 官方额度解析](https://github.com/MiniMax-AI/cli/blob/main/src/utils/quota.ts)。

## 参考实现与许可

本版参考并适配了 [ccusage](https://github.com/ccusage/ccusage) 的采集逻辑，固定参考版本为 [`615bd802`](https://github.com/ccusage/ccusage/tree/615bd802bc5c50246b84e98406f20ab048e27cf6)。重点采用其 [Claude 响应去重与 advisor 规则](https://github.com/ccusage/ccusage/blob/615bd802bc5c50246b84e98406f20ab048e27cf6/rust/adapters/claude/src/lib.rs)、[缓存计费](https://github.com/ccusage/ccusage/blob/615bd802bc5c50246b84e98406f20ab048e27cf6/rust/crates/ccusage-core/src/cost.rs)、[Codex 单次/累计用量解析](https://github.com/ccusage/ccusage/blob/615bd802bc5c50246b84e98406f20ab048e27cf6/rust/adapters/codex/src/parser.rs)和压缩日志选择逻辑，改为适合菜单栏刷新的 Python/SQLite 增量实现。

ccusage 为 MIT 许可，版权声明及完整许可证保存在 [lib/CCUSAGE_LICENSE](lib/CCUSAGE_LICENSE)，安装时一并复制。运行插件不需要安装 ccusage、Node 或 Rust；读取压缩日志仍需要 `zstd` 或具备 Zstandard 支持的 Node.js。

这些本机日志规则提供 Token 和费用统计，不提供账号订阅的实时百分比。订阅用量另由 Code OAuth、App 快照或官方 Code 状态栏回传获取，不从 API 等值费用推算额度。

### ccusage 的数据范围与客户端归属

复核版本 `615bd802`：ccusage 的 [Claude 适配器](https://github.com/ccusage/ccusage/blob/615bd802bc5c50246b84e98406f20ab048e27cf6/rust/adapters/claude/src/paths.rs)发现 `~/.claude/projects`、XDG Claude 目录和 `CLAUDE_CONFIG_DIR` 下的日志；[Codex 适配器](https://github.com/ccusage/ccusage/blob/615bd802bc5c50246b84e98406f20ab048e27cf6/docs/guide/codex/index.md)读取 `CODEX_HOME` 中的活动/归档记录。它以数据目录、日志格式与用量字段识别来源，不要求对应 App 或 CLI 仍然安装，也不把 Claude App、Claude Code、ChatGPT 普通聊天分别识别成账户账单来源。桌面编程客户端若写入相同格式和目录，其记录也可能被纳入。

| 数据 | ccusage 的方式 | 本插件的处理 |
| --- | --- | --- |
| Claude Token 与费用 | 本机日志中的 input/output/cache、响应 ID、已记录费用或价格估算；无需 Cookie 或账户授权 | 默认只纳入 Claude App 登记的可读取会话，沿用去重与增量索引；不把独立 CLI 会话伪装成 App 用量 |
| ChatGPT 编程用量 | Codex 格式的本机日志；不读取普通 ChatGPT 对话用量 | 明确标记为编程会话，支持桌面/CLI 产生的兼容记录，并处理与 OpenCodex 的重复统计 |
| Claude 订阅百分比 | 本机 Token 统计不提供；`blocks --token-limit` 使用手动上限或历史最高量 | 可授权 Code OAuth 主动查询，不用 Cookie；本机快照/状态栏回传为可选来源，不查询余额 |

Claude Code 日志提供 **Token 统计**；[Claude Code 官方状态栏输入](https://code.claude.com/docs/en/statusline#rate-limit-usage)另可在客户端首次 API 响应后传递 `rate_limits.five_hour` / `seven_day` 的百分比与重置时间。本插件已支持用户启用这种本机回传，不必自行读取 Cookie。Code 回传明确标注来源，不与 App 快照的各项拼接，不保证包含 Fable 分项；使用不同账号登录 App 与 Code 时，应以来源所标客户端的账号为准。

OAuth 实现参考 [CodexBar 的 Claude 接入](https://github.com/steipete/CodexBar/blob/458afc6017c4b2f5f97615653ce2999de3551673/docs/claude.md)、[OAuth 请求与错误处理](https://github.com/steipete/CodexBar/blob/458afc6017c4b2f5f97615653ce2999de3551673/Sources/CodexBarCore/Providers/Claude/ClaudeOAuth/ClaudeOAuthUsageFetcher.swift)、[委托客户端续期](https://github.com/steipete/CodexBar/blob/458afc6017c4b2f5f97615653ce2999de3551673/Sources/CodexBarCore/Providers/Claude/ClaudeOAuth/ClaudeOAuthDelegatedRefreshCoordinator.swift)，并对照 [bbchase/claude-usage](https://github.com/bbchase/claude-usage/tree/4600161c827a8180c87833841f32faa11b01b711) 与 [lobner/claude-usage](https://github.com/lobner/claude-usage/tree/8362a9f7a6d2cde3ad96bfefcca4f0a449060c63) 的只读凭据策略。未引入这些项目的运行依赖；CodexBar 的 MIT 版权及许可保留在 [lib/CODEXBAR_LICENSE](lib/CODEXBAR_LICENSE)。

## 开发维护

`opencodex.30s.sh` 负责采集协调、缓存与 SwiftBar 入口；`lib/` 负责独立采集器与偏好设置；`panel/Panel.swift` 负责原生界面。

```sh
python3 scripts/check.py   # 隔离测试，不运行实际插件
python3 scripts/build.py   # 仅构建到忽略的 build/
python3 scripts/install.py # 安装、保留备份、刷新
```

备份位于 `~/Library/Application Support/SwiftBarToken/backups/`。界面修改安装后需实际点星星验证深浅色、下拉范围、多选持久化、悬停侧栏及左右键互斥；不能只凭编译通过判断视觉效果。
