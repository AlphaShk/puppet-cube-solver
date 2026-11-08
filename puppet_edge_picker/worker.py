"""Run solver searches on a background thread with cooperative cancellation.

Tk widgets may only be used from the thread that runs the event loop, so the
worker never calls back into the interface. The caller starts a search,
polls for the outcome (the Tk window does this with ``after``) and may cancel
at any time. The solver checks the cancellation flag between search states
and stops with :class:`~puppet_edge_picker.solver.SearchCancelled`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .algorithms import CompiledAlgorithm
from .solver import Request, SearchCancelled, find_algorithms

SearchFunction = Callable[..., tuple[CompiledAlgorithm, ...]]


@dataclass(frozen=True)
class SearchOutcome:
    """The finished result of one background search."""

    job: int
    request: Request
    results: tuple[CompiledAlgorithm, ...] = ()
    error: Exception | None = None
    elapsed: float = 0.0

    @property
    def cancelled(self) -> bool:
        return isinstance(self.error, SearchCancelled)


class SearchWorker:
    """Run at most one search at a time on a daemon thread.

    ``search`` is called as ``search(request, should_cancel=..., **options)``
    and defaults to :func:`~puppet_edge_picker.solver.find_algorithms`.
    """

    def __init__(self, search: SearchFunction = find_algorithms) -> None:
        self._search = search
        self._lock = threading.Lock()
        self._busy = False
        self._job = 0
        self._cancel_event = threading.Event()
        self._outcome: SearchOutcome | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        """True from :meth:`start` until the outcome is ready to poll."""

        with self._lock:
            return self._busy

    def start(self, request: Request, **options: Any) -> int:
        """Start searching for ``request`` and return the new job number."""

        with self._lock:
            if self._busy:
                raise RuntimeError("A search is already running.")
            self._busy = True
            self._job += 1
            job = self._job
            self._outcome = None
            cancel_event = threading.Event()
            self._cancel_event = cancel_event
        thread = threading.Thread(
            target=self._run,
            args=(job, request, cancel_event, options),
            name=f"puppet-edge-search-{job}",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return job

    def cancel(self) -> None:
        """Ask the running search to stop at its next checkpoint."""

        self._cancel_event.set()

    def poll(self) -> SearchOutcome | None:
        """Return the finished outcome once, or None if there is none yet."""

        with self._lock:
            outcome, self._outcome = self._outcome, None
        return outcome

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the current search ends; return False on timeout."""

        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return not self.running

    def _run(
        self,
        job: int,
        request: Request,
        cancel_event: threading.Event,
        options: dict[str, Any],
    ) -> None:
        started = time.perf_counter()
        results: tuple[CompiledAlgorithm, ...] = ()
        error: Exception | None = None
        try:
            results = self._search(
                request, should_cancel=cancel_event.is_set, **options
            )
        except Exception as exc:  # handed to the caller instead of lost
            error = exc
        outcome = SearchOutcome(
            job=job,
            request=request,
            results=results,
            error=error,
            elapsed=time.perf_counter() - started,
        )
        with self._lock:
            self._outcome = outcome
            self._busy = False
