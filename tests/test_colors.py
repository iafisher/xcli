import unittest

from xcli import colors


class ColorsTests(unittest.TestCase):
    def setUp(self):
        colors.on()

    def test_one_color(self):
        self.assertEqual(colors.red("test"), "\033[91mtest\033[0m")

    def test_can_turn_colors_off(self):
        colors.off()
        self.assertEqual(colors.red("test"), "test")

    def test_can_turn_colors_on(self):
        colors.off()
        self.assertEqual(colors.red("test"), "test")
        colors.on()
        self.assertEqual(colors.red("test"), "\033[91mtest\033[0m")
