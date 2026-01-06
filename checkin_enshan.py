import os
import re
import sys
import json
from curl_cffi import requests

BASE_URL = "https://www.right.com.cn/forum/"
IMPERSONATE_BROWSER = "chrome110"


def get_home_vars(session, headers):
    print("\n--- 步骤1: 正在访问论坛首页 (模拟每日登录) ---")
    home_url = f"{BASE_URL}forum.php"
    req_headers = headers.copy()
    req_headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    try:
        response = session.get(home_url, headers=req_headers, impersonate=IMPERSONATE_BROWSER)
        response.raise_for_status()
        print("✅ 访问首页成功。")
        content = response.text
        formhash_match = re.search(r'name="formhash"\s+value="([^"]+)"', content)
        uid_match = re.search(r"discuz_uid\s*=\s*'(\d+)'", content)
        formhash = formhash_match.group(1) if formhash_match else None
        uid = uid_match.group(1) if uid_match else None
        if not formhash or not uid:
            print("❌ 未能提取到 formhash 或 uid。")
            return None, None
        print(f"✅ 提取 formhash 与 uid 成功。")
        return formhash, uid
    except Exception as e:
        print(f"❌ 访问首页失败: {e}")
        return None, None


def do_sign(session, headers, formhash):
    print("\n--- 步骤2: 正在执行签到 ---")
    sign_url = f"{BASE_URL}plugin.php?id=erling_qd%3Aaction&action=sign"
    ajax_headers = headers.copy()
    ajax_headers.update({
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://www.right.com.cn',
        'Referer': f"{BASE_URL}erling_qd-sign_in.html",
        'Connection': 'keep-alive',
        'DNT': '1'
    })
    data = f"formhash={formhash}"
    try:
        response = session.post(sign_url, headers=ajax_headers, data=data, impersonate=IMPERSONATE_BROWSER)
        response.raise_for_status()
        print("✅ 签到请求成功。")
        return True
    except Exception as e:
        print(f"❌ 签到请求失败: {e}")
        return False


def get_profile_info(session, headers, uid):
    print("\n--- 步骤3: 正在获取个人中心信息 ---")
    profile_url = f"{BASE_URL}home.php?mod=space&uid={uid}&do=profile&mycenter=1"
    req_headers = headers.copy()
    req_headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': f"{BASE_URL}erling_qd-sign_in.html?mobile=2",
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Host': 'www.right.com.cn',
        'Cache-Control': 'max-age=0'
    })
    try:
        response = session.get(profile_url, headers=req_headers, impersonate=IMPERSONATE_BROWSER)
        response.raise_for_status()
        content = response.text
        esb_match = re.search(r"恩山币\s*</em>\s*(\d+)", content)
        user_match = re.search(r"<h2[^>]*>\s*(?:<a[^>]*>)?([^<]+)", content)
        gid_match = re.search(r"用户组[^>]*>[\s\S]*?<a[^>]*>([^<]+)</a>", content)
        esb = esb_match.group(1) if esb_match else None
        user = user_match.group(1) if user_match else None
        gid = gid_match.group(1) if gid_match else None
        if not esb:
            print("❌ 未能解析到恩山币信息。")
        else:
            print("✅ 成功获取到恩山币信息。")
        return esb, user, gid
    except Exception as e:
        print(f"❌ 获取个人中心信息失败: {e}")
        return None, None, None


def main():
    cookie = os.environ.get("COOKIE_ENSHAN")
    if not cookie:
        print("错误：未找到 COOKIE_ENSHAN，请在 GitHub Secrets 中配置。")
        sys.exit(1)
    print("✅ 成功读取 Cookie Secret。")

    base_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0',
        'Cookie': cookie,
    }

    with requests.Session() as s:
        s.headers.update(base_headers)
        formhash, uid = get_home_vars(s, base_headers)
        if not formhash or not uid:
            sys.exit(1)

        signed = do_sign(s, base_headers, formhash)
        if not signed:
            sys.exit(1)

        esb, user, gid = get_profile_info(s, base_headers, uid)

        print("\n========== 任务最终结果 ==========")
        if esb is not None:
            print(f"|  用户名: {user if user else '-'}")
            print(f"|  uid: {uid}")
            print(f"|  用户组: {gid if gid else '-'}")
            print(f"|  恩山币: {esb}")
            # 输出标准化摘要
            summary = {
                "status": "success",
                "message": f"🪙 签到成功，恩山币: {esb}",
                "details": {"coins": esb, "username": user, "user_group": gid}
            }
            print(f"[CHECKIN_SUMMARY] {json.dumps(summary, ensure_ascii=False)}")
        else:
            print("|  未能获取到恩山币信息。")
            summary = {"status": "failed", "message": "❌ 未能获取恩山币信息"}
            print(f"[CHECKIN_SUMMARY] {json.dumps(summary, ensure_ascii=False)}")
        print("==================================")
        print("\n🎉 任务圆满完成！")


if __name__ == "__main__":
    main()