"""Windows UI smoke tests for contextual controls and COM selection."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk

import console_capture


@unittest.skipUnless(sys.platform == 'win32', 'Windows Tk smoke test')
class OperatorUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.root_probe = tk.Tk()
        except tk.TclError as exc:
            self.skipTest('Tk display unavailable: ' + str(exc))
        self.root_probe.destroy()
        self.directory = tempfile.TemporaryDirectory()
        self.patch_base = patch.object(console_capture, 'BASE', Path(self.directory.name))
        self.patch_base.start()
        self.app = console_capture.App()
        self.app.root.update_idletasks()

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.root.destroy()
        if hasattr(self, 'patch_base'):
            self.patch_base.stop()
        if hasattr(self, 'directory'):
            self.directory.cleanup()

    def test_target_port_is_contextual(self):
        self.app.group_name.set('Burn In')
        self.app.single.set('display version')
        self.app.update_target_visibility()
        self.assertEqual(self.app.target_frame.winfo_manager(), '')
        self.app.single.set('display interface {interface}')
        self.app.update_target_visibility()
        self.assertEqual(self.app.target_frame.winfo_manager(), 'pack')

    def test_editor_does_not_grab_terminal_focus(self):
        self.app.edit_groups()
        windows = [child for child in self.app.root.winfo_children()
                   if isinstance(child, tk.Toplevel)]
        editor = next(win for win in windows if win.title() == 'Command Set Editor')
        self.assertIsNone(editor.grab_current())
        controls = list(editor.winfo_children())
        self.assertTrue(controls)
        editor.destroy()

    def test_com_manager_supports_extended_selection(self):
        self.app.open_com_manager()
        manager = self.app.com_manager
        def walk(parent):
            for child in parent.winfo_children():
                yield child
                yield from walk(child)
        trees = [child for child in walk(manager) if isinstance(child, ttk.Treeview)]
        self.assertEqual(len(trees), 1)
        self.assertEqual(str(trees[0].cget('selectmode')), 'extended')
        manager.destroy()


if __name__ == '__main__':
    unittest.main()
