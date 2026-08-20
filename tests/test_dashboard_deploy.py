import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import ALL_CHECKS
from ai_readiness.checks.base import Context, run_check
from ai_readiness.dashboard import build_dashboard_payload, deploy, find_existing
from ai_readiness.nerdgraph import make_mock_client
from ai_readiness.scoring import aggregate


def run_mature():
    gql = make_mock_client("mature")
    ctx = Context(gql=gql, account_id=123, lookback_days=30, config=config_module.THRESHOLDS)
    return [run_check(c, ctx) for c in ALL_CHECKS]


class TestBuildDashboardPayload(unittest.TestCase):
    def setUp(self):
        self.results = run_mature()
        self.agg = aggregate(self.results)
        self.meta = {"account_id": 123, "region": "us", "lookback_days": 30, "mock": True}
        self.payload = build_dashboard_payload(self.results, self.agg, self.meta)

    def test_top_level_shape(self):
        self.assertIn("Account 123", self.payload["name"])
        self.assertEqual(self.payload["permissions"], "PUBLIC_READ_WRITE")

    def test_one_exec_summary_page_plus_one_per_lens(self):
        page_names = [p["name"] for p in self.payload["pages"]]
        self.assertEqual(page_names[0], "Executive Summary")
        self.assertEqual(set(page_names[1:]), set(config_module.LENS_LABELS.values()))
        self.assertEqual(len(self.payload["pages"]), 1 + len(config_module.LENS_LABELS))

    def test_every_dimension_label_appears_somewhere_on_a_lens_page(self):
        lens_pages_text = "".join(
            w["rawConfiguration"]["text"]
            for p in self.payload["pages"][1:]
            for w in p["widgets"]
        )
        for r in self.results:
            self.assertIn(r.label, lens_pages_text)

    def test_custom_name_override(self):
        payload = build_dashboard_payload(self.results, self.agg, self.meta, name="Custom Name")
        self.assertEqual(payload["name"], "Custom Name")


class FakeGql:
    """Records every call; scripted responses keyed by mutation/query substring."""

    def __init__(self, existing_guids=None, create_result=None):
        self.calls = []
        self.existing_guids = existing_guids or []
        self.create_result = create_result or {
            "dashboardCreate": {"entityResult": {"guid": "new-guid", "name": "x"}, "errors": None}
        }

    def __call__(self, query, variables=None, fixture_key=None):
        self.calls.append((query, variables))
        if "entitySearch" in query:
            return {
                "actor": {
                    "entitySearch": {
                        "results": {"entities": [{"guid": g} for g in self.existing_guids]}
                    }
                }
            }
        if "dashboardDelete" in query:
            return {"dashboardDelete": {"status": "SUCCESS"}}
        if "dashboardCreate" in query:
            return self.create_result
        raise AssertionError(f"unexpected query: {query}")


class TestDeployUpsert(unittest.TestCase):
    def setUp(self):
        self.results = run_mature()
        self.agg = aggregate(self.results)
        self.meta = {"account_id": 123, "region": "us", "lookback_days": 30, "mock": False}

    def test_no_existing_dashboard_skips_delete(self):
        gql = FakeGql(existing_guids=[])
        deploy(gql, 123, self.results, self.agg, self.meta)
        kinds = [("delete" if "dashboardDelete" in q else "create" if "dashboardCreate" in q else "search")
                 for q, _ in gql.calls]
        self.assertNotIn("delete", kinds)
        self.assertIn("create", kinds)

    def test_existing_dashboard_deletes_before_create(self):
        gql = FakeGql(existing_guids=["old-guid-1"])
        deploy(gql, 123, self.results, self.agg, self.meta)
        kinds = [("delete" if "dashboardDelete" in q else "create" if "dashboardCreate" in q else "search")
                 for q, _ in gql.calls]
        self.assertEqual(kinds, ["search", "delete", "create"])
        delete_call = gql.calls[1]
        self.assertEqual(delete_call[1], {"g": "old-guid-1"})

    def test_returns_created_entity(self):
        gql = FakeGql(existing_guids=[])
        entity = deploy(gql, 123, self.results, self.agg, self.meta)
        self.assertEqual(entity["guid"], "new-guid")

    def test_raises_on_dashboard_create_errors(self):
        gql = FakeGql(
            existing_guids=[],
            create_result={"dashboardCreate": {"entityResult": None, "errors": [{"description": "bad"}]}},
        )
        with self.assertRaises(Exception):
            deploy(gql, 123, self.results, self.agg, self.meta)


class TestFindExisting(unittest.TestCase):
    def test_returns_guids_from_entity_search(self):
        gql = FakeGql(existing_guids=["g1", "g2"])
        self.assertEqual(find_existing(gql, "some dashboard"), ["g1", "g2"])

    def test_returns_empty_list_when_none_found(self):
        gql = FakeGql(existing_guids=[])
        self.assertEqual(find_existing(gql, "some dashboard"), [])


if __name__ == "__main__":
    unittest.main()
