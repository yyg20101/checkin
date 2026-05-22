from __future__ import annotations

import json
import re

from checkin.core.http import DEFAULT_TIMEOUT_SECONDS, REQUEST_EXCEPTIONS, SessionFactory, standard_session
from checkin.core.result import CheckinResult


SIGN_URL = "https://www.hifiti.com/sg_sign.htm"
TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS

SIGN_PATTERN = re.compile(r'var\s+sign\s*=\s*"([^"]+)"')
MESSAGE_PATTERN = re.compile(r'"message"\s*:\s*"(.+?)"')
FAILURE_KEYWORDS = ("登录", "未登录", "过期", "失败", "错误")

def run(cookie: str, session_factory: SessionFactory = standard_session) -> CheckinResult:
    try:
        with session_factory() as session:
            sign = fetch_sign_token(session, cookie)
            message = submit_checkin(session, cookie, sign)
    except REQUEST_EXCEPTIONS as exc:
        return CheckinResult.failed(
            "Hifiti 签到请求失败",
            {"error": str(exc)},
        )
    except ValueError as exc:
        return CheckinResult.failed(
            f"Hifiti 签到失败: {exc}",
            {"error": str(exc)},
        )

    details = {"sign_result": message}
    if _is_failure_message(message):
        return CheckinResult.failed(f"Hifiti: {message}", details)
    return CheckinResult.success(f"Hifiti: {message}", details)


def fetch_sign_token(session, cookie: str) -> str:
    response = session.get(
        SIGN_URL,
        headers=_get_headers(cookie),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    match = SIGN_PATTERN.search(response.text)
    if not match:
        raise ValueError("未能从签到页提取 sign，Cookie 可能已过期或页面结构已变化")
    return match.group(1)


def submit_checkin(session, cookie: str, sign: str) -> str:
    response = session.post(
        SIGN_URL,
        headers=_post_headers(cookie),
        data={"sign": sign},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    message = _extract_message(response)
    if not message:
        raise ValueError("未能解析签到接口返回消息")
    return message


def _extract_message(response) -> str:
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        payload = None

    if isinstance(payload, dict):
        message = payload.get("message")
        if message:
            return str(message).strip()

    match = MESSAGE_PATTERN.search(response.text)
    return match.group(1).strip() if match else ""


def _get_headers(cookie: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "DNT": "1",
        "Referer": "https://www.hifiti.com/",
        "Upgrade-Insecure-Requests": "1",
    }


def _post_headers(cookie: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0.6045.160 Safari/537.36"
        ),
        "Accept": "text/plain, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "DNT": "1",
        "Origin": "https://www.hifiti.com",
        "Referer": "https://www.hifiti.com/",
        "X-Requested-With": "XMLHttpRequest",
    }


def _is_failure_message(message: str) -> bool:
    return any(keyword in message for keyword in FAILURE_KEYWORDS)
