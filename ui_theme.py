"""Windows-style visual presentation for Console Capture.

Icons are rendered from small vector-style primitives with Pillow. Keeping
them in Python makes the editable-source distribution self-contained.
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw

ACCENT = '#245A84'
MUTED = '#536577'
RIBBON_BG = '#F2F5F8'
RIBBON_HOVER = '#DCE9F4'


def theme_palette(mode='light'):
    if mode == 'dark':
        return dict(bg='#20272F',surface='#2B3540',fg='#ECF1F6',
                    subtle='#AAB9C8',accent='#6BB3EE',input='#19232D',
                    ribbon='#2B3540',hover='#3B5166',
                    terminal_bg='#0F1720',terminal_fg='#D4F1E2',
                    cursor='#F6D37B')
    return dict(bg='#F3F6FA',surface='#FFFFFF',fg='#243849',
                subtle='#526575',accent='#245A84',input='#FFFFFF',
                ribbon=RIBBON_BG,hover=RIBBON_HOVER,
                terminal_bg='#101820',terminal_fg='#DAF5E1',
                cursor='#F6D37B')


def apply_theme(root, mode='light'):
    """Use the same ttk palette for both application modes.

    The Windows Vista native theme ignores some requested foreground colors.
    Dark mode uses the configurable clam theme; light mode can use Vista.
    """
    p = theme_palette(mode)
    style = ttk.Style(root)
    available = style.theme_names()
    target = 'clam' if mode == 'dark' else ('vista' if 'vista' in available else 'clam')
    if target in available:
        style.theme_use(target)
    style.configure('.', background=p['bg'], foreground=p['fg'],
                    font=('Segoe UI', 9))
    style.configure('TFrame', background=p['bg'])
    style.configure('TLabel', background=p['bg'], foreground=p['fg'])
    style.configure('TLabelframe', background=p['bg'], foreground=p['fg'])
    style.configure('TLabelframe.Label', background=p['bg'], foreground=p['fg'])
    style.configure('TNotebook', background=p['bg'])
    style.configure('TNotebook.Tab', background=p['surface'], foreground=p['fg'],
                    padding=(12, 6))
    style.map('TNotebook.Tab', background=[('selected', p['bg'])])
    style.configure('TEntry', fieldbackground=p['input'], foreground=p['fg'])
    style.configure('TCombobox', fieldbackground=p['input'], foreground=p['fg'])
    style.configure('Treeview', background=p['input'], foreground=p['fg'],
                    fieldbackground=p['input'])
    style.map('Treeview', background=[('selected', p['accent'])],
              foreground=[('selected', '#FFFFFF')])
    style.configure('Treeview.Heading', background=p['surface'], foreground=p['fg'])
    style.configure('AppTitle.TLabel', font=('Segoe UI', 16, 'bold'))
    style.configure('AppSubtitle.TLabel', font=('Segoe UI', 9), foreground=p['subtle'])
    style.configure('SectionTitle.TLabel', font=('Segoe UI', 10, 'bold'))
    style.configure('Counter.TLabel', font=('Segoe UI', 9), foreground=p['subtle'])
    style.configure('StatusBar.TLabel', font=('Segoe UI', 9))
    style.configure('Action.TButton', padding=(10, 7))
    style.configure('Primary.Action.TButton', padding=(10, 7),
                    font=('Segoe UI', 9, 'bold'))
    style.configure('Report.TLabelframe', padding=(8, 8))
    style.configure('Report.TLabelframe.Label', font=('Segoe UI', 9, 'bold'))
    return style


ICON_NAMES = ('app', 'ports', 'connect', 'disconnect', 'captures',
              'word', 'diagnostics', 'appearance', 'history', 'terminal')


def render_icon(name, size=26):
    """Return an antialiased transparent icon as a Pillow RGBA image.

    Source coordinates use a 24x24 grid, supersampled 3x. The icon set uses
    restrained colors and consistent stroke widths, not external assets.
    """
    if name not in ICON_NAMES:
        raise ValueError('Unknown icon: ' + str(name))
    if not isinstance(size, int) or not 12 <= size <= 128:
        raise ValueError('Icon size must be an integer from 12 to 128')

    scale = size * 3 / 24
    canvas = Image.new('RGBA', (size * 3, size * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    blue, dark, green, red, amber = '#2D78A5', '#365166', '#26937D', '#BB4E56', '#C79237'
    line_width = max(2, round(scale * 1.8))

    def pt(x, y):
        return (round(x * scale), round(y * scale))

    def line(points, color=dark, width=1.8):
        d.line([pt(*pair) for pair in points], fill=color,
               width=max(2, round(width * scale)), joint='curve')

    def rect(x0, y0, x1, y1, outline=dark, fill=None, radius=2, width=1.7):
        d.rounded_rectangle([pt(x0, y0), pt(x1, y1)], radius=round(radius * scale),
                            outline=outline, fill=fill, width=max(2, round(width * scale)))

    def ellipse(x0, y0, x1, y1, outline=dark, fill=None, width=1.8):
        d.ellipse([pt(x0, y0), pt(x1, y1)], outline=outline, fill=fill,
                  width=max(2, round(width * scale)))

    def polygon(points, fill):
        d.polygon([pt(*p) for p in points], fill=fill)

    if name in ('app', 'terminal'):
        rect(2.5, 4, 21.5, 19, outline=blue, fill='#E8F2F8', radius=2)
        rect(2.5, 4, 21.5, 8, outline=blue, fill=blue, radius=1)
        line([(6, 11), (9, 13.5), (6, 16)], dark, 2)
        line([(11.5, 16.3), (17, 16.3)], green, 2)
        if name == 'app':
            ellipse(17, 2, 22, 7, outline=green, fill=green)
    elif name == 'ports':
        line([(4, 20), (9, 15), (12, 11), (12, 4)], blue, 2.1)
        line([(12, 11), (19, 11), (21, 9)], blue, 2)
        line([(12, 6), (9, 9)], blue, 2)
        polygon([(12, 1), (9, 5), (15, 5)], blue)
        rect(18, 7, 22, 11, outline=blue, fill='#E8F2F8', radius=0.5)
        ellipse(3, 18, 6, 21, outline=green, fill=green)
        rect(7.5, 8.5, 10.5, 11.5, outline=blue, fill=blue, radius=0.4)
    elif name in ('connect', 'disconnect'):
        rect(3, 7, 12, 17, outline=blue, fill='#E8F2F8')
        line([(5, 7), (5, 3)], blue)
        line([(10, 7), (10, 3)], blue)
        line([(12, 12), (17, 12)], dark, 2)
        if name == 'connect':
            line([(16, 9), (20, 12), (16, 15)], green, 2.3)
        else:
            line([(17, 9), (21, 15)], red, 2.3)
            line([(21, 9), (17, 15)], red, 2.3)
    elif name == 'captures':
        polygon([(2, 7), (9, 7), (11, 9), (22, 9), (21, 19), (3, 19)], '#D9EAF5')
        line([(2, 7), (3, 19), (21, 19), (22, 9), (11, 9), (9, 7), (2, 7)], blue, 1.7)
        rect(7, 3, 17, 7.8, outline=dark, fill='white', radius=0.4)
        line([(10, 13), (18, 13)], green, 1.8)
        line([(10, 16), (15, 16)], green, 1.8)
    elif name == 'word':
        polygon([(5, 2), (15, 2), (20, 7), (20, 22), (5, 22)], '#EDF3F8')
        line([(5, 2), (15, 2), (20, 7), (20, 22), (5, 22), (5, 2)], blue, 1.8)
        line([(15, 2), (15, 7), (20, 7)], blue)
        rect(2.5, 10, 16, 18, outline=blue, fill=blue, radius=1)
        line([(5, 12), (6.7, 16), (8.5, 13), (10, 16), (12.3, 12)], 'white', 1.6)
    elif name == 'diagnostics':
        rect(2, 4, 22, 19, outline=blue, fill='#EAF3F9')
        line([(4, 13), (8, 13), (10, 8), (13, 16), (15, 11), (20, 11)], green, 2)
        line([(9, 21), (15, 21)], dark)
    elif name == 'appearance':
        rect(2.5, 4, 18.5, 18, outline=blue, fill='#EDF4F8')
        line([(7, 21), (14, 21)], dark)
        line([(11, 18), (11, 21)], dark)
        ellipse(14, 2, 22, 10, outline=amber, fill='#FCE7B4')
        for p in [[(18, 0), (18, 2)], [(18, 10), (18, 12)], [(12, 6), (14, 6)], [(22, 6), (24, 6)]]:
            line(p, amber, 1.5)
    elif name == 'history':
        ellipse(4, 4, 20, 20, outline=blue, fill='#EDF4FA')
        line([(12, 7), (12, 12), (16, 14)], dark, 2)
        line([(4, 9), (1, 9), (1, 5)], green, 2)
        line([(1, 9), (6, 6)], green, 2)

    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def photo_icon(master, name, size=26):
    """Create a Tk image. Keep a Python reference while widgets are alive."""
    from PIL import ImageTk
    return ImageTk.PhotoImage(render_icon(name, size), master=master)


def ribbon_button(parent, master, text, icon_name, command, icon_refs):
    """Large enough clickable icon action for a classic Windows ribbon."""
    image = photo_icon(master, icon_name, 27)
    icon_refs.append(image)
    button = tk.Button(
        parent, text=text, image=image, compound='top', command=command,
        width=94, height=63, bg=RIBBON_BG, activebackground=RIBBON_HOVER,
        fg='#233D50', activeforeground='#172F42', relief='flat',
        bd=0, highlightthickness=0, padx=2, pady=4,
        font=('Segoe UI', 9), cursor='hand2',
    )
    button.bind('<Enter>', lambda _event: button.configure(bg=RIBBON_HOVER))
    button.bind('<Leave>', lambda _event: button.configure(bg=RIBBON_BG))
    button.pack(side='left', padx=2)
    return button
