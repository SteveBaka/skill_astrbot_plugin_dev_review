# skill_astrbot_plugin_dev_review

> AstrBot 插件开发 + 自动审核一体化 Skill

## 简介

本 Skill 是面向 LLM 和 Vibe Coding 工具的 AstrBot 插件开发参考。本Skill的设计覆盖了从架构理解、代码生成、自动审核到问题修复的完整闭环，核心目标是**减少 LLM 生成插件时的低级错误**。如果遇到一些多次才能解决的问题，推荐让Skill再次读取官方文档的内容进行读取。

实际开发中，LLM 最常犯的错误是 import 路径不正确。例如：

```python
# ❌ astrbot.api.logger 模块不存在
from astrbot.api.logger import logger
# ✅ 正确写法
from astrbot.api import logger
```

本 Skill 内置了 35+ 条目的 import 校验表和 26 个自动修复模式，让Ai生成代码时尽量杜绝以下常见的问题：

- **废弃 API 误用**：`on_keyword`/`on_full_match`/`on_regex` 在 v4.x 已移除，需改用 `event_message_type` + Python 匹配
- **适配器配置冲突**：`default_config_tmpl` 误加 `"enable"` 导致 WebUI 开关错位
- **dataclass 可变默认值**：`parameters: dict = {...}` 必须改为 `field(default_factory=lambda: {...})`
- **配置注入缺失**：`__init__` 必须声明 `config: AstrBotConfig` 参数
- **依赖声明遗漏**：requirements.txt 交叉检查规则
- **main.py 膨胀**：模块拆分指南（`references/modular-split.md`）
- **命令参数绑定**：`event.message_str` 取代函数参数，避免 `got multiple values` 错误
- **ToolExecResult 兼容性**：Python 3.12 下直接返回 `str` 即可
- **未使用 import / 死代码**：LLM 常生成不需要的 import 和未使用的变量

## 核心工作流

```
Step 0:   理解意图
  ↓
Step 0.5: 读取官方必读文档（3 个文件）
  ↓
Step 1:   选择插件类型
  ↓
Step 1.5: 按类型读取对应的官方文档
  ↓
Step 2:   脚手架 + 实现
  ↓
Step 2.5: 代码清理（未使用 import、死代码、重复定义）
  ↓
Step 3:   校验 metadata.yaml
  ↓
Step 4:   审核（官方文档 + Skill 规则）
  ↓
Step 5:   修复 → 重新审核 → 交付
```

> 官方文档是权威来源，Skill 内容是补充。两者冲突时以官方文档为准。

### 意图判断

LLM 应先判断用户需要什么，再决定读哪些文件：

| 用户说 | 意图 | 行动 |
|--------|------|------|
| "写一个插件" | 新插件 | 完整流程 |
| "加一个指令" | 追加功能 | 读现有代码，加 handler |
| "让 AI 调用我的 API" | 加 LLM 工具 | 只读 `agent/tools.md` |
| "帮我审核一下" | 全量审核 | 跑完整审核流水线 |
| "修一下这个报错" | 定位修复 | 读错误信息，定点修复 |

### 插件类型可组合

插件类型不是互斥的，一个插件可以同时包含多种类型：

```
指令 + LLM 工具:   /weather 指令 + AI 自动调用天气 API
指令 + 定时任务:   /remind 指令 + 定时提醒
LLM 工具 + 钩子:   AI 调用工具 + 钩子注入上下文
指令 + Web API:    /status 指令 + Dashboard 页面
```

完整类型选择指南见 `plugin-types/README.md`。

## 开发规范

以下是开发过程中必须遵守的规则，详细说明见 `SKILL.md` Mandatory Rules：

| 规则 | 说明 |
|------|------|
| 官方文档优先 | 代码生成前必须先从 GitHub 读取官方文档，不要依赖缓存知识 |
| docstring | 所有 `@filter.command` 方法必须有 docstring，WebUI 会展示 |
| 参数绑定 | 用 `event.message_str.strip()` 获取用户输入，不要用函数参数 |
| command_group | 必须用函数模式 `def math(): pass`，不能用 class |
| Tool 返回值 | `Tool.call()` 必须返回 `str`，不要用 `ToolExecResult` |
| dataclass 字段 | dict/list 字段必须用 `field(default_factory=...)`，不能直接写字面量 |
| 废弃 API | `on_keyword`/`on_full_match`/`on_regex` 已移除，用 `event_message_type` 替代 |
| 配置读取 | `__init__` 需接收 `config: AstrBotConfig` 并赋值 `self.config = config` |
| 首次生成 | metadata/conf_schema/README 跟随用户语言；`repo` 留空 |
| 代码清理 | 审核前移除未使用 import、死代码、重复定义 |
| 网络库 | 必须用 `aiohttp`/`httpx`（异步），不能用 `requests` |
| 数据存储 | 持久化数据存 `data/` 目录（`StarTools.get_data_dir()`），不存插件目录 |
| 插件命名 | `astrbot_plugin_` 前缀，小写，无空格 |
| 审核流程 | 用户要求审核时，必须全量检查所有文件 |
| 敏感操作 | git push 等必须经用户确认 |
| 上下文连续性 | 多轮交互中确保不丢失已修改文件和未解决问题 |

## 目录结构

```
skill_astrbot_plugin_dev_review/
│
├── SKILL.md                              # 主入口（英文），含 Mandatory Rules + Workflow
├── AGENTS.md                             # Skill 体系标识（AI 自动识别入口）
├── architecture.md                       # 机器可读的完整架构（文件地图 + 调用关系）
├── README.md                             # 本文件（中文）
├── LICENSE                               # MIT 授权
├── plugin-development-workflow.md        # 9 步开发流程
│
├── design_standards/                     # 架构与设计
│   ├── architecture_overview.md          # 核心架构（5 大管理器）
│   ├── event_flow.md                     # 消息流转模型（9 步）
│   ├── context_usage.md                  # Context 对象 API
│   ├── sandbox.md                        # 沙盒存储挂载
│   └── visual_utils.md                   # HTML 渲染 / 文转图详细参数
│
├── messages/                             # 消息模型
│   ├── model.md                          # AstrBotMessage 结构
│   ├── components.md                     # 消息组件（Plain/At/Image/Record/Video...）
│   ├── events.md                         # AstrMessageEvent 完整 API
│   └── umo.md                            # 统一消息源格式
│
├── platform_adapters/                    # 平台适配器
│   ├── adapter_interface.md              # 完整接口 + config_metadata 规则 + 真实示例
│   ├── message_conversion.md             # 消息转换逻辑
│   └── telegram_media_group.md           # Telegram 媒体组防抖合并
│
├── agent/                                # Agent 智能体系统
│   ├── index.md                          # 概述 + 最小示例
│   ├── tools.md                          # 工具定义（类/装饰器/内部工具）
│   ├── invoke-llm.md                     # LLM 调用 API
│   ├── hooks.md                          # Plugin Hooks + Agent Runner Hooks
│   ├── conversation.md                   # 会话管理 + 提示词注入
│   ├── cron.md                           # 定时任务（Basic/Active Job）
│   ├── subagents.md                      # 子智能体 Handoff
│   ├── official-tools.md                 # 官方内置工具列表
│   ├── sandbox.md                        # 沙盒运行时 API
│   ├── agent-runner.md                   # Agent Runner (v4.7.0+)
│   ├── context-compression.md            # 上下文压缩参数
│   ├── persona-control.md                # 人格管理 CRUD
│   └── register-skill.md                 # Skill 注册
│
├── storage_utils/                        # 存储与工具
│   ├── kv_storage.md                     # KV 键值对存储
│   ├── file_storage.md                   # 文件存储规范
│   ├── text_to_image.md                  # 文转图 / HTML 渲染
│   └── plugin-i18n.md                    # 插件国际化
│
├── webui/                                # WebUI
│   └── plugin-pages.md                   # Dashboard 页面 + Bridge API + SSE + 安全约束
│
├── references/                           # 参考文档
│   ├── core-concepts.md                  # 核心 API 清单
│   ├── best-practices.md                 # 最佳实践
│   ├── conf-schema.md                    # 配置 Schema 参考
│   ├── plugin-patterns.md                # 10 种实现模式
│   └── modular-split.md                  # main.py 拆分指南
│
├── review/                               # 自动审核体系
│   ├── review-workflow.md                # 审核流程 + 五维审查模型
│   ├── metadata-validation.md            # 结构校验（含 requirements.txt 交叉检查）
│   ├── main-file-checklist.md            # main.py 10 项检查（含 import 校验表 35+ 条目 + 废弃 API 检查）
│   ├── general-file-checklist.md         # 通用代码审查（含未使用 import / 死代码 / 重复代码检查）
│   └── auto-fix-guide.md                 # 26 个修复模式（FIX-00 ~ FIX-25）
│
├── plugin-types/                         # 插件类型示例（6 种 + script/ 中的基础模板）
│   ├── README.md                         # 类型选择指南 + 决策树
│   ├── REVIEW-REPORTS.md                 # 审核报告（全部 ✅ PASS）
│   ├── type1-llm-tool/                   # LLM 工具插件
│   ├── type2-session-waiter/             # 多轮对话插件
│   ├── type3-scheduled-task/             # 定时任务插件
│   ├── type4-llm-hook/                   # LLM 钩子插件
│   ├── type5-web-api/                    # Web API 插件
│   └── type6-agent-subagent/             # Agent 子智能体插件
│
├── script/                               # 插件模板
│   ├── index.md                          # 模板说明
│   └── astrbot-plugin-demo/              # 基础指令插件模板
│
└── mcp/                                  # 内置 MCP 服务器
    ├── server.py                         # MCP 服务器（6 个工具，自动发现文档）
    ├── requirements.txt                  # MCP 依赖
    └── SETUP.md                          # 安装指南
```

完整文件地图见 `SKILL.md`。

## 审核体系

本 Skill 的审核规则灵感来源于以下项目，在此对AstrBot Community团队表示由衷的感谢：

- [AstrBot-Skill v4](https://github.com/xunxiing/AstrBot-Skill/tree/v4) — AstrBot 的 AGENT SKILL 仓库，包含插件开发的结构化技术文档和 Skill 定义。
- [astr-plugin-reviewer](https://github.com/AstrBotDevs/astr-plugin-reviewer) — GitHub App 自动审核机器人
- 个人开发的插件实践：`astrbot_plugin_synochat_adapter`（适配器配置冲突）、`astrbot_plugin_mimo_tts`（模块化拆分）

审核覆盖 5 个维度：代码质量、功能正确性、安全性、可维护性、潜在缺陷。

## ⚠️ 免责声明

本 Skill 的预审机制**仅用于减少被基础审查驳回的概率**，不能替代完整的代码审查和测试：

- **不要完全依赖预审** — 规则覆盖了常见问题，但无法覆盖所有边界情况
- **自行评估架构影响** — 插件是否影响其他插件或系统，需要开发者判断
- **做好功能测试** — 预审通过不代表功能正确，务必实际测试
- **保持上下文连续性** — 多轮交互中确保不丢失修改状态，必要时先总结再继续

## 官方文档引用规则

代码生成、修复、审核的**每个阶段**都必须参考官方文档，而不是仅在"不确定时"才查阅：

| 阶段 | 必须查阅的官方文档 |
|------|-------------------|
| 代码生成前 | [AstrBot 开发文档](https://docs.astrbot.app/dev/) 中与所选类型对应的指南 |
| 修复 bug 时 | 对应 API 所在的官方文档章节，确认签名和用法 |
| 审核代码时 | 对照官方文档校验所有 API 调用是否正确 |

官方文档是 AstrBot API 的唯一权威来源。本 Skill 中的内容是对官方文档的整合和补充，当两者冲突时以官方文档为准。

## MCP 服务器（可选）

内置 MCP 服务器可让 AI 助手直接查询文档和校验 import 路径，支持 6 个工具。

快速配置：

```bash
cd mcp && python3 -m venv .venv && .venv/bin/pip install mcp pyyaml uvicorn starlette
```

```json
{
  "mcp": {
    "skill-astrbot-plugin": {
      "type": "local",
      "command": ["/实际路径/mcp/.venv/bin/python3", "server.py"],
      "cwd": "/实际路径/mcp",
      "enabled": true
    }
  }
}
```

完整安装指南、客户端配置、工具列表见 `mcp/SETUP.md`。

无 MCP 也能用：按优先级读取 `SKILL.md` → 根据任务选 1-2 个文件即可。

## 版本要求

- AstrBot >= 4.16
- Python >= 3.10

## 相关链接

- [AstrBot 仓库](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 开发文档](https://docs.astrbot.app/dev/)
- [AstrBot 插件市场](https://github.com/AstrBotDevs/AstrBot-Plugins)
- [AstrBot-Skill 官方的Skill仓库](https://github.com/xunxiing/AstrBot-Skill/tree/v4)

## 致谢

本项目源于 `AstrBot-Skill` 的启发，整合了本人在使用Ai开发AstrBot 插件的过程中出现的问题和解决方案，并且在流程上增加了半自动的代码审核体系，力求减少报错。

> 希望本Skill对你的开发有所帮助 ^_^
> 
> 如有问题和建议欢迎提交Issue，我会尽全力进行优化。