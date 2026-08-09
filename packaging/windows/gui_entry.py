import json
import os
from pathlib import Path
import sys


def packaged_smoke_test() -> int:
    result_path = os.environ.get("SILEMIO_SMOKE_RESULT")
    try:
        from silemio_control_hub.diagnostics import run_product_diagnostics

        result = run_product_diagnostics()
        result["status"] = "ok"
        exit_code = 0
    except Exception as exc:
        result = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        exit_code = 2
    if result_path:
        destination = Path(result_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return exit_code


if __name__ == "__main__":
    if "--smoke-test" in sys.argv[1:]:
        raise SystemExit(packaged_smoke_test())
    from silemio_control_hub.desktop import main

    raise SystemExit(main())
