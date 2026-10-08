# SPDX-License-Identifier: MIT
"""Bing daily wallpaper source.

Metadata comes from Bing's public HPImageArchive endpoint. Each entry in the
archive is one past day: `bing_archive_days = 1` (the default) yields only
today's image, which pairs with the 24-hour interval to give one fresh
wallpaper per day. Raising it turns the archive into a real multi-image pool
for short intervals.

Images are downloaded lazily -- only the selected candidate hits the network
-- and cached by startdate, so re-selecting a day never re-downloads.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .. import paths
from .base import Candidate, Source

ARCHIVE_URL = "https://www.bing.com/HPImageArchive.aspx"
REQUEST_TIMEOUT = 15
USER_AGENT = "omarchy-live-wallpaper/0.1 (+https://github.com/)"

# Guards against writing a cache file for a response that is not really a JPEG.
IMAGE_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF", b"GIF8", b"BM")


class BingError(RuntimeError):
    """Any failure talking to Bing: offline, bad response, bad payload."""


def _build_url(market: str, days: int, resolution: str) -> str:
    from urllib.parse import urlencode

    params = {
        "format": "js",
        "idx": "0",
        "n": str(days),
        "mkt": market,
    }
    return f"{ARCHIVE_URL}?{urlencode(params)}"


def _absolute_image_url(urlbase: str, raw_url: str, resolution: str) -> str:
    """Build a full-size URL at the requested resolution.

    `urlbase` is the id without a resolution suffix, so it is the reliable way
    to ask for a specific size. Falling back to rewriting `url` means dealing
    with the query string (`?id=..._1920x1080.jpg&rf=...&pid=hp`), where the
    resolution sits in the middle rather than at the end.
    """
    if urlbase:
        path = urlbase if urlbase.startswith("/th?") else f"/th?id={urlbase.lstrip('/')}"
        return f"https://www.bing.com{path}_{resolution}.jpg"

    url = raw_url
    if not (url.startswith("http://") or url.startswith("https://")):
        url = f"https://www.bing.com{url}"
    return re.sub(r"_\d+x\d+\.jpg(?=[&?#]|$)", f"_{resolution}.jpg", url)


def _cache_filename(startdate: str, resolution: str, final_url: str) -> str:
    suffix = ".jpg"
    match = re.search(r"\.(jpg|jpeg|png|webp)$", final_url, re.IGNORECASE)
    if match:
        suffix = "." + match.group(1).lower()
    return f"{startdate}_{resolution}{suffix}"


def parse_archive(payload: str, resolution: str) -> list[dict[str, str]]:
    """Turn an HPImageArchive JSON response into flat entries.

    Raises BingError when the payload is not shaped as expected.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BingError(f"malformed JSON: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("images"), list):
        raise BingError("response has no 'images' list")

    entries: list[dict[str, str]] = []
    for item in data["images"]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        startdate = str(item.get("startdate") or "").strip()
        if not url or not startdate:
            continue
        final_url = _absolute_image_url(str(item.get("urlbase") or ""), str(url), resolution)
        entries.append(
            {
                "startdate": startdate,
                "url": final_url,
                "title": str(item.get("title") or "").strip(),
                "copyright": str(item.get("copyright") or "").strip(),
            }
        )

    if not entries:
        raise BingError("no usable images in response")
    return entries


class BingSource(Source):
    name = "bing"

    def __init__(
        self,
        market: str = "zh-CN",
        archive_days: int = 1,
        resolution: str = "UHD",
        cache_dir: Path | None = None,
    ) -> None:
        self.market = market
        self.archive_days = archive_days
        self.resolution = resolution
        self.cache_dir = Path(cache_dir) if cache_dir else paths.bing_cache_dir()

    # --- metadata ---------------------------------------------------------

    def fetch_metadata(self) -> list[dict[str, str]]:
        url = _build_url(self.market, self.archive_days, self.resolution)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise BingError(f"cannot reach Bing ({exc})") from exc
        return parse_archive(payload, self.resolution)

    def candidates(self) -> list[Candidate]:
        """Metadata-only listing: cheap, no image downloads."""
        try:
            entries = self.fetch_metadata()
        except BingError:
            return []  # offline -> the rotation falls back to local

        result: list[Candidate] = []
        for entry in entries:
            filename = _cache_filename(entry["startdate"], self.resolution, entry["url"])
            # Newest first, so a 24h rotation shows today's image immediately.
            result.append(
                Candidate(
                    source=self.name,
                    path=str(self.cache_dir / filename),
                    key=f"bing:{entry['startdate']}",
                    title=entry["title"] or entry["copyright"] or entry["startdate"],
                    fetch=True,
                    url=entry["url"],
                )
            )
        result.sort(key=lambda c: c.key, reverse=True)
        return result

    # --- download ---------------------------------------------------------

    def _download(self, url: str, destination: Path) -> bool:
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                body = response.read()
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

        if not body.startswith(IMAGE_MAGIC):
            return False

        fd, tmp_name = tempfile.mkstemp(
            dir=str(destination.parent), prefix=".dl-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, destination)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            return False
        return True

    def prepare(self, candidate: Candidate) -> str | None:
        target = Path(candidate.path)
        if target.is_file() and target.stat().st_size > 0:
            return str(target)

        # The URL rides along on the candidate: downloading must not trigger a
        # second metadata request, which would double the network round trips
        # and fail outright if Bing became unreachable between listing and
        # selection.
        url = candidate.url or self._url_for(candidate)
        if not url:
            return None
        return str(target) if self._download(url, target) else None

    def _url_for(self, candidate: Candidate) -> str | None:
        """Resolve the download URL for a candidate by re-reading metadata."""
        try:
            entries = self.fetch_metadata()
        except BingError:
            return None
        for entry in entries:
            filename = _cache_filename(entry["startdate"], self.resolution, entry["url"])
            if str(self.cache_dir / filename) == candidate.path:
                return entry["url"]
        return None
