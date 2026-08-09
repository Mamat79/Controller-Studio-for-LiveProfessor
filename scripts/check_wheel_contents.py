"""Refuse a SiLeMI/O wheel that accidentally embeds historical bridge code."""

from __future__ import annotations

from pathlib import Path
import sys
from zipfile import ZipFile


FORBIDDEN_PREFIXES = ("ec4lpbridge/",)
REQUIRED_ENTRIES = (
    "silemio_control_hub/assets/controller-studio.ico",
    "silemio_control_hub/assets/controller-studio.png",
    "silemio_control_hub/assets/paypal-support-qr.png",
    "silemio_control_hub/manuals/Controller-Studio-for-LiveProfessor-Manual-EN.pdf",
    "silemio_control_hub/manuals/Controller-Studio-for-LiveProfessor-Notice-FR.pdf",
)


def check_wheel(path: Path) -> tuple[list[str], list[str]]:
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        forbidden = sorted(
            name
            for name in names
            if name.startswith(FORBIDDEN_PREFIXES)
        )
        missing = sorted(name for name in REQUIRED_ENTRIES if name not in names)
        return forbidden, missing


def main(arguments: list[str] | None = None) -> int:
    paths = [Path(argument) for argument in (arguments or sys.argv[1:])]
    if len(paths) != 1 or not paths[0].is_file():
        print("usage: check_wheel_contents.py chemin-du-wheel.whl", file=sys.stderr)
        return 2
    forbidden, missing = check_wheel(paths[0])
    if forbidden:
        print("Fichiers historiques interdits dans le wheel :", file=sys.stderr)
        print("\n".join(forbidden), file=sys.stderr)
        return 1
    if missing:
        print("Ressources produit absentes du wheel :", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        return 1
    print(f"OK: {paths[0]} contient les ressources produit et aucun paquet historique")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
