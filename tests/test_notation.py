from __future__ import annotations

import unittest

from puppet_edge_picker.cube import SOLVED, apply_algorithm
from puppet_edge_picker.notation import (
    NotationError,
    face_turn_count,
    invert_algorithm,
    parse_algorithm,
    rotation_count,
)


class NotationTests(unittest.TestCase):
    def test_parse_ordinary_inverse_double_and_parentheses(self) -> None:
        self.assertEqual(
            parse_algorithm("(R U R' U') (F2)"),
            ("R", "U", "R'", "U'", "F2"),
        )

    def test_parse_guide_latex_double(self) -> None:
        self.assertEqual(parse_algorithm("R^{2} U' B^{2}"), ("R2", "U'", "B2"))

    def test_parse_internal_wide_turns(self) -> None:
        self.assertEqual(parse_algorithm("Rw Uw' Lw2"), ("Rw", "Uw'", "Lw2"))

    def test_reject_unknown_and_malformed_tokens(self) -> None:
        for text in ("Q", "R3", "R''", "(R U)2", "Rww"):
            with self.subTest(text=text), self.assertRaises(NotationError):
                parse_algorithm(text)

    def test_inversion_round_trip(self) -> None:
        moves = parse_algorithm("R U2 F' X Y' Rw")
        self.assertEqual(invert_algorithm(invert_algorithm(moves)), moves)
        self.assertEqual(apply_algorithm(SOLVED, moves + invert_algorithm(moves)), SOLVED)

    def test_counts_separate_rotations(self) -> None:
        moves = parse_algorithm("X R U2 Y' F Rw")
        self.assertEqual(face_turn_count(moves), 4)
        self.assertEqual(rotation_count(moves), 2)


if __name__ == "__main__":
    unittest.main()
