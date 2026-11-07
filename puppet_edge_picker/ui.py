"""Tkinter interface for the phase-3 edge algorithm picker."""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, scrolledtext, ttk
from typing import cast

from .algorithms import CompiledAlgorithm, compiled_catalog
from .cube import EdgeState, flipped_edges, moved_edges
from .instructions import execution_steps, grip_description
from .settings import EDGES, edge_colors, edge_label
from .solver import (
    Request,
    RequestError,
    SearchLimitReached,
    find_algorithms,
    no_match_message,
)


@dataclass
class EdgeChoice:
    variable: tk.StringVar
    combobox: ttk.Combobox
    swatch: tk.Canvas
    allow_none: bool


class EdgePickerApp(ttk.Frame):
    """Self-contained application frame."""

    EFFECT_MODES = {
        "Swap one/two pairs": "swaps",
        "Cycle three edges": "cycle",
        "Flip two edges": "flips",
    }

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=16)
        self.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self._mode = "colors"
        self._effect_mode = "swaps"
        self._last_request: Request | None = None
        self._last_results: tuple[CompiledAlgorithm, ...] = ()
        self.choices: list[EdgeChoice] = []
        self.effect_choices: dict[str, list[EdgeChoice]] = {}
        self.effect_frames: dict[str, ttk.Frame] = {}
        self.preserve_vars = {edge: tk.BooleanVar(value=False) for edge in EDGES}
        self.preserve_labels = {edge: tk.StringVar() for edge in EDGES}
        self.preserve_buttons: dict[str, ttk.Checkbutton] = {}
        self.preserve_swatches: dict[str, tk.Canvas] = {}

        self._build_header()
        self._build_request_panel()
        self._build_actions()
        self._build_results()
        self._refresh_labels(
            ("UF", "UR", None, None, "DL", "FL", "BL", "DL", "FR")
        )
        self._show_effect_mode()
        self._refresh_preserve_states()

        # Compile once at startup so catalog errors surface before a result can
        # be displayed as trustworthy.
        compiled_catalog()

    @property
    def label_mode(self) -> str:
        return self._mode

    def _build_header(self) -> None:
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="Puppet Cube Phase-3 Algorithm Picker",
            font=("TkDefaultFont", 17, "bold"),
        ).grid(row=0, column=0, sticky="w")

        selector = ttk.Frame(header)
        selector.grid(row=0, column=1, sticky="e")
        ttk.Label(selector, text="Edge labels:").grid(row=0, column=0, padx=(0, 6))
        self.mode_var = tk.StringVar(value="Colors")
        mode_box = ttk.Combobox(
            selector,
            textvariable=self.mode_var,
            values=("Colors", "Face letters"),
            state="readonly",
            width=13,
        )
        mode_box.grid(row=0, column=1)
        mode_box.bind("<<ComboboxSelected>>", self._on_mode_changed)

    def _build_request_panel(self) -> None:
        panel = ttk.LabelFrame(self, text="Requested edge effect", padding=12)
        panel.grid(row=1, column=0, sticky="ew")

        selector = ttk.Frame(panel)
        selector.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
        ttk.Label(selector, text="Effect type:").grid(row=0, column=0, padx=(0, 8))
        self.effect_mode_var = tk.StringVar(value="Swap one/two pairs")
        effect_box = ttk.Combobox(
            selector,
            textvariable=self.effect_mode_var,
            values=tuple(self.EFFECT_MODES),
            state="readonly",
            width=22,
        )
        effect_box.grid(row=0, column=1)
        effect_box.bind("<<ComboboxSelected>>", self._on_effect_mode_changed)

        self._build_swap_effect(panel)
        self._build_cycle_effect(panel)
        self._build_flip_effect(panel)

        ttk.Separator(panel).grid(row=2, column=0, columnspan=6, sticky="ew", pady=10)
        ttk.Label(panel, text="Edges to preserve:").grid(
            row=3, column=0, columnspan=6, sticky="w", pady=(0, 5)
        )

        preserve_grid = ttk.Frame(panel)
        preserve_grid.grid(row=4, column=0, columnspan=6, sticky="ew")
        preserve_grid.columnconfigure(0, weight=1)
        preserve_grid.columnconfigure(1, weight=1)
        for index, edge in enumerate(EDGES):
            row = index % 6
            column = index // 6
            cell = ttk.Frame(preserve_grid)
            cell.grid(row=row, column=column, sticky="w", padx=(0, 24), pady=2)
            canvas = tk.Canvas(cell, width=32, height=14, highlightthickness=0)
            canvas.grid(row=0, column=0, padx=(0, 5))
            button = ttk.Checkbutton(
                cell,
                textvariable=self.preserve_labels[edge],
                variable=self.preserve_vars[edge],
            )
            button.grid(row=0, column=1, sticky="w")
            self.preserve_buttons[edge] = button
            self.preserve_swatches[edge] = canvas

        self.orientation_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            panel,
            text="Preserve the orientation of protected edges",
            variable=self.orientation_var,
        ).grid(row=5, column=0, columnspan=6, sticky="w", pady=(10, 0))

    def _effect_frame(self, panel: ttk.Frame, mode: str) -> ttk.Frame:
        frame = ttk.Frame(panel)
        frame.grid(row=1, column=0, columnspan=6, sticky="ew")
        self.effect_frames[mode] = frame
        return frame

    def _build_swap_effect(self, panel: ttk.Frame) -> None:
        frame = self._effect_frame(panel, "swaps")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(4, weight=1)
        choices: list[EdgeChoice] = []
        for row, (label, allow_none) in enumerate(
            (("Swap pair 1:", False), ("Swap pair 2 (optional):", True))
        ):
            ttk.Label(frame, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 8), pady=4
            )
            first = self._make_edge_choice(frame, row, 1, allow_none)
            ttk.Label(frame, text="\N{LEFT RIGHT ARROW}").grid(
                row=row, column=3, padx=8
            )
            second = self._make_edge_choice(frame, row, 4, allow_none)
            choices.extend((first, second))
        self.effect_choices["swaps"] = choices
        self.choices.extend(choices)

    def _build_cycle_effect(self, panel: ttk.Frame) -> None:
        frame = self._effect_frame(panel, "cycle")
        for column in (1, 4, 7):
            frame.columnconfigure(column, weight=1)
        ttk.Label(frame, text="Cycle direction:").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        choices: list[EdgeChoice] = []
        for index, column in enumerate((1, 4, 7)):
            choice = self._make_edge_choice(frame, 0, column, False)
            choices.append(choice)
            if index < 2:
                ttk.Label(frame, text="\N{RIGHTWARDS ARROW}").grid(
                    row=0, column=column + 2, padx=8
                )
        ttk.Label(frame, text="\N{RIGHTWARDS ARROW} back to the first edge").grid(
            row=1, column=1, columnspan=8, sticky="w", pady=(2, 0)
        )
        self.effect_choices["cycle"] = choices
        self.choices.extend(choices)

    def _build_flip_effect(self, panel: ttk.Frame) -> None:
        frame = self._effect_frame(panel, "flips")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(4, weight=1)
        ttk.Label(frame, text="Flip in place:").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        first = self._make_edge_choice(frame, 0, 1, False)
        ttk.Label(frame, text="and").grid(row=0, column=3, padx=8)
        second = self._make_edge_choice(frame, 0, 4, False)
        ttk.Label(
            frame,
            text="Every other edge will be required to stay in place and unflipped.",
        ).grid(row=1, column=1, columnspan=5, sticky="w", pady=(2, 0))
        choices = [first, second]
        self.effect_choices["flips"] = choices
        self.choices.extend(choices)

    def _make_edge_choice(
        self, parent: ttk.Frame, row: int, column: int, allow_none: bool
    ) -> EdgeChoice:
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=column, columnspan=2, sticky="ew", pady=4)
        holder.columnconfigure(0, weight=1)
        variable = tk.StringVar()
        combobox = ttk.Combobox(holder, textvariable=variable, state="readonly", width=24)
        combobox.grid(row=0, column=0, sticky="ew")
        swatch = tk.Canvas(holder, width=34, height=16, highlightthickness=0)
        swatch.grid(row=0, column=1, padx=(6, 0))
        choice = EdgeChoice(variable, combobox, swatch, allow_none)
        combobox.bind("<<ComboboxSelected>>", self._on_edge_changed)
        return choice

    def _build_actions(self) -> None:
        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="ew", pady=12)
        ttk.Button(actions, text="Find algorithm", command=self.find).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(actions, text="Reset", command=self.reset).grid(row=0, column=1)
        self.show_alternatives_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            actions,
            text="Show alternatives",
            variable=self.show_alternatives_var,
            command=self._render_last_results,
        ).grid(row=0, column=2, padx=(18, 0))

    def _build_results(self) -> None:
        panel = ttk.LabelFrame(self, text="Result", padding=8)
        panel.grid(row=3, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(0, weight=1)
        self.result_text = scrolledtext.ScrolledText(
            panel,
            height=18,
            wrap="word",
            state="disabled",
            font=("TkFixedFont", 11),
            padx=8,
            pady=8,
        )
        self.result_text.grid(row=0, column=0, sticky="nsew")
        self._set_result(
            "Choose a swap, directed cycle, or edge flip effect; optionally "
            "protect other edges, then select Find algorithm."
        )

    def _labels(self, mode: str | None = None) -> dict[str, str]:
        selected_mode = mode or self.label_mode
        return {edge: edge_label(edge, selected_mode) for edge in EDGES}

    def _choice_edge(self, choice: EdgeChoice, mode: str | None = None) -> str | None:
        value = choice.variable.get()
        if value == "None" or not value:
            return None
        reverse = {label: edge for edge, label in self._labels(mode).items()}
        return reverse.get(value)

    def _set_choice_edge(self, choice: EdgeChoice, edge: str | None) -> None:
        choice.variable.set("None" if edge is None else edge_label(edge, self.label_mode))
        self._draw_swatch(choice.swatch, edge)

    def _refresh_labels(self, selected: tuple[str | None, ...] | None = None) -> None:
        labels = tuple(self._labels().values())
        if selected is None:
            selected = tuple(self._choice_edge(choice) for choice in self.choices)
        for choice, edge in zip(self.choices, selected):
            choice.combobox["values"] = (("None",) + labels) if choice.allow_none else labels
            self._set_choice_edge(choice, edge)
        for edge in EDGES:
            self.preserve_labels[edge].set(edge_label(edge, self.label_mode))
            self._draw_swatch(self.preserve_swatches[edge], edge)

    def _draw_swatch(self, canvas: tk.Canvas, edge: str | None) -> None:
        canvas.delete("all")
        if edge is None or self.label_mode != "colors":
            return
        first, second = edge_colors(edge)
        canvas.create_rectangle(1, 1, 16, 14, fill=first, outline="#777777")
        canvas.create_rectangle(17, 1, 32, 14, fill=second, outline="#777777")

    def _on_mode_changed(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        previous_mode = self._mode
        selected = tuple(self._choice_edge(choice, previous_mode) for choice in self.choices)
        self._mode = "faces" if self.mode_var.get() == "Face letters" else "colors"
        self._refresh_labels(selected)
        self._refresh_preserve_states()
        self._render_last_results()

    def _on_effect_mode_changed(
        self, _event: tk.Event[tk.Misc] | None = None
    ) -> None:
        self._effect_mode = self.EFFECT_MODES[self.effect_mode_var.get()]
        self._show_effect_mode()
        self._refresh_preserve_states()

    def _show_effect_mode(self) -> None:
        for mode, frame in self.effect_frames.items():
            if mode == self._effect_mode:
                frame.grid()
            else:
                frame.grid_remove()

    def _on_edge_changed(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        for choice in self.choices:
            self._draw_swatch(choice.swatch, self._choice_edge(choice))
        self._refresh_preserve_states()

    def _refresh_preserve_states(self) -> None:
        swapped = {
            edge
            for choice in self.effect_choices[self._effect_mode]
            if (edge := self._choice_edge(choice)) is not None
        }
        for edge, button in self.preserve_buttons.items():
            if edge in swapped:
                self.preserve_vars[edge].set(False)
                button.state(["disabled"])
            else:
                button.state(["!disabled"])

    def _request(self) -> Request:
        selected = tuple(
            self._choice_edge(choice)
            for choice in self.effect_choices[self._effect_mode]
        )
        swaps: tuple[tuple[str, str], ...] = ()
        cycles: tuple[tuple[str, str, str], ...] = ()
        flips: frozenset[str] = frozenset()

        if self._effect_mode == "swaps":
            first_pair = selected[:2]
            second_pair = selected[2:]
            if any(edge is None for edge in first_pair):
                raise RequestError("Swap pair 1 is incomplete.")
            swap_list: list[tuple[str, str]] = [
                (cast(str, first_pair[0]), cast(str, first_pair[1]))
            ]
            if (second_pair[0] is None) != (second_pair[1] is None):
                raise RequestError(
                    "Swap pair 2 is incomplete; choose both edges or neither."
                )
            if second_pair[0] is not None:
                swap_list.append((second_pair[0], cast(str, second_pair[1])))
            swaps = tuple(swap_list)
        elif self._effect_mode == "cycle":
            if any(edge is None for edge in selected):
                raise RequestError("The 3-edge cycle is incomplete.")
            cycles = (
                (
                    cast(str, selected[0]),
                    cast(str, selected[1]),
                    cast(str, selected[2]),
                ),
            )
        else:
            if any(edge is None for edge in selected):
                raise RequestError("Choose both edges to flip.")
            flips = frozenset(cast(tuple[str, str], selected))

        preserved = frozenset(
            edge for edge, variable in self.preserve_vars.items() if variable.get()
        )
        return Request(
            swaps=swaps,
            preserved=preserved,
            preserve_orientation=self.orientation_var.get(),
            cycles=cycles,
            flips=flips,
        )

    def find(self) -> None:
        try:
            request = self._request()
            results = find_algorithms(request)
        except RequestError as exc:
            self._last_request = None
            self._last_results = ()
            self._set_result(f"Invalid or unreachable request\n\n{exc}")
            messagebox.showwarning("Cannot search", str(exc), parent=self.winfo_toplevel())
            return
        except SearchLimitReached as exc:
            self._last_request = request
            self._last_results = ()
            self._set_result(
                "Search limit reached\n\n"
                f"{exc}\n\nTry unprotecting another edge or selecting a second swap pair."
            )
            messagebox.showinfo("Search limit reached", str(exc), parent=self.winfo_toplevel())
            return
        self._last_request = request
        self._last_results = results
        self._render_last_results()

    def _render_last_results(self) -> None:
        if self._last_request is None:
            return
        request = self._last_request
        results = self._last_results
        lines = ["Requested edge effect:"]
        for first, second in request.swaps:
            lines.append(
                f"  {edge_label(first, self.label_mode)} \N{LEFT RIGHT ARROW} "
                f"{edge_label(second, self.label_mode)}"
            )
        for first, second, third in request.cycles:
            labels = tuple(
                edge_label(edge, self.label_mode) for edge in (first, second, third)
            )
            lines.append(
                f"  {labels[0]} \N{RIGHTWARDS ARROW} {labels[1]} "
                f"\N{RIGHTWARDS ARROW} {labels[2]} \N{RIGHTWARDS ARROW} {labels[0]}"
            )
        if request.flips:
            ordered_flips = sorted(request.flips, key=EDGES.index)
            lines.append(
                "  Flip in place: "
                + " and ".join(
                    edge_label(edge, self.label_mode) for edge in ordered_flips
                )
            )
        protected = sorted(request.preserved, key=EDGES.index)
        protected_description = (
            "All other edges (required by flip mode)"
            if request.flips
            else (
                ", ".join(edge_label(edge, self.label_mode) for edge in protected)
                if protected
                else "None"
            )
        )
        lines.extend(
            (
                "",
                "Protected edge slots:",
                "  " + protected_description,
                "",
            )
        )
        if not results:
            lines.append(no_match_message(request))
            self._set_result("\n".join(lines))
            return

        shown = results if self.show_alternatives_var.get() else results[:1]
        for index, result in enumerate(shown):
            heading = "Best match" if index == 0 else f"Alternative {index}"
            effect = result.effect
            steps = execution_steps(result.tokens)
            starting_position = grip_description(result.definition.starting_rotation)
            grip_names = [starting_position] + [step.grip_name for step in steps]
            grip_changes = sum(
                first != second for first, second in zip(grip_names, grip_names[1:])
            )
            display_name = result.definition.name
            macro_label = (
                "Macro path"
                if result.definition.source_section == "Verified macro search"
                else "Guide macros"
            )
            lines.extend(
                (
                    f"{heading}:",
                    f"  {display_name}",
                    f"  {macro_label}: {result.definition.macro_notation or 'expanded case'}",
                    "",
                    "Starting position:",
                    f"  {starting_position}",
                    "",
                )
            )
            if len(steps) == 1 and steps[0].grip_name == starting_position:
                lines.extend(
                    (
                        "Algorithm:",
                        f"  {' '.join(steps[0].moves)}",
                    )
                )
            else:
                lines.append("Execution steps:")
                for step_number, step in enumerate(steps, 1):
                    lines.extend(
                        (
                            f"  Step {step_number} — hold {step.grip_name}:",
                            f"    {' '.join(step.moves)}",
                        )
                    )
            lines.extend(
                (
                    "",
                    "Actual edge permutation:",
                    "  " + self._permutation_summary(effect),
                    "Moved edge slots:",
                    "  " + self._edge_list(moved_edges(effect)),
                    "Flipped edge slots:",
                    "  " + self._edge_list(flipped_edges(effect)),
                    f"Face-turn count: {result.face_turn_count}",
                    f"Grip changes: {grip_changes}",
                )
            )
            if index != len(shown) - 1:
                lines.extend(("", "" + "\N{BOX DRAWINGS LIGHT HORIZONTAL}" * 60, ""))
        self._set_result("\n".join(lines))

    def _edge_list(self, edges: tuple[str, ...]) -> str:
        if not edges:
            return "None"
        return ", ".join(edge_label(edge, self.label_mode) for edge in edges)

    def _permutation_summary(self, effect: EdgeState) -> str:
        source_to_destination = {
            source: destination
            for destination, source in enumerate(effect.permutation)
        }
        seen: set[int] = set()
        cycles: list[str] = []
        for start in range(len(EDGES)):
            if start in seen or source_to_destination[start] == start:
                continue
            cycle: list[int] = []
            current = start
            while current not in seen:
                seen.add(current)
                cycle.append(current)
                current = source_to_destination[current]
            labels = [edge_label(EDGES[index], self.label_mode) for index in cycle]
            if len(labels) == 2:
                cycles.append(f"{labels[0]} ↔ {labels[1]}")
            else:
                cycles.append(" → ".join(labels + labels[:1]))
        return "; ".join(cycles) if cycles else "None"

    def _set_result(self, text: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled")

    def reset(self) -> None:
        self.mode_var.set("Colors")
        self._mode = "colors"
        self.effect_mode_var.set("Swap one/two pairs")
        self._effect_mode = "swaps"
        for variable in self.preserve_vars.values():
            variable.set(False)
        self.orientation_var.set(True)
        self.show_alternatives_var.set(True)
        self._last_request = None
        self._last_results = ()
        self._refresh_labels(
            ("UF", "UR", None, None, "DL", "FL", "BL", "DL", "FR")
        )
        self._show_effect_mode()
        self._refresh_preserve_states()
        self._set_result(
            "Choose a swap, directed cycle, or edge flip effect; optionally "
            "protect other edges, "
            "then select Find algorithm."
        )
