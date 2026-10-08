# SPDX-License-Identifier: MIT
"""Bing metadata parsing and caching. No network access."""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import BING_RESPONSE, XdgTestCase  # noqa: E402

from live_wallpaper.sources import bing as bing_mod  # noqa: E402
from live_wallpaper.sources.bing import BingError, BingSource, parse_archive  # noqa: E402


class ParseTest(unittest.TestCase):
    def test_parses_entries(self):
        entries = parse_archive(json.dumps(BING_RESPONSE), "UHD")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["startdate"], "20261008")
        self.assertEqual(entries[0]["title"], "New day")
        self.assertTrue(entries[0]["url"].startswith("https://www.bing.com/"))

    def test_resolution_is_substituted(self):
        entries = parse_archive(json.dumps(BING_RESPONSE), "UHD")
        self.assertIn("_UHD.jpg", entries[0]["url"])
        entries = parse_archive(json.dumps(BING_RESPONSE), "1920x1080")
        self.assertIn("_1920x1080.jpg", entries[0]["url"])

    def test_absolute_url_is_kept(self):
        payload = {"images": [{"startdate": "20260101", "url": "https://cdn/x.jpg"}]}
        entries = parse_archive(json.dumps(payload), "UHD")
        self.assertEqual(entries[0]["url"], "https://cdn/x.jpg")

    def test_rejects_malformed_json(self):
        with self.assertRaises(BingError):
            parse_archive("<html>oops</html>", "UHD")

    def test_rejects_missing_images(self):
        with self.assertRaises(BingError):
            parse_archive(json.dumps({"toolbar": {}}), "UHD")

    def test_rejects_empty_images(self):
        with self.assertRaises(BingError):
            parse_archive(json.dumps({"images": []}), "UHD")

    def test_skips_entries_without_startdate(self):
        payload = {"images": [{"url": "/th?id=x.jpg", "startdate": ""}]}
        with self.assertRaises(BingError):
            parse_archive(json.dumps(payload), "UHD")


class CandidateTest(XdgTestCase):
    def _source(self, days=2):
        return BingSource(market="zh-CN", archive_days=days, resolution="UHD")

    def _mock_response(self, source, body: bytes):
        payload = json.dumps(BING_RESPONSE).encode("utf-8")
        return mock.patch.object(
            bing_mod.urllib.request,
            "urlopen",
            return_value=_FakeResponse(payload if body is None else body),
        )

    def test_candidates_newest_first(self):
        source = self._source(days=2)
        with self._mock_response(source, None):
            candidates = source.candidates()
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].key, "bing:20261008")
        self.assertTrue(candidates[0].fetch)

    def test_offline_returns_empty_pool(self):
        """No network -> empty pool, so the rotation falls back to local."""
        source = self._source(days=2)
        with mock.patch.object(bing_mod.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertEqual(source.candidates(), [])

    def test_cached_file_is_not_redownloaded(self):
        source = self._source(days=2)
        with self._mock_response(source, None):
            candidates = source.candidates()
        target = Path(candidates[0].path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\xff\xd8\xff\xe0cached")

        calls = []
        original = bing_mod.urllib.request.urlopen

        def counting(req, *a, **k):
            calls.append(req)
            return _FakeResponse(json.dumps(BING_RESPONSE).encode("utf-8"))

        with mock.patch.object(bing_mod.urllib.request, "urlopen", counting):
            result = source.prepare(candidates[0])
        self.assertEqual(result, str(target))
        self.assertEqual(calls, [], "cached image must not trigger a download")

    def test_download_writes_file(self):
        source = self._source(days=2)
        with self._mock_response(source, None):
            candidates = source.candidates()

        jpeg = b"\xff\xd8\xff\xe0" + b"0" * 512
        with mock.patch.object(bing_mod.urllib.request, "urlopen", return_value=_FakeResponse(jpeg)):
            result = source.prepare(candidates[0])
        self.assertEqual(result, candidates[0].path)
        self.assertTrue(Path(candidates[0].path).is_file())

    def test_non_image_response_is_rejected(self):
        source = self._source(days=2)
        with self._mock_response(source, None):
            candidates = source.candidates()
        with mock.patch.object(
            bing_mod.urllib.request, "urlopen", return_value=_FakeResponse(b"<html>404</html>")
        ):
            self.assertIsNone(source.prepare(candidates[0]))
        self.assertFalse(Path(candidates[0].path).exists())

    def test_download_failure_returns_none(self):
        source = self._source(days=2)
        with self._mock_response(source, None):
            candidates = source.candidates()
        with mock.patch.object(bing_mod.urllib.request, "urlopen", side_effect=OSError("boom")):
            self.assertIsNone(source.prepare(candidates[0]))


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


if __name__ == "__main__":
    unittest.main()
