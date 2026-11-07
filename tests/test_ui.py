from __future__ import annotations

import unittest

try:
    import tkinter  # noqa: F401  (some Python builds ship without Tk)
except ImportError:
    TKINTER_AVAILABLE = False
else:
    TKINTER_AVAILABLE = True


@unittest.skipUnless(TKINTER_AVAILABLE, "tkinter is not installed")
class UiModuleTests(unittest.TestCase):
    def test_tkinter_app_module_imports(self) -> None:
        from puppet_edge_picker.ui import EdgePickerApp

        self.assertTrue(callable(EdgePickerApp.find))


if __name__ == "__main__":
    unittest.main()
