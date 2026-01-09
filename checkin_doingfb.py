import os
import requests
import json
from bs4 import BeautifulSoup


# --- 核心函数 ---

def get_initial_data(session):
    """
    访问首页，使用 BeautifulSoup 解析初始 JSON 数据，并从中提取所有必要信息。
    """
    print("正在访问首页以获取初始数据...")
    url = "https://doingfb.com/"
    response = session.get(url)
    response.raise_for_status()

    # 输出响应信息
    print(f"[LOG] 响应状态码: {response.status_code}")
    print(f"[LOG] 响应 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"[LOG] 响应长度: {len(response.text)} 字符")
    # 检查是否有 Set-Cookie 响应头
    if 'Set-Cookie' in response.headers:
        print(f"[LOG] 服务器返回了 Set-Cookie 头（可能 session 已更新）")

    # 使用 BeautifulSoup 解析 HTML，更可靠地提取 JSON payload
    soup = BeautifulSoup(response.text, "html.parser")
    payload_script = soup.find("script", {"id": "flarum-json-payload", "type": "application/json"})

    if not payload_script or not payload_script.string:
        print(f"[LOG] 未找到 flarum-json-payload 脚本标签")
        print(f"[LOG] 页面标题: {soup.title.string if soup.title else 'N/A'}")
        raise ValueError("错误：无法在首页HTML中找到 'flarum-json-payload'。")

    json_payload = json.loads(payload_script.string)

    session_info = json_payload.get("session", {})
    user_id = session_info.get("userId")
    csrf_token = session_info.get("csrfToken")

    # 显示 session 信息
    print(f"[LOG] Session 数据: userId={user_id}, csrfToken={csrf_token[:20] if csrf_token else 'N/A'}...")

    if not user_id or not csrf_token:
        # 输出更详细的错误信息
        print(f"⚠️ 登录状态异常: userId={user_id}, csrfToken={'存在' if csrf_token else '不存在'}")
        print(f"⚠️ 这通常意味着 Cookie 已过期或无效，请更新 COOKIE_DOINGFB 环境变量。")
        raise ValueError("错误：无法从 'session' 数据中提取 userId 或 csrfToken。")
    print(f"✅ 成功获取 User ID: {user_id}")
    print(f"✅ 成功获取 CSRF Token: ******")

    user_resource = next((res for res in json_payload.get("resources", []) if res.get("type") == "users"), None)
    if not user_resource:
        raise ValueError("错误：无法在 'resources' 列表中找到用户数据。")

    attributes = user_resource.get("attributes", {})
    allow_checkin = attributes.get("allowCheckin", False)
    checkin_days_count = attributes.get("checkin_days_count", 0)

    return user_id, csrf_token, allow_checkin, checkin_days_count


def perform_checkin(session, user_id, csrf_token, allow_checkin, checkin_days_count):
    """
    执行签到，并解析返回的JSON，提取用户信息。
    :return: 一个包含用户信息的字典, e.g., {'displayName': 'test', 'id': 123, 'money': 500}
    """
    print("\n正在执行签到...")
    url = f"https://doingfb.com/api/users/{user_id}"

    data = {
        "data": {
            "type": "users",
            "attributes": {
                "allowCheckin": not allow_checkin,
                "checkin_days_count": checkin_days_count + 1,
                "checkin_type": "R"
            },
            "id": str(user_id)
        }
    }

    session.headers.update({
        "content-type": "application/json",
        "x-csrf-token": csrf_token,
    })

    response = session.post(url, json=data)
    session.headers.pop("x-http-method-override", None)
    response.raise_for_status()
    print("✅ 签到成功！正在解析返回的数据...")

    # -- 新增：解析返回的JSON数据 --
    response_data = response.json()

    # 使用 .get() 安全地提取嵌套数据
    data_node = response_data.get('data', {})
    attributes_node = data_node.get('attributes', {})

    # 提取所需信息
    final_info = {
        "displayName": attributes_node.get('displayName'),
        "id": data_node.get('id'),
        "money": attributes_node.get('money')
    }

    return final_info


# --- 主程序入口 ---

if __name__ == "__main__":
    # 从环境变量中获取 Cookie
    cookie = os.environ.get("COOKIE_DOINGFB")
    if not cookie:
        raise ValueError("错误：未找到 COOKIE_DOINGFB，请在 GitHub Secrets 中配置。")

    # 输出 Cookie 信息（部分隐藏，用于调试）
    print(f"[LOG] Cookie 长度: {len(cookie)} 字符")
    print(f"[LOG] Cookie 前50字符: {cookie[:50]}...")
    # 检查关键 Cookie 是否存在
    has_session = "flarum_session=" in cookie
    has_remember = "flarum_remember=" in cookie
    print(f"[LOG] 包含 flarum_session: {has_session}")
    print(f"[LOG] 包含 flarum_remember: {has_remember}")

    with requests.Session() as s:
        # 设置请求头，完全模拟浏览器行为（使用小写 header 名称）
        s.headers.update({
            "cookie": cookie,
            "user-agent": "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36 Edg/143.0.0.0",
        })

        try:
            # 1. 获取所有初始数据
            user_id, token, allow_checkin, days_count = get_initial_data(s)

            # 2. 检查是否可以签到，并执行操作
            if allow_checkin:
                # 执行签到并捕获返回的用户信息
                user_info = perform_checkin(s, user_id, token, allow_checkin, days_count)

                # -- 新增：打印最终的用户信息 --
                print("\n--- 任务结果 ---")
                if user_info and user_info.get("displayName"):
                    print(f"显示昵称: {user_info['displayName']}")
                    print(f"User ID: {user_info['id']}")
                    print(f"当前金币: {user_info['money']}")
                    # 输出标准化摘要
                    summary = {
                        "status": "success",
                        "message": f"💰 签到成功，金币: {user_info['money']}",
                        "details": {"coins": user_info['money'], "display_name": user_info['displayName']}
                    }
                    print(f"[CHECKIN_SUMMARY] {json.dumps(summary, ensure_ascii=False)}")
                else:
                    print("⚠️ 未能从签到响应中解析出完整的用户信息。")
                    summary = {"status": "failed", "message": "⚠️ 未能解析用户信息"}
                    print(f"[CHECKIN_SUMMARY] {json.dumps(summary, ensure_ascii=False)}")
            else:
                # 如果不能签到，直接告知用户
                print("\n--- 任务结果 ---")
                print(f"🟡 今天已经签到过了（已连续签到 {days_count} 天），无需重复签到。")
                summary = {
                    "status": "success",
                    "message": f"📅 已签到过，连续 {days_count} 天",
                    "details": {"consecutive_days": days_count}
                }
                print(f"[CHECKIN_SUMMARY] {json.dumps(summary, ensure_ascii=False)}")

            print("\n🎉 任务圆满完成！")

        except Exception as e:
            print(f"\n❌ 任务执行失败: {e}")