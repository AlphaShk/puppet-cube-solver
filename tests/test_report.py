from __future__ import annotations

import unittest

from puppet_edge_picker.cube import algorithm_effect
from puppet_edge_picker.report import format_report, permutation_summary
from puppet_edge_picker.solver import Request, find_algorithms


class ReportTests(unittest.TestCase):
    def test_permutation_summary_names_swaps_and_cycles(self) -> None:
        self.assertEqual(permutation_summary(algorithm_effect("U2"), "faces"),
                         "UF \N{LEFT RIGHT ARROW} UB; UR \N{LEFT RIGHT ARROW} UL")
        self.assertEqual(
            permutation_summary(algorithm_effect("U"), "faces"),
            " \N{RIGHTWARDS ARROW} ".join(("UF", "UL", "UB", "UR", "UF")),
        )
        self.assertEqual(permutation_summary(algorithm_effect("X"), "faces"), "None")

    def test_report_shows_grip_moves_and_verified_effect(self) -> None:
        request = Request(cycles=(("DL", "FL", "BL"),))
        report = format_report(request, find_algorithms(request), label_mode="faces")
        for expected in (
            "Requested edge effect:\n  DL \N{RIGHTWARDS ARROW} FL",
            "Best match:\n  Move 3 Edges \N{EM DASH} Case 1",
            "Starting position:\n  Orange front, Yellow up, Blue right",
            "Moved edge slots:\n  DL, FL, BL",
            "Face-turn count: 30",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, report)

    def test_best_only_report_hides_alternatives(self) -> None:
        request = Request((("UB", "DF"),), frozenset({"DL"}), False)
        results = find_algorithms(request)
        self.assertGreater(len(results), 1)
        self.assertIn("Alternative 1", format_report(request, results))
        self.assertNotIn(
            "Alternative 1", format_report(request, results, show_alternatives=False)
        )

    def test_empty_result_says_why(self) -> None:
        request = Request(cycles=(("FL", "DB", "BL"),))
        report = format_report(request, ())
        self.assertIn("Protected edge slots:\n  None", report)
        self.assertIn("anchor", report)


if __name__ == "__main__":
    unittest.main()
