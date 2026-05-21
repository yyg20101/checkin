# 新增站点接入模板

这个项目的扩展目标是：新增站点时只改站点 task 和配置，不复制 runner、日志汇总或 CI 逻辑。

## 接入步骤

1. 新增 `checkin/tasks/<site_id>.py`。
2. 在模块中暴露 `run(cookie: str) -> CheckinResult`。
3. 把可展示的每日结果写入 `CheckinResult.details`。
4. 在 `checkin_config.json` 中加入任务配置。
5. 在 GitHub Secrets 中加入对应 Cookie。
6. 本地运行 `python3 run_checkin.py --task <site_id>` 验证单站点流程。

## Task 最小结构

```python
from __future__ import annotations

import requests

from checkin.core.result import CheckinResult


def run(cookie: str) -> CheckinResult:
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0",
    }

    try:
        response = requests.get("https://example.com/checkin", headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        return CheckinResult.failed(
            "Example 签到请求失败",
            {"error": str(exc)},
        )

    return CheckinResult.success(
        "Example 签到成功",
        {
            "coins": 10,
            "consecutive_days": 3,
            "rewards": [{"name": "签到奖励", "value": "+10 金币"}],
        },
    )
```

## 配置示例

```json
{
  "id": "example",
  "name": "Example",
  "module": "checkin.tasks.example",
  "cookie_secret": "COOKIE_EXAMPLE"
}
```

## `details` 字段建议

- 使用短键名和值，避免写入 Cookie、Token、完整请求头或完整响应正文。
- 常用字段：`coins`、`points`、`consecutive_days`、`rewards`、`activity`、`username`、`uid`、`error`。
- 列表明细建议使用 `{"name": "...", "value": "..."}`，Release 摘要会自动渲染成可读条目。
- 失败时也尽量提供可定位的信息，例如 HTTP 状态码、接口消息、解析失败字段。

## 状态语义

- `CheckinResult.success(...)`：新签到成功、已签到、或第三方接口返回非致命结果。
- `CheckinResult.failed(...)`：Cookie 失效、请求失败、关键字段解析失败、站点流程无法继续。
- `CheckinResult.skipped(...)`：站点主动要求跳过，或未来支持按条件禁用任务。
