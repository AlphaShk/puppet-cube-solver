"""Plain-text result report shared by the Tk window and the command line."""

from __future__ import annotations

from .algorithms import CompiledAlgorithm
from .cube import EdgeState, flipped_edges, moved_edges
from .instructions import execution_steps, grip_description
from .settings import EDGES, edge_label
from .solver import Request, no_match_message

SEPARATOR = "\N{BOX DRAWINGS LIGHT HORIZONTAL}" * 60


def edge_list(edges: tuple[str, ...], label_mode: str = "colors") -> str:
    """Return a comma-separated list of edge labels, or ``None``."""

    if not edges:
        return "None"
    return ", ".join(edge_label(edge, label_mode) for edge in edges)


def permutation_summary(effect: EdgeState, label_mode: str = "colors") -> str:
    """Describe an effect's permutation as cycles from source to destination."""

    source_to_destination = {
        source: destination for destination, source in enumerate(effect.permutation)
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
        labels = [edge_label(EDGES[index], label_mode) for index in cycle]
        if len(labels) == 2:
            cycles.append(f"{labels[0]} \N{LEFT RIGHT ARROW} {labels[1]}")
        else:
            cycles.append(" \N{RIGHTWARDS ARROW} ".join(labels + labels[:1]))
    return "; ".join(cycles) if cycles else "None"


def request_lines(request: Request, label_mode: str = "colors") -> list[str]:
    """Describe the requested effect and the protected slots."""

    lines = ["Requested edge effect:"]
    for first, second in request.swaps:
        lines.append(
            f"  {edge_label(first, label_mode)} \N{LEFT RIGHT ARROW} "
            f"{edge_label(second, label_mode)}"
        )
    for first, second, third in request.cycles:
        labels = tuple(edge_label(edge, label_mode) for edge in (first, second, third))
        lines.append(
            f"  {labels[0]} \N{RIGHTWARDS ARROW} {labels[1]} "
            f"\N{RIGHTWARDS ARROW} {labels[2]} \N{RIGHTWARDS ARROW} {labels[0]}"
        )
    if request.flips:
        ordered_flips = sorted(request.flips, key=EDGES.index)
        lines.append(
            "  Flip in place: "
            + " and ".join(edge_label(edge, label_mode) for edge in ordered_flips)
        )
    protected = sorted(request.preserved, key=EDGES.index)
    if request.flips:
        protected_description = "All other edges (required by flip mode)"
    elif protected:
        protected_description = ", ".join(
            edge_label(edge, label_mode) for edge in protected
        )
    else:
        protected_description = "None"
    lines.extend(("", "Protected edge slots:", "  " + protected_description, ""))
    return lines


def result_lines(
    result: CompiledAlgorithm, heading: str, label_mode: str = "colors"
) -> list[str]:
    """Describe one algorithm: grips, moves and the verified effect."""

    effect = result.effect
    steps = execution_steps(result.tokens)
    starting_position = grip_description(result.definition.starting_rotation)
    grip_names = [starting_position] + [step.grip_name for step in steps]
    grip_changes = sum(first != second for first, second in zip(grip_names, grip_names[1:]))
    macro_label = (
        "Macro path"
        if result.definition.source_section == "Verified macro search"
        else "Guide macros"
    )
    lines = [
        f"{heading}:",
        f"  {result.definition.name}",
        f"  {macro_label}: {result.definition.macro_notation or 'expanded case'}",
        "",
        "Starting position:",
        f"  {starting_position}",
        "",
    ]
    if len(steps) == 1 and steps[0].grip_name == starting_position:
        lines.extend(("Algorithm:", f"  {' '.join(steps[0].moves)}"))
    else:
        lines.append("Execution steps:")
        for step_number, step in enumerate(steps, 1):
            lines.extend(
                (
                    f"  Step {step_number} \N{EM DASH} hold {step.grip_name}:",
                    f"    {' '.join(step.moves)}",
                )
            )
    lines.extend(
        (
            "",
            "Actual edge permutation:",
            "  " + permutation_summary(effect, label_mode),
            "Moved edge slots:",
            "  " + edge_list(moved_edges(effect), label_mode),
            "Flipped edge slots:",
            "  " + edge_list(flipped_edges(effect), label_mode),
            f"Face-turn count: {result.face_turn_count}",
            f"Grip changes: {grip_changes}",
        )
    )
    return lines


def format_report(
    request: Request,
    results: tuple[CompiledAlgorithm, ...],
    label_mode: str = "colors",
    show_alternatives: bool = True,
) -> str:
    """Return the full report shown in the result panel."""

    lines = request_lines(request, label_mode)
    if not results:
        lines.append(no_match_message(request))
        return "\n".join(lines)

    shown = results if show_alternatives else results[:1]
    for index, result in enumerate(shown):
        heading = "Best match" if index == 0 else f"Alternative {index}"
        lines.extend(result_lines(result, heading, label_mode))
        if index != len(shown) - 1:
            lines.extend(("", SEPARATOR, ""))
    return "\n".join(lines)
