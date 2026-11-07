from __future__ import annotations

import unittest

from puppet_edge_picker.settings import edge_label


class SettingsTests(unittest.TestCase):
    def test_default_color_labels(self) -> None:
        self.assertEqual(edge_label("UF"), "White–Green")
        self.assertEqual(edge_label("BL"), "Blue–Orange")

    def test_face_labels(self) -> None:
        self.assertEqual(edge_label("DR", "faces"), "DR")


if __name__ == "__main__":
    unittest.main()
