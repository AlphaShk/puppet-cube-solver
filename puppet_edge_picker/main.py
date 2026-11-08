"""Application entry point for the Tk window.

tkinter is imported inside :func:`main`, so a Python build without Tk, or a
session without a display, gets a one-line hint instead of a traceback.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

CLI_HINT = "The command line works without Tk: puppet-edge-picker-cli --help"


def use_readable_theme(root: tk.Misc) -> None:
    """Replace Tk's plain X11 ``default`` theme with ``clam``.

    The native themes on macOS (``aqua``) and Windows (``vista``) are kept.
    """

    from tkinter import ttk

    style = ttk.Style(root)
    if style.theme_use() == "default" and "clam" in style.theme_names():
        style.theme_use("clam")


def main() -> int:
    """Open the window; return 1 with a hint when Tk is unavailable."""

    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print(
            "error: the window needs tkinter, which this Python does not include. "
            "Install it (python3-tk on Debian or Ubuntu, python-tk@3.x with "
            f"Homebrew).\n{CLI_HINT}",
            file=sys.stderr,
        )
        return 1
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"error: Tk cannot open a window ({exc}).\n{CLI_HINT}", file=sys.stderr)
        return 1

    from .ui import EdgePickerApp

    root.title("Puppet Cube Phase-3 Algorithm Picker")
    root.geometry("920x780")
    root.minsize(760, 640)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    use_readable_theme(root)
    try:
        app = EdgePickerApp(root)
    except Exception as exc:
        root.withdraw()
        messagebox.showerror(
            "Startup error",
            f"The verified algorithm catalogue could not be loaded:\n\n{exc}",
            parent=root,
        )
        root.destroy()
        raise
    root.mainloop()
    # Closing the window cancels a running search; let its thread finish
    # before the interpreter releases the Tk objects.
    app.wait_for_search(timeout=5.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
