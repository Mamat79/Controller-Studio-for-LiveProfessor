from pathlib import Path

from silemio_control_hub.help_resources import (
    PAYPAL_QR_PATH,
    PAYPAL_SUPPORT_URL,
    is_trusted_paypal_url,
    manual_path,
    open_local_document,
    open_paypal_support,
)


def test_paypal_support_url_is_exact_and_rejects_lookalikes():
    assert is_trusted_paypal_url(PAYPAL_SUPPORT_URL)
    assert not is_trusted_paypal_url("http://www.paypal.com/paypalme/MamatLeroy")
    assert not is_trusted_paypal_url("https://www.paypal.com.evil.example/paypalme/MamatLeroy")
    assert not is_trusted_paypal_url("https://www.paypal.com/paypalme/SomeoneElse")
    assert not is_trusted_paypal_url(f"{PAYPAL_SUPPORT_URL}?redirect=evil")


def test_support_and_document_openers_are_injectable(tmp_path):
    opened = []
    open_paypal_support(opened.append)
    document = tmp_path / "manual.pdf"
    document.write_bytes(b"%PDF-1.4\n")
    open_local_document(document, opened.append)

    assert opened == [PAYPAL_SUPPORT_URL, str(document.resolve())]


def test_manual_language_selection_falls_back_to_french():
    assert manual_path("en").name.endswith("Manual-EN.pdf")
    assert manual_path("fr").name.endswith("Notice-FR.pdf")
    assert manual_path("de") == manual_path("fr")


def test_packaged_manuals_and_support_qr_are_real_files():
    for language in ("fr", "en"):
        document = manual_path(language)
        assert document.is_file()
        assert document.read_bytes().startswith(b"%PDF-")
    assert PAYPAL_QR_PATH.is_file()
    assert PAYPAL_QR_PATH.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
