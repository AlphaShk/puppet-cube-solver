"""Application entry point."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .ui import EdgePickerApp


def main() -> None:
    root = tk.Tk()
    root.title("Puppet Cube Phase-3 Algorithm Picker")
    root.geometry("920x780")
    root.minsize(760, 640)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    try:
        app = EdgePickerApp(root)
    except Exception as exc:
        root.withdraw()
        messagebox.showerror(
            "Startup error",
            f"The verified algorithm catalog could not be loaded:\n\n{exc}",
            parent=root,
        )
        root.destroy()
        raise
    root.mainloop()
    # Closing the window cancels a running search; let its thread finish
    # before the interpreter releases the Tk objects.
    app.wait_for_search(timeout=5.0)


if __name__ == "__main__":
    main()
