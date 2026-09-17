import io
import json
import unittest
import urllib.error

from ai_readiness.nerdgraph import NerdGraphError, make_live_client


def _http_error(code, body=b"error body"):
    return urllib.error.HTTPError(url="https://api.newrelic.com/graphql", code=code, msg="err",
                                   hdrs=None, fp=io.BytesIO(body))


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


class ScriptedUrlopen:
    """Each call pops the next scripted outcome: an exception instance (to
    raise) or a dict payload (to wrap in a FakeResponse)."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


class TestLiveClientRetry(unittest.TestCase):
    def test_succeeds_without_retry_on_first_try(self):
        urlopen = ScriptedUrlopen([{"data": {"ok": True}}])
        gql = make_live_client("key", _urlopen=urlopen, _sleep=lambda s: None)
        result = gql("query { x }", fixture_key="ignored")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.calls, 1)

    def test_retries_429_then_succeeds(self):
        urlopen = ScriptedUrlopen([_http_error(429), {"data": {"ok": True}}])
        sleeps = []
        gql = make_live_client("key", _urlopen=urlopen, _sleep=sleeps.append)
        result = gql("query { x }")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.calls, 2)
        self.assertEqual(len(sleeps), 1)

    def test_retries_503_with_exponential_backoff(self):
        urlopen = ScriptedUrlopen([_http_error(503), _http_error(503), {"data": {"ok": True}}])
        sleeps = []
        gql = make_live_client("key", retry_base_delay=1.0, _urlopen=urlopen, _sleep=sleeps.append)
        result = gql("query { x }")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_gives_up_after_max_attempts(self):
        urlopen = ScriptedUrlopen([_http_error(429), _http_error(429), _http_error(429)])
        gql = make_live_client("key", max_attempts=3, _urlopen=urlopen, _sleep=lambda s: None)
        with self.assertRaises(NerdGraphError):
            gql("query { x }")
        self.assertEqual(urlopen.calls, 3)

    def test_does_not_retry_non_transient_4xx(self):
        urlopen = ScriptedUrlopen([_http_error(401, b"unauthorized")])
        gql = make_live_client("key", _urlopen=urlopen, _sleep=lambda s: None)
        with self.assertRaises(NerdGraphError):
            gql("query { x }")
        self.assertEqual(urlopen.calls, 1)  # no retry burned on a permission error


if __name__ == "__main__":
    unittest.main()
