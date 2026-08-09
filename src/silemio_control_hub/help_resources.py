"""Trusted support and localized bundled-document resources."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import webbrowser
from collections.abc import Callable
from urllib.parse import urlsplit


PACKAGE_ROOT = Path(__file__).resolve().parent
PAYPAL_SUPPORT_URL = "https://www.paypal.com/paypalme/MamatLeroy"
PAYPAL_QR_PATH = PACKAGE_ROOT / "assets" / "paypal-support-qr.png"
MANUAL_PATHS = {
    "fr": PACKAGE_ROOT / "manuals" / "Controller-Studio-for-LiveProfessor-Notice-FR.pdf",
    "en": PACKAGE_ROOT / "manuals" / "Controller-Studio-for-LiveProfessor-Manual-EN.pdf",
}


def is_trusted_paypal_url(url: str | None) -> bool:
    if url != PAYPAL_SUPPORT_URL:
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "www.paypal.com"
        and parsed.path == "/paypalme/MamatLeroy"
        and not parsed.username
        and not parsed.password
        and port in {None, 443}
        and not parsed.query
        and not parsed.fragment
    )


def open_paypal_support(
    opener: Callable[[str], object] | None = None,
) -> None:
    if not is_trusted_paypal_url(PAYPAL_SUPPORT_URL):
        raise ValueError("adresse PayPal.Me non fiable")
    (opener or webbrowser.open_new_tab)(PAYPAL_SUPPORT_URL)


def manual_path(language: str) -> Path:
    return MANUAL_PATHS["en" if language == "en" else "fr"]


def open_local_document(
    path: Path,
    opener: Callable[[str], object] | None = None,
) -> None:
    document = Path(path).expanduser().resolve()
    if not document.is_file():
        raise FileNotFoundError(document)
    if opener is not None:
        opener(str(document))
        return
    if sys.platform == "win32":
        os.startfile(str(document))
        return
    webbrowser.open_new_tab(document.as_uri())
