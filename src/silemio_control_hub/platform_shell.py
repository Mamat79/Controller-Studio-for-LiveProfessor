"""Open local files and folders with the platform's registered application."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import subprocess
import sys


def open_path(
    path: str | os.PathLike[str],
    *,
    platform_name: str | None = None,
    launcher: Callable[[list[str]], object] | None = None,
) -> Path:
    """Open an existing path and return its resolved value.

    ``launcher`` is intentionally expressed as an argument vector so tests and
    packaged callers never have to construct a shell command.
    """

    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    active_platform = platform_name or sys.platform
    if active_platform == "win32":
        if launcher is not None:
            launcher([str(resolved)])
        else:
            os.startfile(str(resolved))
        return resolved
    command = ["open", str(resolved)] if active_platform == "darwin" else ["xdg-open", str(resolved)]
    if launcher is not None:
        launcher(command)
    else:
        subprocess.Popen(command, close_fds=True)
    return resolved
