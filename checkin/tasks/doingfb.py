from __future__ import annotations

import json

from bs4 import BeautifulSoup

from checkin.core.http import DEFAULT_TIMEOUT_SECONDS, REQUEST_EXCEPTIONS, SessionFactory, standard_session
from checkin.core.result import CheckinResult


TIMEOUT_SECONDS = DEFAULT_TIMEOUT_SECONDS


def run(cookie: str, session_factory: SessionFactory = standard_session) -> CheckinResult:
    try:
        with session_factory() as session:
            session.cookies.update(_parse_cookie(cookie))
            session.headers.update(
                {
                    "user-agent": "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36 Edg/143.0.0.0",
                }
            )

            user_id, token, allow_checkin, days_count = get_initial_data(session)
            if not allow_checkin:
                return CheckinResult.success(
                    f"📅 已签到过，连续 {days_count} 天",
                    {"consecutive_days": days_count},
                )

            user_info = perform_checkin(session, user_id, token, allow_checkin, days_count)
            display_name = user_info.get("displayName")
            money = user_info.get("money")
            if not display_name:
                return CheckinResult.failed("⚠️ 未能解析用户信息")
            return CheckinResult.success(
                f"💰 签到成功，硬币: {money}",
                {"coins": money, "display_name": display_name},
            )
    except REQUEST_EXCEPTIONS as exc:
        return CheckinResult.failed(
            "DoingFB 签到请求失败",
            {"error": str(exc)},
        )
    except ValueError as exc:
        return CheckinResult.failed(
            f"DoingFB 签到失败: {exc}",
            {"error": str(exc)},
        )


def _parse_cookie(cookie: str) -> dict[str, str]:
    cookie_dict = {}
    for item in cookie.split(";"):
        if "=" in item:
            key, value = item.strip().split("=", 1)
            cookie_dict[key] = value
    return cookie_dict


def get_initial_data(session):
    print("正在访问首页以获取初始数据...")
    url = "https://doingfb.com/"
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    print(f"[LOG] 响应状态码: {response.status_code}")
    print(f"[LOG] 响应 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"[LOG] 响应长度: {len(response.text)} 字符")

    soup = BeautifulSoup(response.text, "html.parser")
    payload_script = soup.find("script", {"id": "flarum-json-payload", "type": "application/json"})
    if not payload_script or not payload_script.string:
        print("[LOG] 未找到 flarum-json-payload 脚本标签")
        print(f"[LOG] 页面标题: {soup.title.string if soup.title else 'N/A'}")
        raise ValueError("错误：无法在首页HTML中找到 'flarum-json-payload'。")

    json_payload = json.loads(payload_script.string)
    session_info = json_payload.get("session", {})
    user_id = session_info.get("userId")
    csrf_token = session_info.get("csrfToken")
    print(f"[LOG] Session 数据: userId={user_id}, csrfToken={'存在' if csrf_token else '不存在'}")

    if not user_id or not csrf_token:
        print(f"⚠️ 登录状态异常: userId={user_id}, csrfToken={'存在' if csrf_token else '不存在'}")
        print("⚠️ 这通常意味着 Cookie 已过期或无效，请更新 COOKIE_DOINGFB 环境变量。")
        raise ValueError("错误：无法从 'session' 数据中提取 userId 或 csrfToken。")

    print(f"✅ 成功获取 User ID: {user_id}")
    print("✅ 成功获取 CSRF Token: ******")

    user_resource = next((res for res in json_payload.get("resources", []) if res.get("type") == "users"), None)
    if not user_resource:
        raise ValueError("错误：无法在 'resources' 列表中找到用户数据。")

    attributes = user_resource.get("attributes", {})
    allow_checkin = attributes.get("allowCheckin", False)
    checkin_days_count = attributes.get("checkin_days_count", 0)

    return user_id, csrf_token, allow_checkin, checkin_days_count


def perform_checkin(session, user_id, csrf_token, allow_checkin, checkin_days_count):
    print("\n正在执行签到...")
    url = f"https://doingfb.com/api/users/{user_id}"
    data = {
        "data": {
            "type": "users",
            "attributes": {
                "allowCheckin": not allow_checkin,
                "checkin_days_count": checkin_days_count + 1,
                "checkin_type": "R",
            },
            "id": str(user_id),
        }
    }

    session.headers.update(
        {
            "content-type": "application/json; charset=UTF-8",
            "origin": "https://doingfb.com",
            "referer": "https://doingfb.com/",
            "x-csrf-token": csrf_token,
            "x-http-method-override": "PATCH",
        }
    )

    json_body = json.dumps(data, separators=(",", ":"))
    print(f"[DEBUG] 请求 URL: {url}")
    response = session.post(url, data=json_body, timeout=TIMEOUT_SECONDS)
    session.headers.pop("x-http-method-override", None)

    print(f"[DEBUG] 响应状态码: {response.status_code}")
    response.raise_for_status()
    print("✅ 签到成功！正在解析返回的数据...")

    response_data = response.json()
    data_node = response_data.get("data", {})
    attributes_node = data_node.get("attributes", {})
    return {
        "displayName": attributes_node.get("displayName"),
        "id": data_node.get("id"),
        "money": attributes_node.get("money"),
    }
