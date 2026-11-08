"""Verified phase-3 guide catalogue in mechanically permissible grips."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from .cube import (
    EdgeState,
    algorithm_effect,
    cube_orientation_sequences,
    rotation_face_mapping,
)
from .notation import (
    face_turn_count,
    format_algorithm,
    invert_algorithm,
    parse_algorithm,
    rotation_count,
)

# The published move sequences, macro numbers, section names, case numbers
# and grips below are transcribed from the Puppet Cube (V1) phase-3 page of
# the Twisty Puzzle Guide by mrlhumphreys (GUIDE_URL). Credit for them belongs
# to the guide's author; they are not covered by this repository's MIT licence
# (see README, Credits). BASE_SIMULATION_TEXT is this package's own model of
# the base macros, not part of the guide.
GUIDE_URL = "https://mrlhumphreys.github.io/twisty_guide_j/guides/puppet-cube-phase-3"

# The guide diagrams use two outer-cube grips.  These rotations produce
# Yellow up / Orange front / Blue right and Yellow up / Green front / Orange
# right, respectively, from the stable solved-colour reference in settings.py.
# The table was audited against every a-1 through e-8 SVG used by the guide.
GUIDE_GRIP_A: tuple[str, ...] = ("Y", "X2")
GUIDE_GRIP_B: tuple[str, ...] = ("Z2",)
GUIDE_START_ROTATIONS: dict[str, tuple[tuple[str, ...], ...]] = {
    "Move 3 to 5 Edges": (GUIDE_GRIP_A, GUIDE_GRIP_B) * 4,
    "Move 3 to 5 Edges - Reverse": (GUIDE_GRIP_A, GUIDE_GRIP_B) * 4,
    "Move 3 Edges": (GUIDE_GRIP_A,) * 4 + (GUIDE_GRIP_B,) * 4,
    "Swap/Flip 2 Edge Pairs": (GUIDE_GRIP_A, GUIDE_GRIP_B) * 2,
    "Flip 2 Edges": (
        GUIDE_GRIP_A,
        GUIDE_GRIP_B,
        GUIDE_GRIP_A,
        GUIDE_GRIP_B,
        GUIDE_GRIP_A,
        GUIDE_GRIP_B,
        GUIDE_GRIP_A,
        GUIDE_GRIP_A,
    ),
}


@dataclass(frozen=True)
class Algorithm:
    name: str
    moves: str
    source_section: str
    source_case: str
    macro_count: int = 1
    macro_notation: str = ""
    generated: bool = False
    starting_rotation: tuple[str, ...] = ()
    simulation_moves: str = ""


@dataclass(frozen=True)
class CompiledAlgorithm:
    definition: Algorithm
    tokens: tuple[str, ...]
    effect: EdgeState
    face_turn_count: int
    rotation_count: int
    simulation_tokens: tuple[str, ...]


BASE_MACRO_TEXT: dict[str, str] = {
    "1": "(R U R' U') (R' U' R' U) (R U)",
    "2": "(L' U' L U) (L U L U') (L' U')",
    "3": "(R U R U') (R' U' R' U') (R U)",
    "4": "(L' U' L' U) (L U L U) (L' U')",
    "5": "(R U R U) (R U' R' U') (R' U')",
    "6": "(L' U' L' U') (L' U L U) (L U)",
    "7": "(R U R2 U') (F' U' L' B2) (L F)",
    "8": "(L' U' L2 U) (F U R B2) (R' F')",
}

# A Puppet face turn can move either one or two layers of the hidden 3x3 edge
# mechanism depending on the surrounding fused block.  These internal wide-
# turn equivalents reproduce the edge cycles drawn in guide diagrams a-1
# through a-8; the user-facing formulas remain exactly as published.
BASE_SIMULATION_TEXT: dict[str, str] = {
    "1": "Rw U Rw' Uw' R' Uw' R' Uw R Uw",
    "2": "Lw' U' Lw Uw L Uw L Uw' L' Uw'",
    "3": "Rw U Rw U' Rw' U' Rw' Uw' R Uw",
    "4": "Lw' U' Lw' U Lw U Lw Uw L' Uw'",
    "5": "Rw U Rw U Rw Uw' Rw' Uw' Rw' Uw'",
    "6": "Lw' U' Lw' U' Lw' Uw Lw Uw Lw Uw",
    "7": "Rw U Rw2 Uw' F' Uw' Lw' Bw2 L F",
    "8": "Lw' U' Lw2 Uw F Uw Rw Bw2 R' F'",
}

MACROS: dict[str, tuple[str, ...]] = {
    number: parse_algorithm(text) for number, text in BASE_MACRO_TEXT.items()
}
MACROS.update(
    {f"{number}'": invert_algorithm(tokens) for number, tokens in tuple(MACROS.items())}
)

SIMULATION_MACROS: dict[str, tuple[str, ...]] = {
    number: parse_algorithm(text) for number, text in BASE_SIMULATION_TEXT.items()
}
SIMULATION_MACROS.update(
    {
        f"{number}'": invert_algorithm(tokens)
        for number, tokens in tuple(SIMULATION_MACROS.items())
    }
)


def _expand(
    parts: tuple[str, ...], macros: dict[str, tuple[str, ...]] = MACROS
) -> tuple[tuple[str, ...], int]:
    moves: list[str] = []
    macro_count = 0
    for part in parts:
        if part in macros:
            moves.extend(macros[part])
            macro_count += 1
        else:
            moves.extend(parse_algorithm((part,)))
    return tuple(moves), macro_count


def _composed(
    section: str,
    case: int,
    expression: str,
    *,
    starting_rotation: tuple[str, ...],
    name_prefix: str | None = None,
) -> Algorithm:
    parts = tuple(expression.split())
    tokens, macro_count = _expand(parts)
    simulation_tokens, _ = _expand(parts, SIMULATION_MACROS)
    prefix = name_prefix or section
    definition = Algorithm(
        name=f"{prefix} — Case {case}",
        moves=format_algorithm(tokens),
        source_section=section,
        source_case=f"Case {case}",
        macro_count=macro_count,
        macro_notation=expression,
        simulation_moves=format_algorithm(simulation_tokens),
    )
    return _apply_starting_rotation(definition, starting_rotation)


def _apply_starting_rotation(
    definition: Algorithm, starting_rotation: tuple[str, ...]
) -> Algorithm:
    """Conjugate a local guide formula into the guide's reference colours."""

    visible = _normalize_final_frame(
        starting_rotation + parse_algorithm(definition.moves)
    )
    simulation = _normalize_final_frame(
        starting_rotation
        + parse_algorithm(definition.simulation_moves or definition.moves)
    )
    return replace(
        definition,
        moves=format_algorithm(visible),
        starting_rotation=starting_rotation,
        simulation_moves=format_algorithm(simulation),
    )


def _normalize_final_frame(tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Restore the original colour frame after the guide's final regrip.

    X/Y/Z are physical grip changes, so a guide formula need not undo them at
    the end.  Edge effects, however, must be compared in the original colour
    frame.  Appending a rotation-only restoration does not add puzzle turns
    and is omitted from the displayed execution steps.
    """

    rotations = tuple(token for token in tokens if token[0] in "XYZ")
    identity = rotation_face_mapping(())
    for restoration in cube_orientation_sequences():
        if rotation_face_mapping(rotations + restoration) == identity:
            return tokens + restoration
    raise RuntimeError("Could not restore the guide algorithm's colour frame")


def guide_algorithms() -> tuple[Algorithm, ...]:
    """Return every base and composed algorithm published by the guide."""

    records: list[Algorithm] = []
    for number, text in BASE_MACRO_TEXT.items():
        case_index = int(number) - 1
        forward_start = GUIDE_START_ROTATIONS["Move 3 to 5 Edges"][case_index]
        reverse_start = GUIDE_START_ROTATIONS["Move 3 to 5 Edges - Reverse"][case_index]
        records.append(
            _apply_starting_rotation(Algorithm(
                name=f"Move 3 to 5 Edges — Case {number}",
                moves=format_algorithm(text),
                source_section="Move 3 to 5 Edges",
                source_case=f"Case {number}",
                macro_notation=number,
                simulation_moves=format_algorithm(SIMULATION_MACROS[number]),
            ), forward_start)
        )
        records.append(
            _apply_starting_rotation(Algorithm(
                name=f"Move 3 to 5 Edges Reverse — Case {number}",
                moves=format_algorithm(MACROS[f"{number}'"]),
                source_section="Move 3 to 5 Edges - Reverse",
                source_case=f"Case {number}",
                macro_notation=f"{number}'",
                simulation_moves=format_algorithm(SIMULATION_MACROS[f"{number}'"]),
            ), reverse_start)
        )

    move_three = (
        "5 7 5'",
        "5 Y' 8 Y 5'",
        "Y X 7 Z X' 5 7 5' Z' 8 Z",
        "Y X 7 Z X' 5 Y' 8 Y 5' Z' 8 Z",
        "6 Y 7 Y' 6'",
        "6 8 6'",
        "Z Y' 8 Y Z' 6 Y 7 Y' 6' Z 7 Z'",
        "Z Y' 8 Y Z' 6 8 6' Z 7 Z'",
    )
    records.extend(
        _composed(
            "Move 3 Edges",
            case,
            expression,
            starting_rotation=GUIDE_START_ROTATIONS["Move 3 Edges"][case - 1],
        )
        for case, expression in enumerate(move_three, 1)
    )

    pair_swaps = ("1 5", "2 6", "5 1", "6 2")
    records.extend(
        _composed(
            "Swap/Flip 2 Edge Pairs",
            case,
            expression,
            starting_rotation=GUIDE_START_ROTATIONS["Swap/Flip 2 Edge Pairs"][case - 1],
            name_prefix="Swap 2 Edge Pairs",
        )
        for case, expression in enumerate(pair_swaps, 1)
    )

    right_flip = "1 5 1 5 5 1 5 1"
    left_flip = "2 6 2 6 6 2 6 2"
    flip_two = (
        right_flip,
        left_flip,
        f"1 {right_flip} 1'",
        f"2 {left_flip} 2'",
        f"Y X 3 {right_flip} 3'",
        f"Y' X 4 {left_flip} 4'",
        f"3' {right_flip} 3",
        f"1 Y' {left_flip} Y 1'",
    )
    records.extend(
        _composed(
            "Flip 2 Edges",
            case,
            expression,
            starting_rotation=GUIDE_START_ROTATIONS["Flip 2 Edges"][case - 1],
        )
        for case, expression in enumerate(flip_two, 1)
    )
    return tuple(records)


def _compile(definition: Algorithm) -> CompiledAlgorithm:
    tokens = parse_algorithm(definition.moves)
    simulation_tokens = parse_algorithm(definition.simulation_moves or definition.moves)
    return CompiledAlgorithm(
        definition=definition,
        tokens=tokens,
        effect=algorithm_effect(simulation_tokens),
        face_turn_count=face_turn_count(tokens),
        rotation_count=rotation_count(tokens),
        simulation_tokens=simulation_tokens,
    )


def catalog_rank(item: CompiledAlgorithm) -> tuple[int, int, int, int, int, str]:
    """Stable catalogue/result ranking policy."""

    return (
        item.face_turn_count,
        item.definition.macro_count,
        item.rotation_count,
        len(item.tokens),
        int(item.definition.generated),
        item.definition.name,
    )


@lru_cache(maxsize=1)
def compiled_catalog() -> tuple[CompiledAlgorithm, ...]:
    """Compile, simulate, verify, and deduplicate exact guide cases.

    Puppet Cube algorithms are mechanically constrained by the block layout
    drawn in each guide diagram.  Their starting grips must not be replaced by
    arbitrary whole-cube rotations, even when the resulting edge permutation
    would be valid on an ordinary 3x3 model.
    """

    by_effect: dict[EdgeState, CompiledAlgorithm] = {}
    for definition in guide_algorithms():
        compiled = _compile(definition)
        previous = by_effect.get(compiled.effect)
        if previous is None or catalog_rank(compiled) < catalog_rank(previous):
            by_effect[compiled.effect] = compiled

    result = tuple(sorted(by_effect.values(), key=catalog_rank))
    if not result:  # pragma: no cover - startup integrity guard
        raise RuntimeError("The phase-3 algorithm catalogue is empty")
    for item in result:
        if algorithm_effect(item.simulation_tokens) != item.effect:  # pragma: no cover
            raise RuntimeError(f"Catalogue verification failed for {item.definition.name}")
    return result
