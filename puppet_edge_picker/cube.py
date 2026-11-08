"""Immutable edge-only Rubik/Puppet Cube simulation.

There are no hand-typed move tables: each face turn derives its slot and
orientation mapping from geometry, rotating edge positions and sticker
directions in 3-D. Whole-cube
rotations rename positions and pieces together, matching the guide's use of
rotations as regrips rather than puzzle moves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .notation import move_amount, parse_algorithm
from .settings import EDGE_INDEX, EDGES

Vector = tuple[int, int, int]

FACE_VECTOR: dict[str, Vector] = {
    "R": (1, 0, 0),
    "L": (-1, 0, 0),
    "U": (0, 1, 0),
    "D": (0, -1, 0),
    "F": (0, 0, 1),
    "B": (0, 0, -1),
}
VECTOR_FACE = {vector: face for face, vector in FACE_VECTOR.items()}


@dataclass(frozen=True)
class EdgeState:
    permutation: tuple[int, ...]
    orientation: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.permutation) != len(EDGES):
            raise ValueError("Edge permutation must contain 12 entries")
        if sorted(self.permutation) != list(range(len(EDGES))):
            raise ValueError("Edge permutation must contain every piece once")
        if len(self.orientation) != len(EDGES):
            raise ValueError("Edge orientation must contain 12 entries")
        if any(value not in (0, 1) for value in self.orientation):
            raise ValueError("Edge orientation values must be 0 or 1")


SOLVED = EdgeState(tuple(range(len(EDGES))), (0,) * len(EDGES))


def _dot(first: Vector, second: Vector) -> int:
    return sum(a * b for a, b in zip(first, second))


def _cross(first: Vector, second: Vector) -> Vector:
    ax, ay, az = first
    bx, by, bz = second
    return (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)


def _quarter_rotate(vector: Vector, axis: Vector) -> Vector:
    """Rotate -90 degrees about an outward face axis.

    That is clockwise when looking directly at the face from outside.
    Rodrigues' formula simplifies to ``-axis x vector + axis*(axis·vector)``.
    """

    crossed = _cross(axis, vector)
    projection = _dot(axis, vector)
    return cast(
        Vector,
        tuple(-crossed[index] + axis[index] * projection for index in range(3)),
    )


def _edge_from_faces(faces: tuple[str, ...]) -> str:
    face_set = frozenset(faces)
    for edge in EDGES:
        if frozenset(edge) == face_set:
            return edge
    raise ValueError(f"Faces do not identify an edge: {faces}")


def _face_map(axis: Vector) -> dict[str, str]:
    return {
        face: VECTOR_FACE[_quarter_rotate(vector, axis)]
        for face, vector in FACE_VECTOR.items()
    }


def cube_orientation_sequences() -> tuple[tuple[str, ...], ...]:
    """Return short rotation sequences for all 24 physical orientations."""

    identity = tuple("UDRLFB")
    rotation_maps = {
        rotation: _face_map(FACE_VECTOR[face])
        for rotation, face in {"X": "R", "Y": "U", "Z": "F"}.items()
    }
    queue: list[tuple[tuple[str, ...], tuple[str, ...]]] = [(identity, ())]
    sequences: list[tuple[str, ...]] = []
    seen = {identity}

    while queue:
        face_order, sequence = queue.pop(0)
        sequences.append(sequence)
        current = dict(zip("UDRLFB", face_order))
        for rotation in "XYZ":
            rotation_map = rotation_maps[rotation]
            composed = tuple(rotation_map[current[face]] for face in "UDRLFB")
            if composed not in seen:
                seen.add(composed)
                queue.append((composed, sequence + (rotation,)))

    if len(sequences) != 24:  # pragma: no cover - development integrity guard
        raise RuntimeError(f"Expected 24 cube orientations, generated {len(sequences)}")
    return tuple(sequences)


def rotation_face_mapping(
    moves: str | tuple[str, ...] = (),
) -> dict[str, str]:
    """Map each original face to its local face after X/Y/Z regrips."""

    current = {face: face for face in "UDRLFB"}
    rotation_maps = {
        rotation: _face_map(FACE_VECTOR[face])
        for rotation, face in {"X": "R", "Y": "U", "Z": "F"}.items()
    }
    for token in parse_algorithm(moves):
        if token[0] not in "XYZ":
            raise ValueError(f"Expected a whole-cube rotation, got {token!r}")
        for _ in range(move_amount(token)):
            quarter = rotation_maps[token[0]]
            current = {face: quarter[current[face]] for face in current}
    return current


def _apply_face_quarter(state: EdgeState, face: str, *, wide: bool = False) -> EdgeState:
    axis = FACE_VECTOR[face]
    mapping = _face_map(axis)
    permutation = [0] * len(EDGES)
    orientation = [0] * len(EDGES)

    for old_index, old_position in enumerate(EDGES):
        opposite = {"U": "D", "D": "U", "R": "L", "L": "R", "F": "B", "B": "F"}[face]
        affected = opposite not in old_position if wide else face in old_position
        position_map = mapping if affected else {item: item for item in old_position}
        mapped_faces = tuple(position_map[item] for item in old_position)
        new_position = _edge_from_faces(mapped_faces)
        new_index = EDGE_INDEX[new_position]

        piece_index = state.permutation[old_index]
        old_orientation = state.orientation[old_index]
        first_sticker_location = old_position[old_orientation]
        new_first_location = position_map[first_sticker_location]

        permutation[new_index] = piece_index
        orientation[new_index] = 0 if new_first_location == new_position[0] else 1

    return EdgeState(tuple(permutation), tuple(orientation))


def _apply_rotation_quarter(state: EdgeState, rotation: str) -> EdgeState:
    axis = FACE_VECTOR[{"X": "R", "Y": "U", "Z": "F"}[rotation]]
    mapping = _face_map(axis)
    permutation = [0] * len(EDGES)
    orientation = [0] * len(EDGES)

    for old_index, old_position in enumerate(EDGES):
        mapped_position_faces = tuple(mapping[item] for item in old_position)
        new_position = _edge_from_faces(mapped_position_faces)
        new_index = EDGE_INDEX[new_position]

        old_piece = EDGES[state.permutation[old_index]]
        mapped_piece_faces = tuple(mapping[item] for item in old_piece)
        new_piece = _edge_from_faces(mapped_piece_faces)
        new_piece_index = EDGE_INDEX[new_piece]

        old_first_location = old_position[state.orientation[old_index]]
        mapped_first_piece_face = mapping[old_piece[0]]
        mapped_first_location = mapping[old_first_location]
        new_piece_first_face = new_piece[0]
        # If normalization reversed the renamed piece, its first reference
        # sticker corresponds to the old piece's second sticker.
        if new_piece_first_face != mapped_first_piece_face:
            mapped_first_location = mapping[old_position[1 - state.orientation[old_index]]]

        permutation[new_index] = new_piece_index
        orientation[new_index] = 0 if mapped_first_location == new_position[0] else 1

    return EdgeState(tuple(permutation), tuple(orientation))


def apply_move(state: EdgeState, move: str) -> EdgeState:
    """Apply one face turn or coordinate rotation."""

    token = parse_algorithm((move,))[0]
    result = state
    for _ in range(move_amount(token)):
        if token[0] in "XYZ":
            result = _apply_rotation_quarter(result, token[0])
        else:
            result = _apply_face_quarter(result, token[0], wide="w" in token)
    return result


def apply_algorithm(state: EdgeState, moves: str | tuple[str, ...]) -> EdgeState:
    """Apply an algorithm from left to right."""

    result = state
    for move in parse_algorithm(moves):
        result = apply_move(result, move)
    return result


def algorithm_effect(moves: str | tuple[str, ...]) -> EdgeState:
    return apply_algorithm(SOLVED, moves)


def moved_edges(state: EdgeState) -> tuple[str, ...]:
    """Return slots whose solved piece is no longer present."""

    return tuple(
        edge for index, edge in enumerate(EDGES) if state.permutation[index] != index
    )


def flipped_edges(state: EdgeState) -> tuple[str, ...]:
    """Return slots whose occupying edge has non-zero orientation."""

    return tuple(edge for index, edge in enumerate(EDGES) if state.orientation[index])
