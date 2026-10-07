from __future__ import annotations

import re

from checkin.core.http import DEFAULT_TIMEOUT_SECONDS, REQUEST_EXCEPTIONS, SessionFactory, browser_session
from checkin.core.result import CheckinResult


BASE_URL = "https://www.nodeseek.com"
BOARD_URL = f"{BASE_URL}/board"
SIGN_URL = f"{BASE_URL}/api/attendance?random=true"
TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS
# Let curl_cffi supply matching browser headers and TLS fingerprints.
IMPERSONATE = "chrome"
LOGIN_MESSAGES = ("未登录", "请先登录", "请登录", "登录失效", "登录已过期")
SIGNED_MESSAGES = ("已完成签到", "已经签到", "已签到")
FAILURE_MESSAGES = ("失败", "错误", "异常", "不足")
REWARD_PATTERN = re.compile(r"(\d+)\s*个?\s*鸡腿")


def run(cookie: str, session_factory: SessionFactory = browser_session) -> CheckinResult:
    stage = "board"
    try:
        with session_factory() as session:
            board = session.get(
                BOARD_URL,
                headers={
                    **_headers(cookie),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                impersonate=IMPERSONATE,
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            if board.status_code != 200:
                return _http_failure(board, stage)

            stage = "attendance"
            response = session.post(
                SIGN_URL,
                headers={
                    **_headers(cookie),
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "Origin": BASE_URL,
                    "Referer": BOARD_URL,
                },
                data="",
                impersonate=IMPERSONATE,
                timeout=TIMEOUT_SECONDS,
                allow_redirects=False,
            )
    except REQUEST_EXCEPTIONS as exc:
        return CheckinResult.failed(
            "NodeSeek 签到请求失败",
            {"stage": stage, "error": type(exc).__name__},
        )

    # NodeSeek also uses HTTP 500 / success=false for an already signed account.
    # Inspect the JSON message before treating the HTTP status as a failure.
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        if response.status_code != 200:
            return _http_failure(response, stage)
        return CheckinResult.failed("NodeSeek 签到接口未返回 JSON", {"stage": stage, "http_status": 200})

    raw_message = payload.get("message")
    message = _redact(raw_message.strip(), cookie) if isinstance(raw_message, str) else ""
    details = {"sign_result": message, "http_status": response.status_code}
    if str(payload.get("status")) == "404" or any(text in message for text in LOGIN_MESSAGES):
        return CheckinResult.failed(f"NodeSeek: {message or 'Cookie 已失效，请重新获取'}", details)

    already_signed = any(text in message for text in SIGNED_MESSAGES)
    if already_signed and response.status_code in (200, 500):
        return CheckinResult.success(f"NodeSeek: {message}", {**details, "already_signed": True})
    if response.status_code != 200:
        return _http_failure(response, stage, message)
    if not message:
        return CheckinResult.failed("NodeSeek 签到接口缺少 message", details)
    if (
        payload.get("success") is False
        or any(text in message for text in FAILURE_MESSAGES)
        or (payload.get("success") is not True and "鸡腿" not in message)
    ):
        return CheckinResult.failed(f"NodeSeek: {message}", details)

    details["already_signed"] = False
    reward = REWARD_PATTERN.search(message)
    if reward:
        details["coins"] = int(reward.group(1))
        details["rewards"] = [{"name": "签到奖励", "value": f"{reward.group(1)} 个鸡腿"}]
    return CheckinResult.success(f"NodeSeek: {message}", details)


def _headers(cookie: str) -> dict[str, str]:
    return {"Cookie": cookie, "Accept-Language": "zh-CN,zh;q=0.9"}


def _http_failure(response, stage: str, message: str = "") -> CheckinResult:
    details = {"stage": stage, "http_status": response.status_code}
    if message:
        details["sign_result"] = message
    if response.status_code == 403 or response.headers.get("cf-mitigated") == "challenge":
        return CheckinResult.failed("NodeSeek 请求被 Cloudflare 拦截，请检查 Cookie 或运行网络", details)
    if response.status_code in (301, 302, 303, 307, 308, 401):
        return CheckinResult.failed("NodeSeek 登录状态异常，请更新 Cookie", details)
    return CheckinResult.failed(f"NodeSeek 请求失败: HTTP {response.status_code}", details)


def _redact(message: str, cookie: str) -> str:
    message = message.replace(cookie, "[REDACTED]")
    for part in cookie.split(";"):
        _, separator, value = part.strip().partition("=")
        if separator and len(value) >= 4:
            message = message.replace(value, "[REDACTED]")
    return message
