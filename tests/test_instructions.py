from __future__ import annotations

import unittest

from puppet_edge_picker.algorithms import compiled_catalog, guide_algorithms
from puppet_edge_picker.cube import cube_orientation_sequences, rotation_face_mapping
from puppet_edge_picker.instructions import execution_steps, grip_description, grip_faces
from puppet_edge_picker.notation import face_turn_count, parse_algorithm


class InstructionTests(unittest.TestCase):
    def test_canonical_grip_is_named_by_faces(self) -> None:
        self.assertEqual(grip_faces(), ("F", "U", "R"))
        step = execution_steps("R U R'")[0]
        self.assertEqual(step.grip_name, "Green front, White up, Red right")

    def test_z_regrip_becomes_named_position(self) -> None:
        self.assertEqual(grip_faces(("Z",)), ("F", "L", "U"))
        steps = execution_steps("R U Z L F Z'")
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].grip_name, "Green front, White up, Red right")
        self.assertEqual(steps[1].grip_name, "Green front, Orange up, White right")
        self.assertEqual(steps[0].moves, ("R", "U"))
        self.assertEqual(steps[1].moves, ("L", "F"))

    def test_rotation_followed_by_inverse_restores_grip(self) -> None:
        for rotation in "XYZ":
            with self.subTest(rotation=rotation):
                inverse = f"{rotation}'"
                self.assertEqual(
                    rotation_face_mapping((rotation, inverse)),
                    rotation_face_mapping(()),
                )

    def test_all_24_orientations_have_unique_named_grips(self) -> None:
        grips = {grip_faces(sequence) for sequence in cube_orientation_sequences()}
        self.assertEqual(len(grips), 24)

    def test_every_catalog_algorithm_has_complete_grip_instructions(self) -> None:
        for entry in compiled_catalog():
            with self.subTest(name=entry.definition.name):
                steps = execution_steps(entry.tokens)
                self.assertTrue(steps)
                flattened = tuple(move for step in steps for move in step.moves)
                expected = tuple(move for move in entry.tokens if move[0] not in "XYZ")
                self.assertEqual(flattened, expected)
                self.assertEqual(sum(len(step.moves) for step in steps), entry.face_turn_count)
                for step in steps:
                    self.assertNotEqual(step.front_face, step.up_face)
                    self.assertNotEqual(step.front_face, step.right_face)
                    self.assertNotEqual(step.up_face, step.right_face)
                    self.assertTrue(step.grip_name)

    def test_every_published_algorithm_has_a_starting_position(self) -> None:
        expected_grips = {
            ("Y", "X2"): "Orange front, Yellow up, Blue right",
            ("Z2",): "Green front, Yellow up, Orange right",
        }
        for definition in guide_algorithms():
            with self.subTest(name=definition.name):
                self.assertEqual(
                    grip_description(definition.starting_rotation),
                    expected_grips[definition.starting_rotation],
                )
                steps = execution_steps(parse_algorithm(definition.moves))
                self.assertTrue(steps)
                self.assertEqual(
                    sum(len(step.moves) for step in steps),
                    face_turn_count(definition.moves),
                )


if __name__ == "__main__":
    unittest.main()
