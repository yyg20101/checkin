from __future__ import annotations

import html
import re
from urllib.parse import quote, unquote

from checkin.core.http import (
    BROWSER_IMPERSONATE,
    DEFAULT_TIMEOUT_SECONDS,
    REQUEST_EXCEPTIONS,
    SessionFactory,
    browser_session,
)
from checkin.core.result import CheckinResult


BASE_URL = "https://bbs.binmt.cc"
SIGN_PAGE_URL = f"{BASE_URL}/plugin.php?id=k_misign%3Asign"
TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS

FORMHASH_PATTERNS = (
    re.compile(r'name=["\']formhash["\'][^>]*value=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'value=["\']([^"\']+)["\'][^>]*name=["\']formhash["\']', re.IGNORECASE),
)
REWARD_PATTERN = re.compile(r'id="lxreward"\s+value="(.+?)"')
TOTAL_DAYS_PATTERN = re.compile(r'id="lxtdays"\s+value="(.+?)"')
NOT_SIGNED_TEXT = "您今天还没有签到"
ILLEGAL_REQUEST_TEXT = "访问请求当中含有非法字符"
LOGIN_REQUIRED_TEXT = "您需要先登录"
LOGIN_URL_TEXT = "member.php?mod=logging"
LOGGED_OUT_UID_PATTERN = re.compile(r"discuz_uid\s*=\s*['\"]0['\"]")
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class BinmtPageError(ValueError):
    def __init__(self, message: str, details: dict[str, object] | None = None):
        super().__init__(message)
        self.details = details or {}


def run(cookie: str, session_factory: SessionFactory = browser_session) -> CheckinResult:
    try:
        with session_factory() as session:
            formhash = fetch_formhash(session, cookie)
            submit_checkin(session, cookie, formhash)
            reward, total_days = fetch_checkin_details(session, cookie)
    except REQUEST_EXCEPTIONS as exc:
        return CheckinResult.failed(
            "MT管理器论坛签到请求失败",
            {"error": str(exc)},
        )
    except BinmtPageError as exc:
        return CheckinResult.failed(
            f"MT管理器论坛签到失败: {exc}",
            {"error": str(exc), **exc.details},
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


def fetch_formhash(session, cookie: str) -> str:
    response = session.get(
        SIGN_PAGE_URL,
        headers=_page_headers(cookie),
        impersonate=BROWSER_IMPERSONATE,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    _raise_for_page_error(response.text, "签到页")
    formhash = _extract_formhash(response.text)
    if not formhash:
        raise BinmtPageError(
            "未能从签到页提取 formhash，Cookie 可能已过期或页面结构已变化",
            _build_page_diagnostics(response, cookie),
        )
    return formhash


def submit_checkin(session, cookie: str, formhash: str) -> None:
    url = (
        f"{BASE_URL}/k_misign-sign.html?operation=qiandao&format=button"
        f"&formhash={quote(formhash)}&inajax=1&ajaxtarget=midaben_sign"
    )
    response = session.get(
        url,
        headers=_ajax_headers(cookie),
        impersonate=BROWSER_IMPERSONATE,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    if ILLEGAL_REQUEST_TEXT in response.text:
        raise ValueError(ILLEGAL_REQUEST_TEXT)
    if _is_login_required_response(response.text):
        raise ValueError("签到接口提示需要登录，Cookie 可能已过期或未包含登录态")


def fetch_checkin_details(session, cookie: str) -> tuple[str, str]:
    response = session.get(
        SIGN_PAGE_URL,
        headers=_page_headers(cookie),
        impersonate=BROWSER_IMPERSONATE,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    _raise_for_page_error(response.text, "签到详情页")
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


def _extract_formhash(text: str) -> str:
    for pattern in FORMHASH_PATTERNS:
        match = pattern.search(text)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def _raise_for_page_error(text: str, page_name: str) -> None:
    if ILLEGAL_REQUEST_TEXT in text:
        raise ValueError(ILLEGAL_REQUEST_TEXT)
    if _is_login_required_response(text):
        raise ValueError(f"{page_name}提示需要登录，Cookie 可能已过期或未包含登录态")


def _is_login_required_response(text: str) -> bool:
    if LOGIN_REQUIRED_TEXT in text:
        return True
    return bool(LOGGED_OUT_UID_PATTERN.search(text) and LOGIN_URL_TEXT in text)


def _build_page_diagnostics(response, cookie: str) -> dict[str, object]:
    text = response.text
    return {
        "http_status": getattr(response, "status_code", "unknown"),
        "page_title": _extract_title(text) or "未找到",
        "response_chars": len(text),
        "cookie_pairs": _count_cookie_pairs(cookie),
        "has_auth_cookie": "cQWy_2132_auth=" in cookie,
        "has_sid_cookie": "cQWy_2132_sid=" in cookie,
        "login_required_detected": _is_login_required_response(text),
        "logged_out_uid_detected": bool(LOGGED_OUT_UID_PATTERN.search(text)),
        "login_url_present": LOGIN_URL_TEXT in text,
        "illegal_request_detected": ILLEGAL_REQUEST_TEXT in text,
        "not_signed_text_present": NOT_SIGNED_TEXT in text,
        "reward_field_present": 'id="lxreward"' in text,
        "total_days_field_present": 'id="lxtdays"' in text,
        "captcha_or_challenge_detected": _has_captcha_or_challenge(text),
        "response_excerpt": _safe_response_excerpt(text, cookie),
    }


def _extract_title(text: str) -> str:
    match = TITLE_PATTERN.search(text)
    if not match:
        return ""
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()


def _count_cookie_pairs(cookie: str) -> int:
    return sum(1 for part in cookie.split(";") if part.strip())


def _has_captcha_or_challenge(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "captcha",
        "cf-chl",
        "cloudflare",
        "just a moment",
        "验证码",
        "安全验证",
        "secqaa",
    )
    return any(marker in lowered for marker in markers)


def _safe_response_excerpt(text: str, cookie: str, limit: int = 160) -> str:
    excerpt = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    excerpt = re.sub(r"<style\b[^>]*>.*?</style>", " ", excerpt, flags=re.IGNORECASE | re.DOTALL)
    excerpt = re.sub(r"<[^>]+>", " ", excerpt)
    excerpt = html.unescape(re.sub(r"\s+", " ", excerpt)).strip()
    if not excerpt:
        excerpt = re.sub(r"\s+", " ", text).strip()
        excerpt = excerpt.replace("<", "&lt;").replace(">", "&gt;")
    for value in _cookie_values(cookie):
        if len(value) >= 6:
            excerpt = excerpt.replace(value, "[redacted-cookie]")
    excerpt = re.sub(r"(?i)[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", "[redacted-email]", excerpt)
    excerpt = re.sub(r"\b[A-Fa-f0-9]{24,}\b", "[redacted-token]", excerpt)
    return excerpt[:limit] if excerpt else "空"


def _cookie_values(cookie: str) -> list[str]:
    values: list[str] = []
    for part in cookie.split(";"):
        if "=" not in part:
            continue
        _, value = part.split("=", 1)
        value = value.strip()
        if value:
            values.append(value)
    return values


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
