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

    def test_command_set_actions_are_pinned_and_editable(self):
        self.app.edit_groups()
        windows = [child for child in self.app.root.winfo_children()
                   if isinstance(child, tk.Toplevel)]
        dialog = next(win for win in windows if win.title() == 'Command Set Editor')
        dialog.geometry('650x470+60+60')
        dialog.update_idletasks()

        def walk(parent):
            for child in parent.winfo_children():
                yield child
                yield from walk(child)

        buttons = [widget for widget in walk(dialog)
                   if isinstance(widget, ttk.Button)]
        labels = {widget.cget('text'): widget for widget in buttons}
        for label in ('Add new set', 'Delete set', 'Save changes',
                      '+ Add command', 'Edit command', 'Remove line', 'Close'):
            self.assertIn(label, labels)
            self.assertTrue(labels[label].cget('command'))
        save = labels['Save changes']
        self.assertIs(save.master.master, dialog,
                      'Save changes must be attached to a permanent footer')
        self.assertEqual(save.winfo_manager(), 'pack')
        self.assertGreater(save.winfo_height(), 0)
        self.assertLessEqual(save.winfo_rooty()+save.winfo_height(),
                             dialog.winfo_rooty()+dialog.winfo_height()+2)

        text_widgets = [widget for widget in walk(dialog)
                        if isinstance(widget, tk.Text)]
        self.assertEqual(len(text_widgets), 1)
        editor = text_widgets[0]
        editor.delete('1.0', 'end')
        labels['+ Add command'].invoke()
        editor.insert('insert', 'display version')
        self.assertIn('display version', editor.get('1.0', 'end'))
        dialog.destroy()

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
