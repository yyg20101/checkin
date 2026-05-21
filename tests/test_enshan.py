import unittest

from checkin.tasks import enshan


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


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


class EnshanTaskTests(unittest.TestCase):
    def test_run_signs_and_extracts_profile_details(self):
        session = FakeSession(
            [
                FakeResponse('name="formhash" value="hash123" <a href="space-uid-42.html">'),
                FakeResponse('{"ok": true}'),
                FakeResponse(
                    "<h2> tester </h2>"
                    "用户组</em><a href=\"group\">高级会员</a>"
                    "恩山币</em> 88"
                ),
            ]
        )

        result = enshan.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.details,
            {
                "coins": "88",
                "username": "tester",
                "user_group": "高级会员",
                "uid": "42",
            },
        )
        self.assertEqual(session.calls[0][1], enshan.HOME_URL)
        self.assertEqual(session.calls[0][2]["headers"]["Cookie"], "foo=bar")
        self.assertEqual(session.calls[1][1], enshan.SIGN_URL)
        self.assertEqual(session.calls[1][2]["data"], {"formhash": "hash123"})

    def test_run_supports_discuz_uid_fallback(self):
        session = FakeSession(
            [
                FakeResponse("name=\"formhash\" value=\"hash123\" discuz_uid = '77'"),
                FakeResponse("ok"),
                FakeResponse("<h2>foo</h2>用户组</em><a>bar</a>恩山币</em> 9"),
            ]
        )

        result = enshan.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details["uid"], "77")

    def test_run_fails_when_uid_is_missing(self):
        session = FakeSession([FakeResponse('name="formhash" value="hash123"')])

        result = enshan.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("uid", result.message)


if __name__ == "__main__":
    unittest.main()
