"""Measure how many requests of each kind the picker answers.

Every request in a few families is passed to the same solver call the window
uses. Each is counted as answered from the verified catalogue, answered by
macro search, or unanswered within the search bounds. Unanswered requests
that name DR, DB or BR are impossible, not depth-limited: no verified case or
macro changes those slots.

Run from the repository root:

    python scripts/coverage.py
"""

from __future__ import annotations

import itertools
import platform
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
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


def measure(requests: Iterable[Request]) -> Tally:
    tally = Tally()
    for request in requests:
        tally.requests += 1
        started = time.perf_counter()
        try:
            results = find_algorithms(request)
        except SearchLimitReached:
            results = None
        tally.worst_seconds = max(tally.worst_seconds, time.perf_counter() - started)
        if results is None:
            tally.stopped += 1
        elif not results:
            tally.unanswered += 1
            tally.fixed_edge += bool(fixed_requested_edges(request))
        elif results[0].definition.generated:
            tally.search += 1
        else:
            tally.catalogue += 1
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


def main() -> None:
    print(f"Python {platform.python_version()} on {platform.machine()} ({platform.system()})")
    print()
    print(
        "| Request family | Requests | From catalogue | By macro search "
        "| Unanswered | of which name DR/DB/BR | Slowest request |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|")
    for name, requests in families().items():
        tally = measure(requests)
        unanswered = str(tally.unanswered)
        if tally.stopped:
            unanswered += f" (+{tally.stopped} stopped)"
        print(
            f"| {name} | {tally.requests} | {tally.catalogue} | {tally.search} "
            f"| {unanswered} | {tally.fixed_edge} | {tally.worst_seconds:.2f} s |"
        )


if __name__ == "__main__":
    main()
