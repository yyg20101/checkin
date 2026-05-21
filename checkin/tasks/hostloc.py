from __future__ import annotations

import random
import re
import time

from curl_cffi import requests

from checkin.core.result import CheckinResult


BASE_URL = "https://hostloc.com/"
IMPERSONATE_BROWSER = "chrome110"
RANDOM_VISITS_COUNT = 5
DELAY_SECONDS = 3


def run(cookie: str) -> CheckinResult:
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    }
    with requests.Session() as session:
        visit_random_profiles(session, headers)
        credits = get_user_credits(session, headers)
        if not credits:
            return CheckinResult.failed("❌ 未能获取积分信息")
        return CheckinResult.success(
            f"💎 金钱: {credits['money']} | 🏆 积分: {credits['points']}",
            credits,
        )


def visit_random_profiles(session, headers):
    print(f"\n--- 开始执行随机访问任务，共 {RANDOM_VISITS_COUNT} 次 ---")
    headers["Referer"] = BASE_URL

    for index in range(RANDOM_VISITS_COUNT):
        random_uid = random.randint(1, 45000)
        visit_url = f"{BASE_URL}space-uid-{random_uid}.html"

        try:
            print(f"({index + 1}/{RANDOM_VISITS_COUNT}) 正在访问随机用户空间: UID {random_uid} ...")
            response = session.get(visit_url, headers=headers, impersonate=IMPERSONATE_BROWSER)
            response.raise_for_status()
            print(f"✅ 访问成功, 状态码: {response.status_code}")
        except Exception as exc:
            print(f"❌ 访问 UID {random_uid} 失败: {exc}")

        print(f"🕒 延迟 {DELAY_SECONDS} 秒...")
        time.sleep(DELAY_SECONDS)


def get_user_credits(session, headers):
    print("\n--- 开始获取账户积分信息 ---")
    credit_url = f"{BASE_URL}home.php?mod=spacecp&ac=credit&showcredit=1"

    try:
        response = session.get(credit_url, headers=headers, impersonate=IMPERSONATE_BROWSER)
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
