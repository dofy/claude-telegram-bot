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
| `thinking_messages` | 随机状态消息数组                                                   |
| `plugins`           | 插件启用/禁用及单独配置                                            |
| `claude`            | `dangerously_skip_permissions`、`max_retries`、`session_ttl_hours` |
| `inbox`             | `max_age_hours`（自动删除下载的媒体，默认 72 小时）                |

> 也可以通过 **管理面板** `http://127.0.0.1:8080` 管理配置。

## 运行

### 直接运行

```bash
uv run bot.py
```

### 使用 launchd（macOS 开机自启）

```bash
cp com.seven.claude-telegram-bot.plist.example ~/Library/LaunchAgents/com.seven.claude-telegram-bot.plist
# 编辑 plist 文件，更新路径
launchctl load ~/Library/LaunchAgents/com.seven.claude-telegram-bot.plist
```

停止：

```bash
launchctl unload ~/Library/LaunchAgents/com.seven.claude-telegram-bot.plist
```

## 项目结构

```
├── bot.py                  # 入口文件
├── config.json             # 动态配置（gitignored）
├── .env                    # 密钥（gitignored）
├── claude_bot/
│   ├── app.py              # 应用组装
│   ├── config.py           # 配置加载/保存
│   ├── log.py              # 日志及文件轮转
│   ├── claude.py           # Claude CLI 调用
│   ├── session.py          # 对话会话管理
│   ├── formatter.py        # Markdown → HTML 转换
│   ├── sender.py           # 消息分块与发送
│   ├── acl.py              # 访问控制
│   ├── cleanup.py          # 收件箱媒体清理
│   ├── handlers/
│   │   ├── commands.py     # /start, /status, /reset...
│   │   ├── message.py      # 私聊文本 + 媒体
│   │   └── group.py        # 群聊处理
│   └── plugins/
│       ├── base.py         # 插件基类
│       └── admin_api.py    # 内置管理面板
```

## 插件系统

插件位于 `claude_bot/plugins/`，每个插件是一个导出 `plugin` 实例的 Python 模块：

```python
from claude_bot.plugins.base import Plugin
from telegram.ext import Application

class MyPlugin(Plugin):
    name = "my_plugin"
    description = "做一些很酷的事"

    def register(self, app: Application, config: dict) -> None:
        # 注册 handler、启动后台任务等
        pass

plugin = MyPlugin()
```

在 `config.json` 中启用/禁用：

```json
{
  "plugins": {
    "my_plugin": { "enabled": true }
  }
}
```

## 命令参考

| 命令          | 说明                               |
| ------------- | ---------------------------------- |
| `/start`      | 显示欢迎消息                       |
| `/help`       | 同 /start                          |
| `/status`     | 检查 Bot 状态（主机名 + 时间）     |
| `/sysinfo`    | 显示 Claude 版本、Node、macOS 信息 |
| `/reset`      | 清除当前对话会话                   |
| `/stop`       | 关闭 Bot 进程                      |
| `/ask <文本>` | （群聊）向 Claude 提问             |

## 群聊设置

1. 将 Bot 添加到群组。
2. 获取群组的 Chat ID（例如通过 [@getidsbot](https://t.me/getidsbot)）。
3. 将群组 ID 添加到 `config.json` → `acl.allowed_group_ids`。
4. 在群组中使用以下方式之一：
   - 提及 Bot：`@yourbotname 做点什么`
   - 使用命令：`/ask 做点什么`
