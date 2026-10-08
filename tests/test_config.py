# SPDX-License-Identifier: MIT
"""Config parsing, defaults, and clamping."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import XdgTestCase  # noqa: E402

from live_wallpaper import config as config_mod  # noqa: E402
from live_wallpaper.config import Config, load  # noqa: E402


class DefaultsTest(XdgTestCase):
    def test_defaults_when_no_file(self):
        warnings = []
        cfg = load(warnings=warnings)
        self.assertEqual(cfg.interval_hours, 24.0)
        self.assertEqual(cfg.source, "both")
        self.assertEqual(cfg.bing_market, "zh-CN")
        self.assertEqual(cfg.bing_archive_days, 1)
        self.assertEqual(cfg.bing_resolution, "UHD")
        self.assertTrue(cfg.notify)
        self.assertEqual(warnings, [])
        self.assertEqual(cfg.interval_seconds(), 24 * 3600.0)


class ParsingTest(XdgTestCase):
    def test_reads_all_keys(self):
        self.write_config(
            """
            interval_hours = 0.5
            source = "bing"
            bing_market = "en-US"
            bing_archive_days = 5
            bing_resolution = "1920x1080"
            notify = false
            """
        )
        cfg = load()
        self.assertEqual(cfg.interval_hours, 0.5)
        self.assertEqual(cfg.source, "bing")
        self.assertEqual(cfg.bing_market, "en-US")
        self.assertEqual(cfg.bing_archive_days, 5)
        self.assertEqual(cfg.bing_resolution, "1920x1080")
        self.assertFalse(cfg.notify)

    def test_partial_file_uses_defaults(self):
        self.write_config('source = "local"')
        cfg = load()
        self.assertEqual(cfg.source, "local")
        self.assertEqual(cfg.interval_hours, 24.0)

    def test_unknown_key_warns_but_keeps_going(self):
        self.write_config('nonsense = 1\nsource = "local"')
        warnings = []
        cfg = load(warnings=warnings)
        self.assertEqual(cfg.source, "local")
        self.assertTrue(any("nonsense" in w for w in warnings))


class ClampingTest(XdgTestCase):
    def test_invalid_source_falls_back(self):
        self.write_config('source = "nasa"')
        warnings = []
        cfg = load(warnings=warnings)
        self.assertEqual(cfg.source, "both")
        self.assertTrue(any("source" in w for w in warnings))

    def test_source_is_case_insensitive(self):
        self.write_config('source = "BING"')
        self.assertEqual(load().source, "bing")

    def test_tiny_interval_clamped(self):
        self.write_config("interval_hours = 0.0001")
        cfg = load()
        self.assertEqual(cfg.interval_hours, config_mod.MIN_INTERVAL_HOURS)

    def test_huge_interval_clamped(self):
        self.write_config("interval_hours = 99999")
        cfg = load()
        self.assertEqual(cfg.interval_hours, config_mod.MAX_INTERVAL_HOURS)

    def test_non_numeric_interval(self):
        self.write_config('interval_hours = "soon"')
        warnings = []
        cfg = load(warnings=warnings)
        self.assertEqual(cfg.interval_hours, 24.0)
        self.assertTrue(warnings)

    def test_archive_days_clamped(self):
        self.write_config("bing_archive_days = 500")
        self.assertEqual(load().bing_archive_days, config_mod.MAX_ARCHIVE_DAYS)
        self.write_config("bing_archive_days = 0")
        self.assertEqual(load().bing_archive_days, config_mod.MIN_ARCHIVE_DAYS)

    def test_bad_resolution_falls_back(self):
        self.write_config('bing_resolution = "8k"')
        self.assertEqual(load().bing_resolution, "UHD")

    def test_notify_string_bool(self):
        self.write_config('notify = "yes"')
        self.assertTrue(load().notify)
        self.write_config('notify = "off"')
        self.assertFalse(load().notify)


class MalformedTest(XdgTestCase):
    def test_broken_toml_uses_defaults(self):
        self.write_config("interval_hours = = 3")
        warnings = []
        cfg = load(warnings=warnings)
        self.assertEqual(cfg.interval_hours, 24.0)
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main()
