# astrbot_plugin_mcp_logs_bridge

在 AstrBot 进程内宿主一个 **MCP 服务器**（SSE 传输），通过 MCP 同步暴露 AstrBot 运行日志，供本开发 skill（`skill_astrbot_plugin_dev_review`）的 MCP 客户端或任意 MCP 客户端读取。

## 为什么需要它

AstrBot 的公开 OpenAPI 中没有任何 API Key 可用的日志接口（`/logs/history`、`/logs/live` 需要 `system` 域，仅 Dashboard 会话可用）。本插件在进程内直接读取共享的 `LogBroker`（与 Dashboard `/logs/history` 同源），并以标准 MCP 协议对外提供服务，填补了 skill 无法读取运行日志的缺口。

## 功能

| MCP 工具 | 说明 |
|----------|------|
| `logs_history` | 同步返回最近日志（LogBroker 缓存，最近 500 条，最新在前），支持 `limit` / `level` / `keyword` / `category` 过滤 |
| `logs_tail` | 取最近 N 行日志；优先 LogBroker，文件日志开启时回退读文件 |
| `logs_search` | 在 LogBroker 缓存中按关键字（大小写不敏感）搜索，可选等级过滤 |

数据源优先级：

1. 进程内共享 `LogBroker`（`core_lifecycle.log_broker`，与 Dashboard 同源）
2. 兜底：`LogManager._log_broker`
3. 兜底：日志文件 `<data>/logs/astrbot.log`（需在 AstrBot 配置中开启文件日志）

## 安装

把本目录放入 AstrBot 插件目录（或通过 `astrbot_plugin_install_path` 上传）。启用后：

- SSE 端点：`http://<host>:<port>/api/v1/plugins/extensions/astrbot_plugin_mcp_logs_bridge/sse`
- 消息端点：`http://<host>:<port>/api/v1/plugins/extensions/astrbot_plugin_mcp_logs_bridge/messages`

两个端点都要求 `plugin` 作用域的 API Key（`X-API-Key` 请求头）。

## 安全（双向共享令牌，推荐启用）

除 AstrBot 插件扩展路由自身的 `plugin` 域 API Key 鉴权外，本插件支持**双向共享
令牌**认证，避免误连到错误的桥接服务：

- **插件侧**：配置 `auth_token`（`_conf_schema.json`），或在 AstrBot 进程环境变量
  中设置 `ASTRBOT_LOG_MCP_TOKEN`（配置优先）。两者皆空时不校验（仍受 API Key 保护，
  但不推荐仅依赖它）。
- **客户端侧**：请求头携带 `X-MCP-Token: <相同令牌>`。MCP 宿主机在
  `ASTRBOT_LOG_MCP_TOKEN` 中配置同名令牌即可，skill 中继工具会自动发送。
- 令牌不匹配或缺失时，`/sse` 与 `/messages` 端点一律返回 **401**。

MCP 客户端注册示例（带令牌）：

```json
{
  "mcpServers": {
    "astrbot-logs": {
      "transport": "sse",
      "url": "http://127.0.0.1:6185/api/v1/plugins/extensions/astrbot_plugin_mcp_logs_bridge/sse",
      "headers": {
        "X-API-Key": "<plugin 作用域 API Key>",
        "X-MCP-Token": "<与插件 auth_token 相同的令牌>"
      }
    }
  }
}
```

随后即可调用 `logs_history` / `logs_tail` / `logs_search`。

> 本 skill 的 MCP 服务器（`mcp/server.py`）也内置了中继工具 `astrbot_logs_history` /
> `astrbot_logs_tail` / `astrbot_logs_search`：**仅当** MCP 宿主环境变量
> `ASTRBOT_LOG_MCP_URL` 显式设置时才会注册（`ASTRBOT_BASE_URL` 不会隐式启用）；
> 可选设置 `ASTRBOT_LOG_MCP_TOKEN`（与插件 `auth_token` 相同）后自动以
> `X-MCP-Token` 发送。

## 配置

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `enable_bridge` | bool | true | 是否启用 MCP 日志桥接服务 |
| `auth_token` | string | 空 | 双向共享令牌（`X-MCP-Token`）。留空则回退读取 AstrBot 进程环境变量 `ASTRBOT_LOG_MCP_TOKEN`；两者皆空时不校验（不推荐，仅依赖 AstrBot API Key 鉴权） |
| `log_file_path` | string | 空 | 可选：日志文件路径（兜底读取；留空则用默认 `<data>/logs/astrbot.log`） |
| `history_limit` | int | 200 | `logs_history` 单次返回上限 |
| `search_limit` | int | 200 | `logs_search` 单次返回上限 |

## 安全

- 端点复用 AstrBot 插件扩展路由的 `plugin` 域鉴权，未授权请求返回 403。
- 推荐启用双向共享令牌（`auth_token` / `ASTRBOT_LOG_MCP_TOKEN`），令牌缺失或
  不匹配时两个端点一律返回 401。
- 仅暴露日志文本与等级/分类，不读取任何配置或秘密。
- 只读接口，无写操作。

## 依赖

`mcp>=1.8.0,<2`、`anyio>=4.0`（AstrBot 运行时已自带）。
