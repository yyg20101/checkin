import json
import unittest

import requests

from checkin.tasks import doingfb


class FakeResponse:
    def __init__(self, text="", payload=None, status_code=200, headers=None):
        self.text = text
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html"}

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
        self.cookies = {}
        self.headers = {}

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


def initial_payload(allow_checkin=True, days_count=2):
    payload = {
        "session": {"userId": 42, "csrfToken": "token-123"},
        "resources": [
            {
                "type": "users",
                "attributes": {
                    "allowCheckin": allow_checkin,
                    "checkin_days_count": days_count,
                },
            }
        ],
    }
    return (
        '<script id="flarum-json-payload" type="application/json">'
        f"{json.dumps(payload)}"
        "</script>"
    )


class DoingfbTaskTests(unittest.TestCase):
    def test_run_signs_and_extracts_user_details(self):
        session = FakeSession(
            [
                FakeResponse(initial_payload()),
                FakeResponse(
                    payload={
                        "data": {
                            "id": "42",
                            "attributes": {"displayName": "tester", "money": 18},
                        }
                    }
                ),
            ]
        )

        result = doingfb.run("foo=bar; baz=qux", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details, {"coins": 18, "display_name": "tester"})
        self.assertEqual(session.cookies, {"foo": "bar", "baz": "qux"})
        self.assertEqual(session.calls[0][0], "GET")
        self.assertEqual(session.calls[1][0], "POST")
        self.assertIn("/api/users/42", session.calls[1][1])
        self.assertNotIn("x-http-method-override", session.headers)

    def test_run_returns_success_when_already_signed(self):
        session = FakeSession([FakeResponse(initial_payload(allow_checkin=False, days_count=7))])

        result = doingfb.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details, {"consecutive_days": 7})
        self.assertEqual(len(session.calls), 1)

    def test_run_fails_when_initial_payload_is_missing(self):
        session = FakeSession([FakeResponse("<html>login</html>")])

        result = doingfb.run("foo=bar", session_factory=lambda: session)

        self.assertEqual(result.status, "failed")
        self.assertIn("flarum-json-payload", result.message)


if __name__ == "__main__":
    unittest.main()
