from __future__ import annotations

import html
import re
from typing import Callable
from urllib.parse import quote, unquote

import requests

from checkin.core.result import CheckinResult


BASE_URL = "https://bbs.binmt.cc"
SIGN_PAGE_URL = f"{BASE_URL}/plugin.php?id=k_misign%3Asign"
TIMEOUT_SECONDS = 30

FORMHASH_PATTERN = re.compile(r'name="formhash"\s+value="(.+?)"')
REWARD_PATTERN = re.compile(r'id="lxreward"\s+value="(.+?)"')
TOTAL_DAYS_PATTERN = re.compile(r'id="lxtdays"\s+value="(.+?)"')
NOT_SIGNED_TEXT = "您今天还没有签到"
ILLEGAL_REQUEST_TEXT = "访问请求当中含有非法字符"

SessionFactory = Callable[[], requests.Session]


def run(cookie: str, session_factory: SessionFactory = requests.Session) -> CheckinResult:
    try:
        with session_factory() as session:
            formhash = fetch_formhash(session, cookie)
            submit_checkin(session, cookie, formhash)
            reward, total_days = fetch_checkin_details(session, cookie)
    except requests.RequestException as exc:
        return CheckinResult.failed(
            "MT管理器论坛签到请求失败",
            {"error": str(exc)},
        )
    except ValueError as exc:
        return CheckinResult.failed(
            f"MT管理器论坛签到失败: {exc}",
            {"error": str(exc)},
        )

    details = {
        "rewards": [{"name": "积分奖励", "value": reward}],
        "consecutive_days": total_days,
    }
    return CheckinResult.success(
        f"MT管理器论坛: 积分奖励 {reward}，总天数 {total_days}",
        details,
    )


def fetch_formhash(session: requests.Session, cookie: str) -> str:
    response = session.get(
        SIGN_PAGE_URL,
        headers=_page_headers(cookie),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    match = FORMHASH_PATTERN.search(response.text)
    if not match:
        raise ValueError("未能从签到页提取 formhash，Cookie 可能已过期或页面结构已变化")
    return match.group(1)


def submit_checkin(session: requests.Session, cookie: str, formhash: str) -> None:
    url = (
        f"{BASE_URL}/k_misign-sign.html?operation=qiandao&format=button"
        f"&formhash={quote(formhash)}&inajax=1&ajaxtarget=midaben_sign"
    )
    response = session.get(
        url,
        headers=_ajax_headers(cookie),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    if ILLEGAL_REQUEST_TEXT in response.text:
        raise ValueError(ILLEGAL_REQUEST_TEXT)


def fetch_checkin_details(session: requests.Session, cookie: str) -> tuple[str, str]:
    response = session.get(
        SIGN_PAGE_URL,
        headers=_page_headers(cookie),
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    if NOT_SIGNED_TEXT in response.text:
        raise ValueError("签到后仍显示未签到")

    reward = _extract_value(REWARD_PATTERN, response.text, "积分奖励")
    total_days = _extract_value(TOTAL_DAYS_PATTERN, response.text, "总天数")
    return reward, total_days


def _extract_value(pattern: re.Pattern[str], text: str, label: str) -> str:
    match = pattern.search(text)
    if not match:
        raise ValueError(f"未能解析{label}")
    return html.unescape(unquote(match.group(1))).strip()


def _page_headers(cookie: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Referer": f"{BASE_URL}/forum.php?gid=36",
        "Upgrade-Insecure-Requests": "1",
    }


def _ajax_headers(cookie: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Referer": f"{BASE_URL}/forum.php?gid=36",
        "X-Requested-With": "XMLHttpRequest",
    }
