from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from checkin.core.http import DEFAULT_TIMEOUT_SECONDS, REQUEST_EXCEPTIONS, standard_client
from checkin.core.result import CheckinResult


APP_KEY = "apr1$AwP!wRRT$gJ/q.X24poeBInlUJC"
APP_VERSION = "10.4.1"
APP_SK = "ierkM0OZZbsuBKLoAgQ6OJneLMXBQXmzX+LXkNTuKch8Ui2jGlahuFyWIzBiDq/L"
TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS


def run(cookie: str, http_client: Any = standard_client) -> CheckinResult:
    headers = {
        "Host": "user-api.smzdm.com",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie,
        "User-Agent": "smzdm_android_V10.4.1 rv:841 (22021211RC;Android12;zh)smzdmapp",
    }
    try:
        active_messages = _safe_active(cookie, http_client)
        token = robot_token(headers, http_client)
        error_msg, data = sign(headers, token, http_client)
        reward_messages = all_reward(headers, data, http_client)
    except REQUEST_EXCEPTIONS as exc:
        return CheckinResult.failed(
            "什么值得买签到请求失败",
            {"error": str(exc)},
        )
    except (KeyError, TypeError, ValueError) as exc:
        return CheckinResult.failed(
            f"什么值得买签到失败: {exc}",
            {"error": str(exc)},
        )

    details = {
        "sign_result": error_msg,
        "activity": active_messages,
        "rewards": reward_messages,
    }
    reward_text = "，".join(item["value"] for item in reward_messages if item.get("value"))
    message = f"什么值得买: {error_msg}"
    if reward_text:
        message = f"{message}，{reward_text}"
    return CheckinResult.success(message, details)


def robot_token(headers: dict[str, str], http_client: Any = standard_client) -> str:
    ts = round(time.time() * 1000)
    data = {
        "f": "android",
        "v": APP_VERSION,
        "weixin": 1,
        "time": ts,
        "sign": _md5_upper(f"f=android&time={ts}&v={APP_VERSION}&weixin=1&key={APP_KEY}"),
    }
    response = http_client.post(
        url="https://user-api.smzdm.com/robot/token",
        headers=headers,
        data=data,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["data"]["token"]


def sign(headers: dict[str, str], token: str, http_client: Any = standard_client) -> tuple[str, dict[str, Any]]:
    time_stamp = round(time.time() * 1000)
    data = {
        "f": "android",
        "v": APP_VERSION,
        "sk": APP_SK,
        "weixin": 1,
        "time": time_stamp,
        "token": token,
        "sign": _md5_upper(
            f"f=android&sk={APP_SK}&time={time_stamp}&token={token}&v={APP_VERSION}&weixin=1&key={APP_KEY}"
        ),
    }
    response = http_client.post(
        url="https://user-api.smzdm.com/checkin",
        headers=headers,
        data=data,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return str(payload.get("error_msg", "签到接口无返回消息")), data


def all_reward(headers: dict[str, str], data: dict[str, Any], http_client: Any = standard_client) -> list[dict[str, str]]:
    response = http_client.post(
        url="https://user-api.smzdm.com/checkin/all_reward",
        headers=headers,
        data=data,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    normal_reward = payload.get("data", {}).get("normal_reward")
    if not normal_reward:
        return []

    reward_add = normal_reward.get("reward_add", {})
    messages: list[dict[str, str]] = []
    if reward_add.get("content"):
        messages.append({"name": "签到奖励", "value": str(reward_add["content"])})
    if normal_reward.get("sub_title"):
        messages.append({"name": "连续签到", "value": str(normal_reward["sub_title"])})
    return messages


def active(cookie: str, http_client: Any = standard_client) -> list[dict[str, str]]:
    active_id = "ljX8qVlEA7"
    headers = {
        "Host": "zhiyou.smzdm.com",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/smzdm 10.4.6 rv:130.1 (iPhone 13; iOS 15.6; zh_CN)/iphone_smzdmapp/10.4.6/wkwebview/jsbv_1.0.0",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Referer": "https://m.smzdm.com/",
        "Accept-Encoding": "gzip, deflate, br",
    }
    draw_url = f"https://zhiyou.smzdm.com/user/lottery/jsonp_draw?active_id={active_id}"
    info_url = "https://zhiyou.smzdm.com/user/"
    draw_payload = http_client.post(draw_url, headers=headers, timeout=TIMEOUT_SECONDS).json()
    account_html = http_client.get(info_url, headers=headers, timeout=TIMEOUT_SECONDS).text
    return [
        {"name": "活动结果", "value": str(draw_payload.get("error_msg", "活动接口无返回消息"))},
        {"name": "等级", "value": _extract_first(r"level/(.*?).png\?v=1", account_html)},
        {"name": "昵称", "value": _extract_first(r'<a href="https://zhiyou.smzdm.com/user"> (.*?) </a>', account_html)},
        {
            "name": "金币",
            "value": _clean_asset(
                _extract_first(
                    r'<div class="assets-part assets-gold">\n\s*(.*?)</span>',
                    account_html,
                )
            ),
        },
        {
            "name": "碎银",
            "value": _clean_asset(
                _extract_first(
                    r'<div class="assets-part assets-prestige">\n\s*(.*?)</span>',
                    account_html,
                )
            ),
        },
    ]


def _safe_active(cookie: str, http_client: Any = standard_client) -> list[dict[str, str]]:
    try:
        return active(cookie, http_client)
    except Exception:
        return [{"name": "活动结果", "value": "活动接口失败，不影响主签到"}]


def _md5_upper(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest().upper()


def _extract_first(pattern: str, text: str) -> str:
    matches = re.findall(pattern, text, re.S)
    return str(matches[0]).strip() if matches else ""


def _clean_asset(value: str) -> str:
    return (
        value.replace('<span class="assets-part-element assets-num">', "")
        .replace("'’", "")
        .strip()
    )
