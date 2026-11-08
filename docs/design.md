# Design notes

How the picker models the puzzle and why it is built the way it is. The
[README](../README.md) has the overview; this page has the details.

## Scope

The tool covers phase 3 of the Puppet Cube (V1) method in the
[Twisty Puzzle Guide](https://mrlhumphreys.github.io/twisty_guide_j/guides/puppet-cube-phase-3),
the phase whose algorithms move and flip edges. It assumes the cube is in the
state phase 3 starts from, so only edges are modelled and only the guide's
own macros are combined.

## Conventions

- **Slots.** `UF UR UB UL DF DR DB DL FR FL BR BL`, indexed in that order
  (`settings.py`).
- **Colours.** The reference scheme is U White, D Yellow, F Green, B Blue,
  R Red, L Orange. Colours only change labels; algorithms stay in face-turn
  notation.
- **State.** `EdgeState(permutation, orientation)` is indexed by destination
  slot. `permutation[i]` is the piece now in slot `i`. `orientation[i]` is 0
  when that piece's reference sticker (the face named first in its home slot,
  such as U for UF or F for FR) lies on the first-named face of slot `i`, and
  1 otherwise. `SOLVED` is the identity with no flips.
- **Composition.** `apply_effect(state, effect)` is the state reached by
  performing `effect` from `state`. Slot `d` receives what `state` held in
  slot `effect.permutation[d]`, and its flip is XORed with
  `effect.orientation[d]`. The search composes compiled effects this way and
  only re-simulates face turns for the final check.
- **Notation.** Face turns, wide turns (`Rw`), whole-cube rotations `X Y Z`,
  primes and doubles. Parentheses are ignored and the guide's `R^{2}`
  spelling is accepted. Face turns are counted in the face-turn metric (a
  double turn counts once); rotations are counted separately.
- **Requests.** A swap `(A, B)` requires slot A to hold B's piece and the
  other way round. A cycle `(A, B, C)` is source-directed: A's piece goes to
  B, B's to C and C's to A. A flip request is exact: the two named edges are
  flipped in place and every other edge stays in place, unflipped. Preserved
  slots keep their own piece, and its orientation unless orientation is
  ignored. Slots that are not mentioned are free.

## Move tables from geometry

`cube.py` puts the face centres on the unit axes (R = +x, U = +y, F = +z) and
treats each edge slot as the pair of faces it touches. A clockwise quarter
turn of the face with outward axis `a`, seen from outside, is a rotation by
-90 degrees about `a`. With cos = 0 and sin = -1, Rodrigues' formula
`v cos θ + (a × v) sin θ + a (a · v)(1 − cos θ)` becomes

```text
v' = -(a × v) + a (a · v)
```

which stays in integers. Rotating both faces of a slot gives the destination
slot, and rotating the face that carries the reference sticker gives the new
orientation. A wide turn moves every slot that does not touch the opposite
face. `X`, `Y` and `Z` use the R, U and F axes and relabel slots and pieces
together, because in the guide they are regrips, not puzzle moves. The 24
cube orientations come from a breadth-first search over `X`, `Y` and `Z`, and
a test checks that they give 24 distinct grips.

## Modelling the Puppet Cube

On the Puppet Cube several pieces are fused into blocks, so one visible turn
can carry one or two layers of the underlying 3x3x3 mechanism, depending on
the block it grabs. For the eight base macros the simulation therefore uses
hidden wide-turn sequences (`BASE_SIMULATION_TEXT` in `algorithms.py`), and
tests pin each macro's edge cycle to the cycle drawn in the guide. The user
always sees the published moves; the hidden sequence only computes the
effect. Reverses invert both sequences, and composite cases are expanded
macro by macro, so they inherit the hidden sequences.

The guide draws every case in one of two grips:

| Rotation | Grip |
|---|---|
| `Y X2` | Orange front, Yellow up, Blue right |
| `Z2` | Green front, Yellow up, Orange right |

The compiler puts the grip rotation in front of each case and appends the
shortest rotation-only sequence that returns to the reference colour frame,
so every effect is measured in the same frame. That suffix adds no face turns
and is not shown. A case is never moved to a different grip: the block layout
makes rotated copies of an algorithm mechanically invalid.

## The catalogue

`guide_algorithms()` returns 36 definitions: 8 base macros, their 8 reverses,
8 "Move 3 Edges" compositions, 4 pair swaps and 8 two-edge flips.
`compiled_catalog()` simulates each one, keys it by edge effect and keeps the
better-ranked definition when two share an effect. In their grips, Case 7 and
the reverse of Case 8 have the same effect, and so do the reverse of Case 7
and Case 8, which leaves 34 entries. Every entry is re-simulated before the
catalogue is returned, and `find_algorithms` re-simulates each match again
before handing it on instead of trusting the cached effect.

Ranking (`catalog_rank`) is lexicographic: face turns, macro count,
rotations, token count, published before synthesized, then name. Results are
therefore deterministic.

## Validation and parity

`validate_request` rejects malformed requests before any search: more than
two swaps or more than one cycle, a flip request that does not name exactly
two edges, mixed effect types, a slot used twice, and a slot that is both
requested and preserved.

All 14 distinct macro effects are even permutations (twelve 5-cycles and two
3-cycles), so every state the tool can reach is even. One requested swap is
odd, so the overall permutation can only be even if another transposition
happens among the unconstrained slots, which needs at least two of them. A
single swap with fewer than two free slots is therefore rejected as
parity-impossible. Two swaps and 3-cycles are even and need no such check.

No catalogue entry, and so no product of macros, moves or flips DR, DB or BR.
DB is the anchor every published case keeps in place, and DR and BR turn out
to be fixed as well. A request that needs one of them to change is answered
at once with an explanation instead of a search.

## Search

The generators are the effects of the 16 base and reverse macros, which are
14 distinct effects. A synthesized result chains whole macros, each in its
published grip, so every part of it is a sequence the guide itself uses.

**Breadth-first search** (`search_macro_combinations`) handles swaps and
cycles. These requests constrain only some slots, so many final states are
acceptable and there is no single target to search back from. The search
keeps a global visited set and the macro path to each state, tests every new
state against the request, and stops after the first depth that produces a
match, so all returned results use the fewest macros. The limits are depth 4
and 250,000 states. The number of distinct states reachable with the 14
generators grows like this:

| Macros | New states | Reachable in total |
|---:|---:|---:|
| 1 | 14 | 15 |
| 2 | 180 | 195 |
| 3 | 2,269 | 2,464 |
| 4 | 27,955 | 30,419 |
| 5 | 329,144 | 359,563 |
| 6 | 3,470,623 | 3,830,186 |

Depth 4 is therefore searched exhaustively within the cap, while depth 5
would already exceed it.

**Bidirectional search** (`search_exact_flip_combinations`) handles exact
flips. Here the target state is fully known, so the search grows one ball
from solved and one from the target, always expanding the smaller frontier,
and joins a forward path with the inverted backward path where the two meet.
Each generator's inverse is found by composing it with every candidate until
the product is solved, so case names are never trusted. Two balls of radius 4
hold at most about 61,000 states, compared with over 3.8 million for a
one-way search to depth 6. This makes flips that need 6 to 8 macros
reachable: UB with FR takes 6 macros, UB with UL takes 8.

Every synthesized result is expanded into its visible and hidden move
sequences and simulated from solved. A mismatch raises an error instead of
being displayed.

## Cancellation and the window

Both searches take an optional `should_cancel` callable, poll it once per
expanded state and raise `SearchCancelled` when it returns true. The
catalogue lookup cannot be interrupted, but it takes milliseconds.

`worker.SearchWorker` runs one search at a time on a daemon thread. Each start
gets a job number. The result, or the exception, is stored as a
`SearchOutcome` under a lock and handed out once by `poll()`. The Tk window
never touches the worker's thread. It polls every 50 ms with `after()`, shows
the elapsed time while it waits, and on Cancel sets the flag and keeps the
event loop running. Reset forgets the current job number, so a result that
arrives later is discarded. Closing the window cancels the search, and
`main()` waits up to five seconds for the thread after the event loop ends.

The command line uses the same `should_cancel` hook for `--timeout`.

## Output

`report.py` builds the plain-text report that both the window and the command
line print. `instructions.py` walks the move list, starts a new step at every
`X`, `Y` or `Z` token, and names the grip for each step from the rotations so
far ("Green front, Yellow up, Orange right"). A trailing regrip is dropped
because it does not change the puzzle. In synthesized results each macro
therefore appears as its own step, even when consecutive macros use the same
grip, and the report counts real grip changes separately.

On Linux, where Tk starts with its plain `default` theme, the window switches
to the bundled `clam` theme. The native themes on macOS and Windows are kept.

## Tests

The tests are plain `unittest`. Among other things they pin the base macro
cycles to the guide's diagrams, check that every published case starts in
its drawn grip and returns to the reference frame, and assert the 36
definitions and 34 de-duplicated entries. They also check parity rejection,
fallback search results and cancellation of both searches, and that the
command line runs with tkinter unavailable. The window tests share one Tk
root and collect garbage on the main thread, so that Tk objects are never
finalised on a search thread. They skip on Linux when `DISPLAY` is not set.

## Possible extensions

- Pruning tables or IDA* over macro sequences, to go past four macros for
  requests that protect every other edge.
- A browser build: the solver is pure standard library, so Pyodide could run
  it unchanged.
- A model of the fused blocks, so that results can be checked mechanically
  rather than only through their edge effects.
