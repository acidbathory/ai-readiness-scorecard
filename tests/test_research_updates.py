import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import ai_agent_tracing, ai_change_tracking, model_vendor_diversity, security_vuln
from ai_readiness.checks.base import Context
from ai_readiness.nerdgraph import NerdGraphError


def _nrql(results):
    return {"actor": {"account": {"nrql": {"results": results}}}}


def _ctx(gql):
    return Context(gql=gql, account_id=1, lookback_days=30, config=config_module.THRESHOLDS)


class TestVendorDiversityProviderName(unittest.TestCase):
    def test_provider_name_alone_is_counted(self):
        def gql(query, variables=None, fixture_key=None):
            if fixture_key == "model_vendor_diversity.genai_provider_vendors":
                return _nrql([{"uniqueCount.gen_ai.provider.name": 3}])
            if fixture_key == "model_vendor_diversity.genai_vendors":
                return _nrql([{"uniqueCount.gen_ai.system": 0}])
            return _nrql([{"uniqueCount.vendor": 0}])

        r = model_vendor_diversity.run(_ctx(gql))
        self.assertEqual(r.raw_metrics["genai_vendor_count"], 3)
        self.assertEqual(r.raw_metrics["vendor_count"], 3)


class TestAgentTracingAgentSignals(unittest.TestCase):
    def _run(self, hot_key):
        def gql(query, variables=None, fixture_key=None):
            return _nrql([{"count": 5000 if fixture_key == hot_key else 0}])

        return ai_agent_tracing.run(_ctx(gql))

    def test_llm_agent_events_lift_score(self):
        r = self._run("ai_agent_tracing.agents")
        self.assertGreater(r.score, 0)
        self.assertEqual(r.raw_metrics["agent_count"], 5000)

    def test_gen_ai_agent_spans_lift_score(self):
        r = self._run("ai_agent_tracing.genai_agents")
        self.assertGreater(r.score, 0)

    def test_no_signals_is_absent(self):
        self.assertEqual(self._run(None).score, 0)


class TestChangeTrackingIncludesDeployment(unittest.TestCase):
    def test_queries_both_event_types(self):
        seen = []

        def gql(query, variables=None, fixture_key=None):
            seen.append(variables["nrql"])
            return _nrql([{"count": 0}])

        ai_change_tracking.run(_ctx(gql))
        self.assertTrue(seen)
        for nrql in seen:
            self.assertIn("FROM ChangeTrackingEvent, Deployment", nrql)


class TestSecurityVulnCandidates(unittest.TestCase):
    @staticmethod
    def _entity(n):
        return {"actor": {"entitySearch": {"count": n}}}

    def test_security_finding_used_first(self):
        def gql(query, variables=None, fixture_key=None):
            if fixture_key == "security_vuln.security_finding":
                return self._entity(7)
            raise AssertionError("fallbacks should not run when SECURITY_FINDING has data")

        r = security_vuln.run(_ctx(gql))
        self.assertEqual(r.raw_metrics["scanned_count"], 7)
        self.assertIn("SECURITY_FINDING", r.raw_metrics["source"])

    def test_falls_back_when_security_finding_empty(self):
        def gql(query, variables=None, fixture_key=None):
            if fixture_key == "security_vuln.vuln_domain":
                return self._entity(4)
            return self._entity(0)

        r = security_vuln.run(_ctx(gql))
        self.assertEqual(r.raw_metrics["scanned_count"], 4)

    def test_all_failures_is_unknown(self):
        def gql(query, variables=None, fixture_key=None):
            raise NerdGraphError("nope")

        r = security_vuln.run(_ctx(gql))
        self.assertIsNone(r.score)

    def test_real_zero_is_absent_not_unknown(self):
        def gql(query, variables=None, fixture_key=None):
            if fixture_key == "security_vuln.nrai_vuln":
                return _nrql([{"count": 0}])
            return self._entity(0)

        r = security_vuln.run(_ctx(gql))
        self.assertEqual(r.score, 0)


if __name__ == "__main__":
    unittest.main()
