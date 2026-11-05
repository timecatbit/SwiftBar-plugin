# SwiftBar plugin

在 macOS 菜单栏查看 AI 客户端的费用估算、Token 用量、账户余额与额度。支持自选模块、统一趋势图，以及 Komari 监控和应用更新。

<p align="center">
  <img src="preview.png" width="360" alt="SwiftBar AI 用量面板：全部范围 Summary、OpenCodex 与 Claude Code 明细、DeepSeek 余额、Codex 额度和应用更新">
</p>

实际运行截图，Summary 选择「全部」，使用实色外观。费用为已知价格的 API 等值估算，不代表订阅账单；也可切换系统玻璃外观。

**[安装与配置 →](opencodex/README.md)**

| 插件目录 | 功能 |
| --- | --- |
| [opencodex](opencodex/README.md) | OpenCodex / Claude Code / Codex / WorkBuddy / Gemini CLI / OpenCode / DeepSeek Harness 用量；DeepSeek / ChatGPT / Grok / MiniMax 账户资源；Komari 监控与应用更新 |

每个插件在独立子目录中维护，源码、测试、构建和安装工具均放在对应子目录。本机配置、凭据及运行缓存不进入 Git；预览截图由维护者授权发布。
