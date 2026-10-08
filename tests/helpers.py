# SPDX-License-Identifier: MIT
"""Shared helpers: isolated XDG layout per test."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES = Path(__file__).resolve().parent / "fixtures"

BING_RESPONSE = {
    "images": [
        {
            "startdate": "20261008",
            "fullstartdate": "202610081600",
            "enddate": "20261009",
            "url": "/th?id=OHR.NewDay_ZH-CN1234_1920x1080.jpg&rf=LaDigue_1920x1080.jpg&pid=hp",
            "urlbase": "/th?id=OHR.NewDay_ZH-CN1234",
            "copyright": "A place (© Someone)",
            "title": "New day",
        },
        {
            "startdate": "20261007",
            "url": "/th?id=OHR.OldDay_ZH-CN5678_1920x1080.jpg&pid=hp",
            "title": "Old day",
        },
    ]
}


class XdgTestCase(unittest.TestCase):
    """Redirect HOME and all XDG dirs into a temp dir for the test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.config_home = self.tmp / "config"
        self.state_home = self.tmp / "state"
        self.cache_home = self.tmp / "cache"
        self.data_home = self.tmp / "data"
        for path in (self.home, self.config_home, self.state_home, self.cache_home, self.data_home):
            path.mkdir(parents=True, exist_ok=True)

        env = {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.config_home),
            "XDG_STATE_HOME": str(self.state_home),
            "XDG_CACHE_HOME": str(self.cache_home),
            "XDG_DATA_HOME": str(self.data_home),
        }
        self._saved = {key: os.environ.get(key) for key in env}
        os.environ.update(env)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def write_config(self, text: str):
        from live_wallpaper import paths

        target = paths.config_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def make_images(self, directory: Path, names: list[str]) -> list[Path]:
        directory.mkdir(parents=True, exist_ok=True)
        created = []
        for name in names:
            path = directory / name
            path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
            created.append(path)
        return created
