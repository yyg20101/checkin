import os
import re
import time
import random
# 使用 curl_cffi 来模拟浏览器，防止被屏蔽
from curl_cffi import requests

# --- 配置信息 ---
BASE_URL = "https://hostloc.com/"
IMPERSONATE_BROWSER = "chrome110"
RANDOM_VISITS_COUNT = 5
DELAY_SECONDS = 3


# --- 核心功能函数 ---

def visit_random_profiles(session, headers):
    """
    模拟访问随机用户的空间页面。
    这是论坛任务的一部分，用于增加活跃度和积分。
    """
    print(f"\n--- 开始执行随机访问任务，共 {RANDOM_VISITS_COUNT} 次 ---")
    headers['Referer'] = BASE_URL

    for i in range(RANDOM_VISITS_COUNT):
        random_uid = random.randint(1, 45000)
        visit_url = f"{BASE_URL}space-uid-{random_uid}.html"

        try:
            print(f"({i + 1}/{RANDOM_VISITS_COUNT}) 正在访问随机用户空间: UID {random_uid} ...")
            response = session.get(visit_url, headers=headers, impersonate=IMPERSONATE_BROWSER)
            response.raise_for_status()
            print(f"✅ 访问成功, 状态码: {response.status_code}")
        except Exception as e:
            print(f"❌ 访问 UID {random_uid} 失败: {e}")

        print(f"🕒 延迟 {DELAY_SECONDS} 秒...")
        time.sleep(DELAY_SECONDS)


def get_user_credits(session, headers):
    """
    访问用户积分页面，并使用正则表达式提取积分信息。
    """
    print("\n--- 开始获取账户积分信息 ---")
    credit_url = f"{BASE_URL}home.php?mod=spacecp&ac=credit&showcredit=1"

    try:
        response = session.get(credit_url, headers=headers, impersonate=IMPERSONATE_BROWSER)
        response.raise_for_status()

        content = response.text

        # 使用正则表达式提取金钱、威望和积分
        money_match = re.search(r'金钱: </em>(\d+)', content)
        prestige_match = re.search(r'威望: </em>(\d+)', content)
        points_match = re.search(r'<em>积分: </em>(\d+)', content)

        money = money_match.group(1) if money_match else "未找到"
        prestige = prestige_match.group(1) if prestige_match else "未找到"
        points = points_match.group(1) if points_match else "未找到"

        return {
            "money": money,
            "prestige": prestige,
            "points": points
        }

    except Exception as e:
        print(f"❌ 获取积分信息失败: {e}")
        return None


# --- 主程序入口 ---

def main():
    """
    主执行函数
    """
    cookie = os.environ.get("COOKIE_HOSTLOC")
    if not cookie:
        raise ValueError("错误：未找到 COOKIE_HOSTLOC，请在 GitHub Secrets 中配置。")
    print("✅ 成功读取 Cookie Secret。")

    headers = {
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    }

    # 使用 Session 对象来自动管理 Cookie
    with requests.Session() as s:
        # 执行随机访问任务
        visit_random_profiles(s, headers)

        # 获取最终的积分信息
        credits = get_user_credits(s, headers)

        # 打印最终结果
        print("\n========== 任务最终结果 ==========")
        if credits:
            print(f"|  金钱: {credits['money']}")
            print(f"|  威望: {credits['prestige']}")
            print(f"|  积分: {credits['points']}")
            if "未找到" in credits.values():
                print("\n[注意] 部分信息提取失败，可能是网站页面结构已更新。")
        else:
            print("未能获取到账户积分信息。")
        print("==================================")
        print("\n🎉 任务圆满完成！")


if __name__ == "__main__":
    main()