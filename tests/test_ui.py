from __future__ import annotations

import gc
import os
import sys
import time
import unittest
from collections.abc import Callable
from typing import TYPE_CHECKING, NoReturn
from unittest import mock

from puppet_edge_picker.solver import Request, SearchCancelled
from puppet_edge_picker.worker import SearchWorker

try:
    import tkinter
except ImportError:  # some Python builds ship without Tk
    TK_AVAILABLE = False
else:
    TK_AVAILABLE = True

if TYPE_CHECKING:
    from puppet_edge_picker.ui import EdgePickerApp


def run_until_cancelled(
    _request: Request, *, should_cancel: Callable[[], bool]
) -> NoReturn:
    """Stand-in search that only ends when it is cancelled."""

    while not should_cancel():
        time.sleep(0.001)
    raise SearchCancelled("cancelled")


@unittest.skipUnless(TK_AVAILABLE, "tkinter is not installed")
class UiModuleTests(unittest.TestCase):
    def test_tkinter_app_module_imports(self) -> None:
        from puppet_edge_picker.ui import EdgePickerApp

        self.assertTrue(callable(EdgePickerApp.find))


class UiWindowTests(unittest.TestCase):
    """Drive the real window; skipped where no display is available.

    The class shares one Tk root: creating a second root after destroying a
    first one is unreliable on some Tk builds (it can stall ``update``).
    Garbage is collected on the main thread before each test and after the
    class, because Tk objects finalised by a collection that happens to run
    on a search thread would call into Tcl from the wrong thread.
    """

    root: tkinter.Tk | None = None
    skip_reason: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        if not TK_AVAILABLE:
            cls.skip_reason = "tkinter is not installed"
        elif sys.platform not in ("darwin", "win32") and not os.environ.get("DISPLAY"):
            cls.skip_reason = "no display (DISPLAY is not set)"
        else:
            try:
                cls.root = tkinter.Tk()
            except tkinter.TclError as exc:
                cls.skip_reason = f"Tk cannot open a window: {exc}"
            else:
                cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.root is not None:
            cls.root.destroy()
            cls.root = None
        gc.collect()

    def setUp(self) -> None:
        if self.skip_reason is not None:
            self.skipTest(self.skip_reason)
        gc.collect()
        # Dialogs would block the test run; none is expected here.
        patcher = mock.patch("puppet_edge_picker.ui.messagebox")
        self.messagebox = patcher.start()
        self.addCleanup(patcher.stop)

    def make_app(self, worker: SearchWorker | None = None) -> EdgePickerApp:
        from puppet_edge_picker.ui import EdgePickerApp

        app = EdgePickerApp(self.root, worker=worker)
        self.addCleanup(self.destroy_app, app)
        return app

    def destroy_app(self, app: EdgePickerApp) -> None:
        if app.winfo_exists():
            app.destroy()
        self.pump_until(lambda: not app.busy)

    def pump_until(self, condition: Callable[[], bool], timeout: float = 30) -> None:
        assert self.root is not None
        deadline = time.monotonic() + timeout
        while not condition():
            if time.monotonic() > deadline:
                self.fail("timed out waiting for the window")
            self.root.update()
            time.sleep(0.005)

    @staticmethod
    def result_text(app: EdgePickerApp) -> str:
        return app.result_text.get("1.0", "end-1c")

    def test_find_shows_the_background_search_result(self) -> None:
        app = self.make_app()
        app.find()  # the default request swaps White-Green and White-Red
        self.pump_until(lambda: "Best match" in self.result_text(app))
        self.assertFalse(app.busy)
        self.assertTrue(app.find_button.instate(["!disabled"]))
        self.assertTrue(app.cancel_button.instate(["disabled"]))
        self.assertIn("result", app.status_var.get())
        self.messagebox.assert_not_called()

    def test_window_stays_responsive_and_cancel_stops_the_search(self) -> None:
        app = self.make_app(SearchWorker(run_until_cancelled))
        app.find()
        self.assertTrue(app.busy)
        self.assertTrue(app.find_button.instate(["disabled"]))
        self.assertTrue(app.cancel_button.instate(["!disabled"]))

        ticks: list[int] = []
        assert self.root is not None
        self.root.after(1, lambda: ticks.append(1))
        self.pump_until(lambda: bool(ticks))
        self.assertTrue(app.busy, "the event loop ran while the search was busy")

        app.cancel()
        self.pump_until(lambda: "Search cancelled" in self.result_text(app))
        self.assertFalse(app.busy)
        self.assertTrue(app.find_button.instate(["!disabled"]))
        self.assertTrue(app.cancel_button.instate(["disabled"]))

    def test_reset_discards_a_running_search(self) -> None:
        app = self.make_app(SearchWorker(run_until_cancelled))
        app.find()
        app.reset()
        self.pump_until(lambda: app.find_button.instate(["!disabled"]))
        self.assertFalse(app.busy)
        self.assertNotIn("cancelled", self.result_text(app))
        self.assertIn("Find algorithm", self.result_text(app))

    def test_reset_discards_a_finished_search_that_is_not_shown_yet(self) -> None:
        worker = SearchWorker()
        app = self.make_app(worker)
        app.find()
        self.assertTrue(worker.wait(timeout=30))  # finished, but not yet polled
        app.reset()
        self.pump_until(lambda: not app.busy)
        self.assertNotIn("Best match", self.result_text(app))
        self.assertIn("Find algorithm", self.result_text(app))

    def test_closing_the_window_cancels_the_search(self) -> None:
        worker = SearchWorker(run_until_cancelled)
        app = self.make_app(worker)
        app.find()
        app.destroy()
        self.assertTrue(worker.wait(timeout=10))


if __name__ == "__main__":
    unittest.main()
