"""Measure how many requests of each kind the picker answers, and at what cost.

Every request in a few families is passed to the same solver call the window
uses. Each is counted as answered from the verified catalogue, answered by
macro search, or unanswered within the search bounds. Unanswered requests
that name DR, DB or BR are impossible, not depth-limited: no verified case or
macro changes those slots, so the "answered" column counts only requests on
the nine movable edges.

A second table reports, per family, the slowest request (time and the macro
count of its best answer) and the face-turn range of the best answers from
the catalogue and from the search.

Run from the repository root (under a minute):

    python scripts/coverage.py
"""

from __future__ import annotations

import itertools
import platform
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from puppet_edge_picker.settings import EDGES
from puppet_edge_picker.solver import (
    Request,
    SearchLimitReached,
    find_algorithms,
    fixed_requested_edges,
)


@dataclass
class Tally:
    requests: int = 0
    catalogue: int = 0
    search: int = 0
    unanswered: int = 0
    fixed_edge: int = 0
    stopped: int = 0
    worst_seconds: float = 0.0
    worst_macros: int | None = None
    catalogue_turns: list[int] = field(default_factory=list)
    search_turns: list[int] = field(default_factory=list)

    @property
    def answered(self) -> int:
        return self.catalogue + self.search

    @property
    def movable_requests(self) -> int:
        return self.requests - self.fixed_edge


def measure(requests: Iterable[Request]) -> Tally:
    tally = Tally()
    for request in requests:
        tally.requests += 1
        tally.fixed_edge += bool(fixed_requested_edges(request))
        started = time.perf_counter()
        try:
            results = find_algorithms(request)
        except SearchLimitReached:
            results = None
        seconds = time.perf_counter() - started
        if seconds > tally.worst_seconds:
            tally.worst_seconds = seconds
            tally.worst_macros = results[0].definition.macro_count if results else None
        if results is None:
            tally.stopped += 1
        elif not results:
            tally.unanswered += 1
        elif results[0].definition.generated:
            tally.search += 1
            tally.search_turns.append(results[0].face_turn_count)
        else:
            tally.catalogue += 1
            tally.catalogue_turns.append(results[0].face_turn_count)
    return tally


def rest(*used: str) -> frozenset[str]:
    return frozenset(edge for edge in EDGES if edge not in used)


def families() -> dict[str, list[Request]]:
    pairs = list(itertools.combinations(EDGES, 2))
    cycles = [
        cycle
        for a, b, c in itertools.combinations(EDGES, 3)
        for cycle in ((a, b, c), (a, c, b))
    ]
    double_swaps = [
        ((a, b), (c, d))
        for a, b, c, d in itertools.permutations(EDGES, 4)
        if a < b and c < d and a < c
    ]
    return {
        "Flip two edges in place": [Request(flips=frozenset(pair)) for pair in pairs],
        "Swap one pair, nothing protected": [Request((pair,)) for pair in pairs],
        "Directed 3-cycle, nothing protected": [Request(cycles=(cycle,)) for cycle in cycles],
        "Directed 3-cycle, all other edges protected": [
            Request(cycles=(cycle,), preserved=rest(*cycle)) for cycle in cycles
        ],
        "Two swaps, all other edges protected": [
            Request(swaps, rest(*itertools.chain(*swaps))) for swaps in double_swaps
        ],
    }


def turn_range(turns: list[int]) -> str:
    if not turns:
        return "-"
    low, high = min(turns), max(turns)
    return str(low) if low == high else f"{low} to {high}"


def main() -> None:
    print(f"Python {platform.python_version()} on {platform.machine()} ({platform.system()})")
    tallies = {name: measure(requests) for name, requests in families().items()}

    print()
    print(
        "| Request family | Requests | From catalogue | By macro search "
        "| Unanswered | of which name DR/DB/BR | Answered on the 9 movable edges |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name, tally in tallies.items():
        unanswered = str(tally.unanswered)
        if tally.stopped:
            unanswered += f" (+{tally.stopped} stopped)"
        print(
            f"| {name} | {tally.requests} | {tally.catalogue} | {tally.search} "
            f"| {unanswered} | {tally.fixed_edge} "
            f"| {tally.answered} of {tally.movable_requests} |"
        )

    print()
    print(
        "| Request family | Slowest request | Its best answer "
        "| Face turns, catalogue answers | Face turns, search answers |"
    )
    print("|---|---:|---:|---:|---:|")
    for name, tally in tallies.items():
        macros = "none" if tally.worst_macros is None else f"{tally.worst_macros} macros"
        print(
            f"| {name} | {tally.worst_seconds:.2f} s | {macros} "
            f"| {turn_range(tally.catalogue_turns)} | {turn_range(tally.search_turns)} |"
        )

    catalogue_turns = [t for tally in tallies.values() for t in tally.catalogue_turns]
    search_turns = [t for tally in tallies.values() for t in tally.search_turns]
    print()
    print(
        f"All families: best answers {turn_range(catalogue_turns + search_turns)} "
        f"face turns; synthesized answers {turn_range(search_turns)}."
    )


if __name__ == "__main__":
    main()
