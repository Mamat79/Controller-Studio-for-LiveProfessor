from __future__ import annotations

import webbrowser


REPOSITORY_URL = "https://github.com/Mamat79/EC4-LiveProfessor-Bridge"
RELEASES_URL = f"{REPOSITORY_URL}/releases"
ISSUES_URL = f"{REPOSITORY_URL}/issues"
CONTRIBUTE_URL = f"{REPOSITORY_URL}#contribuer"
PAYPAL_URL = "https://www.paypal.com/paypalme/MamatLeroy"

ALLOWED_URLS = frozenset(
    {REPOSITORY_URL, RELEASES_URL, ISSUES_URL, CONTRIBUTE_URL, PAYPAL_URL}
)


def open_external_url(url: str) -> bool:
    if url not in ALLOWED_URLS or not url.startswith("https://"):
        raise ValueError("URL externe non autorisee")
    return bool(webbrowser.open(url, new=2))
