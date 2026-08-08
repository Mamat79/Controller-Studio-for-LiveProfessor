from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen


LATEST_RELEASE_API = (
    "https://api.github.com/repos/Mamat79/EC4-LiveProfessor-Bridge/releases/latest"
)
USER_AGENT = "EC4-LiveProfessor-Bridge-Updater/2026.1"


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: str
    tag_name: str
    title: str
    notes: str
    page_url: str
    asset_url: str
    asset_name: str
    asset_size: int


def version_tuple(value: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+){0,3})(?:[-+].*)?", str(value).strip())
    if not match:
        raise ValueError(f"version invalide: {value!r}")
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def is_newer_version(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def _select_asset(assets: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("browser_download_url", "")).startswith("https://github.com/")
    ]
    installers = [
        asset
        for asset in usable
        if str(asset.get("name", "")).lower().endswith(".exe")
        and "setup" in str(asset.get("name", "")).lower()
    ]
    archives = [
        asset for asset in usable if str(asset.get("name", "")).lower().endswith(".zip")
    ]
    return (installers or archives or usable or [{}])[0]


def parse_release(payload: dict[str, Any]) -> ReleaseInfo:
    if payload.get("draft") or payload.get("prerelease"):
        raise ValueError("la release recue n'est pas une version stable")
    tag = str(payload.get("tag_name", "")).strip()
    version_tuple(tag)
    page_url = str(payload.get("html_url", "")).strip()
    if not page_url.startswith("https://github.com/Mamat79/EC4-LiveProfessor-Bridge/"):
        raise ValueError("URL de release GitHub inattendue")
    asset = _select_asset(payload.get("assets") or [])
    return ReleaseInfo(
        version=tag.removeprefix("v"),
        tag_name=tag,
        title=str(payload.get("name") or tag),
        notes=str(payload.get("body") or "").strip(),
        page_url=page_url,
        asset_url=str(asset.get("browser_download_url") or ""),
        asset_name=str(asset.get("name") or ""),
        asset_size=int(asset.get("size") or 0),
    )


def fetch_latest_release(timeout: float = 5.0) -> ReleaseInfo:
    request = Request(
        LATEST_RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("reponse GitHub invalide")
    return parse_release(payload)
