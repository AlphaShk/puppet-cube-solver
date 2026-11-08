"""Count the states that the macro search can reach, depth by depth.

Breadth-first search from solved over the search generators (the effects of
the 16 base and reverse macros), composed with the same rule as
``solver.apply_effect``. It prints the layer table in docs/design.md and the
figures the README quotes from it.

Run from the repository root (a few seconds and a few hundred MB at depth 6):

    python scripts/search_sizes.py [MAX_DEPTH]
"""

from __future__ import annotations

import sys
import time
from operator import itemgetter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from puppet_edge_picker.cube import SOLVED, EdgeState, moved_edges
from puppet_edge_picker.solver import _macro_generators, apply_effect

# A state is packed into 12 bytes, one per destination slot:
# 2 * (piece in that slot) + (its flip).
Packed = bytes


def pack(state: EdgeState) -> Packed:
    return bytes(2 * piece + flip for piece, flip in zip(state.permutation, state.orientation))


def unpack(packed: Packed) -> EdgeState:
    return EdgeState(tuple(code >> 1 for code in packed), tuple(code & 1 for code in packed))


class PackedGenerator:
    """One generator effect, applied to packed states."""

    def __init__(self, effect: EdgeState) -> None:
        self._gather = itemgetter(*effect.permutation)
        self._flips = int.from_bytes(bytes(effect.orientation), "big")

    def __call__(self, packed: Packed) -> Packed:
        gathered = bytes(self._gather(packed))
        return (int.from_bytes(gathered, "big") ^ self._flips).to_bytes(12, "big")


def main() -> None:
    max_depth = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    generators = _macro_generators()
    packed_generators = [PackedGenerator(g.effect) for g in generators]

    # The packed composition must agree with the solver's own on every
    # product of two generators before it is trusted for the counts.
    for first in generators:
        for second, packed_second in zip(generators, packed_generators):
            expected = apply_effect(first.effect, second.effect)
            if unpack(packed_second(pack(first.effect))) != expected:
                raise SystemExit("packed composition disagrees with solver.apply_effect")

    sizes = sorted(len(moved_edges(g.effect)) for g in generators)
    print(
        f"{len(generators)} distinct generators: "
        f"{sizes.count(5)} five-cycles, {sizes.count(3)} three-cycles, "
        f"face turns each: {sorted({g.face_turn_count for g in generators})}"
    )
    print()
    print("| Macros | New states | Reachable in total |")
    print("|---:|---:|---:|")

    started = time.perf_counter()
    seen: set[Packed] = {pack(SOLVED)}
    frontier = list(seen)
    totals = {0: 1}
    for depth in range(1, max_depth + 1):
        next_frontier: list[Packed] = []
        for packed in frontier:
            for generator in packed_generators:
                following = generator(packed)
                if following not in seen:
                    seen.add(following)
                    next_frontier.append(following)
        frontier = next_frontier
        totals[depth] = len(seen)
        print(f"| {depth} | {len(frontier):,} | {len(seen):,} |")

    print()
    if max_depth >= 4:
        print(
            "Two radius-4 balls (bidirectional flip search) hold at most "
            f"{2 * totals[4]:,} states."
        )
    print(f"Counted in {time.perf_counter() - started:.1f} s.")


if __name__ == "__main__":
    main()
