"""Command-line interface: print a verified phase-3 algorithm without Tk.

Installed as ``puppet-edge-picker-cli``; ``python -m puppet_edge_picker.cli``
runs the same program. Examples::

    puppet-edge-picker-cli swap UF UR
    puppet-edge-picker-cli swap UB UL DL BL --preserve-rest --ignore-orientation
    puppet-edge-picker-cli cycle DL FL BL --preserve-rest
    puppet-edge-picker-cli flip UB FR
    puppet-edge-picker-cli catalogue

Edges are named by face letters in either order (``UF`` or ``FU``), by colour
initials (``WG``) or by colour names (``white-green``), using the solved
colour scheme U = White, D = Yellow, F = Green, B = Blue, R = Red, L = Orange.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence

from . import __version__
from .algorithms import GUIDE_URL, compiled_catalog
from .cube import flipped_edges
from .instructions import grip_description
from .report import edge_list, format_report, permutation_summary
from .settings import COLOR_NAMES, EDGES, FACE_COLORS
from .solver import (
    Request,
    RequestError,
    SearchCancelled,
    SearchLimitReached,
    find_algorithms,
)

EXIT_FOUND = 0
EXIT_NO_MATCH = 1
EXIT_INVALID = 2
EXIT_STOPPED = 3
EXIT_INTERRUPTED = 130

# The window asks the solver for six candidates and shows the best first;
# the command line does the same so both report the same best match.
RESULT_LIMIT = 6

_FACE_FOR_NAME: dict[str, str] = {face: face for face in FACE_COLORS}
_FACE_FOR_NAME.update({color: face for face, color in FACE_COLORS.items()})
_FACE_FOR_NAME.update(
    {COLOR_NAMES[color].upper(): face for face, color in FACE_COLORS.items()}
)
_SEPARATORS = ("-", "\N{EN DASH}", "/", "+")


def parse_edge(token: str) -> str:
    """Return the canonical slot name (for example ``UF``) for ``token``."""

    text = token.strip().upper()
    parts: list[str] = []
    for separator in _SEPARATORS:
        if separator in text:
            parts = [part.strip() for part in text.split(separator)]
            break
    else:
        parts = list(text) if len(text) == 2 else [text]
    faces = {_FACE_FOR_NAME.get(part) for part in parts}
    if len(parts) == 2 and None not in faces and len(faces) == 2:
        for edge in EDGES:
            if set(edge) == faces:
                return edge
    raise argparse.ArgumentTypeError(
        f"{token!r} is not an edge slot; use two adjacent faces such as UF, "
        f"colour initials such as WG, or colour names such as white-green "
        f"(slots: {' '.join(EDGES)})"
    )


def _add_request_options(parser: argparse.ArgumentParser, *, flips: bool) -> None:
    if not flips:
        parser.add_argument(
            "--preserve",
            nargs="+",
            action="extend",
            default=[],
            type=parse_edge,
            metavar="EDGE",
            help="edge slots that must keep their piece",
        )
        parser.add_argument(
            "--preserve-rest",
            action="store_true",
            help="protect every edge that the requested effect does not use",
        )
        parser.add_argument(
            "--ignore-orientation",
            action="store_true",
            help="protected edges may be flipped in place",
        )
    parser.add_argument(
        "--labels",
        choices=("colors", "faces"),
        default="colors",
        help="name edges by colours (default) or by face letters",
    )
    parser.add_argument(
        "--alternatives",
        action="store_true",
        help="also print up to five alternative algorithms",
    )
    parser.add_argument(
        "--catalogue-only",
        action="store_true",
        help="do not fall back to combining macros",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        metavar="SECONDS",
        help="cancel the macro search after this many seconds",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="puppet-edge-picker-cli",
        description=(
            "Pick a verified Puppet Cube (V1) phase-3 algorithm for an edge "
            "effect and print grip-by-grip instructions."
        ),
        epilog=(
            "Exit status: 0 algorithm found, 1 no algorithm within the search "
            "bounds, 2 invalid request, 3 search stopped (state limit or "
            "timeout)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    swap = commands.add_parser(
        "swap",
        help="swap one or two pairs of edges",
        description="Swap one pair (A B) or two pairs (A B C D) of edges.",
    )
    swap.add_argument("edges", nargs="+", type=parse_edge, metavar="EDGE")
    _add_request_options(swap, flips=False)

    cycle = commands.add_parser(
        "cycle",
        help="cycle three edges A -> B -> C -> A",
        description="Move the piece in A to B, B to C and C to A.",
    )
    cycle.add_argument("edges", nargs=3, type=parse_edge, metavar="EDGE")
    _add_request_options(cycle, flips=False)

    flip = commands.add_parser(
        "flip",
        help="flip two edges in place",
        description="Flip two edges in place; every other edge must stay unchanged.",
    )
    flip.add_argument("edges", nargs=2, type=parse_edge, metavar="EDGE")
    _add_request_options(flip, flips=True)

    catalogue = commands.add_parser(
        "catalogue",
        aliases=["catalog"],
        help="list the verified catalogue of guide cases",
        description="List every verified catalogue entry and its edge effect.",
    )
    catalogue.add_argument(
        "--labels",
        choices=("colors", "faces"),
        default="colors",
        help="name edges by colours (default) or by face letters",
    )
    return parser


def build_request(args: argparse.Namespace) -> Request:
    """Translate parsed arguments into a solver request."""

    edges: list[str] = args.edges
    if args.command == "flip":
        return Request(flips=frozenset(edges))
    swaps: tuple[tuple[str, str], ...] = ()
    cycles: tuple[tuple[str, str, str], ...] = ()
    if args.command == "swap":
        if len(edges) not in (2, 4):
            raise RequestError("swap takes two edges (one pair) or four (two pairs).")
        swaps = tuple((edges[i], edges[i + 1]) for i in range(0, len(edges), 2))
    else:
        cycles = ((edges[0], edges[1], edges[2]),)
    preserved = set(args.preserve)
    if args.preserve_rest:
        preserved.update(edge for edge in EDGES if edge not in edges)
    return Request(
        swaps=swaps,
        cycles=cycles,
        preserved=frozenset(preserved),
        preserve_orientation=not args.ignore_orientation,
    )


def _print_catalogue(label_mode: str) -> int:
    catalogue = compiled_catalog()
    print(
        f"{len(catalogue)} verified catalogue entries "
        "(each simulated and de-duplicated by edge effect)"
    )
    print(f"Source: {GUIDE_URL}")
    for entry in catalogue:
        definition = entry.definition
        print()
        print(definition.name)
        print(
            f"  macros: {definition.macro_notation or definition.source_case} | "
            f"{entry.face_turn_count} face turns | "
            f"start: {grip_description(definition.starting_rotation)}"
        )
        print(f"  moves: {permutation_summary(entry.effect, label_mode)}")
        print(f"  flips: {edge_list(flipped_edges(entry.effect), label_mode)}")
    return EXIT_FOUND


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in ("catalogue", "catalog"):
        return _print_catalogue(args.labels)

    deadline = None if args.timeout is None else time.monotonic() + args.timeout

    def should_cancel() -> bool:
        return deadline is not None and time.monotonic() >= deadline

    try:
        request = build_request(args)
        results = find_algorithms(
            request,
            RESULT_LIMIT,
            search_macros=not args.catalogue_only,
            should_cancel=should_cancel,
        )
    except RequestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except SearchCancelled:
        print(f"error: search stopped after the {args.timeout:g} s timeout", file=sys.stderr)
        return EXIT_STOPPED
    except SearchLimitReached as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_STOPPED
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED

    print(
        format_report(
            request,
            results,
            label_mode=args.labels,
            show_alternatives=args.alternatives,
        )
    )
    return EXIT_FOUND if results else EXIT_NO_MATCH


if __name__ == "__main__":
    sys.exit(main())
