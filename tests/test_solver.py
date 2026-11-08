from __future__ import annotations

import unittest
from unittest import mock

from puppet_edge_picker.algorithms import catalog_rank, compiled_catalog
from puppet_edge_picker.cube import SOLVED, EdgeState, algorithm_effect, moved_edges
from puppet_edge_picker.instructions import execution_steps, grip_description
from puppet_edge_picker.settings import EDGES
from puppet_edge_picker.solver import (
    Request,
    RequestError,
    SearchLimitReached,
    _macro_generators,
    apply_effect,
    find_algorithms,
    matches,
    movable_edges,
    no_match_message,
    search_exact_flip_combinations,
    search_macro_combinations,
    validate_request,
)


class SolverTests(unittest.TestCase):
    def test_directed_three_edge_cycle_matches_the_published_direction(self) -> None:
        cycle = ("DL", "FL", "BL")
        request = Request(
            cycles=(cycle,),
            preserved=frozenset(set(EDGES) - set(cycle)),
        )
        results = find_algorithms(request)
        self.assertTrue(results)
        self.assertTrue(all(matches(result.effect, request) for result in results))
        self.assertEqual(results[0].definition.source_section, "Move 3 Edges")
        self.assertEqual(results[0].definition.source_case, "Case 1")

    def test_reversing_a_three_edge_cycle_changes_the_requested_effect(self) -> None:
        forward = Request(cycles=(("DL", "FL", "BL"),))
        reverse = Request(cycles=(("DL", "BL", "FL"),))
        result = find_algorithms(forward, limit=1)[0]
        self.assertTrue(matches(result.effect, forward))
        self.assertFalse(matches(result.effect, reverse))

    def test_two_in_place_edge_flips_are_first_class_constraints(self) -> None:
        request = Request(flips=frozenset({"DL", "FR"}))
        results = find_algorithms(request)
        self.assertTrue(results)
        self.assertTrue(all(matches(result.effect, request) for result in results))
        self.assertTrue(all(result.effect.permutation == tuple(range(12)) for result in results))
        self.assertTrue(
            all(
                {
                    EDGES[index]
                    for index, orientation in enumerate(result.effect.orientation)
                    if orientation
                }
                == request.flips
                for result in results
            )
        )
        self.assertEqual(results[0].definition.source_section, "Flip 2 Edges")
        self.assertEqual(results[0].definition.source_case, "Case 1")

    def test_deeper_flip_search_restores_every_temporary_edge_change(self) -> None:
        # This pair previously returned a synthesized three-macro result that
        # flipped the requested edges but also permuted five unrelated edges.
        request = Request(flips=frozenset({"UB", "FR"}))
        results = find_algorithms(request)
        self.assertTrue(results)
        for result in results:
            self.assertTrue(matches(result.effect, request))
            self.assertEqual(result.effect.permutation, tuple(range(12)))
            self.assertEqual(result.definition.macro_count, 6)

    def test_blue_yellow_anchor_cycle_has_a_specific_no_match_explanation(self) -> None:
        request = Request(cycles=(("FL", "DB", "BL"),))
        self.assertEqual(find_algorithms(request, search_macros=False), ())
        self.assertIn("anchor", no_match_message(request))
        # The same name the window, the CLI and edge_label() use for DB.
        self.assertIn("Yellow\N{EN DASH}Blue (DB)", no_match_message(request))

    def test_known_two_pair_swap(self) -> None:
        request = Request(
            (("UB", "UL"), ("DL", "BL")),
            frozenset(set(EDGES) - {"UB", "UL", "DL", "BL"}),
            False,
        )
        results = find_algorithms(request)
        self.assertTrue(results)
        self.assertTrue(all(matches(result.effect, request) for result in results))

    def test_unmentioned_edges_are_unconstrained(self) -> None:
        request = Request((("UF", "FR"),), frozenset(), True)
        results = find_algorithms(request)
        self.assertTrue(results)
        self.assertTrue(
            any(set(moved_edges(result.effect)) - {"UF", "FR"} for result in results)
        )

    def test_catalog_match_keeps_the_exact_guide_grip(self) -> None:
        results = find_algorithms(Request((("UF", "UR"),), frozenset(), True))
        self.assertTrue(results)
        self.assertTrue(all(not result.definition.generated for result in results))
        self.assertEqual(results[0].definition.source_case, "Case 2")
        self.assertEqual(
            grip_description(results[0].definition.starting_rotation),
            "Green front, Yellow up, Orange right",
        )

    def test_uncatalogued_swap_falls_back_to_macro_search(self) -> None:
        request = Request((("UB", "DF"),), frozenset({"DL"}), False)
        self.assertEqual(find_algorithms(request, search_macros=False), ())
        results = find_algorithms(request)
        self.assertTrue(results)
        self.assertTrue(all(matches(result.effect, request) for result in results))
        self.assertTrue(
            all(result.definition.source_section == "Verified macro search" for result in results)
        )

    def test_white_blue_to_blue_orange_falls_back_to_single_grip_macro_search(self) -> None:
        request = Request((("UB", "BL"),), frozenset(), True)
        results = find_algorithms(request)
        self.assertTrue(results)
        self.assertTrue(all(matches(result.effect, request) for result in results))
        self.assertTrue(
            all(result.definition.source_section == "Verified macro search" for result in results)
        )
        for result in results:
            self.assertSetEqual(
                {step.grip_name for step in execution_steps(result.tokens)},
                {"Green front, Yellow up, Orange right"},
            )

    def test_depth_four_macro_result_keeps_the_published_grip(self) -> None:
        request = Request(
            (("DF", "UR"),),
            frozenset({"FR", "BL"}),
            True,
        )
        results = find_algorithms(request)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.definition.source_case, "Depth 4")
        self.assertTrue(matches(result.effect, request))
        self.assertSetEqual(
            {step.grip_name for step in execution_steps(result.tokens)},
            {"Green front, Yellow up, Orange right"},
        )

    def test_compiled_effect_composition_matches_move_simulation(self) -> None:
        generators = [
            result
            for result in compiled_catalog()
            if result.definition.source_section == "Move 3 to 5 Edges"
        ]
        first, second = generators[0], generators[-1]
        composed = apply_effect(first.effect, second.effect)
        simulated = algorithm_effect(first.simulation_tokens + second.simulation_tokens)
        self.assertEqual(composed, simulated)

    def test_preserve_constraints_are_respected(self) -> None:
        request = Request((("UF", "FR"),), frozenset({"UR", "UB", "UL"}), True)
        for result in find_algorithms(request):
            self.assertTrue(matches(result.effect, request))

    def test_fully_constrained_single_transposition_is_rejected(self) -> None:
        request = Request(
            (("UF", "UR"),), frozenset(set(EDGES) - {"UF", "UR"}), True
        )
        with self.assertRaisesRegex(RequestError, "parity-impossible"):
            validate_request(request)

    def test_one_extra_free_edge_is_still_an_isolated_transposition(self) -> None:
        request = Request(
            (("UF", "UR"),), frozenset(set(EDGES) - {"UF", "UR", "UB"}), True
        )
        with self.assertRaises(RequestError):
            validate_request(request)

    def test_fixed_edges_cannot_absorb_the_parity_transposition(self) -> None:
        # The only unprotected slots are DR, DB and BR, which no macro moves,
        # so the request is rejected before any search.
        request = Request(
            (("UF", "UR"),), frozenset({"UB", "UL", "DF", "DL", "FR", "FL", "BL"})
        )
        with self.assertRaisesRegex(RequestError, "parity-impossible"):
            validate_request(request)

    def test_conflicting_requests_are_rejected(self) -> None:
        cases = (
            Request((("UF", "UF"),)),
            Request((("UF", "UR"), ("UF", "UB"))),
            Request((("UF", "UR"),), frozenset({"UF"})),
            Request(()),
            Request(cycles=(("UF", "UR", "UF"),)),
            Request(flips=frozenset({"UF"})),
        )
        for request in cases:
            with self.subTest(request=request), self.assertRaises(RequestError):
                validate_request(request)

    def test_results_use_stable_ranking(self) -> None:
        results = find_algorithms(Request((("UF", "FR"),)), limit=6)
        self.assertEqual(list(results), sorted(results, key=catalog_rank))

    def test_orientation_protection_can_rule_out_a_permutation_match(self) -> None:
        swaps = (("UB", "UL"), ("DL", "BL"))
        protected = frozenset(set(EDGES) - {"UB", "UL", "DL", "BL"})
        self.assertTrue(find_algorithms(Request(swaps, protected, False)))
        self.assertEqual(
            find_algorithms(Request(swaps, protected, True), search_macros=False), ()
        )

    def test_every_returned_result_matches_after_simulation(self) -> None:
        request = Request((("UF", "UR"),), frozenset(), True)
        results = find_algorithms(request)
        self.assertTrue(results)
        for result in results:
            self.assertTrue(matches(result.effect, request))


class FixedEdgeTests(unittest.TestCase):
    """DR, DB and BR are never changed by any verified case or macro."""

    def test_phase_three_cases_change_only_nine_edges(self) -> None:
        self.assertEqual(movable_edges(), frozenset(EDGES) - {"DR", "DB", "BR"})

    def test_requests_on_fixed_edges_return_without_searching(self) -> None:
        for request in (
            Request((("UF", "DR"),)),
            Request(cycles=(("UF", "BR", "FL"),)),
            Request(flips=frozenset({"BR", "FL"})),
        ):
            with self.subTest(request=request), mock.patch(
                "puppet_edge_picker.solver.search_macro_combinations"
            ) as breadth_first, mock.patch(
                "puppet_edge_picker.solver.search_exact_flip_combinations"
            ) as bidirectional:
                self.assertEqual(find_algorithms(request), ())
                breadth_first.assert_not_called()
                bidirectional.assert_not_called()

    def test_skipping_the_search_does_not_change_the_answer(self) -> None:
        self.assertEqual(search_macro_combinations(Request((("UF", "DR"),))), ())
        self.assertEqual(
            search_exact_flip_combinations(Request(flips=frozenset({"UF", "BR"}))), ()
        )

    def test_no_match_message_names_the_fixed_edge(self) -> None:
        message = no_match_message(Request((("UF", "DR"),)))
        self.assertIn("Yellow\N{EN DASH}Red (DR) edge", message)
        self.assertNotIn("search limits", message)
        message = no_match_message(Request(flips=frozenset({"DR", "BR"})))
        self.assertIn("(DR) and Blue\N{EN DASH}Red (BR) edges", message)

    def test_depth_limited_requests_keep_the_search_limit_message(self) -> None:
        request = Request(
            (("UF", "UR"), ("UB", "UL")),
            frozenset(set(EDGES) - {"UF", "UR", "UB", "UL"}),
            True,
        )
        self.assertEqual(find_algorithms(request), ())
        self.assertIn("search limits", no_match_message(request))


class SearchSpaceTests(unittest.TestCase):
    """Pin the search-space figures quoted in the README and docs/design.md."""

    def test_sixteen_macros_give_fourteen_distinct_even_generators(self) -> None:
        generators = _macro_generators()
        self.assertEqual(len(generators), 14)
        cycle_sizes = sorted(len(moved_edges(g.effect)) for g in generators)
        self.assertEqual(cycle_sizes, [3] * 2 + [5] * 12)
        self.assertTrue(all(g.face_turn_count == 10 for g in generators))

    def test_breadth_first_layer_sizes_up_to_four_macros(self) -> None:
        generators = _macro_generators()
        seen = {SOLVED}
        frontier = [SOLVED]
        layer_sizes: list[int] = []
        for _depth in range(4):
            next_frontier: list[EdgeState] = []
            for state in frontier:
                for generator in generators:
                    following = apply_effect(state, generator.effect)
                    if following not in seen:
                        seen.add(following)
                        next_frontier.append(following)
            layer_sizes.append(len(next_frontier))
            frontier = next_frontier
        self.assertEqual(layer_sizes, [14, 180, 2269, 27955])
        self.assertEqual(len(seen), 30419)

    def test_flip_search_keeps_a_meeting_found_as_it_reaches_the_cap(self) -> None:
        # With this cap the step that finds the 6-macro UB/FR flip also
        # reaches the cap, so the answer must still be returned.
        request = Request(flips=frozenset({"UB", "FR"}))
        results = search_exact_flip_combinations(request, max_states=4928)
        self.assertTrue(results)
        self.assertEqual(results[0].definition.macro_count, 6)
        with self.assertRaises(SearchLimitReached):
            search_exact_flip_combinations(request, max_states=500)


if __name__ == "__main__":
    unittest.main()
