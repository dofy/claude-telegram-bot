# Claude Telegram Bot

[English](README.md)

一个将消息转发给 [Claude Code](https://claude.ai/code) 并返回回复的 Telegram 机器人。支持多轮对话、媒体处理、群聊、插件系统和 Web 管理面板。

## 功能特性

- **多轮对话** — 每个聊天的会话持久化（存储在 `/tmp`，重启后清除）
- **输入状态指示** — Claude 思考时显示"正在输入…"
- **图片/文件接收** — 自动下载照片和文档并传递给 Claude
- **文件自动发送** — Claude 回复中引用本地文件路径时自动发送文件
- **群聊支持** — 在群聊中通过 `@botname` 提及或 `/ask` 命令响应
- **Markdown → HTML** — 将 Claude 的 Markdown 输出转换为 Telegram 兼容的 HTML
- **插件系统** — 通过配置扩展或禁用功能
- **管理面板** — 基于 NiceGUI 的 Web UI，支持 Token 认证和速率限制
- **自动重试** — Claude CLI 调用失败时以指数退避策略重试
- **会话 TTL** — 对话在可配置的空闲时间后自动过期
- **收件箱清理** — 下载的媒体文件在可配置的时间后自动删除
- **日志轮转** — 按天/周轮转日志文件，可配置保留时长

## 前置要求

- Python 3.14+ / [uv](https://docs.astral.sh/uv/)
- 从 [@BotFather](https://t.me/BotFather) 获取的 Telegram Bot Token
- 已安装 Claude Code CLI（`claude` 在 PATH 中）
- Anthropic API Key（或 OpenRouter Key）

## 安装

```bash
git clone https://github.com/dofy/claude-telegram-bot.git
cd claude-telegram-bot
uv sync
```

## 配置

Bot 使用两层配置：

| 文件          | 用途                                    |
| ------------- | --------------------------------------- |
| `.env`        | 仅存储密钥（Bot Token、API Key）        |
| `config.json` | 动态配置（ACL、思考消息、插件、日志等） |

```bash
cp .env.example .env
cp config.json.example config.json
# 编辑 .env 填入 BOT_TOKEN 和 API 凭证
# 编辑 config.json 设置 owner_chat_id
```

### `.env` 变量

| 变量                   | 必填 | 说明                                 |
| ---------------------- | ---- | ------------------------------------ |
| `BOT_TOKEN`            | 是   | Telegram Bot Token                   |
| `ANTHROPIC_API_KEY`    | \*   | Anthropic 直连密钥                   |
| `ANTHROPIC_AUTH_TOKEN` | \*   | OpenRouter / 代理 Token              |
| `ANTHROPIC_BASE_URL`   | 否   | 自定义 API 端点                      |
| `ADMIN_TOKEN`          | 否   | 管理面板登录 Token（留空则无需认证） |

\* `ANTHROPIC_API_KEY` 和 `ANTHROPIC_AUTH_TOKEN` 至少需要配置一个。

### `config.json` 结构

| 区块                | 关键字段                                                           |
| ------------------- | ------------------------------------------------------------------ |
| `acl`               | `owner_chat_id`、`allowed_group_ids`                               |
| `log`               | `dir`、`rotation`（daily/weekly）、`keep_days`、`level`            |
| `thinking_messages` | `{text, enabled}` 对象数组，支持单条启用/禁用                      |
| `plugins`           | 插件启用/禁用及单独配置                                            |
| `claude`            | `dangerously_skip_permissions`、`max_retries`、`session_ttl_hours` |
| `inbox`             | `max_age_hours`（自动删除下载的媒体，默认 72 小时）                |

> 也可以通过 **管理面板** 管理配置（默认 `http://127.0.0.1:8080`，端口可在 `plugins.admin_api.port` 中配置）。

## 运行

### 直接运行

```bash
uv run bot.py
```

### 使用 launchd（macOS 开机自启）

```bash
cp xyz.phpz.claude-telegram-bot.plist.example ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
# 编辑 plist 文件，更新路径
launchctl load ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
```

停止（完全卸载，防止 KeepAlive 自动重启）：

```bash
launchctl unload ~/Library/LaunchAgents/xyz.phpz.claude-telegram-bot.plist
```

> **注意：** `launchctl stop` 只是杀掉进程，KeepAlive 会立即重启。要真正停止请用 `unload`，恢复启动用 `load`。

## 项目结构

```
├── bot.py                          # 入口文件
├── config.json                     # 动态配置（gitignored）
├── .env                            # 密钥（gitignored）
├── data/                           # 插件数据（统计、定时任务）
├── claude_bot/
│   ├── app.py                      # 应用组装
│   ├── config.py                   # 配置加载/保存
│   ├── log.py                      # 日志及文件轮转
│   ├── claude.py                   # Claude CLI 调用
│   ├── session.py                  # 对话会话管理
│   ├── formatter.py                # Markdown → HTML 转换
│   ├── sender.py                   # 消息分块与发送
│   ├── acl.py                      # 访问控制
│   ├── cleanup.py                  # 收件箱媒体清理
│   ├── utils.py                    # 公共装饰器（owner_only）
│   ├── handlers/
│   │   ├── commands.py             # /start, /status, /reset...
│   │   ├── message.py              # 私聊文本 + 媒体
│   │   └── group.py                # 群聊处理
│   └── plugins/
│       ├── base.py                 # 插件基类 + GuardedCommandHandler
│       ├── theme.py                # 统一 UI 配色定义
│       ├── admin_api/              # Web 管理面板（NiceGUI）
│       │   ├── __init__.py         # 认证、主题、页面路由
│       │   └── panels.py           # Dashboard、密钥、ACL、日志、帮助
│       ├── management/             # Owner 专用 Telegram 命令
│       ├── scheduler/              # 定时任务与提醒
│       │   ├── __init__.py         # 调度器核心 + 命令
│       │   └── panel.py            # 管理面板 UI
│       ├── stats/                  # 使用统计
│       └── thinking/               # 随机思考中消息
│           ├── __init__.py         # 消息逻辑
│           └── panel.py            # 管理面板 UI
```

## 插件系统

所有插件在启动时全部注册。启用/禁用是**运行时开关**——通过 `GuardedCommandHandler` 和 `is_enabled()` 检查即时生效，无需重启。

插件位于 `claude_bot/plugins/`，以 Python 包形式存在：

```python
from claude_bot.plugins.base import Plugin
from telegram.ext import Application

class MyPlugin(Plugin):
    name = "my_plugin"
    display_name = "My Plugin"
    description = "做一些很酷的事"

    def register(self, app: Application, config: dict) -> None:
        app.add_handler(self.command("mycommand", my_handler))

    def get_commands(self) -> list[tuple[str, str]]:
        return [("mycommand", "BotFather 命令描述")]

    def get_admin_tabs(self):
        return [("my_tab", "My Tab", "icon", build_panel_fn)]

plugin = MyPlugin()
```

### 内置插件

| 插件         | 说明                                     |
| ------------ | ---------------------------------------- |
| `admin_api`  | Web 管理面板（核心，不可禁用）           |
| `management` | Owner 命令：/reload, /sessions, /logs 等 |
| `scheduler`  | 定时任务与提醒（/remind, /tasks）        |
| `stats`      | 使用统计（/usage）                       |
| `thinking`   | Claude 处理时的随机状态消息              |

### UI 主题

所有 UI 颜色统一定义在 `claude_bot/plugins/theme.py`，修改该文件即可改变整个管理面板的外观。

## 命令参考

| 命令                    | 说明                               |
| ----------------------- | ---------------------------------- |
| `/start`                | 显示欢迎消息                       |
| `/help`                 | 同 /start                          |
| `/status`               | 检查 Bot 状态                      |
| `/sysinfo`              | 显示 Claude 版本、Node、macOS 信息 |
| `/reset`                | 清除当前对话会话                   |
| `/stop`                 | 关闭 Bot 进程                      |
| `/ask <文本>`           | （群聊）向 Claude 提问             |
| `/reload`               | 重新加载配置（仅 Owner）           |
| `/sessions`             | 查看活跃会话（仅 Owner）           |
| `/logs [n]`             | 查看最近日志（仅 Owner）           |
| `/config`               | 显示配置摘要（仅 Owner）           |
| `/admin`                | 显示管理面板链接（仅 Owner）       |
| `/prompt [文本\|clear]` | 设置/查看每个聊天的系统提示词      |
| `/usage`                | 查看使用统计                       |
| `/remind <时间> <消息>` | 创建定时任务/提醒                  |
| `/tasks`                | 列出所有定时任务                   |

## 群聊设置

1. 将 Bot 添加到群组。
2. 获取群组的 Chat ID（例如通过 [@getidsbot](https://t.me/getidsbot)）。
3. 将群组 ID 添加到 `config.json` → `acl.allowed_group_ids`。
4. 在群组中使用以下方式之一：
   - 提及 Bot：`@yourbotname 做点什么`
   - 使用命令：`/ask 做点什么`
