"""Shared cube conventions and display settings."""

from __future__ import annotations

EDGES = (
    "UF",
    "UR",
    "UB",
    "UL",
    "DF",
    "DR",
    "DB",
    "DL",
    "FR",
    "FL",
    "BR",
    "BL",
)

EDGE_INDEX = {edge: index for index, edge in enumerate(EDGES)}

# Stable solved-color reference used for edge-slot names.  Published guide
# cases are rotated into their diagram grips in algorithms.py.
FACE_COLORS = {
    "U": "W",
    "D": "Y",
    "F": "G",
    "B": "B",
    "R": "R",
    "L": "O",
}

# Keep familiar color-pair names (White–Blue, Blue–Orange, and so on)
# independent of the internal face-letter order.
COLOR_LABEL_ORDER = {color: index for index, color in enumerate("W Y G B R O".split())}

COLOR_NAMES = {
    "W": "White",
    "Y": "Yellow",
    "G": "Green",
    "B": "Blue",
    "R": "Red",
    "O": "Orange",
}

TK_COLORS = {
    "W": "#f5f5f5",
    "Y": "#ffd500",
    "G": "#009b48",
    "B": "#0046ad",
    "R": "#d50000",
    "O": "#ff7a00",
}

MOVE_LEGEND = (
    "U = White    D = Yellow\n"
    "F = Green    B = Blue\n"
    "R = Red      L = Orange"
)


def edge_color_codes(edge: str) -> tuple[str, str]:
    """Return an edge's colors in stable user-facing label order."""

    if edge not in EDGE_INDEX:
        raise ValueError(f"Unknown edge slot: {edge}")
    first, second = sorted(
        (FACE_COLORS[edge[0]], FACE_COLORS[edge[1]]), key=COLOR_LABEL_ORDER.__getitem__
    )
    return first, second


def edge_label(edge: str, mode: str = "colors") -> str:
    """Return a human-readable edge-slot label."""

    if edge not in EDGE_INDEX:
        raise ValueError(f"Unknown edge slot: {edge}")
    if mode == "faces":
        return edge
    if mode != "colors":
        raise ValueError(f"Unknown label mode: {mode}")
    first_code, second_code = edge_color_codes(edge)
    first = COLOR_NAMES[first_code]
    second = COLOR_NAMES[second_code]
    return f"{first}\N{EN DASH}{second}"


def edge_colors(edge: str) -> tuple[str, str]:
    """Return the two Tk colors used for an edge label."""

    first, second = edge_color_codes(edge)
    return TK_COLORS[first], TK_COLORS[second]
