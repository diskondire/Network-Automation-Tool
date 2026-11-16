"""Regression test: Word export's actions must remain visible on short screens."""
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from tkinter import ttk

from ui_theme import apply_theme
import console_capture


@unittest.skipUnless(sys.platform == 'win32', 'Tk window positioning checked on Windows CI')
class ExportDialogLayoutTests(unittest.TestCase):
    def test_export_button_stays_visible_when_window_is_short(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest('No interactive Tk display: ' + str(exc))
        try:
            root.geometry('350x230+30+30')
            apply_theme(root)
            app = console_capture.App.__new__(console_capture.App)
            app.root = root
            with tempfile.TemporaryDirectory() as folder:
                with patch.object(console_capture, 'BASE', Path(folder)):
                    app.open_word_export()
                    dialogs = [widget for widget in root.winfo_children()
                               if isinstance(widget, tk.Toplevel)]
                    self.assertEqual(len(dialogs), 1)
                    dialog = dialogs[0]
                    dialog.geometry('700x480+80+80')
                    root.update_idletasks()
                    self.assertTrue(dialog.winfo_exists())

                    def descendants(widget):
                        for child in widget.winfo_children():
                            yield child
                            yield from descendants(child)

                    buttons = [widget for widget in descendants(dialog)
                               if isinstance(widget, ttk.Button)]
                    labels = {button.cget('text'): button for button in buttons}
                    self.assertIn('Export selected captures', labels)
                    self.assertIn('Cancel', labels)
                    export_button = labels['Export selected captures']
                    self.assertTrue(export_button.cget('command'),
                                    'Export button has no connected action')
                    self.assertGreater(export_button.winfo_height(), 0)
                    self.assertGreaterEqual(export_button.winfo_rooty(),
                                            dialog.winfo_rooty())
                    self.assertLessEqual(
                        export_button.winfo_rooty() + export_button.winfo_height(),
                        dialog.winfo_rooty() + dialog.winfo_height() + 2)
                    self.assertTrue(export_button.winfo_ismapped(),
                                    'Export button not visible inside dialog')
                    dialog.destroy()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
