from unittest.mock import Mock

import pytest
import requests
from curl_cffi.requests import exceptions as browser_exceptions

from checkin.tasks import nodeseek


class FakeResponse:
    def __init__(self, payload=None, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        if self.payload is None:
            raise ValueError("not JSON")
        return self.payload


def make_session(response, board=None):
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get.return_value = board or FakeResponse()
    session.post.return_value = response
    return session


def test_run_signs_with_browser_fingerprint_and_extracts_reward():
    session = make_session(FakeResponse({"success": True, "message": "今天的签到收益是5个鸡腿"}))

    result = nodeseek.run("session=example", session_factory=lambda: session)

    assert result.status == "success"
    assert result.details["coins"] == 5
    assert result.details["rewards"] == [{"name": "签到奖励", "value": "5 个鸡腿"}]
    assert result.details["already_signed"] is False
    assert session.get.call_args.args == (nodeseek.BOARD_URL,)
    assert session.post.call_args.args == (nodeseek.SIGN_URL,)
    for call in (session.get.call_args, session.post.call_args):
        assert call.kwargs["headers"]["Cookie"] == "session=example"
        assert call.kwargs["impersonate"] == "chrome"
        assert call.kwargs["timeout"] == 30
        assert call.kwargs["allow_redirects"] is False
        assert "User-Agent" not in call.kwargs["headers"]
    assert session.post.call_args.kwargs["data"] == ""
    assert session.post.call_args.kwargs["headers"]["Referer"] == nodeseek.BOARD_URL
    assert session.post.call_args.kwargs["headers"]["Origin"] == nodeseek.BASE_URL


@pytest.mark.parametrize("http_status", [200, 500])
def test_already_signed_is_success_even_with_http_500_and_success_false(http_status):
    session = make_session(
        FakeResponse({"success": False, "message": "今天已完成签到，请勿重复操作"}, http_status)
    )

    result = nodeseek.run("session=example", session_factory=lambda: session)

    assert result.status == "success"
    assert result.details["already_signed"] is True
    assert result.details["http_status"] == http_status
    assert "coins" not in result.details


@pytest.mark.parametrize(
    "payload,http_status",
    [
        ({"message": "未登录"}, 200),
        ({"message": "请先登录"}, 500),
        ({"message": "登录失效"}, 200),
        ({"message": "登录已过期"}, 200),
        ({"status": 404, "message": "今天已完成签到"}, 200),
        ({"status": "404"}, 500),
        ({"success": False, "message": "鸡腿不足，签到失败"}, 200),
        ({"success": True, "message": "签到错误"}, 200),
        ({"success": False, "message": "签到失败"}, 500),
        ({"success": False, "message": "今天的签到收益是5个鸡腿"}, 200),
        ({"message": "未知结果"}, 200),
        ({"success": True}, 200),
        ({"message": {"unexpected": "object"}}, 200),
        (None, 200),
        ([], 200),
        (None, 502),
        ({"message": "今天已完成签到"}, 403),
    ],
)
def test_run_rejects_login_failures_and_unconfirmed_results(payload, http_status):
    session = make_session(FakeResponse(payload, http_status))

    result = nodeseek.run("session=example", session_factory=lambda: session)

    assert result.status == "failed"


@pytest.mark.parametrize("http_status", [302, 403, 500])
def test_board_failure_stops_before_signing(http_status):
    session = make_session(FakeResponse(), board=FakeResponse(status_code=http_status))

    result = nodeseek.run("session=example", session_factory=lambda: session)

    assert result.status == "failed"
    assert result.details == {"stage": "board", "http_status": http_status}
    session.post.assert_not_called()
    if http_status == 403:
        assert "Cloudflare" in result.message


def test_attendance_cloudflare_challenge_is_reported():
    session = make_session(FakeResponse(status_code=403, headers={"cf-mitigated": "challenge"}))

    result = nodeseek.run("session=example", session_factory=lambda: session)

    assert result.status == "failed"
    assert "Cloudflare" in result.message
    assert result.details["stage"] == "attendance"


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("error_class", [requests.Timeout, browser_exceptions.Timeout])
def test_network_failure_is_reported_without_leaking_cookie(method, error_class):
    session = make_session(FakeResponse())
    getattr(session, method).side_effect = error_class("request included session=secret-cookie")

    result = nodeseek.run("session=secret-cookie", session_factory=lambda: session)

    assert result.status == "failed"
    assert result.details["stage"] == ("board" if method == "get" else "attendance")
    assert "secret-cookie" not in result.to_summary_line()


def test_api_message_redacts_cookie_and_individual_values():
    cookie = "session=secret-cookie; fog=another-secret"
    session = make_session(FakeResponse({"message": f"请求失败: {cookie}; another-secret"}))

    result = nodeseek.run(cookie, session_factory=lambda: session)

    assert result.status == "failed"
    assert "secret-cookie" not in result.to_summary_line()
    assert "another-secret" not in result.to_summary_line()


def test_template_reward_message_without_success_field_is_accepted():
    session = make_session(FakeResponse({"message": "今天的签到收益是8个鸡腿"}))

    result = nodeseek.run("session=example", session_factory=lambda: session)

    assert result.status == "success"
    assert result.details["coins"] == 8
