from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__
from .bridge import BridgeSnapshot, EC4LiveProfessorBridge
from .config import BridgeConfig, default_config_path, default_data_dir, load_config, save_config
from .ec4_protocol import main_display_message, parameter_grid_message, total_display_message
from .midi_backend import MidiBackendError, input_names, output_names
from .osc_codec import decode_message, encode_message


def configure_logging(level: str = "INFO") -> Path:
    data_dir = default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "bridge.log"
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not root.handlers:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        file_handler = RotatingFileHandler(
            log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        if not getattr(sys, "frozen", False):
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            root.addHandler(console)
    return log_path


def protocol_self_test() -> list[str]:
    results: list[str] = []
    packet = encode_message("/EC4/Test", [1, 0.5, "ok", True])
    address, args = decode_message(packet)
    assert address == "/EC4/Test" and args[0] == 1 and args[2] == "ok" and args[3] is True
    results.append("OSC encode/decode: OK")
    main = main_display_message([f"P{i + 1}" for i in range(16)])
    assert main[0] == 0xF0 and main[-1] == 0xF7 and len(main) == 206
    results.append("SysEx affichage principal: OK")
    total = total_display_message(["EC4", "LiveProfessor", "Banque 1", "Test"])
    assert total[0] == 0xF0 and total[-1] == 0xF7 and len(total) == 257
    results.append("SysEx affichage total: OK")
    grid = parameter_grid_message([f"P{i + 1}" for i in range(16)])
    assert grid[0] == 0xF0 and grid[-1] == 0xF7 and len(grid) == 257
    results.append("SysEx grille de parametres: OK")
    return results


class BridgeGUI:
    def __init__(self, config_path: Path) -> None:
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.messagebox = messagebox
        self.config_path = config_path
        self.config = load_config(config_path)
        self.bridge: EC4LiveProfessorBridge | None = None

        self.root = tk.Tk()
        self.root.title(f"SiLeMI/O | EC4 LiveProfessor Bridge {__version__} | By Mamat")
        self.root.geometry("820x710")
        self.root.minsize(720, 620)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.mode_var = tk.StringVar(value=self.config.mode)
        self.midi_in_var = tk.StringVar(value=self.config.midi_input)
        self.midi_out_var = tk.StringVar(value=self.config.midi_output)
        self.host_var = tk.StringVar(value=self.config.liveprofessor_host)
        self.lp_port_var = tk.StringVar(value=str(self.config.liveprofessor_port))
        self.feedback_port_var = tk.StringVar(value=str(self.config.feedback_port))
        self.profile_var = tk.StringVar(value=self.config.profile_file)
        self.display_var = tk.BooleanVar(value=self.config.display_enabled)
        self.persistent_display_var = tk.BooleanVar(
            value=self.config.persistent_parameter_display
        )
        self.target_setup_var = tk.StringVar(value=str(self.config.target_setup))
        self.target_group_var = tk.StringVar(value=str(self.config.target_group))
        self.status_var = tk.StringVar(value="Arrete")
        self.bank_var = tk.StringVar(value="Banque 1")
        self.learn_var = tk.StringVar(value="Mapping Ableton par defaut")
        self._learn_controls: list[tuple[int, int]] = []
        self._learn_pushes: list[tuple[int, int]] = []
        self._learn_phase = ""
        self._learning = False

        self._build()
        self._update_mapping_status()
        self.refresh_ports()
        self._append_log(f"Configuration: {self.config_path}")

    def _build(self) -> None:
        tk = self.tk
        ttk = self.ttk
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        row = 0
        brand = tk.Frame(main, bg="#111820", height=58, highlightthickness=1, highlightbackground="#2a4050")
        brand.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        brand.grid_propagate(False)
        tk.Label(
            brand,
            text="SiLeMI/O",
            bg="#111820",
            fg="#43d6ff",
            font=("Segoe UI Semibold", 18),
        ).pack(side="left", padx=(16, 12))
        tk.Label(
            brand,
            text="EC4 × LiveProfessor",
            bg="#111820",
            fg="#e8f4f8",
            font=("Segoe UI", 11),
        ).pack(side="left")
        tk.Label(
            brand,
            text="By Mamat  ------[]---",
            bg="#111820",
            fg="#91a9b5",
            font=("Segoe UI", 9),
            width=24,
            anchor="e",
        ).pack(side="right", padx=12)

        row += 1
        ttk.Label(main, text="Mode LiveProfessor").grid(row=row, column=0, sticky="w", pady=4)
        mode = ttk.Combobox(
            main,
            textvariable=self.mode_var,
            values=("companion", "generic"),
            state="readonly",
            width=22,
        )
        mode.grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(
            main,
            text="Companion: noms/valeurs dynamiques | Generic: libelles de profil",
        ).grid(row=row, column=2, sticky="w", padx=(8, 0))

        row += 1
        ttk.Label(main, text="Entree MIDI").grid(row=row, column=0, sticky="w", pady=4)
        self.input_combo = ttk.Combobox(main, textvariable=self.midi_in_var)
        self.input_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)

        row += 1
        ttk.Label(main, text="Sortie MIDI").grid(row=row, column=0, sticky="w", pady=4)
        self.output_combo = ttk.Combobox(main, textvariable=self.midi_out_var)
        self.output_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)

        row += 1
        ttk.Button(main, text="Actualiser les ports MIDI", command=self.refresh_ports).grid(
            row=row, column=1, sticky="w", pady=(0, 8)
        )

        row += 1
        ttk.Separator(main).grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        row += 1
        ttk.Label(main, text="Adresse LiveProfessor").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(main, textvariable=self.host_var).grid(row=row, column=1, sticky="ew", pady=4)
        ports = ttk.Frame(main)
        ports.grid(row=row, column=2, sticky="ew", padx=(8, 0))
        ttk.Label(ports, text="Port LP").pack(side="left")
        ttk.Entry(ports, textvariable=self.lp_port_var, width=7).pack(side="left", padx=(4, 12))
        ttk.Label(ports, text="Retour").pack(side="left")
        ttk.Entry(ports, textvariable=self.feedback_port_var, width=7).pack(side="left", padx=4)

        row += 1
        ttk.Label(main, text="Profil de noms (optionnel)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(main, textvariable=self.profile_var).grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=4
        )

        row += 1
        ttk.Label(main, text="Zone EC4 dediee").grid(row=row, column=0, sticky="w", pady=4)
        target = ttk.Frame(main)
        target.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(target, text="Setup").pack(side="left")
        ttk.Spinbox(target, from_=1, to=16, textvariable=self.target_setup_var, width=5).pack(
            side="left", padx=(4, 12)
        )
        ttk.Label(target, text="Groupe").pack(side="left")
        ttk.Spinbox(target, from_=1, to=16, textvariable=self.target_group_var, width=5).pack(
            side="left", padx=(4, 12)
        )
        ttk.Button(
            target,
            text="Utiliser le setup/groupe actuel",
            command=self.use_current_target,
        ).pack(side="left")

        row += 1
        ttk.Label(main, text="Mapping des encodeurs").grid(row=row, column=0, sticky="w", pady=4)
        learn_frame = ttk.Frame(main)
        learn_frame.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        self.learn_button = ttk.Button(
            learn_frame,
            text="Apprendre rotatifs + push",
            command=self.toggle_midi_learn,
        )
        self.learn_button.pack(side="left")
        ttk.Label(learn_frame, textvariable=self.learn_var).pack(side="left", padx=12)

        row += 1
        ttk.Checkbutton(main, text="Activer l'affichage SysEx EC4", variable=self.display_var).grid(
            row=row, column=1, columnspan=2, sticky="w", pady=4
        )

        row += 1
        ttk.Checkbutton(
            main,
            text="Afficher en permanence les parametres du plugin selectionne",
            variable=self.persistent_display_var,
        ).grid(row=row, column=1, columnspan=2, sticky="w", pady=4)

        row += 1
        action_frame = ttk.Frame(main)
        action_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        self.start_button = ttk.Button(action_frame, text="Demarrer", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(action_frame, text="Arreter", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=6)
        ttk.Button(action_frame, text="Enregistrer", command=self.save).pack(side="left", padx=6)
        ttk.Button(action_frame, text="Diagnostic", command=self.diagnostic).pack(side="left", padx=6)
        ttk.Button(action_frame, text="Raccourcis EC4", command=self.show_shortcuts).pack(
            side="left", padx=6
        )
        ttk.Button(action_frame, text="Tester l'ecran EC4", command=self.demo_display).pack(
            side="left", padx=6
        )

        row += 1
        state_frame = ttk.LabelFrame(main, text="Etat", padding=8)
        state_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)
        state_frame.columnconfigure(0, weight=1)
        ttk.Label(state_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(state_frame, text="Banque precedente", command=lambda: self.change_bank(-1)).grid(
            row=0, column=1, padx=4
        )
        ttk.Label(state_frame, textvariable=self.bank_var, width=14, anchor="center").grid(
            row=0, column=2
        )
        ttk.Button(state_frame, text="Banque suivante", command=lambda: self.change_bank(1)).grid(
            row=0, column=3, padx=4
        )

        row += 1
        log_frame = ttk.LabelFrame(main, text="Journal", padding=6)
        log_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        main.rowconfigure(row, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=14, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

    def _config_from_form(self) -> BridgeConfig:
        config = replace(
            self.config,
            mode=self.mode_var.get().strip(),
            midi_input=self.midi_in_var.get().strip(),
            midi_output=self.midi_out_var.get().strip(),
            liveprofessor_host=self.host_var.get().strip(),
            liveprofessor_port=int(self.lp_port_var.get()),
            feedback_port=int(self.feedback_port_var.get()),
            profile_file=self.profile_var.get().strip(),
            display_enabled=bool(self.display_var.get()),
            persistent_parameter_display=bool(self.persistent_display_var.get()),
            target_setup=int(self.target_setup_var.get()),
            target_group=int(self.target_group_var.get()),
            restrict_to_target=True,
        )
        config.validate()
        return config

    def refresh_ports(self) -> None:
        try:
            inputs = input_names()
            outputs = output_names()
            self.input_combo.configure(values=inputs)
            self.output_combo.configure(values=outputs)
            self._append_log(f"Ports MIDI: {len(inputs)} entree(s), {len(outputs)} sortie(s)")
            for name in inputs:
                if "faderfox" in name.casefold():
                    self.midi_in_var.set(name)
                    break
            for name in outputs:
                if "faderfox" in name.casefold():
                    self.midi_out_var.set(name)
                    break
        except Exception as exc:
            self._append_log(f"Inventaire MIDI impossible: {exc}")

    def save(self) -> None:
        try:
            self.config = self._config_from_form()
            path = save_config(self.config, self.config_path)
            self._append_log(f"Configuration enregistree: {path}")
        except Exception as exc:
            self.messagebox.showerror("Configuration invalide", str(exc))

    def start(self) -> None:
        try:
            if self.bridge:
                self.bridge.stop()
            self.config = self._config_from_form()
            save_config(self.config, self.config_path)
            self.bridge = EC4LiveProfessorBridge(
                self.config,
                status_callback=self._queue_snapshot,
                log_callback=self._queue_log,
            )
            self.bridge.start()
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
        except Exception as exc:
            self._append_log(f"Demarrage impossible: {exc}")
            self.messagebox.showerror("Demarrage impossible", str(exc))

    def stop(self) -> None:
        self._cancel_midi_learn()
        if self.bridge:
            self.bridge.stop()
            self.bridge = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_var.set("Arrete")

    def change_bank(self, delta: int) -> None:
        if self.bridge:
            self.bridge.change_bank(delta)

    def demo_display(self) -> None:
        if not self.bridge or not self.bridge.running:
            self.messagebox.showinfo("Pont arrete", "Demarrez d'abord le pont.")
            return
        if not self.bridge.snapshot().midi_connected:
            self.messagebox.showinfo("EC4 absent", "Connectez l'EC4 puis attendez l'etat Connecte.")
            return
        self.bridge.demo_display()

    def use_current_target(self) -> None:
        if not self.bridge or not self.bridge.running:
            self.messagebox.showinfo("Pont arrete", "Demarrez d'abord le pont.")
            return
        snapshot = self.bridge.snapshot()
        if snapshot.setup is None or snapshot.group is None:
            self.messagebox.showinfo(
                "Etat EC4 inconnu",
                "Changez une fois de setup ou de groupe sur l'EC4, puis recommencez.",
            )
            return
        setup = snapshot.setup + 1
        group = snapshot.group + 1
        self.target_setup_var.set(str(setup))
        self.target_group_var.set(str(group))
        try:
            self.config = self._config_from_form()
            save_config(self.config, self.config_path)
            self.bridge.set_target(setup, group)
            self._update_mapping_status()
            self._append_log(f"Zone EC4 enregistree: setup {setup}, groupe {group}")
        except Exception as exc:
            self.messagebox.showerror("Configuration invalide", str(exc))

    def _mapping_key(self) -> str:
        return f"{int(self.target_setup_var.get())}:{int(self.target_group_var.get())}"

    def _update_mapping_status(self) -> None:
        mapping = self.config.encoder_mappings.get(self._mapping_key())
        if mapping and len(mapping) == 16:
            self.learn_var.set("Mapping appris et enregistre")
        else:
            self.learn_var.set("Mapping Ableton par defaut")

    def toggle_midi_learn(self) -> None:
        if self._learning:
            self._cancel_midi_learn()
            return
        if not self.bridge or not self.bridge.running:
            self.messagebox.showinfo("Pont arrete", "Demarrez d'abord le pont.")
            return
        snapshot = self.bridge.snapshot()
        target = (int(self.target_setup_var.get()), int(self.target_group_var.get()))
        current = (
            snapshot.setup + 1 if snapshot.setup is not None else None,
            snapshot.group + 1 if snapshot.group is not None else None,
        )
        if current != target:
            self.messagebox.showinfo(
                "Mauvaise zone EC4",
                f"Selectionnez d'abord le setup {target[0]}, groupe {target[1]} sur l'EC4.",
            )
            return
        try:
            self.config = self._config_from_form()
            save_config(self.config, self.config_path)
            self.bridge.config.encoder_mappings = self.config.encoder_mappings
            self.bridge.set_target(*target)
        except Exception as exc:
            self.messagebox.showerror("Configuration invalide", str(exc))
            return
        self._learning = True
        self._learn_controls = []
        self._learn_pushes = []
        self._learn_phase = "cc"
        self.learn_button.configure(text="Annuler l'apprentissage")
        self.learn_var.set("Tournez l'encodeur 1")
        self.bridge.set_midi_learn_callback(self._queue_midi_learn)
        self._append_log("Apprentissage MIDI: tournez les encodeurs 1 a 16 dans l'ordre")
        self.messagebox.showinfo(
            "Apprentissage MIDI",
            "Phase 1 : tournez legerement l'encodeur 1, puis le 2, jusqu'au 16. "
            "Phase 2 : vous appuierez ensuite sur leurs 16 push dans le meme ordre.",
        )

    def _queue_midi_learn(self, kind: str, channel: int, identifier: int, value: int) -> bool:
        self.root.after(0, self._capture_midi_learn, kind, channel, identifier, value)
        return True

    def _capture_midi_learn(
        self, kind: str, channel: int, identifier: int, _value: int
    ) -> None:
        if not self._learning:
            return
        if self._learn_phase == "cc" and kind != "cc":
            return
        if self._learn_phase == "note" and kind != "note":
            return
        learned = self._learn_controls if self._learn_phase == "cc" else self._learn_pushes
        address = (channel, identifier)
        if address in learned:
            return
        learned.append(address)
        number = len(learned)
        label = "CC" if self._learn_phase == "cc" else "Note push"
        self._append_log(f"{label} {number}: canal {channel + 1}, numero {identifier}")
        if number < 16:
            if self._learn_phase == "cc":
                self.learn_var.set(f"Tournez l'encodeur {number + 1} ({number}/16 rotatifs)")
            else:
                self.learn_var.set(f"Appuyez sur le push {number + 1} ({number}/16 push)")
            return
        if self._learn_phase == "cc":
            self._learn_phase = "note"
            self.learn_var.set("Appuyez sur le push 1 (0/16 push)")
            self._append_log("Rotatifs appris. Appuyez maintenant sur les push 1 a 16")
            self.messagebox.showinfo(
                "Rotatifs termines",
                "Appuyez maintenant une fois sur le push de l'encodeur 1, puis 2, jusqu'au 16.",
            )
            return
        mapping = [
            {
                "channel": learned_channel,
                "control": learned_control,
                "push_channel": push_channel,
                "push_note": push_note,
            }
            for (learned_channel, learned_control), (push_channel, push_note) in zip(
                self._learn_controls, self._learn_pushes
            )
        ]
        key = self._mapping_key()
        self.config.encoder_mappings[key] = mapping
        if self.bridge:
            self.bridge.config.encoder_mappings = self.config.encoder_mappings
            self.bridge.set_midi_learn_callback(None)
            self.bridge.refresh_target()
        save_config(self.config, self.config_path)
        self._learning = False
        self._learn_phase = ""
        self.learn_button.configure(text="Apprendre rotatifs + push")
        self.learn_var.set("Mapping appris et enregistre")
        self._append_log(f"Mapping MIDI enregistre pour la zone {key}")
        self.messagebox.showinfo("Apprentissage termine", "Les 16 encodeurs sont enregistres.")

    def _cancel_midi_learn(self) -> None:
        if self.bridge:
            self.bridge.set_midi_learn_callback(None)
        if self._learning:
            self._append_log("Apprentissage MIDI annule")
        self._learning = False
        self._learn_controls = []
        self._learn_pushes = []
        self._learn_phase = ""
        if hasattr(self, "learn_button"):
            self.learn_button.configure(text="Apprendre rotatifs + push")
        if hasattr(self, "learn_var"):
            self._update_mapping_status()

    def diagnostic(self) -> None:
        lines = [f"EC4 LiveProfessor Bridge {__version__}"]
        try:
            lines.extend(protocol_self_test())
            lines.append("Entrees MIDI: " + (", ".join(input_names()) or "aucune"))
            lines.append("Sorties MIDI: " + (", ".join(output_names()) or "aucune"))
        except Exception as exc:
            lines.append(f"ERREUR: {exc}")
        self.messagebox.showinfo("Diagnostic", "\n".join(lines))

    def show_shortcuts(self) -> None:
        self.messagebox.showinfo(
            "Raccourcis EC4",
            "Shift + push 1 : premiere banque\n"
            "Shift + push 2 / 3 : banque precedente / suivante\n"
            "Shift + push 4 : derniere banque\n\n"
            "Shift + push 6 / 7 : plugin precedent / suivant\n"
            "Shift + push 10 / 11 : chaine precedente / suivante\n\n"
            "Shift + push 14 / 15 : snapshot precedent / suivant\n"
            "Shift + push 13 : activer / desactiver le plugin\n"
            "Shift + push 16 : afficher / masquer le plugin\n"
            "Push 16 seul : Tap Tempo",
        )

    def _queue_snapshot(self, snapshot: BridgeSnapshot) -> None:
        self.root.after(0, self._apply_snapshot, snapshot)

    def _apply_snapshot(self, snapshot: BridgeSnapshot) -> None:
        details = snapshot.status
        if snapshot.setup is not None:
            details += f" | Setup {snapshot.setup + 1}, groupe {snapshot.group + 1}"
        self.status_var.set(details)
        self.bank_var.set(f"Banque {snapshot.active_bank + 1}/{snapshot.bank_count}")

    def _queue_log(self, message: str) -> None:
        self.root.after(0, self._append_log, message)

    def _append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{stamp}  {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_close(self) -> None:
        self.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_headless(config_path: Path) -> int:
    config = load_config(config_path)
    configure_logging(config.log_level)
    bridge = EC4LiveProfessorBridge(config, log_callback=print)
    bridge.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        bridge.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pont Faderfox EC4 vers LiveProfessor")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--list-midi", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    configure_logging(config.log_level)
    if args.self_test:
        for result in protocol_self_test():
            print(result)
        return 0
    if args.list_midi:
        print("Entrees MIDI:")
        for name in input_names():
            print(f"  {name}")
        print("Sorties MIDI:")
        for name in output_names():
            print(f"  {name}")
        return 0
    if args.headless:
        return run_headless(args.config)
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    BridgeGUI(args.config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
