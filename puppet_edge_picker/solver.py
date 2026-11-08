"""Constraint validation, catalogue matching, and result ranking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from .algorithms import Algorithm, CompiledAlgorithm, catalog_rank, compiled_catalog
from .cube import SOLVED, EdgeState, algorithm_effect, flipped_edges, moved_edges
from .notation import face_turn_count, format_algorithm, rotation_count
from .settings import EDGE_INDEX, EDGES, edge_label

# Polled between search states; returning True stops the search.
CancelCheck = Callable[[], bool]


class RequestError(ValueError):
    """Raised when a request is conflicting or provably unreachable."""


class SearchLimitReached(RuntimeError):
    """Raised when bounded macro search cannot complete its current depth."""


class SearchCancelled(RuntimeError):
    """Raised when the caller cancels a search before it finishes."""


def _raise_if_cancelled(should_cancel: CancelCheck | None) -> None:
    if should_cancel is not None and should_cancel():
        raise SearchCancelled("The search was cancelled.")


@dataclass(frozen=True)
class Request:
    swaps: tuple[tuple[str, str], ...] = ()
    preserved: frozenset[str] = frozenset()
    preserve_orientation: bool = True
    cycles: tuple[tuple[str, str, str], ...] = ()
    flips: frozenset[str] = frozenset()


def requested_edges(request: Request) -> frozenset[str]:
    """Return every slot whose permutation or orientation was requested."""

    return frozenset(
        edge
        for group in (*request.swaps, *request.cycles, tuple(request.flips))
        for edge in group
    )


@lru_cache(maxsize=1)
def movable_edges() -> frozenset[str]:
    """Return the slots that at least one verified catalogue entry changes.

    The search generators are catalogue entries and every search result is
    a product of them, so no result can move or flip any other slot.
    """

    touched: set[str] = set()
    for entry in compiled_catalog():
        touched.update(moved_edges(entry.effect))
        touched.update(flipped_edges(entry.effect))
    return frozenset(touched)


def fixed_requested_edges(request: Request) -> tuple[str, ...]:
    """Return requested slots that no verified case or macro moves or flips."""

    requested = requested_edges(request)
    return tuple(edge for edge in EDGES if edge in requested and edge not in movable_edges())


def validate_request(request: Request) -> None:
    """Validate conflicts and fully constrained parity special cases."""

    if not (request.swaps or request.cycles or request.flips):
        raise RequestError("Select an edge effect to request.")
    if len(request.swaps) > 2:
        raise RequestError("At most two swap pairs can be requested.")
    if len(request.cycles) > 1:
        raise RequestError("At most one directed 3-edge cycle can be requested.")
    if request.flips and len(request.flips) != 2:
        raise RequestError("Select exactly two edges to flip.")
    if sum(bool(effect) for effect in (request.swaps, request.cycles, request.flips)) > 1:
        raise RequestError("Choose only one effect type: swaps, a cycle, or flips.")

    affected: set[str] = set()
    for pair_number, pair in enumerate(request.swaps, 1):
        if len(pair) != 2 or not pair[0] or not pair[1]:
            raise RequestError(f"Swap pair {pair_number} is incomplete.")
        first, second = pair
        if first not in EDGE_INDEX or second not in EDGE_INDEX:
            raise RequestError(f"Swap pair {pair_number} contains an unknown edge slot.")
        if first == second:
            raise RequestError(f"Swap pair {pair_number} uses the same edge twice.")
        duplicate = affected.intersection(pair)
        if duplicate:
            edge = sorted(duplicate)[0]
            raise RequestError(f"{edge} is used more than once in the requested effect.")
        affected.update(pair)

    for cycle_number, cycle in enumerate(request.cycles, 1):
        if len(cycle) != 3 or any(not edge for edge in cycle):
            raise RequestError(f"3-edge cycle {cycle_number} is incomplete.")
        unknown = set(cycle).difference(EDGE_INDEX)
        if unknown:
            raise RequestError(
                f"3-edge cycle {cycle_number} contains an unknown edge slot."
            )
        if len(set(cycle)) != 3:
            raise RequestError("A 3-edge cycle must use three different edges.")
        duplicate = affected.intersection(cycle)
        if duplicate:
            edge = sorted(duplicate)[0]
            raise RequestError(f"{edge} is used more than once in the requested effect.")
        affected.update(cycle)

    unknown_flips = request.flips.difference(EDGE_INDEX)
    if unknown_flips:
        raise RequestError(
            f"Unknown edge slot selected for flipping: {sorted(unknown_flips)[0]}."
        )
    duplicate = affected.intersection(request.flips)
    if duplicate:
        edge = sorted(duplicate)[0]
        raise RequestError(f"{edge} is used more than once in the requested effect.")
    affected.update(request.flips)

    unknown_preserved = request.preserved.difference(EDGE_INDEX)
    if unknown_preserved:
        raise RequestError(
            f"Unknown preserved edge slot: {sorted(unknown_preserved)[0]}."
        )
    conflict = affected.intersection(request.preserved)
    if conflict:
        edge = sorted(conflict)[0]
        raise RequestError(
            f"{edge} is selected both for the requested effect and preservation."
        )

    # A 3-cycle has even permutation parity; each transposition is odd.  When
    # the explicitly requested permutation is odd, at least two unconstrained
    # slots must remain available to carry the compensating transposition.
    # Only slots that some macro moves can carry it: DR, DB and BR never move.
    if len(request.swaps) % 2:
        free_edges = (
            set(EDGES).difference(affected, request.preserved) & movable_edges()
        )
        if len(free_edges) < 2:
            raise RequestError(
                "An odd number of edge-pair swaps while every other edge is "
                "fixed is parity-impossible. Add a second swap pair or leave "
                "at least two other edges unprotected (DR, DB and BR never "
                "move, so they do not count)."
            )


def matches(state: EdgeState, request: Request) -> bool:
    """Return whether a simulated effect satisfies every explicit constraint."""

    for first, second in request.swaps:
        first_index = EDGE_INDEX[first]
        second_index = EDGE_INDEX[second]
        if state.permutation[first_index] != second_index:
            return False
        if state.permutation[second_index] != first_index:
            return False
    for cycle in request.cycles:
        # Cycle notation is source-directed: A -> B -> C -> A.  The state is
        # destination-indexed, so B must contain A, C must contain B, and A
        # must contain C.
        for source, destination in zip(cycle, cycle[1:] + cycle[:1]):
            if state.permutation[EDGE_INDEX[destination]] != EDGE_INDEX[source]:
                return False
    for edge in request.flips:
        index = EDGE_INDEX[edge]
        if state.permutation[index] != index or state.orientation[index] != 1:
            return False
    if request.flips:
        # "Flip in place" is an exact effect, not a partial constraint: no
        # edge may move and no unselected edge may be flipped.  Without this
        # check, a fallback macro path could satisfy the two requested flips
        # while scrambling otherwise unconstrained pieces.
        for index, edge in enumerate(EDGES):
            if state.permutation[index] != index:
                return False
            if state.orientation[index] != int(edge in request.flips):
                return False
    for edge in request.preserved:
        index = EDGE_INDEX[edge]
        if state.permutation[index] != index:
            return False
        if request.preserve_orientation and state.orientation[index]:
            return False
    return True


def apply_effect(state: EdgeState, effect: EdgeState) -> EdgeState:
    """Apply a compiled edge transformation to an arbitrary edge state."""

    return EdgeState(
        tuple(
            state.permutation[effect.permutation[destination]]
            for destination in range(len(EDGES))
        ),
        tuple(
            state.orientation[effect.permutation[destination]]
            ^ effect.orientation[destination]
            for destination in range(len(EDGES))
        ),
    )


@lru_cache(maxsize=1)
def _macro_generators() -> tuple[CompiledAlgorithm, ...]:
    sections = {"Move 3 to 5 Edges", "Move 3 to 5 Edges - Reverse"}
    return tuple(
        candidate
        for candidate in compiled_catalog()
        if candidate.definition.source_section in sections
    )


def _synthesized_result(
    state: EdgeState,
    path: tuple[int, ...],
    generators: tuple[CompiledAlgorithm, ...],
) -> CompiledAlgorithm:
    chosen = tuple(generators[index] for index in path)
    tokens = tuple(token for generator in chosen for token in generator.tokens)
    simulation_tokens = tuple(
        token for generator in chosen for token in generator.simulation_tokens
    )
    description = " → ".join(
        generator.definition.name.split(" — rotated ", 1)[0]
        for generator in chosen
    )
    definition = Algorithm(
        name=f"Synthesized {len(path)}-macro match",
        moves=format_algorithm(tokens),
        source_section="Verified macro search",
        source_case=f"Depth {len(path)}",
        macro_count=len(path),
        macro_notation=description,
        generated=True,
        starting_rotation=chosen[0].definition.starting_rotation,
        simulation_moves=format_algorithm(simulation_tokens),
    )
    result = CompiledAlgorithm(
        definition=definition,
        tokens=tokens,
        effect=state,
        face_turn_count=face_turn_count(tokens),
        rotation_count=rotation_count(tokens),
        simulation_tokens=simulation_tokens,
    )
    if algorithm_effect(simulation_tokens) != state:  # pragma: no cover
        raise RuntimeError("Synthesized macro sequence failed final verification")
    return result


def search_macro_combinations(
    request: Request,
    limit: int = 6,
    *,
    max_depth: int = 4,
    max_states: int = 250_000,
    should_cancel: CancelCheck | None = None,
) -> tuple[CompiledAlgorithm, ...]:
    """Breadth-first search combinations of exact-grip guide macros.

    ``should_cancel`` is polled once per expanded state; when it returns
    True the search stops with :class:`SearchCancelled`.
    """

    validate_request(request)
    if max_depth < 1 or max_states < 2:
        raise ValueError("Macro search limits must be positive")

    generators = _macro_generators()
    visited = {SOLVED}
    frontier: list[tuple[EdgeState, tuple[int, ...]]] = [(SOLVED, ())]
    found: list[CompiledAlgorithm] = []

    for _depth in range(1, max_depth + 1):
        next_frontier: list[tuple[EdgeState, tuple[int, ...]]] = []
        for state, path in frontier:
            _raise_if_cancelled(should_cancel)
            for generator_index, generator in enumerate(generators):
                next_state = apply_effect(state, generator.effect)
                if next_state in visited:
                    continue
                visited.add(next_state)
                next_path = path + (generator_index,)
                if matches(next_state, request):
                    found.append(
                        _synthesized_result(next_state, next_path, generators)
                    )
                    if len(found) >= limit:
                        return tuple(sorted(found, key=catalog_rank)[:limit])
                next_frontier.append((next_state, next_path))
                if len(visited) >= max_states:
                    if found:
                        return tuple(sorted(found, key=catalog_rank)[:limit])
                    raise SearchLimitReached(
                        f"Macro search reached its {max_states:,}-state safety limit."
                    )
        if found:
            return tuple(sorted(found, key=catalog_rank)[:limit])
        frontier = next_frontier
        if not frontier:
            break
    return ()


def _exact_flip_target(request: Request) -> EdgeState:
    orientation = tuple(int(edge in request.flips) for edge in EDGES)
    return EdgeState(SOLVED.permutation, orientation)


def search_exact_flip_combinations(
    request: Request,
    limit: int = 6,
    *,
    max_depth: int = 8,
    max_states: int = 250_000,
    should_cancel: CancelCheck | None = None,
) -> tuple[CompiledAlgorithm, ...]:
    """Bidirectionally search for an exact two-edge flip transformation.

    Flip requests identify a complete target state, unlike partial swap
    constraints.  Searching simultaneously from solved and from that target
    reaches depth-six constructions without materializing the millions of
    states required by one-way breadth-first search.  ``should_cancel`` is
    polled once per expanded state, as in :func:`search_macro_combinations`.
    """

    validate_request(request)
    if not request.flips:
        raise ValueError("Exact flip search requires a flip request")
    if max_depth < 1 or max_states < 2:
        raise ValueError("Macro search limits must be positive")

    target = _exact_flip_target(request)
    generators = _macro_generators()
    inverse_indexes: dict[int, int] = {}
    for index, generator in enumerate(generators):
        # The verified catalogue contains every base macro together with its
        # reverse. Applying a generator until it reaches solved identifies the
        # corresponding reverse without relying on case names.
        for candidate_index, candidate in enumerate(generators):
            if apply_effect(generator.effect, candidate.effect) == SOLVED:
                inverse_indexes[index] = candidate_index
                break
        else:  # pragma: no cover
            raise RuntimeError("A macro generator is missing its verified inverse")

    def expand(
        seen: dict[EdgeState, tuple[int, ...]],
        frontier: list[EdgeState],
    ) -> list[EdgeState]:
        next_frontier: list[EdgeState] = []
        for state in frontier:
            _raise_if_cancelled(should_cancel)
            path = seen[state]
            for generator_index, generator in enumerate(generators):
                next_state = apply_effect(state, generator.effect)
                if next_state in seen:
                    continue
                seen[next_state] = path + (generator_index,)
                next_frontier.append(next_state)
        return next_frontier

    forward_seen: dict[EdgeState, tuple[int, ...]] = {SOLVED: ()}
    backward_seen: dict[EdgeState, tuple[int, ...]] = {target: ()}
    forward_frontier = [SOLVED]
    backward_frontier = [target]

    for _combined_depth in range(1, max_depth + 1):
        if len(forward_frontier) <= len(backward_frontier):
            forward_frontier = expand(forward_seen, forward_frontier)
            intersections = [
                state for state in forward_frontier if state in backward_seen
            ]
        else:
            backward_frontier = expand(backward_seen, backward_frontier)
            intersections = [
                state for state in backward_frontier if state in forward_seen
            ]

        if not intersections:
            # Only a step that found nothing counts against the cap, so a
            # meeting found in the step that crosses it is still returned.
            if len(forward_seen) + len(backward_seen) >= max_states:
                raise SearchLimitReached(
                    f"Exact flip search reached its {max_states:,}-state safety limit."
                )
            continue

        results: list[CompiledAlgorithm] = []
        seen_paths: set[tuple[int, ...]] = set()
        for state in intersections:
            backward_path = backward_seen[state]
            path = forward_seen[state] + tuple(
                inverse_indexes[index] for index in reversed(backward_path)
            )
            if path in seen_paths:
                continue
            seen_paths.add(path)
            result = _synthesized_result(target, path, generators)
            if matches(result.effect, request):
                results.append(result)
        return tuple(sorted(results, key=catalog_rank)[:limit])

    return ()


def find_algorithms(
    request: Request,
    limit: int = 6,
    *,
    search_macros: bool = True,
    should_cancel: CancelCheck | None = None,
) -> tuple[CompiledAlgorithm, ...]:
    """Return catalogue matches, then bounded synthesized matches as fallback.

    The catalogue check takes milliseconds and always completes;
    ``should_cancel`` applies to the fallback search.
    """

    validate_request(request)
    if limit < 1:
        raise ValueError("Result limit must be positive")
    if fixed_requested_edges(request):
        # Neither a catalogue entry nor any product of the search generators
        # changes these slots, so the answer is empty without searching.
        return ()

    matches_found: list[CompiledAlgorithm] = []
    for candidate in compiled_catalog():
        if not matches(candidate.effect, request):
            continue
        # Do not trust cached metadata at the final display boundary.
        verified_effect = algorithm_effect(candidate.simulation_tokens)
        if verified_effect != candidate.effect or not matches(verified_effect, request):
            continue
        matches_found.append(candidate)

    ranked = tuple(sorted(matches_found, key=catalog_rank)[:limit])
    if ranked or not search_macros:
        return ranked
    _raise_if_cancelled(should_cancel)
    if request.flips:
        return search_exact_flip_combinations(
            request, limit, should_cancel=should_cancel
        )
    return search_macro_combinations(request, limit, should_cancel=should_cancel)


def no_match_message(request: Request | None = None) -> str:
    anchor = f"{edge_label('DB')} (DB)"
    if request is not None and "DB" in requested_edges(request):
        return (
            f"No verified phase-3 case can move or flip the {anchor} "
            "edge in the guide's fixed Puppet Cube grips. That edge is the "
            "anchor preserved by every published case; check the phase setup "
            "or choose a request that leaves it fixed."
        )
    fixed = fixed_requested_edges(request) if request is not None else ()
    if fixed:
        names = " and ".join(f"{edge_label(edge)} ({edge})" for edge in fixed)
        if len(fixed) == 1:
            noun, pronoun, verb, object_pronoun = "edge", "it", "stays", "it"
        else:
            noun, pronoun, verb, object_pronoun = "edges", "they", "stay", "them"
        return (
            f"No verified phase-3 case or macro moves or flips the {names} "
            f"{noun}, so no combination of them can produce this effect. Like "
            f"the {anchor} anchor, {pronoun} {verb} in place "
            f"in every published case; choose a request that leaves "
            f"{object_pronoun} fixed."
        )
    if request is not None and request.flips:
        return (
            "No verified guide case or permitted macro combination flips "
            "exactly those two edges while leaving every other edge untouched."
        )
    return (
        "No exact-grip guide case or permitted macro combination within the "
        "current search limits satisfies all selected constraints. Unprotect "
        "another edge or select a different requested effect."
    )
