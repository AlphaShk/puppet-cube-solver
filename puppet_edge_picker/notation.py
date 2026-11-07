"""Parser and helpers for standard face-turn notation."""

from __future__ import annotations

import re
from collections.abc import Iterable

FACES = frozenset("UDRLFB")
ROTATIONS = frozenset("XYZ")
MOVE_RE = re.compile(r"^([UDRLFB])([Ww]?)([2']?)$|^([XYZ])([2']?)$")


class NotationError(ValueError):
    """Raised when an algorithm contains unsupported notation."""


def parse_algorithm(text: str | Iterable[str]) -> tuple[str, ...]:
    """Normalize an algorithm to validated move tokens.

    Parentheses are formatting only. Both ordinary ``R2`` and the guide's
    LaTeX-style ``R^{2}`` spelling are accepted.
    """

    if not isinstance(text, str):
        tokens = tuple(text)
    else:
        cleaned = re.sub(r"([UDRLFBXYZ][Ww]?)\^\{2\}", r"\g<1>2", text)
        cleaned = cleaned.replace("(", " ").replace(")", " ")
        tokens = tuple(
            token[0].upper() + token[1:].replace("W", "w")
            for token in cleaned.split()
        )

    for token in tokens:
        if not MOVE_RE.fullmatch(token):
            raise NotationError(f"Unsupported move token: {token!r}")
    return tokens


def invert_move(move: str) -> str:
    """Return the inverse of one validated move."""

    parse_algorithm((move,))
    if move.endswith("2"):
        return move
    if move.endswith("'"):
        return move[:-1]
    return f"{move}'"


def invert_algorithm(moves: str | Iterable[str]) -> tuple[str, ...]:
    """Reverse and invert an algorithm."""

    tokens = parse_algorithm(moves)
    return tuple(invert_move(move) for move in reversed(tokens))


def move_amount(move: str) -> int:
    """Return the number of clockwise quarter turns represented by a token."""

    parse_algorithm((move,))
    if move.endswith("2"):
        return 2
    if move.endswith("'"):
        return 3
    return 1


def face_turn_count(moves: str | Iterable[str]) -> int:
    """Count face-turn tokens using face-turn metric (a double is one turn)."""

    return sum(move[0] in FACES for move in parse_algorithm(moves))


def rotation_count(moves: str | Iterable[str]) -> int:
    """Count whole-cube-rotation tokens."""

    return sum(move[0] in ROTATIONS for move in parse_algorithm(moves))


def format_algorithm(moves: str | Iterable[str]) -> str:
    """Return canonical space-separated notation."""

    return " ".join(parse_algorithm(moves))
