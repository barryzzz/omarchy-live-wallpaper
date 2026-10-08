# SPDX-License-Identifier: MIT
"""Rotation: pool building, source alternation, interval, single-image rule."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import XdgTestCase  # noqa: E402

from live_wallpaper import paths, rotate  # noqa: E402
from live_wallpaper.config import Config  # noqa: E402
from live_wallpaper.state import State  # noqa: E402


def cfg(**overrides):
    base = dict(
        interval_hours=24.0,
        source="local",
        bing_market="zh-CN",
        bing_archive_days=1,
        bing_resolution="UHD",
        notify=False,
    )
    base.update(overrides)
    return Config(**base)


class LocalPoolTest(XdgTestCase):
    def test_finds_theme_backgrounds(self):
        theme_dir = paths.theme_backgrounds_dir()
        self.make_images(theme_dir, ["a.jpg", "b.png", "c.webp"])
        pool = rotate.build_pool(cfg())
        self.assertEqual(len(pool), 3)
        self.assertTrue(all(c.source == "local" for c in pool))
        # Sorted, so rotation order is stable across runs.
        self.assertEqual([Path(c.path).name for c in pool], ["a.jpg", "b.png", "c.webp"])

    def test_ignores_non_images(self):
        theme_dir = paths.theme_backgrounds_dir()
        self.make_images(theme_dir, ["a.jpg"])
        (theme_dir / "notes.txt").write_text("nope")
        (theme_dir / "README.md").write_text("nope")
        pool = rotate.build_pool(cfg())
        self.assertEqual(len(pool), 1)

    def test_includes_user_theme_dir(self):
        self.make_images(paths.theme_backgrounds_dir(), ["a.jpg"])
        user_dir = paths.user_backgrounds_dir("tokyo-night")
        self.make_images(user_dir, ["extra.png"])
        paths.theme_name_file().parent.mkdir(parents=True, exist_ok=True)
        paths.theme_name_file().write_text("tokyo-night", encoding="utf-8")
        pool = rotate.build_pool(cfg())
        self.assertEqual(len(pool), 2)

    def test_empty_pool(self):
        plan = rotate.plan(cfg(), State(), now=0)
        self.assertEqual(plan.action, "skip-empty")


class IntervalTest(XdgTestCase):
    def setUp(self):
        super().setUp()
        self.make_images(paths.theme_backgrounds_dir(), ["a.jpg", "b.jpg"])

    def test_first_run_is_due(self):
        plan = rotate.plan(cfg(), State(), now=1000)
        self.assertEqual(plan.action, "apply")

    def test_not_due_before_interval(self):
        state = State(last_switch=1000, last_source="local", last_image="")
        plan = rotate.plan(cfg(), state, now=1000 + 3600)  # 1h later
        self.assertEqual(plan.action, "skip-interval")

    def test_due_exactly_at_interval(self):
        state = State(last_switch=0, last_source="local", last_image="")
        plan = rotate.plan(cfg(), state, now=24 * 3600)
        self.assertEqual(plan.action, "apply")

    def test_force_ignores_interval(self):
        state = State(last_switch=1000, last_source="local", last_image="")
        plan = rotate.plan(cfg(), state, now=1001, force=True)
        self.assertEqual(plan.action, "apply")

    def test_fractional_interval(self):
        state = State(last_switch=0, last_source="local", last_image="")
        config = cfg(interval_hours=0.5)
        self.assertEqual(rotate.plan(config, state, now=1799).action, "skip-interval")
        self.assertEqual(rotate.plan(config, state, now=1800).action, "apply")


class SingleImageTest(XdgTestCase):
    def test_single_image_already_showing_is_skipped(self):
        """The rule: one wallpaper and it is up -> do not churn."""
        images = self.make_images(paths.theme_backgrounds_dir(), ["only.jpg"])
        state = State(last_switch=0, last_source="local", last_image=str(images[0].resolve()))
        plan = rotate.plan(cfg(), state, now=24 * 3600)
        self.assertEqual(plan.action, "skip-single")
        self.assertFalse(plan.changed)

    def test_single_image_first_run_applies(self):
        self.make_images(paths.theme_backgrounds_dir(), ["only.jpg"])
        plan = rotate.plan(cfg(), State(), now=0)
        self.assertEqual(plan.action, "apply")

    def test_single_image_applies_when_other_is_showing(self):
        """One candidate, but the desktop shows something else -> apply ours."""
        self.make_images(paths.theme_backgrounds_dir(), ["only.jpg"])
        state = State(last_switch=0, last_source="local", last_image="/somewhere/else.jpg")
        plan = rotate.plan(cfg(), state, now=24 * 3600)
        self.assertEqual(plan.action, "apply")

    def test_two_images_rotate(self):
        images = self.make_images(paths.theme_backgrounds_dir(), ["a.jpg", "b.jpg"])
        first = str(images[0].resolve())
        state = State(last_switch=0, last_source="local", last_image=first)
        plan = rotate.plan(cfg(), state, now=24 * 3600)
        self.assertEqual(plan.action, "apply")
        self.assertEqual(Path(plan.candidate.path).name, "b.jpg")

    def test_rotation_wraps_around(self):
        images = self.make_images(paths.theme_backgrounds_dir(), ["a.jpg", "b.jpg"])
        last = str(images[-1].resolve())
        state = State(last_switch=0, last_source="local", last_image=last)
        plan = rotate.plan(cfg(), state, now=24 * 3600)
        self.assertEqual(Path(plan.candidate.path).name, "a.jpg")


class AlternationTest(XdgTestCase):
    """`both` mode should not serve the same source twice in a row."""

    def _pool(self, local_names, bing_keys):
        from live_wallpaper.sources.base import Candidate

        pool = [
            Candidate(source="local", path=f"/local/{n}", key=f"/local/{n}", title=n)
            for n in local_names
        ]
        pool += [
            Candidate(source="bing", path=f"/bing/{k}", key=f"bing:{k}", title=k, fetch=True)
            for k in bing_keys
        ]
        return pool

    def test_alternates_when_both_available(self):
        pool = self._pool(["a", "b"], ["1"])
        state = State(last_source="local", last_image="/local/a")
        chosen = rotate._choose(pool, cfg(source="both"), state)
        self.assertEqual(chosen.source, "bing")

        state = State(last_source="bing", last_image="bing:1")
        chosen = rotate._choose(pool, cfg(source="both"), state)
        self.assertEqual(chosen.source, "local")

    def test_local_only_pool_never_blocks(self):
        """Degenerate case: alternation must not stall a single-source pool."""
        pool = self._pool(["a", "b"], [])
        state = State(last_source="local", last_image="/local/a")
        chosen = rotate._choose(pool, cfg(source="both"), state)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.path, "/local/b")

    def test_bing_only_pool_never_blocks(self):
        pool = self._pool([], ["1", "2"])
        state = State(last_source="bing", last_image="bing:1")
        chosen = rotate._choose(pool, cfg(source="both"), state)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.key, "bing:2")

    def test_stale_key_falls_back_to_first(self):
        pool = self._pool(["a", "b"], ["1"])
        state = State(last_source="local", last_image="/gone/deleted.jpg")
        chosen = rotate._choose(pool, cfg(source="both"), state)
        self.assertIsNotNone(chosen)

    def test_local_pool_advances_across_alternations(self):
        """Regression: every local image must be reachable, not just the first.

        Alternating by picking from the merged pool kept landing back on
        local[0], so a theme with several backgrounds only ever showed one.
        """
        pool = self._pool(["a", "b", "c"], ["1"])
        state = State()
        state.remember("bing", "bing:1")
        seen = []
        for _ in range(6):  # alternation: 6 ticks -> 3 local turns
            chosen = rotate._choose(pool, cfg(source="both"), state)
            state.remember(chosen.source, chosen.key)
            if chosen.source == "local":
                seen.append(Path(chosen.path).name)

        self.assertEqual(seen, ["a", "b", "c"], "local images must cycle")

    def test_bing_pool_advances_too(self):
        pool = self._pool(["a"], ["1", "2", "3"])
        state = State()
        state.remember("local", "/local/a")
        seen = []
        for _ in range(6):  # alternation: 6 ticks -> 3 bing turns
            chosen = rotate._choose(pool, cfg(source="both"), state)
            state.remember(chosen.source, chosen.key)
            if chosen.source == "bing":
                seen.append(chosen.key)
        self.assertEqual(seen, ["bing:1", "bing:2", "bing:3"])

    def test_single_source_mode_ignores_alternation(self):
        """source=local must walk the local list even if state says bing."""
        pool = self._pool(["a", "b"], ["1"])
        state = State()
        state.remember("local", "/local/a")
        chosen = rotate._choose(pool, cfg(source="local"), state)
        self.assertEqual(chosen.source, "local")
        self.assertEqual(chosen.path, "/local/b")

    def test_position_is_tracked_per_source(self):
        """State must remember where each source left off."""
        state = State()
        state.remember("local", "/local/a")
        state.remember("bing", "bing:1")
        self.assertEqual(state.position("local"), "/local/a")
        self.assertEqual(state.position("bing"), "bing:1")


if __name__ == "__main__":
    unittest.main()
