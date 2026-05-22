import unittest

import requests

from checkin.tasks import smzdm


class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


class FakeHttpClient:
    def __init__(self):
        self.calls = []

    def post(self, *args, **kwargs):
        url = kwargs.get("url") or args[0]
        self.calls.append(("POST", url, kwargs))
        if "robot/token" in url:
            return FakeResponse({"data": {"token": "robot-token"}})
        if "checkin/all_reward" in url:
            return FakeResponse(
                {
                    "data": {
                        "normal_reward": {
                            "reward_add": {"content": "+5 金币"},
                            "sub_title": "连续签到 3 天",
                        }
                    }
                }
            )
        if "checkin" in url:
            return FakeResponse({"error_msg": "签到成功"})
        if "jsonp_draw" in url:
            return FakeResponse({"error_msg": "活动成功"})
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(
            text=(
                "level/vip.png?v=1"
                '<a href="https://zhiyou.smzdm.com/user"> tester </a>'
                '<div class="assets-part assets-gold">\n'
                '<span class="assets-part-element assets-num">100</span>'
                '<div class="assets-part assets-prestige">\n'
                '<span class="assets-part-element assets-num">20</span>'
            )
        )


class SmzdmTaskTests(unittest.TestCase):
    def test_run_uses_injected_http_client_and_renders_rewards(self):
        client = FakeHttpClient()

        result = smzdm.run("foo=bar", http_client=client)

        self.assertEqual(result.status, "success")
        self.assertIn("签到成功", result.message)
        self.assertIn("+5 金币", result.message)
        self.assertEqual(result.details["sign_result"], "签到成功")
        self.assertEqual(
            result.details["rewards"],
            [
                {"name": "签到奖励", "value": "+5 金币"},
                {"name": "连续签到", "value": "连续签到 3 天"},
            ],
        )
        self.assertEqual(result.details["activity"][0], {"name": "活动结果", "value": "活动成功"})
        self.assertEqual(client.calls[0][0], "POST")
        self.assertIn("jsonp_draw", client.calls[0][1])
        self.assertEqual(client.calls[0][2]["headers"]["Cookie"], "foo=bar")
        self.assertEqual(client.calls[0][2]["timeout"], smzdm.TIMEOUT_SECONDS)
        self.assertIn("robot/token", client.calls[2][1])
        self.assertEqual(client.calls[2][2]["timeout"], smzdm.TIMEOUT_SECONDS)
        self.assertIn("checkin/all_reward", client.calls[4][1])

    def test_safe_active_does_not_block_main_checkin(self):
        class FailingActiveClient(FakeHttpClient):
            def post(self, *args, **kwargs):
                url = kwargs.get("url") or args[0]
                if "jsonp_draw" in url:
                    raise RuntimeError("activity failed")
                return super().post(*args, **kwargs)

        result = smzdm.run("foo=bar", http_client=FailingActiveClient())

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details["activity"], [{"name": "活动结果", "value": "活动接口失败，不影响主签到"}])

    def test_run_wraps_main_checkin_request_errors(self):
        class FailingMainClient(FakeHttpClient):
            def post(self, *args, **kwargs):
                url = kwargs.get("url") or args[0]
                if "robot/token" in url:
                    raise requests.ConnectionError("network down")
                return super().post(*args, **kwargs)

        result = smzdm.run("foo=bar", http_client=FailingMainClient())

        self.assertEqual(result.status, "failed")
        self.assertIn("请求失败", result.message)
        self.assertEqual(result.details["error"], "network down")


if __name__ == "__main__":
    unittest.main()
