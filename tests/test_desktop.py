import tkinter as tk

from silemio_control_hub.desktop import (
    PRODUCT_ICON_PATH,
    UI_TEXT,
    _widget_exists,
    _safe_filename,
    controller_table_rows,
    live_runtime_supported,
    translated_text,
)
from silemio_control_hub.registry import ControllerRegistry


def test_desktop_controller_table_uses_the_registry_without_legacy_dependencies(tmp_path):
    rows = controller_table_rows(
        ControllerRegistry(profile_directories=[], library_cache_root=tmp_path / "cache")
    )

    profile_ids = {row.profile_id for row in rows}
    assert len(profile_ids) == 33
    assert {
        "faderfox.ec4",
        "akai.midimix.factory",
        "arturia.minilab-3.user",
        "behringer.x-touch.mcu",
        "novation.launchkey-mk4.49-61-88-custom",
        "presonus.faderport-16.mcu",
        "ssl.uf8.mcu",
    } <= profile_ids
    assert all(row.controls > 0 for row in rows)


def test_desktop_export_filename_is_windows_safe():
    assert _safe_filename("SiLeMI/O: X-Touch Compact") == "SiLeMI-O-X-Touch-Compact"


def test_live_runtime_is_enabled_only_for_profiles_with_a_native_driver():
    assert live_runtime_supported("faderfox.ec4")
    assert not live_runtime_supported("generic.midi.16")
    assert not live_runtime_supported(None)


def test_destroyed_widgets_are_not_reused_after_language_rebuild():
    class ExistingWidget:
        def winfo_exists(self):
            return 1

    class DestroyedWidget:
        def winfo_exists(self):
            raise tk.TclError("destroyed")

    assert _widget_exists(ExistingWidget())
    assert not _widget_exists(DestroyedWidget())
    assert not _widget_exists(object())


def test_french_and_english_desktop_catalogs_are_complete_and_distinct():
    assert set(UI_TEXT["fr"]) == set(UI_TEXT["en"])
    assert translated_text("fr", "menu_file") == "Fichier"
    assert translated_text("en", "menu_file") == "File"
    assert translated_text("en", "catalog_ready", controllers=2, plugins=1) == (
        "Catalog ready: 2 controller(s), 1 plug-in profile(s)."
    )


def test_unknown_language_falls_back_to_french():
    assert translated_text("de", "quit") == "Quitter"


def test_product_icon_contains_multiple_windows_sizes():
    icon = PRODUCT_ICON_PATH.read_bytes()
    png = PRODUCT_ICON_PATH.with_suffix(".png").read_bytes()

    assert icon[:4] == b"\x00\x00\x01\x00"
    assert int.from_bytes(icon[4:6], "little") >= 8
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
