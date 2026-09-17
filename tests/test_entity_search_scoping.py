import unittest

from ai_readiness.checks import apm_coverage, infra_gpu, security_vuln
from ai_readiness.checks.base import Context


class RecordingGql:
    """Records every call and returns a shaped-but-empty response for
    whichever NerdGraph field the query document targets, so each check's
    run() completes without raising -- these tests only care about what was
    sent, not what came back."""

    def __init__(self):
        self.calls = []

    def __call__(self, query, variables=None, fixture_key=None):
        self.calls.append((query, variables))
        if "entitySearch" in query and "count" in query:
            return {"actor": {"entitySearch": {"count": 0}}}
        if "entitySearch" in query:
            return {"actor": {"entitySearch": {"results": {"entities": [], "nextCursor": None}}}}
        if "nrql" in query:
            return {"actor": {"account": {"nrql": {"results": []}}}}
        raise AssertionError(f"unexpected query: {query}")


def _ctx(gql, account_id=42):
    return Context(gql=gql, account_id=account_id, lookback_days=30, config=_config())


def _config():
    from ai_readiness import config as config_module
    return config_module.THRESHOLDS


class TestEntitySearchScopedToAccount(unittest.TestCase):
    """Each of these checks queries entitySearch, which spans every account
    the user key can reach unless scoped -- these confirm the accountId
    filter is actually present in the outgoing query, not just that the
    check runs."""

    def test_apm_coverage_scopes_entity_search_to_account(self):
        gql = RecordingGql()
        apm_coverage.run(_ctx(gql, account_id=42))
        entity_search_calls = [v for q, v in gql.calls if "entitySearch" in q]
        self.assertTrue(entity_search_calls)
        for variables in entity_search_calls:
            self.assertIn("accountId = 42", variables["query"])

    def test_infra_gpu_scopes_host_count_to_account(self):
        gql = RecordingGql()
        infra_gpu.run(_ctx(gql, account_id=42))
        entity_search_calls = [v for q, v in gql.calls if "entitySearch" in q]
        self.assertTrue(entity_search_calls)
        for variables in entity_search_calls:
            self.assertIn("accountId = 42", variables["query"])

    def test_security_vuln_scopes_vuln_domain_count_to_account(self):
        gql = RecordingGql()
        security_vuln.run(_ctx(gql, account_id=42))
        entity_search_calls = [v for q, v in gql.calls if "entitySearch" in q]
        self.assertTrue(entity_search_calls)
        for variables in entity_search_calls:
            self.assertIn("accountId = 42", variables["query"])


if __name__ == "__main__":
    unittest.main()
