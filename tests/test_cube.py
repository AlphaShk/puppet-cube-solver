from __future__ import annotations

import unittest

from puppet_edge_picker.cube import (
    SOLVED,
    algorithm_effect,
    apply_algorithm,
    apply_move,
    cube_orientation_sequences,
    flipped_edges,
    moved_edges,
)


class CubeTests(unittest.TestCase):
    def test_quarter_turn_four_times_is_identity(self) -> None:
        for move in tuple("UDRLFBXYZ") + ("Rw", "Uw", "Fw"):
            with self.subTest(move=move):
                self.assertEqual(apply_algorithm(SOLVED, (move,) * 4), SOLVED)

    def test_move_then_inverse_is_identity(self) -> None:
        for move in ("U", "D", "R", "L", "F", "B", "X", "Y", "Z", "Rw", "Uw"):
            with self.subTest(move=move):
                self.assertEqual(apply_algorithm(SOLVED, (move, f"{move}'")), SOLVED)

    def test_double_turn_twice_is_identity(self) -> None:
        for move in ("U2", "R2", "F2", "Rw2"):
            with self.subTest(move=move):
                self.assertEqual(apply_algorithm(SOLVED, (move, move)), SOLVED)

    def test_face_turn_edge_effects(self) -> None:
        self.assertEqual(moved_edges(algorithm_effect("R")), ("UR", "DR", "FR", "BR"))
        self.assertEqual(
            flipped_edges(algorithm_effect("F")), ("UF", "DF", "FR", "FL")
        )

    def test_rotations_are_regrips(self) -> None:
        for rotation in "XYZ":
            with self.subTest(rotation=rotation):
                self.assertEqual(apply_move(SOLVED, rotation), SOLVED)

    def test_generate_24_orientations(self) -> None:
        sequences = cube_orientation_sequences()
        self.assertEqual(len(sequences), 24)
        self.assertEqual(len(set(sequences)), 24)

    def test_every_state_stays_well_formed(self) -> None:
        state = apply_algorithm(SOLVED, "Rw U Rw' Uw' R' Uw' R' Uw R Uw")
        self.assertEqual(sorted(state.permutation), list(range(12)))
        self.assertTrue(all(value in (0, 1) for value in state.orientation))


if __name__ == "__main__":
    unittest.main()
