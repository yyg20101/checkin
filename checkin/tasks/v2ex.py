from __future__ import annotations

import html
import re
from urllib.parse import quote, unquote

from checkin.core.http import DEFAULT_TIMEOUT_SECONDS, REQUEST_EXCEPTIONS, SessionFactory, standard_session
from checkin.core.result import CheckinResult


BASE_URL = "https://www.v2ex.com"
HOME_URL = f"{BASE_URL}/"
DAILY_URL = f"{BASE_URL}/mission/daily"
BALANCE_URL = f"{BASE_URL}/balance"
TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS

ONCE_PATTERN = re.compile(r"once=(.+?)'")
DAYS_PATTERN = re.compile(r"已连续登录(.+?)天")
REWARD_PATTERN = re.compile(r"每日登录奖励(.+?)铜币")
SIGNED_TEXT = "每日登录奖励已领取"
UNSIGNED_TEXT = "领取 X 铜币"

def run(cookie: str, session_factory: SessionFactory = standard_session) -> CheckinResult:
    try:
        with session_factory() as session:
            visit_home(session, cookie)
            daily_page = fetch_daily_page(session, cookie)
            once = extract_once(daily_page)
            if once:
                redeem_daily_reward(session, cookie, once)
                daily_page = fetch_daily_page(session, cookie)

            days = extract_signed_days(daily_page)
            reward = fetch_reward(session, cookie)
    except REQUEST_EXCEPTIONS as exc:
        return CheckinResult.failed(
            "V2EX 签到请求失败",
            {"error": str(exc)},
        )
    except ValueError as exc:
        return CheckinResult.failed(
            f"V2EX 签到失败: {exc}",
            {"error": str(exc)},
        )

    details = {
        "consecutive_days": days,
        "rewards": [{"name": "每日登录奖励", "value": f"{reward} 铜币"}],
    }
    return CheckinResult.success(
        f"V2EX: 已连续登录 {days} 天，每日登录奖励 {reward} 铜币",
        details,
    )


def visit_home(session, cookie: str) -> None:
    response = session.get(
        HOME_URL,
        headers=_headers(cookie),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def fetch_daily_page(session, cookie: str) -> str:
    response = session.get(
        DAILY_URL,
        headers=_headers(cookie, referer=HOME_URL),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def extract_once(content: str) -> str | None:
    match = ONCE_PATTERN.search(content)
    if match:
        return html.unescape(unquote(match.group(1))).strip()
    if SIGNED_TEXT in content:
        return None
    raise ValueError("未能从每日任务页提取 once，Cookie 可能已过期或页面结构已变化")


def redeem_daily_reward(session, cookie: str, once: str) -> None:
    response = session.get(
        f"{DAILY_URL}/redeem?once={quote(once)}",
        headers=_headers(cookie, referer=DAILY_URL),
        timeout=TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    if response.status_code not in (302, 200):
        response.raise_for_status()
        raise ValueError(f"领取请求返回异常状态码 {response.status_code}")


def extract_signed_days(content: str) -> str:
    if UNSIGNED_TEXT in content:
        raise ValueError("签到后仍显示未领取每日登录奖励")
    if SIGNED_TEXT not in content:
        raise ValueError("未能确认每日登录奖励已领取")

    match = DAYS_PATTERN.search(content)
    if not match:
        raise ValueError("未能解析连续登录天数")
    return html.unescape(unquote(match.group(1))).strip()


def fetch_reward(session, cookie: str) -> str:
    response = session.get(
        BALANCE_URL,
        headers=_headers(cookie, referer=DAILY_URL),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    match = REWARD_PATTERN.search(response.text)
    if not match:
        raise ValueError("未能解析每日登录奖励")
    return html.unescape(unquote(match.group(1))).strip()


def _headers(cookie: str, referer: str | None = None) -> dict[str, str]:
    headers = {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers
