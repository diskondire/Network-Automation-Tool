import unittest

from ui_theme import ICON_NAMES, render_icon


class IconTests(unittest.TestCase):
    def test_all_icons_are_valid_and_have_visible_pixels(self):
        for name in ICON_NAMES:
            with self.subTest(icon=name):
                img = render_icon(name, 28)
                self.assertEqual(img.mode, 'RGBA')
                self.assertEqual(img.size, (28, 28))
                self.assertIsNotNone(img.getchannel('A').getbbox())

    def test_resize_and_invalid_names(self):
        self.assertEqual(render_icon('app', 48).size, (48, 48))
        with self.assertRaises(ValueError):
            render_icon('unknown', 24)
        with self.assertRaises(ValueError):
            render_icon('ports', 0)


if __name__ == '__main__':
    unittest.main()
