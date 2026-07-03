import unittest

import requests

from checkin.tasks import hifiti


class FakeResponse:
    def __init__(self, text, payload=None, status_code=200):
        self.text = text
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

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

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)


class HifitiTaskTests(unittest.TestCase):
    def test_run_extracts_sign_and_posts_checkin(self):
        session = FakeSession(
            [
                FakeResponse('<script>var sign = "abc+123"</script>'),
                FakeResponse(
                    '{"message": "签到成功，奖励 10 金币"}',
                    {"message": "签到成功，奖励 10 金币"},
                ),
            ]
        )

        result = hifiti.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details, {"sign_result": "签到成功，奖励 10 金币"})
        self.assertEqual(session.calls[0][0], "GET")
        self.assertEqual(session.calls[0][1], hifiti.SIGN_URL)
        self.assertEqual(session.calls[0][2]["headers"]["Cookie"], "foo=bar")
        self.assertEqual(session.calls[1][0], "POST")
        self.assertEqual(session.calls[1][2]["data"], {"sign": "abc+123"})

    def test_run_falls_back_to_direct_post_when_sign_token_is_missing(self):
        session = FakeSession(
            [
                FakeResponse("<html>new sign page without token</html>"),
                FakeResponse('{"message": "签到成功，奖励 2 金币"}', {"message": "签到成功，奖励 2 金币"}),
            ]
        )

        result = hifiti.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details, {"sign_result": "签到成功，奖励 2 金币"})
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[1][0], "POST")
        self.assertEqual(session.calls[1][2]["data"], {})

    def test_run_treats_direct_post_login_message_as_failed(self):
        session = FakeSession(
            [
                FakeResponse("<html>login</html>"),
                FakeResponse('{"code":"0","message":"请登录后再签到!"}', {"code": "0", "message": "请登录后再签到!"}),
            ]
        )

        result = hifiti.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("请登录", result.message)
        self.assertEqual(result.details, {"sign_result": "请登录后再签到!"})

    def test_run_treats_login_message_as_failed(self):
        session = FakeSession(
            [
                FakeResponse('var sign = "abc"'),
                FakeResponse('{"message": "请先登录"}', {"message": "请先登录"}),
            ]
        )

        result = hifiti.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.details, {"sign_result": "请先登录"})


if __name__ == "__main__":
    unittest.main()
