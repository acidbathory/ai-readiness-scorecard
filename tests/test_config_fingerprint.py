import unittest

from ai_readiness import config as config_module


class TestConfigFingerprint(unittest.TestCase):
    def test_deterministic_for_same_thresholds(self):
        a = config_module.config_fingerprint(config_module.THRESHOLDS)
        b = config_module.config_fingerprint(config_module.THRESHOLDS)
        self.assertEqual(a, b)

    def test_changes_when_thresholds_change(self):
        default_fp = config_module.config_fingerprint(config_module.THRESHOLDS)
        overridden = config_module.deep_merge(
            config_module.THRESHOLDS, {"apm_coverage": {"min_entities_for_tier": {1: 5, 2: 10, 3: 20}}}
        )
        overridden_fp = config_module.config_fingerprint(overridden)
        self.assertNotEqual(default_fp, overridden_fp)

    def test_short_and_stable_length(self):
        fp = config_module.config_fingerprint(config_module.THRESHOLDS)
        self.assertEqual(len(fp), 12)


if __name__ == "__main__":
    unittest.main()
