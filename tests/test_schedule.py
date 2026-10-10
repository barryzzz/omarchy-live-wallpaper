# SPDX-License-Identifier: MIT
"""Wall-clock scheduling: the countdown keeps running while the machine is off.

The systemd timer cannot fire while the machine is down, so "time until the
next switch" has to be derived from when the last switch happened rather than
from a countdown maintained in memory. These tests pin that behaviour, plus
the slot anchoring that keeps a 15-minute timer from drifting a daily
schedule later over time.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import XdgTestCase  # noqa: E402

from live_wallpaper import rotate  # noqa: E402
from live_wallpaper.config import Config  # noqa: E402
from live_wallpaper.state import State  # noqa: E402

HOUR = 3600.0
DAY = 24 * HOUR


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


class CountdownTest(XdgTestCase):
    """`schedule_due_at` is measured from the slot, not the last switch."""

    def test_no_switch_yet_has_no_due_time(self):
        self.assertIsNone(rotate.schedule_due_at(State(), cfg().interval_seconds()))

    def test_due_one_interval_after_the_slot(self):
        state = State()
        state.record_switch(1000.0, 1000.0)
        self.assertEqual(rotate.schedule_due_at(state, DAY), 1000.0 + DAY)

    def test_slot_is_used_not_the_switch_moment(self):
        """A switch served 10 minutes late must not push the next one later."""
        state = State()
        state.record_switch(1000.0 + 600, 1000.0)
        self.assertEqual(rotate.schedule_due_at(state, DAY), 1000.0 + DAY)


class OfflineElapsedTest(XdgTestCase):
    """The point of the change: time powered off counts towards the interval."""

    def setUp(self):
        super().setUp()
        self.make_images(paths_theme_dir(), ["a.jpg", "b.jpg"])

    def test_due_immediately_after_a_long_shutdown(self):
        """Off for three days on a 24h interval: one switch on boot, not three."""
        state = State()
        state.record_switch(0.0, 0.0)
        plan = rotate.plan(cfg(), state, now=3 * DAY)
        self.assertEqual(plan.action, "apply")

    def test_due_exactly_at_the_interval(self):
        state = State()
        state.record_switch(0.0, 0.0)
        plan = rotate.plan(cfg(), state, now=DAY)
        self.assertEqual(plan.action, "apply")

    def test_not_due_before_the_interval(self):
        state = State()
        state.record_switch(0.0, 0.0)
        plan = rotate.plan(cfg(), state, now=DAY - 60)
        self.assertEqual(plan.action, "skip-interval")

    def test_short_interval_counts_offline_time_too(self):
        state = State()
        state.record_switch(0.0, 0.0)
        plan = rotate.plan(cfg(interval_hours=0.5), state, now=2 * HOUR)
        self.assertEqual(plan.action, "apply")

    def test_suspend_over_night_is_due_on_wake(self):
        """Lid closed at 22:00, opened at 08:00 with an 8h interval: the
        wall clock ran on, so the switch is waiting on wake."""
        state = State()
        state.record_switch(0.0, 0.0)
        plan = rotate.plan(cfg(interval_hours=8), state, now=10 * HOUR)
        self.assertEqual(plan.action, "apply")


class AnchorTest(XdgTestCase):
    """`schedule_anchor` keeps switch times on the grid."""

    def test_first_switch_anchors_on_now(self):
        self.assertEqual(rotate.schedule_anchor(None, 5000.0, DAY), 5000.0)

    def test_switching_late_keeps_the_slot(self):
        """Timer fired 10 minutes after the slot -- the next due time is
        unchanged, so the schedule does not drift later every day."""
        anchor = rotate.schedule_anchor(0.0, DAY + 600, DAY)
        self.assertEqual(anchor, DAY)

    def test_switching_many_slots_late_takes_the_latest_passed_slot(self):
        anchor = rotate.schedule_anchor(0.0, 3 * DAY + 600, DAY)
        self.assertEqual(anchor, 3 * DAY)

    def test_a_whole_interval_missed_restarts_from_now(self):
        """Off for exactly one interval: the missed slot collapses into the
        switch happening now, so the countdown is not already expired."""
        anchor = rotate.schedule_anchor(0.0, DAY, DAY)
        self.assertEqual(anchor, DAY)
        state = State()
        state.record_switch(DAY, anchor)
        self.assertFalse(rotate.plan(cfg(), state, now=DAY).changed)

    def test_switching_early_regrids(self):
        """A forced switch ahead of schedule becomes the new reference."""
        anchor = rotate.schedule_anchor(0.0, 2 * HOUR, DAY)
        self.assertEqual(anchor, 2 * HOUR)

    def test_zero_interval_does_not_divide(self):
        self.assertEqual(rotate.schedule_anchor(0.0, 500.0, 0.0), 500.0)


def paths_theme_dir():
    from live_wallpaper import paths

    return paths.theme_backgrounds_dir()


if __name__ == "__main__":
    unittest.main()
