# SPDX-License-Identifier: MIT
"""State persistence."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import XdgTestCase  # noqa: E402

from live_wallpaper import paths  # noqa: E402
from live_wallpaper.state import State, load, save  # noqa: E402


class StateTest(XdgTestCase):
    def test_missing_file_gives_fresh_state(self):
        state = load()
        self.assertIsNone(state.last_switch)
        self.assertIsNone(state.last_source)
        self.assertIsNone(state.last_image)

    def test_roundtrip(self):
        save(State(last_switch=1700.5, last_source="bing", last_image="/x/y.jpg"))
        state = load()
        self.assertEqual(state.last_switch, 1700.5)
        self.assertEqual(state.last_source, "bing")
        self.assertEqual(state.last_image, "/x/y.jpg")

    def test_creates_parent_directories(self):
        save(State(last_switch=1))
        self.assertTrue(paths.state_file().is_file())

    def test_corrupt_file_gives_fresh_state(self):
        paths.state_file().parent.mkdir(parents=True, exist_ok=True)
        paths.state_file().write_text("{not json", encoding="utf-8")
        state = load()
        self.assertIsNone(state.last_switch)

    def test_wrong_version_gives_fresh_state(self):
        paths.state_file().parent.mkdir(parents=True, exist_ok=True)
        paths.state_file().write_text(json.dumps({"version": 99, "last_switch": 5}))
        state = load()
        self.assertIsNone(state.last_switch)

    def test_null_values_tolerated(self):
        save(State())
        data = json.loads(paths.state_file().read_text())
        self.assertIsNone(data["last_switch"])
        self.assertEqual(load().last_switch, None)

    def test_write_is_atomic(self):
        """No stray temp files left behind."""
        save(State(last_switch=1))
        save(State(last_switch=2))
        leftovers = list(paths.state_file().parent.glob(".state-*"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
