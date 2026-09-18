# astrbot_plugin_mcp_logs_bridge

在 AstrBot 进程内宿主一个 **MCP 服务器**（SSE 传输），通过 MCP 同步暴露 AstrBot 运行日志，供本开发 skill（`skill_astrbot_plugin_dev_review`）的 MCP 客户端或任意 MCP 客户端读取。

**版本**：v0.1.6 · **适配**：AstrBot `>=4.27,<5`（生产验证 **4.27.4 / 4.28.1**）

## 为什么需要它（4.28.1 仍成立）

AstrBot 的公开 OpenAPI 中**仍然**没有任何 API Key 可用的日志接口（`/logs/history`、`/logs/live` 需要 `system` 域，仅 Dashboard 会话可用）。对 4.28.1 live OpenAPI 做 drift 检查：**ETag 304，无新增 `/logs/*` public 路径**。因此本插件继续在进程内读取共享的 `LogBroker`（与 Dashboard `/logs/history` 同源），以标准 MCP 协议对外提供服务。

Web 注册一律使用官方 public API：`from astrbot.api.web import json_response, stream_response, request`（对齐 `guides/plugin-pages.md` / v4.28.1）。

## 功能

| MCP 工具 | 说明 |
|----------|------|
| `logs_history` | 同步返回最近日志（LogBroker 缓存，最近 500 条，最新在前），支持 `limit` / `level` / `keyword` / `category` 过滤 |
| `logs_tail` | 取最近 N 行日志。`source=auto`（默认）优先 LogBroker；`source=file` 强制读日志文件（含轮转归档），行数不足时自动向更老的归档补齐 |
| `logs_search` | 按关键字（大小写不敏感）搜索，可选等级过滤。`source=auto`（默认）搜缓存；`source=file` 逐行搜日志文件**及其全部轮转归档**（`astrbot.log*`，`.gz` 自动解压，新→旧），并支持 `since` / `until` 时间范围过滤（含当天日期写法，闭区间），适合多日错误定位 |

数据源优先级：

1. 进程内共享 `LogBroker`（`core_lifecycle.log_broker`，与 Dashboard 同源）
2. 兜底：`LogManager._log_broker`
3. 文件：`source=file` 强制走日志文件（默认 `<data>/logs/astrbot.log`，`log_file_path` 可覆盖），自动并入同目录轮转归档；`logs_search` 指定 `since`/`until` 时也隐含走文件源（时间过滤依赖日志行时间戳前缀）

## 安装

把本目录放入 AstrBot 插件目录（或通过 `astrbot_plugin_install_path` 上传）。启用后：

- SSE 端点：`http://<host>:<port>/api/v1/plugins/extensions/astrbot_plugin_mcp_logs_bridge/sse`
- 消息端点：`http://<host>:<port>/api/v1/plugins/extensions/astrbot_plugin_mcp_logs_bridge/messages`

两个端点都要求 `plugin` 作用域的 API Key（`X-API-Key` 请求头）。扩展路由前缀在 4.28.1 仍为 `/api/v1/plugins/extensions/<plugin_name>/...`（与 skill MCP `tools_logs.py` 一致）。

## 安全（双向共享令牌，推荐启用）

除 AstrBot 插件扩展路由自身的 `plugin` 域 API Key 鉴权外，本插件支持**双向共享
令牌**认证，避免误连到错误的桥接服务：

- **插件侧**：配置 `auth_token`（`_conf_schema.json`，`secret: true` — Dashboard ≥4.28 默认遮罩），或在 AstrBot 进程环境变量
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
| `auth_token` | string | 空 | 双向共享令牌（`X-MCP-Token`）；`secret: true` |
| `log_file_path` | string | 空 | 可选：日志文件路径，供 `source=file` 模式读取。与 AstrBot 本体语义一致：相对路径以 data 目录为基准（如 `logs/astrbot.log`），绝对路径原样使用；留空则用默认 `<data>/logs/astrbot.log` |
| `history_limit` | int | 200 | `logs_history` 未传 limit 时的默认上限（1-500，超出丢弃，最新在前） |
| `search_limit` | int | 200 | `logs_search` 未传 limit 时的默认上限（1-500，最新在前截断） |

## 4.28 插件开发对照（本仓库 skill）

| 主題 | 本插件行為 |
|------|------------|
| OpenAPI | 4.28.1 仍无 public `/logs/*`；桥接仍必要 |
| Web 注册 | `register_web_api` + `astrbot.api.web`（非 Quart） |
| 载入闸 | `astrbot_version: ">=4.27,<5"` |
| 生产验证 | 4.28.1 `logs_history` / `logs_tail` / `logs_search` 返回 `source=broker` |

## 安全

- 端点复用 AstrBot 插件扩展路由的 `plugin` 域鉴权，未授权请求返回 403。
- 推荐启用双向共享令牌（`auth_token` / `ASTRBOT_LOG_MCP_TOKEN`），令牌缺失或
  不匹配时两个端点一律返回 401。
- 仅暴露日志文本与等级/分类，不读取任何配置或秘密。
- 只读接口，无写操作。

## 依赖

`mcp>=1.8.0,<2`、`anyio>=4.0`（AstrBot 运行时已自带）。

