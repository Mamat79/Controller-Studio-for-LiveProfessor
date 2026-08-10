import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from silemio_control_hub.vst3_scanner import (
    ScannedParameter,
    VST3ScanError,
    VST3ScanResult,
    installed_plugin_paths,
    scan_installed_vst3,
    scan_vst3_module,
)


def _result(path: Path, *, count: int = 2) -> VST3ScanResult:
    return VST3ScanResult(
        plugin_name="Test Plug",
        class_name="Test Plug",
        module_path=path.resolve(),
        parameters=tuple(
            ScannedParameter(index, 100 + index, f"Name {index}", "", "", 0, 1)
            for index in range(count)
        ),
    )


def test_liveprofessor_database_resolves_only_exact_existing_vst3_entries(tmp_path):
    plugin = tmp_path / "Test Plug.vst3"
    plugin.mkdir()
    other = tmp_path / "Other.vst3"
    other.mkdir()
    database = tmp_path / "PluginsX64.xml"
    database.write_text(
        "<PLUGINS>"
        f'<PLUGIN name="Test Plug" format="VST3" file="{plugin}" />'
        f'<PLUGIN name="Test Plug" format="VST2" file="{other}" />'
        f'<PLUGIN name="Other" format="VST3" file="{other}" />'
        "</PLUGINS>",
        encoding="utf-8",
    )

    assert installed_plugin_paths("test plug", database=database) == (plugin.resolve(),)


def test_worker_result_is_parsed_and_validated(monkeypatch, tmp_path):
    plugin = tmp_path / "Test.vst3"
    plugin.mkdir()
    result = _result(plugin)
    completed = SimpleNamespace(
        returncode=0,
        stdout="plug-in diagnostic line\n" + json.dumps(result.to_dict()) + "\n",
        stderr="",
    )
    monkeypatch.setattr("silemio_control_hub.vst3_scanner.subprocess.run", lambda *a, **k: completed)

    assert scan_vst3_module(plugin, expected_name="Test Plug") == result


def test_installed_scan_rejects_a_shift_risk_when_counts_differ(monkeypatch, tmp_path):
    plugin = tmp_path / "Test.vst3"
    plugin.mkdir()
    monkeypatch.setattr(
        "silemio_control_hub.vst3_scanner.installed_plugin_paths",
        lambda *a, **k: (plugin.resolve(),),
    )
    monkeypatch.setattr(
        "silemio_control_hub.vst3_scanner.scan_vst3_module",
        lambda *a, **k: _result(plugin, count=2),
    )

    with pytest.raises(VST3ScanError, match="expose 2 paramètres.*en contient 3"):
        scan_installed_vst3("Test Plug", expected_parameter_count=3)
