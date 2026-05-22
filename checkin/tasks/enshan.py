from __future__ import annotations

import html
import re
from urllib.parse import unquote

from checkin.core.http import (
    BROWSER_IMPERSONATE,
    DEFAULT_TIMEOUT_SECONDS,
    REQUEST_EXCEPTIONS,
    SessionFactory,
    browser_session,
)
from checkin.core.result import CheckinResult


BASE_URL = "https://www.right.com.cn/forum"
HOME_URL = f"{BASE_URL}/forum.php"
SIGN_URL = f"{BASE_URL}/plugin.php?id=erling_qd%3Aaction&action=sign"
TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS

FORMHASH_PATTERN = re.compile(r'name="formhash"\s+value="([^"]+)"')
UID_PATTERNS = (
    re.compile(r"space-uid-(\d+)"),
    re.compile(r"discuz_uid\s*=\s*'(\d+)'"),
)
COINS_PATTERN = re.compile(r"恩山币\s*</em>\s*(\d+)")
USERNAME_PATTERN = re.compile(r"<h2[^>]*>\s*(?:<a[^>]*>)?([^<]+)")
USER_GROUP_PATTERN = re.compile(r"用户组[^>]*>.*?<a[^>]*>([^<]+)</a>", re.S)


def run(cookie: str, session_factory: SessionFactory = browser_session) -> CheckinResult:
    try:
        with session_factory() as session:
            formhash, uid = fetch_home_vars(session, cookie)
            submit_checkin(session, cookie, formhash)
            coins, username, user_group = fetch_profile_info(session, cookie, uid)
    except REQUEST_EXCEPTIONS as exc:
        return CheckinResult.failed(
            f"恩山无线论坛签到请求失败: {exc}",
            {"error": str(exc)},
        )
    except ValueError as exc:
        return CheckinResult.failed(
            f"恩山无线论坛签到失败: {exc}",
            {"error": str(exc)},
        )
    except Exception as exc:
        return CheckinResult.failed(
            f"恩山无线论坛签到请求失败: {exc}",
            {"error": str(exc)},
        )

    return CheckinResult.success(
        f"恩山无线论坛: 恩山币 {coins}",
        {"coins": coins, "username": username, "user_group": user_group, "uid": uid},
    )


def fetch_home_vars(session, cookie: str) -> tuple[str, str]:
    response = session.get(
        HOME_URL,
        headers=_page_headers(cookie),
        impersonate=BROWSER_IMPERSONATE,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    formhash_match = FORMHASH_PATTERN.search(response.text)
    uid = _extract_uid(response.text)
    if not formhash_match:
        raise ValueError("未能从首页提取 formhash")
    if not uid:
        raise ValueError("未能从首页提取 uid")
    return formhash_match.group(1), uid


def submit_checkin(session, cookie: str, formhash: str) -> None:
    response = session.post(
        SIGN_URL,
        headers=_sign_headers(cookie),
        data={"formhash": formhash},
        impersonate=BROWSER_IMPERSONATE,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def fetch_profile_info(session, cookie: str, uid: str) -> tuple[str, str, str]:
    response = session.get(
        f"{BASE_URL}/home.php?mod=space&uid={uid}&do=profile&mycenter=1",
        headers=_profile_headers(cookie),
        impersonate=BROWSER_IMPERSONATE,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    coins = _extract_value(COINS_PATTERN, response.text, "恩山币")
    username = _extract_value(USERNAME_PATTERN, response.text, "用户名")
    user_group = _extract_value(USER_GROUP_PATTERN, response.text, "用户组")
    return coins, username, user_group


def _extract_uid(content: str) -> str | None:
    for pattern in UID_PATTERNS:
        match = pattern.search(content)
        if match:
            return match.group(1)
    return None


def _extract_value(pattern: re.Pattern[str], content: str, label: str) -> str:
    match = pattern.search(content)
    if not match:
        raise ValueError(f"未能解析{label}")
    return html.unescape(unquote(match.group(1))).strip()


def _page_headers(cookie: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }


def _sign_headers(cookie: str) -> dict[str, str]:
    headers = _page_headers(cookie)
    headers.update(
        {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.right.com.cn",
            "Referer": f"{BASE_URL}/erling_qd-sign_in.html",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return headers


def _profile_headers(cookie: str) -> dict[str, str]:
    headers = _page_headers(cookie)
    headers.update(
        {
            "Referer": f"{BASE_URL}/erling_qd-sign_in.html?mobile=2",
            "Cache-Control": "max-age=0",
        }
    )
    return headers
