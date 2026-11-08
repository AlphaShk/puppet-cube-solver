from __future__ import annotations

import argparse
import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path

import puppet_edge_picker
from puppet_edge_picker import cli
from puppet_edge_picker.report import format_report
from puppet_edge_picker.solver import Request, find_algorithms


def run_cli(*argv: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            code = cli.main(argv)
        except SystemExit as exc:  # argparse usage errors
            code = int(exc.code or 0)
    return code, stdout.getvalue(), stderr.getvalue()


class EdgeNameTests(unittest.TestCase):
    def test_accepts_face_letters_colour_initials_and_colour_names(self) -> None:
        cases = {
            "UF": "UF",
            "fu": "UF",
            "WG": "UF",
            "white-green": "UF",
            "Green\N{EN DASH}White": "UF",
            "RB": "BR",
            "OB": "BL",
            "yellow/red": "DR",
        }
        for token, edge in cases.items():
            with self.subTest(token=token):
                self.assertEqual(cli.parse_edge(token), edge)

    def test_rejects_names_that_are_not_edge_slots(self) -> None:
        for token in ("UD", "WY", "XX", "U", "white", "UFR", "white-white"):
            with self.subTest(token=token), self.assertRaises(argparse.ArgumentTypeError):
                cli.parse_edge(token)


class CommandLineTests(unittest.TestCase):
    def test_swap_prints_the_same_report_as_the_window(self) -> None:
        code, out, err = run_cli("swap", "UF", "UR")
        self.assertEqual((code, err), (0, ""))
        request = Request((("UF", "UR"),))
        expected = format_report(request, find_algorithms(request), show_alternatives=False)
        self.assertEqual(out, expected + "\n")
        self.assertIn("Swap 2 Edge Pairs \N{EM DASH} Case 2", out)

    def test_preserve_rest_and_ignore_orientation_build_the_request(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(
            ["swap", "UB", "UL", "DL", "BL", "--preserve-rest", "--ignore-orientation"]
        )
        request = cli.build_request(args)
        self.assertEqual(request.swaps, (("UB", "UL"), ("DL", "BL")))
        self.assertEqual(len(request.preserved), 8)
        self.assertFalse(request.preserve_orientation)
        code, out, _ = run_cli(
            "swap", "UB", "UL", "DL", "BL", "--preserve-rest", "--ignore-orientation"
        )
        self.assertEqual(code, 0)
        self.assertIn("Best match", out)

    def test_flip_falls_back_to_bidirectional_macro_search(self) -> None:
        code, out, _ = run_cli("flip", "UB", "FR", "--labels", "faces")
        self.assertEqual(code, 0)
        self.assertIn("Synthesized 6-macro match", out)
        self.assertIn("Flipped edge slots:\n  UB, FR", out)

    def test_alternatives_flag_prints_more_results(self) -> None:
        argv = ("swap", "UB", "DF", "--preserve", "DL", "--ignore-orientation")
        _, best_only, _ = run_cli(*argv)
        _, with_alternatives, _ = run_cli(*argv, "--alternatives")
        self.assertNotIn("Alternative 1", best_only)
        self.assertIn("Alternative 1", with_alternatives)

    def test_exit_status_reports_no_match(self) -> None:
        code, out, _ = run_cli("cycle", "FL", "DB", "BL")
        self.assertEqual(code, cli.EXIT_NO_MATCH)
        self.assertIn("anchor", out)

    def test_exit_status_reports_invalid_requests(self) -> None:
        for argv, message in (
            (("swap", "UF", "UR", "--preserve-rest"), "parity-impossible"),
            (("swap", "UF", "UR", "--preserve", "UF"), "preservation"),
            (("swap", "UF", "UR", "UB"), "two edges"),
            (("flip", "UF", "UF"), "exactly two"),
        ):
            with self.subTest(argv=argv):
                code, _, err = run_cli(*argv)
                self.assertEqual(code, cli.EXIT_INVALID)
                self.assertIn(message, err)

    def test_unknown_edge_is_a_usage_error(self) -> None:
        code, _, err = run_cli("swap", "UD", "UF")
        self.assertEqual(code, 2)
        self.assertIn("not an edge slot", err)

    def test_timeout_cancels_the_search(self) -> None:
        code, out, err = run_cli("flip", "UF", "UL", "--timeout", "0")
        self.assertEqual(code, cli.EXIT_STOPPED)
        self.assertEqual(out, "")
        self.assertIn("timeout", err)

    def test_catalogue_lists_every_verified_entry(self) -> None:
        code, out, _ = run_cli("catalogue")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("34 verified catalogue entries"))
        self.assertEqual(out.count("face turns"), 34)

    def test_module_runs_as_a_script(self) -> None:
        root = Path(puppet_edge_picker.__file__).resolve().parent.parent
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        completed = subprocess.run(
            [sys.executable, "-m", "puppet_edge_picker.cli", "swap", "UF", "UR"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Best match", completed.stdout)


if __name__ == "__main__":
    unittest.main()
