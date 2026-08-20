import unittest

from ai_readiness.nerdgraph import NerdGraphError, resolve_endpoint


class TestResolveEndpoint(unittest.TestCase):
    def test_us_default(self):
        self.assertEqual(resolve_endpoint(None), "https://api.newrelic.com/graphql")
        self.assertEqual(resolve_endpoint("us"), "https://api.newrelic.com/graphql")

    def test_eu(self):
        self.assertEqual(resolve_endpoint("eu"), "https://api.eu.newrelic.com/graphql")
        self.assertEqual(resolve_endpoint("EU"), "https://api.eu.newrelic.com/graphql")

    def test_unknown_region_raises(self):
        with self.assertRaises(NerdGraphError):
            resolve_endpoint("apac")


if __name__ == "__main__":
    unittest.main()
