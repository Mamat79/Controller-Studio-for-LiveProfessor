"""Tk controller creator used by Controller Studio's controller bank."""

from __future__ import annotations

import json
from pathlib import Path
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from .adapters.hosts import export_liveprofessor_controller
from .controller_studio import (
    controller_profile_payload,
    midi_binding_from_message,
    save_user_controller_profile,
    suggest_controller_profile_id,
    validate_controller_draft,
)
from .models import ProfileError
from .registry import default_user_profile_dir
from .transports.midi import MidiInputListener, input_names


Translator = Callable[..., str]
SavedCallback = Callable[[str], None]


def _split_patterns(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


class ControllerEditorDialog:
    """Create or edit a declarative controller without exposing JSON to users."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        translator: Translator,
        payload: dict[str, Any],
        on_saved: SavedCallback,
        on_contribute: SavedCallback,
        icon_path: Path | None = None,
    ) -> None:
        self.parent = parent
        self._t = translator
        self.payload = json.loads(json.dumps(payload, ensure_ascii=False))
        self.controls: list[dict[str, Any]] = self.payload.setdefault("controls", [])
        self.on_saved = on_saved
        self.on_contribute = on_contribute
        self.listener: MidiInputListener | None = None
        self.learn_queue: queue.SimpleQueue[Any] = queue.SimpleQueue()
        self.learn_target: str | None = None
        self.learn_after_id: str | None = None
        self.selected_index: int | None = None

        self.window = tk.Toplevel(parent)
        self.window.title(self._t("controller_editor_title"))
        self.window.geometry("1120x780")
        self.window.minsize(940, 680)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        if icon_path and icon_path.is_file():
            try:
                self.window.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

        self.manufacturer_var = tk.StringVar(value=str(self.payload.get("manufacturer", "")))
        self.model_var = tk.StringVar(value=str(self.payload.get("model", "")))
        self.profile_id_var = tk.StringVar(value=str(self.payload.get("id", "")))
        self.firmware_var = tk.StringVar(value=str(self.payload.get("firmware", "")))
        identity = self.payload.get("midi_identity") or {}
        self.input_pattern_var = tk.StringVar(
            value="; ".join(identity.get("input_name_patterns", []))
        )
        self.output_pattern_var = tk.StringVar(
            value="; ".join(identity.get("output_name_patterns", []))
        )
        self.bank_size_var = tk.StringVar(value=str(self.payload.get("bank_size", 1)))
        self.bank_count_var = tk.StringVar(value=str(self.payload.get("bank_count", 1)))
        self.page_count_var = tk.StringVar(value=str(self.payload.get("page_count", 1)))
        self.midi_port_var = tk.StringVar()
        self.learn_status_var = tk.StringVar(value=self._t("controller_learn_idle"))

        self.control_id_var = tk.StringVar()
        self.kind_var = tk.StringVar()
        self.message_var = tk.StringVar()
        self.channel_var = tk.StringVar(value="1")
        self.number_var = tk.StringVar(value="0")
        self.relative_mode_var = tk.StringVar(value="twos_complement")
        self.push_enabled_var = tk.BooleanVar(value=False)
        self.push_message_var = tk.StringVar()
        self.push_channel_var = tk.StringVar(value="1")
        self.push_number_var = tk.StringVar(value="0")

        self.kind_labels = {
            self._t("controller_kind_absolute"): "absolute_encoder",
            self._t("controller_kind_relative"): "relative_encoder",
            self._t("controller_kind_fader"): "fader",
            self._t("controller_kind_button"): "button",
            self._t("controller_kind_pad"): "pad",
        }
        self.kind_names = {value: label for label, value in self.kind_labels.items()}
        self.message_labels = {
            "CC": "cc",
            self._t("controller_message_note"): "note",
            "NRPN": "nrpn",
            self._t("controller_message_pitch"): "pitch_bend",
        }
        self.message_names = {value: label for label, value in self.message_labels.items()}
        self._build()
        self._refresh_midi_ports()
        self._refresh_controls(select=0 if self.controls else None)

    def _build(self) -> None:
        root = ttk.Frame(self.window, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        intro = ttk.Label(
            root,
            text=self._t("controller_editor_intro"),
            justify="left",
            wraplength=1040,
        )
        intro.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        identity = ttk.LabelFrame(root, text=self._t("controller_identity"), padding=8)
        identity.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for column in (1, 3, 5):
            identity.columnconfigure(column, weight=1)
        fields = (
            ("maker", self.manufacturer_var, 0, 0),
            ("model", self.model_var, 0, 2),
            ("controller_profile_id", self.profile_id_var, 0, 4),
            ("controller_input_pattern", self.input_pattern_var, 1, 0),
            ("controller_output_pattern", self.output_pattern_var, 1, 2),
            ("controller_firmware", self.firmware_var, 1, 4),
        )
        for key, variable, row, column in fields:
            ttk.Label(identity, text=self._t(key)).grid(
                row=row, column=column, sticky="w", padx=(0, 5), pady=3
            )
            ttk.Entry(identity, textvariable=variable).grid(
                row=row, column=column + 1, sticky="ew", padx=(0, 12), pady=3
            )
        ttk.Label(identity, text=self._t("controller_bank_size")).grid(
            row=2, column=0, sticky="w", pady=3
        )
        ttk.Spinbox(identity, from_=1, to=99, textvariable=self.bank_size_var, width=7).grid(
            row=2, column=1, sticky="w", pady=3
        )
        ttk.Label(identity, text=self._t("controller_bank_count")).grid(
            row=2, column=2, sticky="w", pady=3
        )
        ttk.Spinbox(identity, from_=1, to=99, textvariable=self.bank_count_var, width=7).grid(
            row=2, column=3, sticky="w", pady=3
        )
        ttk.Label(identity, text=self._t("controller_page_count")).grid(
            row=2, column=4, sticky="w", pady=3
        )
        ttk.Spinbox(identity, from_=1, to=99, textvariable=self.page_count_var, width=7).grid(
            row=2, column=5, sticky="w", pady=3
        )
        ttk.Button(
            identity,
            text=self._t("controller_generate_id"),
            command=self._generate_id,
        ).grid(row=2, column=6, sticky="e", padx=(8, 0))

        center = ttk.Panedwindow(root, orient="vertical")
        center.grid(row=2, column=0, sticky="nsew")
        table_frame = ttk.Frame(center)
        editor_frame = ttk.LabelFrame(center, text=self._t("controller_selected_control"), padding=8)
        center.add(table_frame, weight=3)
        center.add(editor_frame, weight=2)

        columns = ("number", "id", "kind", "message", "channel", "value", "push")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "number": "N°",
            "id": self._t("controller_control_id"),
            "kind": self._t("controller_control_kind"),
            "message": self._t("controller_message"),
            "channel": self._t("controller_channel"),
            "value": self._t("controller_number"),
            "push": self._t("controller_push"),
        }
        widths = {"number": 50, "id": 180, "kind": 180, "message": 100, "channel": 80, "value": 80, "push": 180}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._load_selected)

        add = ttk.Frame(root)
        add.grid(row=3, column=0, sticky="ew", pady=(7, 7))
        for key, kind in (
            ("controller_add_encoder", "absolute_encoder"),
            ("controller_add_relative", "relative_encoder"),
            ("controller_add_fader", "fader"),
            ("controller_add_button", "button"),
        ):
            ttk.Button(add, text=self._t(key), command=lambda value=kind: self._add_control(value)).pack(
                side="left", padx=(0, 6)
            )
        ttk.Button(add, text=self._t("controller_delete_control"), command=self._delete_control).pack(side="left", padx=(8, 6))
        ttk.Button(add, text="↑", width=3, command=lambda: self._move_control(-1)).pack(side="left")
        ttk.Button(add, text="↓", width=3, command=lambda: self._move_control(1)).pack(side="left", padx=(3, 0))

        for column in (1, 3, 5):
            editor_frame.columnconfigure(column, weight=1)
        ttk.Label(editor_frame, text=self._t("controller_control_id")).grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(editor_frame, textvariable=self.control_id_var).grid(row=0, column=1, sticky="ew", padx=(5, 12), pady=3)
        ttk.Label(editor_frame, text=self._t("controller_control_kind")).grid(row=0, column=2, sticky="w", pady=3)
        ttk.Combobox(editor_frame, textvariable=self.kind_var, values=tuple(self.kind_labels), state="readonly").grid(row=0, column=3, sticky="ew", padx=(5, 12), pady=3)
        ttk.Label(editor_frame, text=self._t("controller_relative_mode")).grid(row=0, column=4, sticky="w", pady=3)
        ttk.Combobox(
            editor_frame,
            textvariable=self.relative_mode_var,
            values=("twos_complement", "binary_offset", "signed_bit", "increment_decrement"),
            state="readonly",
        ).grid(row=0, column=5, sticky="ew", padx=(5, 0), pady=3)

        ttk.Label(editor_frame, text=self._t("controller_input_message")).grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(editor_frame, textvariable=self.message_var, values=tuple(self.message_labels), state="readonly").grid(row=1, column=1, sticky="ew", padx=(5, 12), pady=3)
        ttk.Label(editor_frame, text=self._t("controller_channel")).grid(row=1, column=2, sticky="w", pady=3)
        ttk.Spinbox(editor_frame, from_=1, to=16, textvariable=self.channel_var, width=7).grid(row=1, column=3, sticky="w", padx=(5, 12), pady=3)
        ttk.Label(editor_frame, text=self._t("controller_number")).grid(row=1, column=4, sticky="w", pady=3)
        ttk.Spinbox(editor_frame, from_=0, to=16383, textvariable=self.number_var, width=9).grid(row=1, column=5, sticky="w", padx=(5, 0), pady=3)

        ttk.Checkbutton(editor_frame, text=self._t("controller_push_enable"), variable=self.push_enabled_var).grid(row=2, column=0, sticky="w", pady=3)
        ttk.Combobox(editor_frame, textvariable=self.push_message_var, values=tuple(self.message_labels), state="readonly").grid(row=2, column=1, sticky="ew", padx=(5, 12), pady=3)
        ttk.Label(editor_frame, text=self._t("controller_channel")).grid(row=2, column=2, sticky="w", pady=3)
        ttk.Spinbox(editor_frame, from_=1, to=16, textvariable=self.push_channel_var, width=7).grid(row=2, column=3, sticky="w", padx=(5, 12), pady=3)
        ttk.Label(editor_frame, text=self._t("controller_number")).grid(row=2, column=4, sticky="w", pady=3)
        ttk.Spinbox(editor_frame, from_=0, to=16383, textvariable=self.push_number_var, width=9).grid(row=2, column=5, sticky="w", padx=(5, 0), pady=3)

        learn = ttk.Frame(editor_frame)
        learn.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(7, 0))
        learn.columnconfigure(1, weight=1)
        ttk.Label(learn, text=self._t("controller_midi_port")).grid(row=0, column=0, sticky="w")
        self.midi_combo = ttk.Combobox(learn, textvariable=self.midi_port_var, state="normal")
        self.midi_combo.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(learn, text=self._t("refresh"), command=self._refresh_midi_ports).grid(row=0, column=2)
        ttk.Button(learn, text=self._t("controller_learn_input"), command=lambda: self._start_learn("input")).grid(row=0, column=3, padx=(8, 4))
        ttk.Button(learn, text=self._t("controller_learn_push"), command=lambda: self._start_learn("push")).grid(row=0, column=4)
        ttk.Label(learn, textvariable=self.learn_status_var, foreground="#087d9d").grid(row=1, column=0, columnspan=5, sticky="w", pady=(5, 0))
        ttk.Button(editor_frame, text=self._t("controller_apply_control"), command=self._apply_selected).grid(row=4, column=5, sticky="e", pady=(7, 0))

        footer = ttk.Frame(root)
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(footer, text=self._t("controller_close"), command=self.close).pack(side="right")
        ttk.Button(footer, text=self._t("controller_submit"), command=self._submit).pack(side="right", padx=(0, 6))
        ttk.Button(footer, text=self._t("controller_save_export"), command=self._save_and_export).pack(side="right", padx=(0, 6))
        tk.Button(
            footer,
            text=self._t("controller_save_local"),
            command=self._save,
            bg="#087d9d",
            fg="#ffffff",
            activebackground="#0aa1c9",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=5,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        ).pack(side="right", padx=(0, 6))

    def _generate_id(self) -> None:
        self.profile_id_var.set(
            suggest_controller_profile_id(self.manufacturer_var.get(), self.model_var.get())
        )

    def _refresh_midi_ports(self) -> None:
        try:
            names = tuple(input_names())
        except Exception:
            names = ()
        self.midi_combo.configure(values=names)
        if not self.midi_port_var.get() and names:
            self.midi_port_var.set(names[0])

    def _display_binding(self, binding: dict[str, Any] | None) -> str:
        if not binding:
            return "—"
        message = self.message_names.get(str(binding.get("message")), str(binding.get("message", "")))
        channel = binding.get("channel")
        number = binding.get("number")
        parts = [message]
        if channel is not None:
            parts.append(f"ch {channel}")
        if number is not None:
            parts.append(str(number))
        return " / ".join(parts)

    def _refresh_controls(self, *, select: int | None = None) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for index, item in enumerate(self.controls):
            binding = item.get("input") or {}
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    index + 1,
                    item.get("id", ""),
                    self.kind_names.get(str(item.get("kind")), str(item.get("kind", ""))),
                    self.message_names.get(str(binding.get("message")), str(binding.get("message", ""))),
                    binding.get("channel", "—"),
                    binding.get("number", "—"),
                    self._display_binding(item.get("push")),
                ),
            )
        if select is not None and 0 <= select < len(self.controls):
            self.tree.selection_set(str(select))
            self.tree.focus(str(select))
            self.tree.see(str(select))
            self._load_selected()
        else:
            self.selected_index = None

    def _load_selected(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        index = int(selection[0])
        self.selected_index = index
        item = self.controls[index]
        binding = item.get("input") or {}
        self.control_id_var.set(str(item.get("id", "")))
        self.kind_var.set(self.kind_names.get(str(item.get("kind")), str(item.get("kind", ""))))
        self.message_var.set(self.message_names.get(str(binding.get("message")), str(binding.get("message", ""))))
        self.channel_var.set(str(binding.get("channel", 1)))
        self.number_var.set(str(binding.get("number", 0)))
        self.relative_mode_var.set(str(binding.get("mode", "twos_complement")))
        push = item.get("push")
        self.push_enabled_var.set(push is not None)
        push = push or {"message": "note", "channel": 1, "number": 0}
        self.push_message_var.set(self.message_names.get(str(push.get("message")), str(push.get("message", ""))))
        self.push_channel_var.set(str(push.get("channel", 1)))
        self.push_number_var.set(str(push.get("number", 0)))

    def _binding_from_fields(self, message_label: str, channel: str, number: str) -> dict[str, Any]:
        message = self.message_labels.get(message_label, message_label)
        binding: dict[str, Any] = {"message": message, "channel": int(channel)}
        if message in {"cc", "note", "nrpn"}:
            binding["number"] = int(number)
        return binding

    def _apply_selected(self, *, quiet: bool = False) -> bool:
        if self.selected_index is None:
            return True
        try:
            item = self.controls[self.selected_index]
            item["id"] = self.control_id_var.get().strip()
            kind = self.kind_labels.get(self.kind_var.get(), self.kind_var.get())
            item["kind"] = kind
            binding = self._binding_from_fields(
                self.message_var.get(), self.channel_var.get(), self.number_var.get()
            )
            if kind == "relative_encoder":
                binding["mode"] = self.relative_mode_var.get()
            else:
                binding.pop("mode", None)
            item["input"] = binding
            if self.push_enabled_var.get():
                item["push"] = self._binding_from_fields(
                    self.push_message_var.get(),
                    self.push_channel_var.get(),
                    self.push_number_var.get(),
                )
            else:
                item.pop("push", None)
            self._refresh_controls(select=self.selected_index)
            return True
        except (TypeError, ValueError) as exc:
            if not quiet:
                messagebox.showerror(self._t("controller_invalid_title"), str(exc), parent=self.window)
            return False

    def _next_number(self, message: str) -> int:
        used = {
            int(binding["number"])
            for item in self.controls
            for binding in (item.get("input"), item.get("push"))
            if binding and binding.get("message") == message and "number" in binding
        }
        return next((value for value in range(128) if value not in used), 0)

    def _add_control(self, kind: str) -> None:
        self._apply_selected(quiet=True)
        index = len(self.controls) + 1
        prefix = {
            "absolute_encoder": "encoder",
            "relative_encoder": "encoder",
            "fader": "fader",
            "button": "button",
            "pad": "pad",
        }[kind]
        message = "note" if kind in {"button", "pad"} else "cc"
        binding: dict[str, Any] = {
            "message": message,
            "channel": 1,
            "number": self._next_number(message),
        }
        if kind == "relative_encoder":
            binding["mode"] = "twos_complement"
        self.controls.append({"id": f"{prefix}_{index:02d}", "kind": kind, "input": binding})
        if int(self.bank_size_var.get() or 1) == index - 1:
            self.bank_size_var.set(str(index))
        self._refresh_controls(select=index - 1)

    def _delete_control(self) -> None:
        if self.selected_index is None:
            return
        if len(self.controls) <= 1:
            messagebox.showwarning(
                self._t("controller_invalid_title"),
                self._t("controller_need_one_control"),
                parent=self.window,
            )
            return
        index = self.selected_index
        del self.controls[index]
        try:
            bank_size = int(self.bank_size_var.get())
        except ValueError:
            bank_size = len(self.controls)
        self.bank_size_var.set(str(min(bank_size, len(self.controls))))
        self._refresh_controls(select=min(index, len(self.controls) - 1))

    def _move_control(self, delta: int) -> None:
        if self.selected_index is None:
            return
        destination = self.selected_index + delta
        if not 0 <= destination < len(self.controls):
            return
        self._apply_selected(quiet=True)
        self.controls[self.selected_index], self.controls[destination] = (
            self.controls[destination],
            self.controls[self.selected_index],
        )
        self._refresh_controls(select=destination)

    def _start_learn(self, target: str) -> None:
        if self.selected_index is None:
            messagebox.showwarning(
                self._t("controller_invalid_title"),
                self._t("controller_select_control"),
                parent=self.window,
            )
            return
        self._apply_selected(quiet=True)
        self._stop_learn()
        try:
            self.listener = MidiInputListener(self.learn_queue.put)
            opened = self.listener.open(self.midi_port_var.get())
        except Exception as exc:
            self.listener = None
            messagebox.showerror(self._t("controller_midi_error"), str(exc), parent=self.window)
            return
        self.learn_target = target
        self.midi_port_var.set(opened)
        self.learn_status_var.set(
            self._t("controller_learn_wait", target=self._t(f"controller_learn_target_{target}"))
        )
        self.learn_after_id = self.window.after(50, self._poll_learn)

    def _poll_learn(self) -> None:
        self.learn_after_id = None
        while True:
            try:
                message = self.learn_queue.get_nowait()
            except queue.Empty:
                break
            binding = midi_binding_from_message(message)
            if binding is None:
                continue
            if self.selected_index is None or self.learn_target is None:
                self._stop_learn()
                return
            item = self.controls[self.selected_index]
            if self.learn_target == "input" and item.get("kind") == "relative_encoder":
                binding["mode"] = self.relative_mode_var.get()
            item[self.learn_target] = binding
            if self.learn_target == "push":
                self.push_enabled_var.set(True)
            if not self.input_pattern_var.get().strip():
                self.input_pattern_var.set(self.midi_port_var.get())
            learned = self._display_binding(binding)
            self._stop_learn()
            self.learn_status_var.set(self._t("controller_learn_received", binding=learned))
            self._refresh_controls(select=self.selected_index)
            return
        self.learn_after_id = self.window.after(50, self._poll_learn)

    def _stop_learn(self) -> None:
        if self.learn_after_id is not None:
            try:
                self.window.after_cancel(self.learn_after_id)
            except tk.TclError:
                pass
            self.learn_after_id = None
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        self.learn_target = None

    def _draft(self) -> tuple[Any, dict[str, Any]]:
        if not self._apply_selected():
            raise ProfileError(self._t("controller_fix_selected"))
        profile_id = self.profile_id_var.get().strip()
        if not profile_id:
            profile_id = suggest_controller_profile_id(
                self.manufacturer_var.get(), self.model_var.get()
            )
            self.profile_id_var.set(profile_id)
        self.payload.update(
            {
                "schema_version": 1,
                "profile_version": str(self.payload.get("profile_version", "1.0.0")),
                "id": profile_id,
                "manufacturer": self.manufacturer_var.get().strip(),
                "model": self.model_var.get().strip(),
                "bank_size": int(self.bank_size_var.get()),
                "bank_count": int(self.bank_count_var.get()),
                "page_count": int(self.page_count_var.get()),
                "status": "community",
                "midi_identity": {
                    "input_name_patterns": _split_patterns(self.input_pattern_var.get()),
                    "output_name_patterns": _split_patterns(self.output_pattern_var.get()),
                },
                "controls": self.controls,
            }
        )
        firmware = self.firmware_var.get().strip()
        if firmware:
            self.payload["firmware"] = firmware
        else:
            self.payload.pop("firmware", None)
        if int(self.bank_count_var.get()) == 1:
            self.payload.pop("last_bank_size", None)
        return validate_controller_draft(self.payload)

    def _save_profile(self):
        profile, payload = self._draft()
        destination = default_user_profile_dir() / f"{profile.id}.json"
        replace = destination.exists()
        if replace and not messagebox.askyesno(
            self._t("controller_replace_title"),
            self._t("controller_replace_body", name=destination.name),
            parent=self.window,
        ):
            return None
        result = save_user_controller_profile(payload, replace=replace)
        self.payload = controller_profile_payload(result.profile)
        self.on_saved(result.profile.id)
        return result

    def _save(self) -> None:
        try:
            result = self._save_profile()
        except Exception as exc:
            messagebox.showerror(self._t("controller_invalid_title"), str(exc), parent=self.window)
            return
        if result is None:
            return
        backup = f"\n{self._t('controller_backup', path=result.backup_path)}" if result.backup_path else ""
        messagebox.showinfo(
            self._t("controller_saved_title"),
            self._t("controller_saved_body", name=result.profile.display_name, path=result.path) + backup,
            parent=self.window,
        )

    def _save_and_export(self) -> None:
        try:
            result = self._save_profile()
            if result is None:
                return
            initial = f"Controller-Studio-{result.profile.manufacturer}-{result.profile.model}".replace("/", "-")
            destination = filedialog.asksaveasfilename(
                parent=self.window,
                title=self._t("export_title"),
                defaultextension=".ctrl2",
                filetypes=((self._t("controller_file_type"), "*.ctrl2"),),
                initialfile=f"{initial}.ctrl2",
            )
            if not destination:
                return
            path = Path(destination)
            replace = path.exists() and messagebox.askyesno(
                self._t("replace_file"),
                self._t("replace_file_body", name=path.name),
                parent=self.window,
            )
            if path.exists() and not replace:
                return
            exported = export_liveprofessor_controller(result.profile, path, replace=replace)
        except Exception as exc:
            messagebox.showerror(self._t("export_error"), str(exc), parent=self.window)
            return
        messagebox.showinfo(
            self._t("controller_created"),
            self._t(
                "export_details",
                path=exported.path,
                rotaries=exported.rotary_count,
                buttons=exported.button_count,
                sha256=exported.sha256,
            ),
            parent=self.window,
        )

    def _submit(self) -> None:
        try:
            result = self._save_profile()
        except Exception as exc:
            messagebox.showerror(self._t("controller_invalid_title"), str(exc), parent=self.window)
            return
        if result is not None:
            self.on_contribute(result.profile.id)

    def close(self) -> None:
        self._stop_learn()
        try:
            self.window.destroy()
        except tk.TclError:
            pass
