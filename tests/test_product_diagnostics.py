from silemio_control_hub.identity import FULL_PRODUCT_NAME
import silemio_control_hub.diagnostics as diagnostics


def test_product_diagnostics_exercise_the_midi_backend(monkeypatch):
    monkeypatch.setattr(diagnostics, "input_names", lambda: ["EC4 input"])
    monkeypatch.setattr(diagnostics, "output_names", lambda: ["EC4 output"])

    result = diagnostics.run_product_diagnostics()

    assert result == {
        "product": FULL_PRODUCT_NAME,
        "config": "ok",
        "osc": "ok",
        "ec4_sysex": "ok",
        "midi_backend": "ok",
        "midi_inputs": 1,
        "midi_outputs": 1,
    }
