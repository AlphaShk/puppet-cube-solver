from __future__ import annotations

import functools
import threading
import time
import unittest
from collections.abc import Callable
from typing import NoReturn

from puppet_edge_picker.algorithms import CompiledAlgorithm
from puppet_edge_picker.solver import (
    Request,
    RequestError,
    SearchCancelled,
    find_algorithms,
    search_exact_flip_combinations,
    search_macro_combinations,
)
from puppet_edge_picker.worker import SearchOutcome, SearchWorker


def cancel_after(polls: int) -> Callable[[], bool]:
    """Return a cancellation check that fires on its ``polls``-th call."""

    count = 0

    def should_cancel() -> bool:
        nonlocal count
        count += 1
        return count >= polls

    return should_cancel


def run_until_cancelled(
    _request: Request, *, should_cancel: Callable[[], bool]
) -> NoReturn:
    """Stand-in search that only ends when it is cancelled."""

    while not should_cancel():
        time.sleep(0.001)
    raise SearchCancelled("cancelled")


class SolverCancellationTests(unittest.TestCase):
    def test_breadth_first_search_stops_when_cancelled(self) -> None:
        # The only match for this request is at depth 4; the 100th poll
        # happens while depth 3 is being expanded.
        request = Request((("DF", "UR"),), frozenset({"FR", "BL"}), True)
        with self.assertRaises(SearchCancelled):
            search_macro_combinations(request, should_cancel=cancel_after(100))

    def test_bidirectional_flip_search_stops_when_cancelled(self) -> None:
        # Flipping UF and UL needs eight macros, so the search is still
        # expanding its frontiers when the 50th poll fires.
        request = Request(flips=frozenset({"UF", "UL"}))
        with self.assertRaises(SearchCancelled):
            search_exact_flip_combinations(request, should_cancel=cancel_after(50))

    def test_find_algorithms_checks_cancellation_before_searching(self) -> None:
        request = Request((("UB", "DF"),), frozenset({"DL"}), False)
        self.assertEqual(find_algorithms(request, search_macros=False), ())
        with self.assertRaises(SearchCancelled):
            find_algorithms(request, should_cancel=lambda: True)

    def test_catalogue_matches_complete_even_when_cancelled(self) -> None:
        request = Request((("UF", "UR"),))
        self.assertTrue(find_algorithms(request, should_cancel=lambda: True))

    def test_cancellation_hook_does_not_change_results(self) -> None:
        for request in (
            Request(flips=frozenset({"UB", "FR"})),
            Request((("UB", "DF"),), frozenset({"DL"}), False),
        ):
            with self.subTest(request=request):
                self.assertEqual(
                    find_algorithms(request),
                    find_algorithms(request, should_cancel=lambda: False),
                )


class SearchWorkerTests(unittest.TestCase):
    def finished_outcome(self, worker: SearchWorker, timeout: float = 60) -> SearchOutcome:
        self.assertTrue(worker.wait(timeout=timeout), "the search did not finish")
        outcome = worker.poll()
        if outcome is None:
            self.fail("no outcome was delivered")
        return outcome

    def test_results_are_computed_on_a_background_thread(self) -> None:
        search_threads: list[int] = []

        def recording_search(
            request: Request, *, should_cancel: Callable[[], bool]
        ) -> tuple[CompiledAlgorithm, ...]:
            search_threads.append(threading.get_ident())
            return find_algorithms(request, should_cancel=should_cancel)

        worker = SearchWorker(recording_search)
        job = worker.start(Request((("UF", "UR"),)))
        outcome = self.finished_outcome(worker)
        self.assertEqual(outcome.job, job)
        self.assertIsNone(outcome.error)
        self.assertTrue(outcome.results)
        self.assertEqual(len(search_threads), 1)
        self.assertNotEqual(search_threads[0], threading.get_ident())
        self.assertIsNone(worker.poll(), "an outcome is delivered only once")

    def test_request_errors_are_reported_not_raised(self) -> None:
        worker = SearchWorker()
        worker.start(Request(()))
        outcome = self.finished_outcome(worker)
        self.assertIsInstance(outcome.error, RequestError)
        self.assertFalse(outcome.cancelled)

    def test_cancel_ends_a_running_search(self) -> None:
        worker = SearchWorker(run_until_cancelled)
        worker.start(Request((("UF", "UR"),)))
        self.assertTrue(worker.running)
        self.assertFalse(worker.wait(timeout=0.05), "runs until cancelled")
        worker.cancel()
        self.assertTrue(self.finished_outcome(worker).cancelled)

    def test_cancel_interrupts_a_long_real_search(self) -> None:
        # DR is never moved by a phase-3 macro, so this breadth-first search
        # cannot succeed. Left alone it would run until its one-million-state
        # cap and report SearchLimitReached rather than cancellation.
        deep_search = functools.partial(
            search_macro_combinations, max_depth=8, max_states=1_000_000
        )
        worker = SearchWorker(deep_search)
        worker.start(Request((("UF", "DR"),)))
        time.sleep(0.05)
        worker.cancel()
        outcome = self.finished_outcome(worker)
        self.assertTrue(outcome.cancelled, f"unexpected outcome: {outcome.error!r}")

    def test_only_one_search_runs_at_a_time(self) -> None:
        worker = SearchWorker(run_until_cancelled)
        worker.start(Request((("UF", "UR"),)))
        with self.assertRaises(RuntimeError):
            worker.start(Request((("UF", "UR"),)))
        worker.cancel()
        self.finished_outcome(worker)

        second = worker.start(Request((("UF", "UR"),)))
        worker.cancel()
        self.assertEqual(self.finished_outcome(worker).job, second)


if __name__ == "__main__":
    unittest.main()
