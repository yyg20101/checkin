import unittest

import requests

from checkin.tasks import v2ex


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


class V2exTaskTests(unittest.TestCase):
    def test_run_redeems_daily_reward_and_extracts_details(self):
        session = FakeSession(
            [
                FakeResponse("home"),
                FakeResponse("redeem?once=abc%2B123'"),
                FakeResponse("", status_code=302),
                FakeResponse("每日登录奖励已领取 已连续登录12天"),
                FakeResponse("每日登录奖励 10 铜币"),
            ]
        )

        result = v2ex.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.details,
            {
                "consecutive_days": "12",
                "rewards": [{"name": "每日登录奖励", "value": "10 铜币"}],
            },
        )
        self.assertEqual(session.calls[0][1], v2ex.HOME_URL)
        self.assertEqual(session.calls[0][2]["headers"]["Cookie"], "foo=bar")
        self.assertIn("once=abc%2B123", session.calls[2][1])
        self.assertFalse(session.calls[2][2]["allow_redirects"])

    def test_run_handles_already_signed_daily_page(self):
        session = FakeSession(
            [
                FakeResponse("home"),
                FakeResponse("每日登录奖励已领取 已连续登录8天"),
                FakeResponse("每日登录奖励 7 铜币"),
            ]
        )

        result = v2ex.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details["consecutive_days"], "8")
        self.assertEqual(len(session.calls), 3)

    def test_run_fails_when_once_is_missing_before_signing(self):
        session = FakeSession(
            [
                FakeResponse("home"),
                FakeResponse("领取 X 铜币"),
            ]
        )

        result = v2ex.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("once", result.message)

    def test_run_fails_when_daily_reward_is_still_unsigned(self):
        session = FakeSession(
            [
                FakeResponse("home"),
                FakeResponse("redeem?once=abc'"),
                FakeResponse("", status_code=302),
                FakeResponse("领取 X 铜币"),
            ]
        )

        result = v2ex.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("未领取", result.message)


if __name__ == "__main__":
    unittest.main()
