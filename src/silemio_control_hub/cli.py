from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil

from .adapters.hosts import export_liveprofessor_controller, inspect_plugins
from .library import (
    LibraryError,
    LibraryManifest,
    validate_library,
    validate_plugin_library,
)
from .library_remote import (
    DEFAULT_LIBRARY_REF,
    DEFAULT_LIBRARY_REPOSITORY,
    GitHubLibraryClient,
    LibraryRemoteError,
    list_library_backups,
    rollback_library,
    update_library,
)
from .models import ProfileError
from .plugin_registry import PluginProfileRegistry
from .registry import ControllerRegistry, default_user_profile_dir
from .simulator import ControllerSimulator
from .workflow import prepare_liveprofessor_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="silemio-control-hub")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("profiles", help="Lister les profils de contrôleurs intégrés")
    subparsers.add_parser(
        "plugin-profiles", help="Lister les profils de plug-ins en cache et locaux"
    )
    validate = subparsers.add_parser("validate-profile", help="Valider un profil JSON")
    validate.add_argument("path", type=Path)
    subparsers.add_parser("profile-dir", help="Afficher le dossier des profils utilisateur")
    install = subparsers.add_parser("install-profile", help="Installer un profil validé")
    install.add_argument("path", type=Path)
    install.add_argument("--replace", action="store_true")
    simulate = subparsers.add_parser(
        "simulate", help="Émettre un événement normalisé sans contrôleur physique"
    )
    simulate.add_argument("profile_id")
    simulate.add_argument(
        "action",
        choices=[
            "state",
            "rotate",
            "press",
            "release",
            "touch",
            "untouch",
            "modifier-on",
            "modifier-off",
        ],
    )
    simulate.add_argument("target", nargs="?")
    simulate.add_argument("value", nargs="?", type=float)
    simulate.add_argument("--bank", type=int, default=1, help="Banque logique, à partir de 1")
    simulate.add_argument("--page", type=int, default=1, help="Page logique, à partir de 1")
    export = subparsers.add_parser(
        "export-liveprofessor-controller",
        help="Générer un fichier Companion .ctrl2 depuis un profil",
    )
    export.add_argument("profile_id")
    export.add_argument("destination", type=Path)
    export.add_argument("--name", help="Nom affiché dans LiveProfessor")
    export.add_argument("--osc-in-port", type=int, default=8010)
    export.add_argument("--osc-out-port", type=int, default=8011)
    export.add_argument("--replace", action="store_true")
    library = subparsers.add_parser(
        "validate-library",
        help="Valider un manifeste et tous les profils d'une bibliothèque locale",
    )
    library.add_argument("root", type=Path)
    library.add_argument("--manifest", type=Path)
    prepare = subparsers.add_parser(
        "prepare-liveprofessor",
        help="Créer le CTRL2 et une copie AutoMap depuis un profil",
    )
    prepare.add_argument("profile_id")
    prepare.add_argument("source_project", type=Path)
    prepare.add_argument("destination_project", type=Path)
    prepare.add_argument("controller_output", type=Path)
    prepare.add_argument("--plugin-uid", type=int)
    prepare.add_argument("--name", help="Nom du contrôleur dans LiveProfessor")
    prepare.add_argument("--osc-in-port", type=int, default=8010)
    prepare.add_argument("--osc-out-port", type=int, default=8011)
    prepare.add_argument("--replace-controller", action="store_true")
    prepare.add_argument("--replace-project", action="store_true")
    inspect_plugins_parser = subparsers.add_parser(
        "inspect-liveprofessor-plugins",
        help="Identifier les plug-ins d'un projet sans exiger de contrôleur",
    )
    inspect_plugins_parser.add_argument("project", type=Path)
    library_update = subparsers.add_parser(
        "library-update",
        help="Prévisualiser ou appliquer une mise à jour facultative depuis GitHub",
    )
    library_update.add_argument("--repo", default=DEFAULT_LIBRARY_REPOSITORY)
    library_update.add_argument("--ref", default=DEFAULT_LIBRARY_REF)
    library_update.add_argument("--cache-dir", type=Path)
    library_update.add_argument("--apply", action="store_true")
    library_update.add_argument("--allow-downgrade", action="store_true")
    library_update.add_argument("--allow-removals", action="store_true")
    library_backups = subparsers.add_parser(
        "library-backups", help="Lister les versions de bibliothèque restaurables"
    )
    library_backups.add_argument("--cache-dir", type=Path)
    library_rollback = subparsers.add_parser(
        "library-rollback", help="Prévisualiser ou restaurer une bibliothèque sauvegardée"
    )
    library_rollback.add_argument("backup")
    library_rollback.add_argument("--cache-dir", type=Path)
    library_rollback.add_argument("--apply", action="store_true")
    return parser


def _json_ready(value):
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_json_ready(item) for item in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


def _print_library_changes(result) -> None:
    if not result.preview.changes:
        print("BIBLIOTHÈQUE: déjà à jour")
    for change in result.preview.changes:
        current = change.current_version or "—"
        remote = change.remote_version or "—"
        print(
            f"{change.kind.upper()}: {change.collection} {change.id} "
            f"{current} -> {remote}"
        )
    if result.applied and result.preview.changes:
        print(f"INSTALLÉE: {result.cache_root / 'current'}")
        if result.backup_path is not None:
            print(f"SAUVEGARDE: {result.backup_path.name}")
    elif result.applied:
        print("AUCUNE ÉCRITURE: le cache validé est inchangé")
    else:
        print("APERÇU UNIQUEMENT: relancez avec --apply pour installer")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry = ControllerRegistry()
    try:
        if args.command == "profiles":
            for profile in registry.all():
                print(
                    f"{profile.id}\t{profile.display_name}\t"
                    f"v{profile.profile_version}\t{len(profile.controls)} contrôles\t{profile.status}"
                )
            return 0
        if args.command == "plugin-profiles":
            for profile in PluginProfileRegistry().all():
                print(
                    f"{profile.id}\t{profile.plugin_name}\t"
                    f"v{profile.profile_version}\t{profile.layer.value}\t"
                    f"{profile.status}\t{len(profile.parameters)} paramètre(s)"
                )
            return 0
        if args.command == "validate-profile":
            profile = registry.load_file(args.path)
            print(
                f"OK: {profile.display_name} ({profile.id}), "
                f"{len(profile.controls)} contrôles, banque {profile.bank_size}"
            )
            return 0
        if args.command == "profile-dir":
            print(default_user_profile_dir())
            return 0
        if args.command == "install-profile":
            profile = registry.load_file(args.path)
            destination_dir = default_user_profile_dir()
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"{profile.id}.json"
            if destination.exists() and not args.replace:
                raise ProfileError(
                    f"{destination} existe déjà; utilisez --replace pour le remplacer"
                )
            shutil.copy2(args.path, destination)
            print(f"INSTALLÉ: {profile.display_name} -> {destination}")
            return 0
        if args.command == "export-liveprofessor-controller":
            profile = registry.get(args.profile_id)
            result = export_liveprofessor_controller(
                profile,
                args.destination,
                replace=args.replace,
                controller_name=args.name,
                osc_in_port=args.osc_in_port,
                osc_out_port=args.osc_out_port,
                plugin_profiles=PluginProfileRegistry().all(),
            )
            print(
                f"CRÉÉ: {result.path} | {result.rotary_count} rotatifs | "
                f"{result.button_count} boutons | SHA-256 {result.sha256}"
            )
            return 0
        if args.command == "validate-library":
            root = args.root.expanduser().resolve()
            manifest_path = args.manifest or root / "manifest-v1.json"
            manifest = LibraryManifest.load_file(manifest_path)
            profiles = validate_library(root, manifest)
            plugin_profiles = validate_plugin_library(root, manifest)
            print(
                f"OK: bibliothèque v{manifest.manifest_version}, "
                f"{len(profiles)} contrôleur(s), "
                f"{len(plugin_profiles)} plug-in(s), générée {manifest.generated_at}"
            )
            return 0
        if args.command == "prepare-liveprofessor":
            profile = registry.get(args.profile_id)
            result = prepare_liveprofessor_project(
                profile,
                args.source_project,
                args.destination_project,
                args.controller_output,
                plugin_uid=args.plugin_uid,
                replace_controller=args.replace_controller,
                replace_project=args.replace_project,
                controller_name=args.name,
                osc_in_port=args.osc_in_port,
                osc_out_port=args.osc_out_port,
            )
            print(
                f"CONTRÔLEUR: {result.controller.path} | "
                f"{result.controller.rotary_count} rotatifs | "
                f"SHA-256 {result.controller.sha256}"
            )
            print(
                f"AUTOMAP: {result.automap.output_path} | "
                f"{result.automap.mapped_rotaries}/"
                f"{result.automap.available_parameters} paramètre(s) | "
                f"source inchangée {result.source_sha256}"
            )
            if result.automap.backup_path is not None:
                print(f"SAUVEGARDE: {result.automap.backup_path}")
            return 0
        if args.command == "inspect-liveprofessor-plugins":
            payload = []
            for plugin in inspect_plugins(args.project):
                observation = plugin.observation
                payload.append(
                    {
                        "uid": plugin.plugin_uid,
                        "name": plugin.name,
                        "format": observation.plugin_format,
                        "stable_id": observation.stable_id,
                        "parameter_count": plugin.parameter_count,
                        "parameter_fingerprint": observation.parameter_fingerprint,
                    }
                )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if args.command == "library-update":
            result = update_library(
                GitHubLibraryClient(args.repo, args.ref),
                cache_root=args.cache_dir,
                apply=args.apply,
                allow_downgrade=args.allow_downgrade,
                allow_removals=args.allow_removals,
            )
            _print_library_changes(result)
            return 0
        if args.command == "library-backups":
            backups = list_library_backups(args.cache_dir)
            if backups:
                print("\n".join(backups))
            else:
                print("AUCUNE SAUVEGARDE")
            return 0
        if args.command == "library-rollback":
            result = rollback_library(
                args.backup,
                cache_root=args.cache_dir,
                apply=args.apply,
            )
            _print_library_changes(result)
            return 0
        if args.command == "simulate":
            profile = registry.get(args.profile_id)
            simulator = ControllerSimulator(profile)
            simulator.set_bank(args.bank - 1)
            simulator.set_page(args.page - 1)
            if args.action == "state":
                payload = {"profile_id": profile.id, "context": asdict(simulator.state.context)}
            else:
                if not args.target:
                    raise ValueError("target est requis pour cette action")
                if args.action == "rotate":
                    if args.value is None:
                        raise ValueError("value est requise pour rotate")
                    event = simulator.rotate(args.target, args.value)
                elif args.action == "press":
                    event = simulator.press(args.target)
                elif args.action == "release":
                    event = simulator.press(args.target, False)
                elif args.action == "touch":
                    event = simulator.touch(args.target)
                elif args.action == "untouch":
                    event = simulator.touch(args.target, False)
                elif args.action == "modifier-on":
                    event = simulator.modifier(args.target)
                else:
                    event = simulator.modifier(args.target, False)
                payload = {"event": type(event).__name__, **asdict(event)}
            print(json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True))
            return 0
    except (
        LibraryError,
        LibraryRemoteError,
        ProfileError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"ERREUR: {exc}")
        return 2
    return 1
