import unittest

import demicode.util.image as img


class TestImage(unittest.TestCase):

    def test_box(self) -> None:
        self.assertEqual(
            img.box_in_box((1, 2, 3, 4), (10, 20, 30, 40)),
            (11, 22, 13, 24)
        )
