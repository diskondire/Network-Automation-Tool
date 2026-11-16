"""Low-contrast Windows-style Tkinter presentation helpers.

Keep platform-native ttk widgets; do not theme console output or vendor responses.
"""
from tkinter import ttk

ACCENT = '#245a84'
MUTED = '#536577'


def apply_theme(root):
    style = ttk.Style(root)
    available = style.theme_names()
    if 'vista' in available:
        style.theme_use('vista')
    elif 'clam' in available:
        style.theme_use('clam')
    style.configure('AppTitle.TLabel', font=('Segoe UI', 16, 'bold'))
    style.configure('AppSubtitle.TLabel', font=('Segoe UI', 9), foreground=MUTED)
    style.configure('SectionTitle.TLabel', font=('Segoe UI', 10, 'bold'))
    style.configure('Counter.TLabel', font=('Segoe UI', 9), foreground=MUTED)
    style.configure('StatusBar.TLabel', font=('Segoe UI', 9))
    style.configure('Action.TButton', padding=(10, 7))
    style.configure('Primary.Action.TButton', padding=(10, 7), font=('Segoe UI', 9, 'bold'))
    style.configure('Report.TLabelframe', padding=(8, 8))
    style.configure('Report.TLabelframe.Label', font=('Segoe UI', 9, 'bold'))
    return style
