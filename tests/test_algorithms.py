from __future__ import annotations

import unittest

from puppet_edge_picker.algorithms import (
    GUIDE_START_ROTATIONS,
    MACROS,
    SIMULATION_MACROS,
    compiled_catalog,
    guide_algorithms,
)
from puppet_edge_picker.cube import (
    SOLVED,
    algorithm_effect,
    apply_algorithm,
    flipped_edges,
    moved_edges,
    rotation_face_mapping,
)
from puppet_edge_picker.notation import invert_algorithm, parse_algorithm
from puppet_edge_picker.settings import EDGES


class AlgorithmCatalogTests(unittest.TestCase):
    def test_all_36_published_definitions_parse(self) -> None:
        records = guide_algorithms()
        self.assertEqual(len(records), 36)
        for record in records:
            with self.subTest(name=record.name):
                self.assertTrue(parse_algorithm(record.moves))
                self.assertTrue(parse_algorithm(record.simulation_moves))

    def test_reverse_macros_really_reverse_visible_and_hidden_moves(self) -> None:
        for number in map(str, range(1, 9)):
            with self.subTest(number=number):
                self.assertEqual(MACROS[f"{number}'"], invert_algorithm(MACROS[number]))
                self.assertEqual(
                    SIMULATION_MACROS[f"{number}'"],
                    invert_algorithm(SIMULATION_MACROS[number]),
                )
                self.assertEqual(
                    apply_algorithm(
                        SOLVED, SIMULATION_MACROS[number] + SIMULATION_MACROS[f"{number}'"]
                    ),
                    SOLVED,
                )

    def test_base_macros_have_published_cycle_sizes(self) -> None:
        expected = {
            "1": {"UF", "FR", "DF", "BL", "FL"},
            "2": {"UF", "FL", "DF", "BR", "FR"},
            "3": {"UF", "FR", "DF", "DB", "FL"},
            "4": {"UF", "FL", "DF", "DB", "FR"},
            "5": {"UF", "FL", "BL", "DR", "DF"},
            "6": {"UF", "FR", "BR", "DL", "DF"},
            "7": {"FR", "FL", "BL"},
            "8": {"FL", "FR", "BR"},
        }
        for number, expected_edges in expected.items():
            with self.subTest(number=number):
                self.assertSetEqual(
                    set(moved_edges(algorithm_effect(SIMULATION_MACROS[number]))),
                    expected_edges,
                )

    def test_base_macros_match_published_directed_cycles(self) -> None:
        expected = {
            "1": ("UF", "FR", "DF", "BL", "FL"),
            "2": ("UF", "FL", "DF", "BR", "FR"),
            "3": ("UF", "FR", "DF", "DB", "FL"),
            "4": ("UF", "FL", "DF", "DB", "FR"),
            "5": ("UF", "FL", "BL", "DR", "DF"),
            "6": ("UF", "FR", "BR", "DL", "DF"),
            "7": ("FR", "FL", "BL"),
            "8": ("FR", "BR", "FL"),
        }
        for number, cycle in expected.items():
            state = algorithm_effect(SIMULATION_MACROS[number])
            old_to_new = {
                EDGES[source]: EDGES[destination]
                for destination, source in enumerate(state.permutation)
            }
            with self.subTest(number=number):
                for current, following in zip(cycle, cycle[1:] + cycle[:1]):
                    self.assertEqual(old_to_new[current], following)

    def test_move_three_cases_move_exactly_three_edges(self) -> None:
        for record in guide_algorithms():
            if record.source_section != "Move 3 Edges":
                continue
            with self.subTest(name=record.name):
                self.assertEqual(len(moved_edges(algorithm_effect(record.simulation_moves))), 3)

    def test_pair_swap_cases_are_two_transpositions(self) -> None:
        for record in guide_algorithms():
            if record.source_section != "Swap/Flip 2 Edge Pairs":
                continue
            state = algorithm_effect(record.simulation_moves)
            moved = moved_edges(state)
            with self.subTest(name=record.name):
                self.assertEqual(len(moved), 4)
                for edge in moved:
                    index = EDGES.index(edge)
                    self.assertEqual(state.permutation[state.permutation[index]], index)

    def test_flip_cases_only_flip_two_edges(self) -> None:
        expected = {
            "Case 1": {"DL", "FR"},
            "Case 2": {"DF", "BL"},
            "Case 3": {"UL", "FL"},
            "Case 4": {"UF", "FL"},
            "Case 5": {"UL", "DL"},
            "Case 6": {"UF", "DF"},
            "Case 7": {"FR", "BL"},
            "Case 8": {"DF", "DL"},
        }
        for record in guide_algorithms():
            if record.source_section != "Flip 2 Edges":
                continue
            state = algorithm_effect(record.simulation_moves)
            with self.subTest(name=record.name):
                self.assertEqual(moved_edges(state), ())
                self.assertEqual(len(flipped_edges(state)), 2)
                self.assertSetEqual(set(flipped_edges(state)), expected[record.source_case])

    def test_every_published_case_uses_its_diagram_starting_rotation(self) -> None:
        for record in guide_algorithms():
            case_index = int(record.source_case.removeprefix("Case ")) - 1
            expected = GUIDE_START_ROTATIONS[record.source_section][case_index]
            with self.subTest(name=record.name):
                self.assertEqual(record.starting_rotation, expected)

    def test_every_published_effect_returns_to_the_original_color_frame(self) -> None:
        identity = rotation_face_mapping(())
        for record in guide_algorithms():
            rotations = tuple(
                token
                for token in parse_algorithm(record.simulation_moves)
                if token[0] in "XYZ"
            )
            with self.subTest(name=record.name):
                self.assertEqual(rotation_face_mapping(rotations), identity)

    def test_compiled_catalog_is_verified_and_deduplicated(self) -> None:
        catalog = compiled_catalog()
        self.assertEqual(len(catalog), 34)
        self.assertEqual(len({entry.effect for entry in catalog}), len(catalog))
        for entry in catalog:
            with self.subTest(name=entry.definition.name):
                self.assertFalse(entry.definition.generated)
                self.assertEqual(entry.definition.rotations, ())
                self.assertIn(
                    entry.definition.starting_rotation,
                    {tuple(("Y", "X2")), tuple(("Z2",))},
                )
                self.assertEqual(algorithm_effect(entry.simulation_tokens), entry.effect)


if __name__ == "__main__":
    unittest.main()
