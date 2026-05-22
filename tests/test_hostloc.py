import unittest

from checkin.tasks import hostloc
from checkin.core.http import BROWSER_IMPERSONATE


class FakeResponse:
    def __init__(self, text="", status_code=200):
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


class HostlocTaskTests(unittest.TestCase):
    def test_run_visits_profiles_and_extracts_credits(self):
        session = FakeSession(
            [
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse("金钱: </em>12 威望: </em>3 <em>积分: </em>88"),
            ]
        )
        slept = []

        result = hostloc.run(
            "foo=bar",
            session_factory=lambda: session,
            uid_factory=lambda: 100,
            sleep=slept.append,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.details, {"money": "12", "prestige": "3", "points": "88"})
        self.assertEqual(len(session.calls), 6)
        self.assertEqual(session.calls[0][1], f"{hostloc.BASE_URL}space-uid-100.html")
        self.assertEqual(session.calls[0][2]["headers"]["Cookie"], "foo=bar")
        self.assertEqual(session.calls[0][2]["impersonate"], BROWSER_IMPERSONATE)
        self.assertEqual(session.calls[0][2]["timeout"], hostloc.TIMEOUT_SECONDS)
        self.assertEqual(session.calls[-1][1], f"{hostloc.BASE_URL}home.php?mod=spacecp&ac=credit&showcredit=1")
        self.assertEqual(session.calls[-1][2]["timeout"], hostloc.TIMEOUT_SECONDS)
        self.assertEqual(slept, [hostloc.DELAY_SECONDS] * hostloc.RANDOM_VISITS_COUNT)

    def test_run_fails_when_credits_request_fails(self):
        session = FakeSession(
            [
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse("visit ok"),
                FakeResponse(status_code=500),
            ]
        )

        result = hostloc.run(
            "foo=bar",
            session_factory=lambda: session,
            uid_factory=lambda: 100,
            sleep=lambda delay: None,
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("积分信息", result.message)


if __name__ == "__main__":
    unittest.main()
