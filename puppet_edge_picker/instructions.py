"""Translate whole-cube rotation notation into named execution grips."""

from __future__ import annotations

from dataclasses import dataclass

from .cube import rotation_face_mapping
from .notation import parse_algorithm
from .settings import COLOR_NAMES, FACE_COLORS


@dataclass(frozen=True)
class ExecutionStep:
    """A run of face turns performed without changing the cube grip."""

    moves: tuple[str, ...]
    front_face: str
    up_face: str
    right_face: str

    @property
    def grip_name(self) -> str:
        return (
            f"{_face_color_name(self.front_face)} front, "
            f"{_face_color_name(self.up_face)} up, "
            f"{_face_color_name(self.right_face)} right"
        )


def _face_color_name(face: str) -> str:
    return COLOR_NAMES[FACE_COLORS[face]]


def grip_faces(rotations: tuple[str, ...] = ()) -> tuple[str, str, str]:
    """Return the original faces currently at local front, up, and right."""

    old_to_new = rotation_face_mapping(rotations)
    new_to_old = {new: old for old, new in old_to_new.items()}
    return new_to_old["F"], new_to_old["U"], new_to_old["R"]


def grip_description(rotations: tuple[str, ...] = ()) -> str:
    """Return a colour-name description for a physical cube grip."""

    front, up, right = grip_faces(rotations)
    return ExecutionStep((), front, up, right).grip_name


def execution_steps(moves: str | tuple[str, ...]) -> tuple[ExecutionStep, ...]:
    """Replace X/Y/Z tokens with explicitly named physical grips.

    Face-turn notation remains local to the grip named for each step. Trailing
    regrips are intentionally omitted because they do not affect the puzzle.
    """

    rotation_history: list[str] = []
    pending_moves: list[str] = []
    steps: list[ExecutionStep] = []

    def flush() -> None:
        if not pending_moves:
            return
        front, up, right = grip_faces(tuple(rotation_history))
        steps.append(ExecutionStep(tuple(pending_moves), front, up, right))
        pending_moves.clear()

    for token in parse_algorithm(moves):
        if token[0] in "XYZ":
            flush()
            rotation_history.append(token)
        else:
            pending_moves.append(token)
    flush()
    return tuple(steps)
