from __future__ import annotations

import random
import re
import time
from typing import Callable

from checkin.core.http import (
    BROWSER_IMPERSONATE,
    DEFAULT_TIMEOUT_SECONDS,
    SessionFactory,
    browser_session,
)
from checkin.core.result import CheckinResult


BASE_URL = "https://hostloc.com/"
RANDOM_VISITS_COUNT = 5
DELAY_SECONDS = 3
TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS

UidFactory = Callable[[], int]
SleepFunction = Callable[[float], None]


def run(
    cookie: str,
    session_factory: SessionFactory = browser_session,
    uid_factory: UidFactory | None = None,
    sleep: SleepFunction = time.sleep,
) -> CheckinResult:
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    }
    with session_factory() as session:
        visit_random_profiles(session, headers, uid_factory or random_uid, sleep)
        credits = get_user_credits(session, headers)
        if not credits:
            return CheckinResult.failed("❌ 未能获取积分信息")
        return CheckinResult.success(
            f"💎 金钱: {credits['money']} | 🏆 积分: {credits['points']}",
            credits,
        )


def visit_random_profiles(
    session,
    headers,
    uid_factory: UidFactory = lambda: random.randint(1, 45000),
    sleep: SleepFunction = time.sleep,
    visit_count: int = RANDOM_VISITS_COUNT,
    delay_seconds: int = DELAY_SECONDS,
):
    print(f"\n--- 开始执行随机访问任务，共 {visit_count} 次 ---")
    headers["Referer"] = BASE_URL

    for index in range(visit_count):
        uid = uid_factory()
        visit_url = f"{BASE_URL}space-uid-{uid}.html"

        try:
            print(f"({index + 1}/{visit_count}) 正在访问随机用户空间: UID {uid} ...")
            response = session.get(
                visit_url,
                headers=headers,
                impersonate=BROWSER_IMPERSONATE,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            print(f"✅ 访问成功, 状态码: {response.status_code}")
        except Exception as exc:
            print(f"❌ 访问 UID {uid} 失败: {exc}")

        print(f"🕒 延迟 {delay_seconds} 秒...")
        sleep(delay_seconds)


def random_uid() -> int:
    return random.randint(1, 45000)


def get_user_credits(session, headers):
    print("\n--- 开始获取账户积分信息 ---")
    credit_url = f"{BASE_URL}home.php?mod=spacecp&ac=credit&showcredit=1"

    try:
        response = session.get(
            credit_url,
            headers=headers,
            impersonate=BROWSER_IMPERSONATE,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.text

        money_match = re.search(r"金钱: </em>(\d+)", content)
        prestige_match = re.search(r"威望: </em>(\d+)", content)
        points_match = re.search(r"<em>积分: </em>(\d+)", content)

        return {
            "money": money_match.group(1) if money_match else "未找到",
            "prestige": prestige_match.group(1) if prestige_match else "未找到",
            "points": points_match.group(1) if points_match else "未找到",
        }
    except Exception as exc:
        print(f"❌ 获取积分信息失败: {exc}")
        return None
