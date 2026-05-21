import unittest

import requests

from checkin.tasks import binmt


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


class BinmtTaskTests(unittest.TestCase):
    def test_run_signs_and_extracts_reward_details(self):
        session = FakeSession(
            [
                FakeResponse('<input type="hidden" name="formhash" value="abc+123">'),
                FakeResponse("签到成功"),
                FakeResponse(
                    '<input id="lxreward" value="%E9%87%91%E5%B8%81%2B5">'
                    '<input id="lxtdays" value="12">'
                ),
            ]
        )

        result = binmt.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.details,
            {
                "rewards": [{"name": "积分奖励", "value": "金币+5"}],
                "consecutive_days": "12",
            },
        )
        self.assertEqual(session.calls[0][1], binmt.SIGN_PAGE_URL)
        self.assertEqual(session.calls[0][2]["headers"]["Cookie"], "foo=bar")
        self.assertIn("formhash=abc%2B123", session.calls[1][1])
        self.assertEqual(session.calls[1][2]["headers"]["Cookie"], "foo=bar")
        self.assertEqual(session.calls[2][1], binmt.SIGN_PAGE_URL)

    def test_run_fails_when_formhash_is_missing(self):
        session = FakeSession([FakeResponse("<html>login</html>")])

        result = binmt.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("formhash", result.message)
        self.assertEqual(len(session.calls), 1)

    def test_run_fails_on_illegal_request_response(self):
        session = FakeSession(
            [
                FakeResponse('name="formhash" value="abc"'),
                FakeResponse("访问请求当中含有非法字符"),
            ]
        )

        result = binmt.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("非法字符", result.message)

    def test_run_fails_when_still_not_signed(self):
        session = FakeSession(
            [
                FakeResponse('name="formhash" value="abc"'),
                FakeResponse("签到成功"),
                FakeResponse("您今天还没有签到"),
            ]
        )

        result = binmt.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("未签到", result.message)


if __name__ == "__main__":
    unittest.main()
