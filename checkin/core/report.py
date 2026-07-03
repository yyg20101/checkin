from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


DETAIL_LABELS = {
    "account_id": "账号 ID",
    "account_name": "账号名称",
    "activity": "活动详情",
    "captcha_or_challenge_detected": "检测到验证码/挑战",
    "coins": "硬币/金币",
    "consecutive_days": "连续签到天数",
    "cookie_secret": "Secret 变量",
    "cookie_pairs": "Cookie 项数",
    "display_name": "用户名",
    "guard_challenge_detected": "检测到站点防护",
    "has_auth_cookie": "包含 auth Cookie",
    "has_sid_cookie": "包含 sid Cookie",
    "http_status": "HTTP 状态",
    "illegal_request_detected": "检测到非法请求提示",
    "logged_out_uid_detected": "检测到未登录 UID",
    "login_required_detected": "检测到登录提示",
    "login_url_present": "出现登录链接",
    "money": "金钱",
    "not_signed_text_present": "出现未签到文案",
    "page_title": "页面标题",
    "points": "积分",
    "prestige": "威望",
    "proxy_configured": "已配置代理",
    "response_chars": "响应字符数",
    "response_excerpt": "响应摘要",
    "reward_field_present": "出现奖励字段",
    "rewards": "奖励详情",
    "sign_result": "签到结果",
    "task_id": "任务 ID",
    "task_name": "任务名称",
    "total_days_field_present": "出现总天数字段",
    "uid": "UID",
    "user_group": "用户组",
    "username": "用户名",
}
ENV_MULTILINE_DELIMITER = "CHECKIN_TASK_RESULTS_EOF"
INTERNAL_DETAIL_KEYS = {"task_id", "task_name", "account_id"}
SUMMARY_MARKER = "[CHECKIN_SUMMARY]"


def load_summaries(log_path: str | Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    with Path(log_path).open(encoding="utf-8") as log_file:
        for line in log_file:
            if SUMMARY_MARKER not in line:
                continue
            payload = line.split(SUMMARY_MARKER, 1)[1].strip()
            summaries.append(json.loads(payload))
    return summaries


def build_task_results(summaries: list[dict[str, Any]]) -> tuple[int, int, int, int, str]:
    total_tasks = len(summaries)
    success_tasks = sum(1 for item in summaries if item.get("status") == "success")
    failed_tasks = sum(1 for item in summaries if item.get("status") == "failed")
    skipped_tasks = sum(1 for item in summaries if item.get("status") == "skipped")
    result_lines: list[str] = []
    for item in summaries:
        details = item.get("details") or {}
        task_name = details.get("task_name") or details.get("task_id") or "任务"
        account_name = details.get("account_name")
        display_name = f"{task_name} / {account_name}" if account_name else task_name
        result_lines.append(f"**{display_name}:** {_status_text(item.get('status'))}")

        message = item.get("message")
        if message:
            result_lines.append(f"  - {clean_scalar(message)}")
        append_detail_lines(result_lines, details)
        result_lines.append("")
    return total_tasks, success_tasks, failed_tasks, skipped_tasks, "\n".join(result_lines)


def write_github_env(log_path: str | Path, env_path: str | Path) -> None:
    total_tasks, success_tasks, failed_tasks, skipped_tasks, task_results = build_task_results(load_summaries(log_path))
    with Path(env_path).open("a", encoding="utf-8") as env_file:
        env_file.write(f"TOTAL_TASKS={total_tasks}\n")
        env_file.write(f"SUCCESS_TASKS={success_tasks}\n")
        env_file.write(f"FAILED_TASKS={failed_tasks}\n")
        env_file.write(f"SKIPPED_TASKS={skipped_tasks}\n")
        env_file.write(f"TASK_RESULTS<<{ENV_MULTILINE_DELIMITER}\n")
        env_file.write(task_results)
        env_file.write(f"\n{ENV_MULTILINE_DELIMITER}\n")


def clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def detail_label(key: str) -> str:
    return DETAIL_LABELS.get(key, key)


def render_mapping(mapping: dict[str, Any]) -> str:
    if not mapping:
        return ""
    if set(mapping).issuperset({"name", "value"}):
        name = clean_scalar(mapping.get("name"))
        value = clean_scalar(mapping.get("value"))
        return f"{name}: {value}" if name else value

    parts = []
    for key, value in mapping.items():
        rendered = render_detail(value)
        if rendered:
            parts.append(f"{detail_label(key)}: {rendered}")
    return "，".join(parts)


def render_detail(value: Any) -> str:
    if isinstance(value, dict):
        return render_mapping(value)
    if isinstance(value, list):
        rendered_items = [render_detail(item) for item in value]
        return "\n".join(item for item in rendered_items if item)
    return clean_scalar(value)


def append_detail_lines(result_lines: list[str], details: dict[str, Any]) -> None:
    for key, value in details.items():
        if key in INTERNAL_DETAIL_KEYS:
            continue
        rendered = render_detail(value)
        if not rendered:
            continue
        label = detail_label(key)
        if "\n" in rendered:
            result_lines.append(f"  - **{label}:**")
            for line in rendered.splitlines():
                result_lines.append(f"    - {line}")
        else:
            result_lines.append(f"  - **{label}:** {rendered}")


def _status_text(status: Any) -> str:
    if status == "success":
        return "✅ 成功"
    if status == "skipped":
        return "⏭️ 跳过"
    return "❌ 失败"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("Usage: python -m checkin.core.report <log_path> <github_env_path>")
        return 2
    write_github_env(args[0], args[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
