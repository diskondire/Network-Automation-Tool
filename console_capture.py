"""Console Capture v7.7 preview — operator workspace and Word evidence reports."""
import ctypes
import json
import os
import time
import threading
from queue import Queue, Empty
import re
import uuid
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import tkinter.font as tkfont
import serial
from serial.tools import list_ports
from PIL import Image, ImageDraw, ImageFont
from word_export import export_word
from capture_catalog import list_capture_runs, matches_capture
from ui_theme import apply_theme, photo_icon, ribbon_button, RIBBON_BG
from discovery import scan_available_ports, propose_matches, probe_port, candidates_for
from core import (transcript, prompt_kind, validate_profile, command_text, wrap_output,
                  defaults, new_profile, save_json, safe_name, PAGER, ERROR)

BASE = Path(__file__).resolve().parent
class Session:
    def __init__(self, app, profile):
        self.app, self.profile = app, dict(profile)
        self.ser = None
        self.raw = bytearray()
        self.visible = ''
        self.last_rx = time.monotonic()
        self.verified = False
        self.auto_allowed = False
        self.sent = set()
        self.password = ''
        self.seen_failure = False
        self.cli_hostname = None
        self.frame = ttk.Frame(app.tabs)
        app.tabs.add(self.frame, text=profile['name'])
        if hasattr(app, 'empty_state'):
            app.empty_state.place_forget()
        scroll = ttk.Scrollbar(self.frame)
        self.text = tk.Text(self.frame, font=('Consolas',int(app.terminal_font_size.get())), bg='#101820', fg='#daf5e1', wrap='char', state='disabled', yscrollcommand=scroll.set)
        # Disabled for edits, but keyboard events are sent directly over serial.
        self.text.bind('<KeyPress>', self.on_terminal_key)
        self.text.bind('<Button-1>', lambda event: self.text.focus_set())
        self.text.bind('<<Paste>>', lambda event: 'break')
        scroll.configure(command=self.text.yview)
        scroll.pack(side='right',fill='y'); self.text.pack(fill='both',expand=True)
        self.status = 'Disconnected'
        self.last_error = ''
        self.tx_bytes = 0
        self.rx_bytes = 0
    def close(self):
        if self.ser: self.ser.close()
        self.ser=None; self.verified=False; self.auto_allowed=False
        self.password=''; self.cli_hostname=None; self.status='Disconnected'
    def send(self, value):
        if not self.ser: raise RuntimeError('Connect this device first.')
        written = self.ser.write(value)
        self.tx_bytes = getattr(self, "tx_bytes", 0) + (written or 0)
    def on_terminal_key(self, event):
        # Leave the terminal display read-only; the device echoes its own input.
        # Never buffer locally typed passwords or commands in a second field.
        if not self.ser:
            self.app.status.set('Connect the selected COM port first.')
            return 'break'
        jobs = getattr(self.app, 'jobs', None)
        device_id = getattr(self, 'profile', {}).get('id')
        busy = (device_id in jobs if jobs is not None else bool(getattr(self.app, 'job', None) or getattr(self.app, 'capture', None)))
        if busy:
            self.app.status.set('Capture running on this device; wait for completion before manual input.')
            return 'break'
        keys = {
            'Return': b'\r', 'KP_Enter': b'\r', 'BackSpace': b'\x08',
            'Delete': b'\x1b[3~', 'Tab': b'\t',
            'Up': b'\x1b[A', 'Down': b'\x1b[B',
            'Right': b'\x1b[C', 'Left': b'\x1b[D',
            'Home': b'\x1b[H', 'End': b'\x1b[F',
            'Escape': b'\x1b',
        }
        try:
            control = event.state & 0x4
            if control:
                key = event.keysym.lower()
                if key == 'c': data = b'\x03'
                elif key == 'u': data = b'\x15'
                elif key == 'w': data = b'\x17'
                elif key == 'v':
                    # Never transmit clipboard contents implicitly.
                    self.app.status.set('Clipboard paste blocked for safety; type in terminal.')
                    return 'break'
                else: return 'break'
            elif event.keysym in keys:
                data = keys[event.keysym]
            elif event.char and ord(event.char) >= 32 and event.char != '\x7f':
                data = event.char.encode('utf-8')
            else:
                return 'break'
            # Manual CLI should not be blocked by saved hostname mismatch.
            # Turn off auto-reply as soon as a user takes keyboard control.
            self.auto_allowed = False
            self.send(data)
        except serial.SerialTimeoutException as exc:
            self.status = ('COM port is open, but sending timed out. '
                           'Check Flow control = None and the USB-to-serial adapter. '
                           'Details: ' + str(exc))
            self.last_error = self.status
            self.app.status.set(self.status)
        except Exception as exc:
            self.status = 'Terminal send failed: ' + str(exc)
            self.last_error = self.status
            self.app.status.set(self.status)
        return 'break'

    def redraw(self):
        value = transcript(self.raw)
        if self.password: value = value.replace(self.password, '[REDACTED]')
        self.visible = value
        scroll_position = self.text.yview()
        was_at_bottom = scroll_position[1] >= 0.98
        self.text.configure(state='normal'); self.text.delete('1.0','end')
        self.text.insert('end',value); self.text.configure(state='disabled')
        if was_at_bottom: self.text.see('end')
        else: self.text.yview_moveto(scroll_position[0])
    def poll(self):
        if not self.ser: return
        try:
            data = self.ser.read(min(self.ser.in_waiting,65536))
            if data:
                self.raw.extend(data); self.rx_bytes = getattr(self, "rx_bytes", 0) + len(data); self.last_rx=time.monotonic(); self.redraw()
                if len(self.raw)>8_000_000: raise RuntimeError('Output exceeded 8 MB; stopping connection.')
                if re_auth_failure(self.visible) and not self.seen_failure:
                    self.seen_failure=True; self.auto_allowed=False
                    self.status='Login failed. Automatic responses stopped; check credentials.'
                kind, host=prompt_kind(self.visible)
                if kind=='cli':
                    self.cli_hostname=host
                    self.verified=True
                    self.status='Connected: '+host+' ('+self.profile['port']+')'
                elif kind in ('username','password'):
                    self.verified=False; self.cli_hostname=None; self.status=kind.capitalize()+' required'
                    if self.auto_allowed and kind not in self.sent:
                        value=self.profile['username'] if kind=='username' else self.password
                        if value:
                            self.sent.add(kind); self.send(value.encode()+b'\r')
                            self.status='Sent saved '+kind+'; waiting for device'
                        else: self.status=kind.capitalize()+' required: enter credentials manually in the terminal.'
        except Exception as exc:
            self.last_error = 'Connection error: '+str(exc)
            self.close(); self.status=self.last_error

def re_auth_failure(value):
    import re
    return bool(re.search(r'(?:authentication|login)\s+(?:failed|failure)|incorrect password|invalid (?:password|username)',value,re.I))

class Capture:
    """Render the complete captured transcript to PNGs independently of GUI size/state.

    These are faithful text renderings of the received console transcript, not
    OS screenshots. This works even if the application is minimized.
    """
    def __init__(self, app, session, destination, callback):
        self.files = []
        try:
            self.files = self.save_transcript(
                session.visible, destination, int(app.font_size.get())
            )
            app.root.after(0, lambda: callback(None, self.files))
        except Exception as exc:
            error = str(exc)
            app.root.after(0, lambda: callback(error, self.files))

    @staticmethod
    def save_transcript(value, destination, font_size=11):
        font_path = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / 'consola.ttf'
        if not font_path.exists():
            font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
        try:
            font = ImageFont.truetype(str(font_path), max(9, font_size * 4 // 3))
        except OSError:
            font = ImageFont.load_default()

        # Fixed layout: no dependence on the visible Tkinter console viewport.
        columns = 120
        lines = wrap_output(value, columns)
        if not lines:
            lines = ['(No output received)']
        sample = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        bounds = sample.textbbox((0, 0), 'M', font=font)
        cell_w = max(7, bounds[2] - bounds[0])
        line_height = max(16, (bounds[3] - bounds[1]) + 7)
        pad = 20
        width = columns * cell_w + pad * 2
        page_lines = max(1, min(160, (8000 - 2 * pad) // line_height))
        filenames = []
        for start in range(0, len(lines), page_lines):
            page = len(filenames) + 1
            part = lines[start:start + page_lines]
            filename = destination if page == 1 else destination.with_name(
                f'{destination.stem}_part{page:02d}{destination.suffix}'
            )
            image = Image.new('RGB', (width, len(part) * line_height + 2 * pad), '#101820')
            draw = ImageDraw.Draw(image)
            for row, content in enumerate(part):
                draw.text((pad, pad + row * line_height), content, font=font, fill='#daf5e1')
            image.save(filename)
            filenames.append(filename.name)
        return filenames

class App:
    def __init__(self):
        #Title and window size
        self.root = tk.Tk()
        self.root.title("Console Capture v7.7 — UX Preview")
        self.root.geometry("1450x870")
        self.root.minsize(1090, 690)
        apply_theme(self.root)
        self._visual_icons=[]
        self._app_icon=photo_icon(self.root,'app',46)
        self._visual_icons.append(self._app_icon)
        self.root.iconphoto(True,self._app_icon)
        self.sessions={}; self.jobs={}; self.captures={}; self.last_jobs={}; self.discovery_active=False; self.discovery_queue=Queue()
        config=defaults()
        try:
            if (BASE/'device_profiles.json').exists(): config['profiles']=json.loads((BASE/'device_profiles.json').read_text(encoding='utf-8'))
            if (BASE/'command_groups.json').exists(): config['groups']=json.loads((BASE/'command_groups.json').read_text(encoding='utf-8'))
        except Exception as exc:
            messagebox.showerror('Settings',f'Could not load settings: {exc}\nClose the app and repair the JSON before proceeding.'); self.root.destroy(); raise SystemExit(1)
        self.legacy_profiles=config['profiles']; self.profiles=[]; self.groups=config['groups']
        self.port_results={}; self.port_scan_active=False; self.port_scan_queue=Queue()
        self.serial_settings={}  # Per-COM settings, not device-role profiles
        if not any(g.get('name','').casefold()=='burn in' for g in self.groups):
            self.groups.append({'name': 'Burn In', 'target': 'Any', 'commands': ['display clock', 'display version', 'display device esn', 'display cpu-usage', 'display memory all', 'display device power system', 'display device temperature', 'display device fan', 'display alarm active']})
        self.selected=None
        # A compact informational header, not a second row of duplicate buttons.
        header=ttk.Frame(self.root,padding=(14,9,14,9))
        header.pack(side='top',fill='x')
        brand=ttk.Frame(header);brand.pack(side='left')
        ttk.Label(brand,image=self._app_icon).pack(side='left',padx=(0,10))
        brand_titles=ttk.Frame(brand);brand_titles.pack(side='left')
        ttk.Label(brand_titles,text='Console Capture v7.7',style='AppTitle.TLabel').pack(anchor='w')
        ttk.Label(brand_titles,text='Made by Tom Chan',style='AppSubtitle.TLabel').pack(anchor='w')
        self.workspace_summary=tk.StringVar(value='No active connections')
        ttk.Label(header,textvariable=self.workspace_summary,style='Counter.TLabel').pack(side='right',padx=12)
        ttk.Separator(self.root).pack(side='top',fill='x')

        # Windows-style icon ribbon: main navigation and common actions.
        ribbon=tk.Frame(self.root,bg=RIBBON_BG,height=79)
        ribbon.pack(side='top',fill='x')
        actions=tk.Frame(ribbon,bg=RIBBON_BG)
        actions.pack(side='left',padx=12,pady=5)
        def ribbon_action(label,icon,callback):
            return ribbon_button(actions,self.root,label,icon,callback,self._visual_icons)
        def ribbon_divider():
            tk.Frame(actions,bg='#CAD5DE',width=1,height=49).pack(side='left',padx=7,pady=7)
        ribbon_action('COM Ports','ports',self.open_com_manager)
        ribbon_action('Connect','connect',self.connect)
        ribbon_action('Disconnect','disconnect',self.disconnect)
        ribbon_divider()
        ribbon_action('Captures','captures',self.open_captures)
        ribbon_action('Word Export','word',self.open_word_export)
        ribbon_divider()
        ribbon_action('Diagnostics','diagnostics',self.open_diagnostics_window)
        ribbon_action('Appearance','appearance',self.open_appearance_window)
        ribbon_action('History','history',self.open_version_history)
        ttk.Separator(self.root).pack(side='top',fill='x')

        footer=ttk.Frame(self.root,padding=(12,5,12,6))
        footer.pack(side='bottom',fill='x')
        self.activity_summary=tk.StringVar(value='Ready · Discover COM ports to begin')
        ttk.Label(footer,textvariable=self.activity_summary,style='StatusBar.TLabel').pack(side='left')
        self.run_progress=tk.DoubleVar(value=0)
        ttk.Progressbar(footer,maximum=100,variable=self.run_progress,length=150).pack(side='right',padx=(8,0))
        self.run_progress_label=tk.StringVar(value='Idle')
        ttk.Label(footer,textvariable=self.run_progress_label,style='Counter.TLabel').pack(side='right')
        ttk.Separator(self.root).pack(side='bottom',fill='x')
        body=ttk.Frame(self.root); body.pack(fill='both',expand=True)
        left=ttk.Frame(body,padding=8,width=278)
        left.pack(side='left',fill='y')
        left.pack_propagate(False)
        center=ttk.Frame(body); center.pack(side='left',fill='both',expand=True)
        # Scrollable right panel prevents lower controls from being hidden on laptop screens.
        right_holder=ttk.Frame(body);right_holder.pack(side='right',fill='y')
        right_scroll=ttk.Scrollbar(right_holder,orient='vertical')
        right_scroll.pack(side='right',fill='y')
        right_canvas=tk.Canvas(right_holder,width=360,highlightthickness=0,
                               yscrollcommand=right_scroll.set)
        right_canvas.pack(side='left',fill='both',expand=True)
        right_scroll.configure(command=right_canvas.yview)
        right=ttk.Frame(right_canvas,padding=8)
        right_window=right_canvas.create_window((0,0),window=right,anchor='nw')
        right.bind('<Configure>',lambda e:right_canvas.configure(scrollregion=right_canvas.bbox('all')))
        right_canvas.bind('<Configure>',lambda e:right_canvas.itemconfigure(right_window,width=e.width))

        # Sidebar navigator: live sessions and historical captures are distinct.
        self.left_tabs=ttk.Notebook(left)
        self.left_tabs.pack(fill='both',expand=True)
        devices_page=ttk.Frame(self.left_tabs,padding=6)
        history_page=ttk.Frame(self.left_tabs,padding=6)
        device_tab_icon=photo_icon(self.root,'ports',16)
        capture_tab_icon=photo_icon(self.root,'captures',16)
        self._visual_icons.extend((device_tab_icon,capture_tab_icon))
        self.left_tabs.add(devices_page,text='Devices',image=device_tab_icon,compound='left')
        self.left_tabs.add(history_page,text='Captures',image=capture_tab_icon,compound='left')

        ttk.Label(devices_page,text='LIVE DEVICE SESSIONS',style='SectionTitle.TLabel').pack(anchor='w')
        self.device_count=tk.StringVar(value='No discovered devices')
        ttk.Label(devices_page,textvariable=self.device_count,style='Counter.TLabel').pack(anchor='w',pady=(3,9))
        self.profile_list=tk.Listbox(devices_page,height=12,exportselection=False,width=28,
                                    selectbackground='#2865a6',selectforeground='white',
                                    font=('Segoe UI',10),relief='solid',borderwidth=1)
        self.profile_list.pack(fill='both',expand=True)
        self.profile_list.bind('<<ListboxSelect>>',self.select_profile)
        self.active_port_label=ttk.Label(devices_page,text='Port: —')
        self.active_port_label.pack(anchor='w',pady=(9,0))
        self.active_host_label=ttk.Label(devices_page,text='Hostname: Unknown',wraplength=225)
        self.active_host_label.pack(anchor='w')
        self.active_status_label=tk.Label(devices_page,text='Not connected',anchor='w',
                                         bg='#E9EDF1',fg='#30495C',padx=9,pady=5,
                                         font=('Segoe UI',9,'bold'))
        self.active_status_label.pack(fill='x',pady=(7,10))
        ttk.Button(devices_page,text='Connect device',command=self.connect,
                   style='Action.TButton').pack(fill='x',pady=(2,4))
        ttk.Button(devices_page,text='Disconnect device',command=self.disconnect,
                   style='Action.TButton').pack(fill='x')

        ttk.Label(history_page,text='SAVED COMMAND EVIDENCE',style='SectionTitle.TLabel').pack(anchor='w')
        self.recent_count=tk.StringVar(value='No captures')
        ttk.Label(history_page,textvariable=self.recent_count,
                  style='Counter.TLabel').pack(anchor='w',pady=(3,9))
        self.recent_capture_list=tk.Listbox(history_page,height=13,width=27,
                                            font=('Segoe UI',9),selectbackground='#2865a6',
                                            selectforeground='white',exportselection=False)
        self.recent_capture_list.pack(fill='both',expand=True)
        self.recent_capture_list.bind('<Double-Button-1>',lambda _event:self.open_selected_capture())
        self._recent_runs=[]
        ttk.Label(history_page,text='Double-click to open the saved run folder.',
                  style='Counter.TLabel',wraplength=230).pack(anchor='w',pady=(6,8))
        ttk.Button(history_page,text='Open selected capture',
                   command=self.open_selected_capture,style='Action.TButton').pack(fill='x',pady=(0,4))
        ttk.Button(history_page,text='Refresh list',
                   command=self.refresh_recent_captures).pack(fill='x')

        # Only session-specific fields are retained; no Device Profiles editor.
        self.fields={key:tk.StringVar(value='') for key in ('name','ip','port','baud','parity','stopbits','flow','timeout')}
        self.fields['interface']=tk.StringVar(value='MultiGE 1/0/1')
        self.port_box=None
        self.terminal_font_size=tk.StringVar(value='11')
        self.center_controls=ttk.Frame(center,padding=(7,4))
        self.center_controls.pack(side='bottom',fill='x')
        # Cancellation is adjacent to Run, not buried below the terminal.
        self.stop_button=None
        self.tabs=ttk.Notebook(center); self.tabs.pack(fill='both',expand=True)
        self.tabs.bind('<<NotebookTabChanged>>',self.tab_changed)
        # Actionable empty state, hidden automatically when a terminal is opened.
        self.empty_state=ttk.Frame(self.tabs,padding=24)
        self.empty_state.place(relx=0.5,rely=0.43,anchor='center')
        home_icon=photo_icon(self.root,'terminal',58)
        self._visual_icons.append(home_icon)
        ttk.Label(self.empty_state,image=home_icon).pack(pady=(0,10))
        ttk.Label(self.empty_state,text='Your console workspace',
                  font=('Segoe UI',15,'bold')).pack(pady=(0,7))
        ttk.Label(self.empty_state,
                  text='Discover a COM port, check its response, and connect to begin.\n'
                       'Capture CLI evidence and prepare Word reports from the same workspace.',
                  justify='center',wraplength=430).pack(pady=(0,16))
        home_actions=ttk.Frame(self.empty_state);home_actions.pack()
        for label,action in [('Find COM ports',self.open_com_manager),
                             ('Browse captures',self.open_captures),
                             ('Word reports',self.open_word_export)]:
            ttk.Button(home_actions,text=label,command=action,
                       style='Action.TButton').pack(side='left',padx=5)
        # The terminal Text widget handles keyboard input directly.
        self.status=tk.StringVar(value='Discover COM ports to begin.'); ttk.Label(center,textvariable=self.status,wraplength=650,padding=8).pack(fill='x')
        # Login prompts are handled manually in the terminal until that workflow is redesigned.
        # Preserve inert session-local variables for compatibility with older session helpers.
        self.username=tk.StringVar(value='')
        self.password=tk.StringVar(value='')
        self.auto=tk.BooleanVar(value=False)
        self.remember=tk.BooleanVar(value=False)

        # Interface is a command parameter, NOT a connection setting.
        # Editable per device; required only by commands containing {interface}.
        target_frame=ttk.LabelFrame(right,text='PORT-SPECIFIC COMMANDS',padding=8)
        self.target_frame=target_frame
        ttk.Label(target_frame,text='Only commands containing {interface} use this port name.',wraplength=305).pack(anchor='w')
        self.interface_box=ttk.Combobox(
            target_frame,textvariable=self.fields['interface'],width=29,
            values=['MultiGE 1/0/1','GigabitEthernet 0/0/1','XGigabitEthernet 0/0/1',
                    'GE 1/0/1','XGE 1/0/1','10GE 1/0/1','Eth-Trunk 1'])
        self.interface_box.pack(fill='x',pady=(5,2))
        self.interface_box.bind('<<ComboboxSelected>>',self.apply_interface)
        self.interface_box.bind('<FocusOut>',self.apply_interface)
        self.interface_box.bind('<Return>',self.apply_interface)
        ttk.Label(target_frame,text='Choose a physical port, e.g. MultiGE 1/0/1. No reconnect required.',wraplength=305).pack(anchor='w')

        # Clear task-oriented command workspace; vendor command sets remain editable.
        commands_panel=ttk.LabelFrame(right,text='COMMAND AUTOMATION',padding=9,style='Report.TLabelframe')
        commands_panel.pack(fill='x',pady=(0,9))
        ttk.Label(commands_panel,text='Command set',style='SectionTitle.TLabel').pack(anchor='w')
        self.group_name=tk.StringVar()
        self.group_box=ttk.Combobox(commands_panel,textvariable=self.group_name,state='readonly',width=27)
        self.group_box.pack(fill='x',pady=(4,7))
        self.group_box.bind('<<ComboboxSelected>>',self.update_target_visibility)
        editor_row=ttk.Frame(commands_panel);editor_row.pack(fill='x',pady=(0,7))
        ttk.Button(editor_row,text='Manage sets',command=self.edit_groups).pack(side='left',fill='x',expand=True,padx=(0,3))
        ttk.Button(editor_row,text='Preview',command=self.preview_command_group).pack(side='left',fill='x',expand=True,padx=(3,0))
        ttk.Button(commands_panel,text='Run selected group',command=self.run_group,style='Primary.Action.TButton').pack(fill='x',pady=(0,4))
        ttk.Button(commands_panel,text='Run on multiple devices...',command=self.run_multiple,style='Action.TButton').pack(fill='x')
        self.stop_button=ttk.Button(commands_panel,text='Cancel current run',command=self.stop)
        self.stop_button.pack(fill='x',pady=(6,0))

        queue_panel=ttk.LabelFrame(right,text='EXECUTION QUEUE',padding=9,style='Report.TLabelframe')
        queue_panel.pack(fill='x',pady=(0,9))
        self.queue_list=tk.Listbox(queue_panel,height=6,width=34,exportselection=False,font=('Consolas',9))
        self.queue_list.pack(fill='x')
        self.all_jobs_label=ttk.Label(queue_panel,text='Selected device: no run',wraplength=280,justify='left')
        self.all_jobs_label.pack(fill='x',pady=(6,0))

        single_panel=ttk.LabelFrame(right,text='SINGLE COMMAND',padding=9,style='Report.TLabelframe')
        single_panel.pack(fill='x',pady=(0,9))
        self.single=tk.StringVar(value='display version')
        self.single_entry=ttk.Entry(single_panel,textvariable=self.single,width=28)
        self.single_entry.pack(fill='x',pady=(0,6))
        ttk.Label(single_panel,text='Save capture under command set',style='Counter.TLabel').pack(anchor='w')
        self.single_group=tk.StringVar(value='Single command')
        self.single_group_box=ttk.Combobox(single_panel,textvariable=self.single_group,state='readonly')
        self.single_group_box.pack(fill='x',pady=(4,6))
        ttk.Button(single_panel,text='Capture on selected device',command=self.run_single,style='Action.TButton').pack(fill='x')
        ttk.Button(single_panel,text='Capture on multiple devices...',command=self.run_single_multiple).pack(fill='x',pady=(5,0))

        export_panel=ttk.LabelFrame(right,text='WORD REPORTS',padding=9,style='Report.TLabelframe')
        export_panel.pack(fill='x',pady=(0,8))
        ttk.Label(export_panel,text='Export saved command evidence using a Word template.',wraplength=290).pack(anchor='w')
        ttk.Button(export_panel,text='Export captured evidence...',command=self.open_word_export,style='Action.TButton').pack(fill='x',pady=(7,0))
        # Terminal appearance and connection diagnostics moved to toolbar dialogs.
        self.font_size=tk.StringVar(value='11')
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh_profiles(); self.refresh_groups(); self.refresh_ports()
        self.refresh_recent_captures()
        self.tick()
        self.root.after(250,self.open_com_manager)


    @staticmethod
    def display_timestamp(value):
        """UI-only DD:MM:YY (HH:MM); retain ISO-8601 internally."""
        try:
            return datetime.fromisoformat(str(value).replace('Z','+00:00')).strftime('%d-%m-%y (%H:%M)')
        except (TypeError,ValueError):
            return str(value or 'Unknown date')

    def open_version_history(self):
        win=tk.Toplevel(self.root)
        win.title('Console Capture — Version History')
        win.geometry('780x590');win.transient(self.root)
        ttk.Label(win,text='Version History',font=('Segoe UI',14,'bold'),padding=(14,14,14,6)).pack(anchor='w')
        ttk.Label(win,text='Documented project milestones (not every intermediate build has a verified changelog).',padding=(14,0,14,9)).pack(anchor='w')
        panel=ttk.Frame(win,padding=(12,2,12,12));panel.pack(fill='both',expand=True)
        text=tk.Text(panel,wrap='word',font=('Segoe UI',10),state='normal',padx=12,pady=10)
        scroll=ttk.Scrollbar(panel,command=text.yview);text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True)
        history=[
            ('v7.7 preview','Icon ribbon, Devices/Captures sidebar, status indicators, guided home screen, activity bar and searchable Word capture history. Built from v7.6.4.'),
            ('v7.6.4','Combined Burn-In inventory rows share one cover page; evidence tables repeat by device; DD-MM-YY timestamps; simplified Windows menu.'),
            ('v7.6.3','Cancel controls and per-device status colors; readable export dates; combined template export per device; Windows-style menu and version history.'),
            ('v7.6.2','Huawei CloudEngine model recognition; screenshots sized to Word table cells.'),
            ('v7.6.1','Custom Burn-In Word templates; metadata tokens and command-image placeholders inside tables.'),
            ('v7.6','Top utility toolbar; Word template export introduced.'),
            ('v7.5.1','Huawei abbreviated commands and output filters; simplified login panel and optional interface parameter.'),
            ('v7.5','COM response checking without a separate connection step; bounded Enter probing.'),
            ('v7.4','Serial settings and command sets separated; session persistence; USB/Bluetooth grouping and consolidated connection status.'),
            ('v7.3','Connected-device-oriented left panel and separate profile settings.'),
            ('v7.2','Restored hostname and device-response probing during COM discovery.'),
            ('v7.1','Response checking and connection state added to port manager.'),
            ('v7.0 trial','Port-first workflow; optional hostnames; manual port entry initially trialled.'),
            ('v6.5','COM manager, parallel command execution, Stop Selected Run and Word evidence export.'),
            ('v6.1','Per-run PNG/TXT/BIN capture folders with summary.json.'),
            ('v6.0','Console fixes, execution queue, connection diagnostics and Burn In command set.'),
            ('Earlier prototypes / v3','Python/pySerial console automation, command evidence files, transcript screenshots, and capture status tracking.'),
        ]
        text.tag_configure('heading',font=('Segoe UI',10,'bold'),spacing1=12,spacing3=3)
        for version,details in history:
            text.insert('end',version+'\n','heading')
            text.insert('end',details+'\n')
        text.configure(state='disabled')
        ttk.Button(win,text='Close',command=win.destroy).pack(anchor='e',padx=14,pady=(0,12))

    def _device_run_color(self, profile_id):
        job=self.jobs.get(profile_id)
        if job: return '#ffe0a3'  # orange: in progress / paused
        last=self.last_jobs.get(profile_id)
        if last:
            state=last.get('final_status')
            if state=='completed':return '#c5ecc5'
            if state in ('failed','partial','stopped'):return '#ffcccc'
        return '#ffffff'  # white: no command run

    def refresh_device_colors(self):
        for index,profile in enumerate(self.profiles):
            if index<self.profile_list.size():
                self.profile_list.itemconfig(index,bg=self._device_run_color(profile['id']),fg='#202020')

    def open_appearance_window(self):
        win=tk.Toplevel(self.root)
        win.title('Terminal Appearance')
        win.geometry('390x245')
        win.transient(self.root)
        panel=ttk.Frame(win,padding=16); panel.pack(fill='both',expand=True)
        ttk.Label(panel,text='Display settings',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,12))
        ttk.Label(panel,text='Live terminal font size').pack(anchor='w')
        box=ttk.Combobox(panel,textvariable=self.terminal_font_size,
                         values=['9','10','11','12','13','14','16','18'],state='readonly',width=16)
        box.pack(anchor='w',pady=(4,12));box.bind('<<ComboboxSelected>>',self.update_terminal_appearance)
        ttk.Label(panel,text='Screenshot font size').pack(anchor='w')
        screenshot=ttk.Combobox(panel,textvariable=self.font_size,
                                values=['9','10','11','12','13','14','16'],state='readonly',width=16)
        screenshot.pack(anchor='w',pady=(4,10))
        ttk.Label(panel,text='Screenshots are rendered from the full transcript, not the window size.',
                  wraplength=340).pack(anchor='w')

    def open_diagnostics_window(self):
        win=tk.Toplevel(self.root)
        win.title('Connection Diagnostics')
        win.geometry('670x400')
        win.transient(self.root)
        outer=ttk.Frame(win,padding=12);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='Selected device / session diagnostics',font=('Segoe UI',11,'bold')).pack(anchor='w')
        view=tk.Text(outer,height=14,wrap='word',font=('Consolas',10))
        view.pack(fill='both',expand=True,pady=10)
        def refresh():
            view.configure(state='normal');view.delete('1.0','end');view.insert('end',self.diagnostic_text());view.configure(state='disabled')
        actions=ttk.Frame(outer);actions.pack(fill='x')
        ttk.Button(actions,text='Refresh',command=refresh).pack(side='left',padx=(0,8))
        ttk.Button(actions,text='Copy diagnostics',command=self.copy_diagnostics).pack(side='left')
        refresh()

    def update_console_font(self, event=None):
        pass  # Screenshot rendering uses this setting; terminal font is independent.

    @property
    def job(self):
        jobs = getattr(self, 'jobs', None)
        if jobs is None:
            return getattr(self, '_legacy_job', None)
        return jobs.get(getattr(self, 'selected', None))

    @job.setter
    def job(self, value):
        jobs = getattr(self, 'jobs', None)
        if jobs is None:
            self._legacy_job = value
        elif value is None:
            jobs.pop(getattr(self, 'selected', None), None)
        else:
            jobs[getattr(self, 'selected', None)] = value

    @property
    def capture(self):
        captures = getattr(self, 'captures', None)
        if captures is None:
            return getattr(self, '_legacy_capture', None)
        return captures.get(getattr(self, 'selected', None))

    @capture.setter
    def capture(self, value):
        captures = getattr(self, 'captures', None)
        if captures is None:
            self._legacy_capture = value
        elif value is None:
            captures.pop(getattr(self, 'selected', None), None)
        else:
            captures[getattr(self, 'selected', None)] = value

    def busy(self, profile_id=None):
        device_id = profile_id if profile_id is not None else getattr(self, 'selected', None)
        jobs = getattr(self, 'jobs', None)
        active = (device_id in jobs if jobs is not None else bool(self.job or self.capture))
        if active:
            messagebox.showinfo('Busy', 'This device has an active automation run. You can use other devices.')
        return active

    def persist(self):
        # Do not persist temporary COM-to-device associations or credentials.
        save_json(BASE/'command_groups.json',self.groups)
    def refresh_ports(self):
        pass
    def show_error_details(self,title,details,parent=None):
        window=tk.Toplevel(parent or self.root)
        window.title(title)
        window.geometry('750x460')
        window.transient(parent or self.root)
        view=tk.Text(window,wrap='word',font=('Consolas',10))
        view.pack(fill='both',expand=True,padx=10,pady=10)
        view.insert('1.0',details)
        view.configure(state='disabled')
        controls=ttk.Frame(window);controls.pack(fill='x',padx=10,pady=(0,10))
        ttk.Button(controls,text='Copy details',command=lambda:self.root.clipboard_clear() or self.root.clipboard_append(details)).pack(side='left')
        ttk.Button(controls,text='Close',command=window.destroy).pack(side='right')

    def error_details(self,reason,j=None):
        lines=[f'Reason: {reason}']
        if j:
            session=j['session']
            lines.extend([f'Device: {session.profile.get("name", "Unknown")}',f'COM port: {session.profile.get("port", "Unknown")}',f'Last command: {j.get("command") or "None"}',f'Command number: {j.get("index",0)+1}'])
            tail=session.visible[-6000:] if session.visible else '(no output received)'
            if session.password:tail=tail.replace(session.password,'[REDACTED]')
            lines.extend(['', 'Last received terminal output:',tail])
        return '\n'.join(lines)

    def connect_discovered_port(self, port, settings=None):
        """Open exactly one app-owned session per COM port; hostname not required."""
        port=port.strip().upper()
        if not re.fullmatch(r'COM[1-9][0-9]*',port):
            raise ValueError('Invalid Windows COM port.')
        existing=next((x for x in self.profiles if x.get('port','').upper()==port),None)
        if existing is None:
            existing=new_profile('Session')
            existing.update(name=port,port=port,role='Any',hostname='',username='',auto_login=False)
            self.profiles.append(existing)
        if settings:
            existing.update(settings)
            self.serial_settings[port]={k:existing[k] for k in ('baud','parity','stopbits','flow','timeout')}
        elif port in self.serial_settings:
            existing.update(self.serial_settings[port])
        self.selected=existing['id']
        self.refresh_profiles()
        if not (self.sessions.get(self.selected) and self.sessions[self.selected].ser):
            self.connect()
        session=self.sessions.get(self.selected)
        if session and session.ser:
            self.port_results.setdefault(port,{})['disconnected']=False
            self.tabs.select(session.frame)
            session.text.focus_set()
            return True
        return False

    def _port_class(self, item):
        description=(getattr(item,'description','') or '').lower()
        hwid=(getattr(item,'hwid','') or '').lower()
        if 'bluetooth' in description or 'bthenum' in hwid or 'bth' in hwid:
            return 'Bluetooth'
        if 'usb' in description or 'usb' in hwid or getattr(item,'vid',None) is not None:
            return 'USB'
        return 'Other / Unknown'

    def _scan_ports(self):
        """Run v6.5-compatible serial probes off the Tk thread, retaining results."""
        if self.port_scan_active:return
        try: found=list(list_ports.comports())
        except Exception as exc:
            self.status.set('COM enumeration failed: '+str(exc));return
        found_ports=set()
        for item in found:
            port=item.device.upper();found_ports.add(port)
            record=self.port_results.setdefault(port,{})
            record.update(category=self._port_class(item),description=item.description or '',present=True)
            record.setdefault('hostname',None)
            record.setdefault('probe_status','Not checked')
        for port,record in self.port_results.items():
            if port not in found_ports:record['present']=False;record['probe_status']='Not present'
        if not found:
            self.status.set('No COM ports reported by Windows.');return
        self.port_scan_active=True
        snapshot=[dict(p) for p in self.legacy_profiles]
        for port,setting in self.serial_settings.items():snapshot.append(dict(port=port,**setting))
        busy={s.profile['port'].upper() for s in self.sessions.values() if s.ser}
        def worker():
            for item in found:
                port=item.device.upper()
                if port in busy:
                    self.port_scan_queue.put(('result',port,None,'Open in Console Capture'))
                else:
                    try:
                        hostname,detail=probe_port(port,candidates_for(port,snapshot))
                    except Exception as exc:
                        hostname,detail=None,'Probe error: '+str(exc)[:120]
                    self.port_scan_queue.put(('result',port,hostname,detail))
            self.port_scan_queue.put(('done',len(found),None,None))
        threading.Thread(target=worker,daemon=True).start()
        self._scan_total=len(found);self._scan_done=0
        self._poll_port_scan()

    def _poll_port_scan(self):
        finished=False
        while True:
            try:kind,port,host,detail=self.port_scan_queue.get_nowait()
            except Empty:break
            if kind=='done':finished=True;continue
            self._scan_done+=1
            row=self.port_results.setdefault(port,{})
            if host:row['hostname']=host
            row['probe_status']=detail
            row['disconnected']=False
        if finished:
            self.port_scan_active=False
            self.status.set(f'COM discovery complete: {self._scan_done}/{self._scan_total} checked.')
        else:
            self.root.after(100,self._poll_port_scan)

    def _operational_status(self, port, row):
        sess=next((s for s in self.sessions.values() if s.profile.get('port','').upper()==port and s.ser),None)
        if sess:
            if sess.cli_hostname:return 'Connected · '+sess.cli_hostname
            if prompt_kind(sess.visible)[0] in ('username','password'):return 'Login required'
            if sess.rx_bytes:return 'Connected · responding'
            return 'Connected · no response'
        if not row.get('present',False):return 'Not present'
        if row.get('disconnected'):return 'Not connected'
        detail=row.get('probe_status','Not checked')
        if detail.startswith('Unavailable'):return 'Unavailable'
        if 'Login required' in detail:return 'Login required'
        if row.get('hostname'):return 'Responding · not connected'
        if detail.startswith('CLI prompt'):return 'Responding · not connected'
        if detail.startswith('Response received'):return 'Responding · hostname unknown'
        if detail.startswith('No response'):return 'No response'
        if detail.startswith('Probe error'):return 'Probe error'
        return 'Not connected'

    def open_com_manager(self):
        """Persistent in-app discovery state; window closing never resets sessions."""
        existing=getattr(self,'com_manager',None)
        if existing is not None and existing.winfo_exists():
            existing.deiconify();existing.lift();existing.focus_force();return
        win=tk.Toplevel(self.root);self.com_manager=win
        win.title('COM Port Manager — Console Capture')
        win.geometry('960x630');win.minsize(760,480)
        win.protocol('WM_DELETE_WINDOW',win.withdraw)
        ttk.Label(win,text='Discover ports; use Ctrl/Shift to select multiple devices, then Connect Selected.',padding=10).pack(anchor='w')
        top=ttk.Frame(win,padding=(10,4));top.pack(fill='x')
        ttk.Label(top,text='Serial connection speed:').pack(side='left')
        speed=tk.StringVar(value='Auto (detected)')
        speed_box=ttk.Combobox(top,textvariable=speed,values=['Auto (detected)','9600 / 8N1','115200 / 8N1','Custom...'],state='readonly',width=19)
        speed_box.pack(side='left',padx=(5,12))
        custom={'baud':9600,'parity':'N','stopbits':1,'flow':'None','timeout':60}
        def edit_serial():
            editor=tk.Toplevel(win);editor.title('Serial connection settings');editor.geometry('335x310');editor.transient(win)
            inputs={}
            for key,label,options in [('baud','Speed (bps)',None),('parity','Parity',['N','E','O']),('stopbits','Stop bits',['1','2']),('flow','Flow control',['None','RTS/CTS','XON/XOFF']),('timeout','Command timeout (seconds)',None)]:
                line=ttk.Frame(editor,padding=(10,3));line.pack(fill='x')
                ttk.Label(line,text=label,width=26).pack(side='left')
                var=tk.StringVar(value=str(custom[key]));inputs[key]=var
                if options:ttk.Combobox(line,textvariable=var,values=options,state='readonly',width=11).pack(side='right')
                else:ttk.Entry(line,textvariable=var,width=13).pack(side='right')
            def apply():
                try:
                    values={k:v.get() for k,v in inputs.items()}
                    values['baud']=int(values['baud']);values['stopbits']=int(values['stopbits']);values['timeout']=int(values['timeout'])
                    if values['baud']<=0 or not 5<=values['timeout']<=600:raise ValueError('Invalid baud or timeout.')
                    custom.update(values);speed.set('Custom...');editor.destroy()
                except Exception as exc:messagebox.showerror('Serial settings',str(exc),parent=editor)
            ttk.Button(editor,text='Apply',command=apply).pack(pady=12)
        ttk.Button(top,text='Edit Serial Settings...',command=edit_serial).pack(side='left')
        columns=('port','hostname','status','description')
        tree=ttk.Treeview(win,columns=columns,show='tree headings',selectmode='extended')
        tree.heading('#0',text='Connection Type');tree.column('#0',width=170,stretch=False)
        for key,label,width in [('port','Port',90),('hostname','Hostname',170),('status','Status',240),('description','Windows Description',260)]:
            tree.heading(key,text=label);tree.column(key,width=width,stretch=key in ('status','description'))
        for label in ('USB','Bluetooth','Other / Unknown'):
            tree.insert('', 'end',iid='group:'+label,text=label,open=True)
        tree.pack(fill='both',expand=True,padx=10,pady=8)
        details=tk.StringVar(value='Select a COM port to see identify the connection. No credentials are sent during discovery.')
        ttk.Label(win,textvariable=details,padding=(10,4),wraplength=850).pack(anchor='w')
        progress=tk.IntVar(value=0)
        bottom=ttk.Frame(win,padding=(10,6));bottom.pack(side='bottom',fill='x')
        progress_label=tk.StringVar(value='Ready')
        ttk.Label(bottom,textvariable=progress_label).pack(side='left')
        pct=ttk.Label(bottom,text='0%');pct.pack(side='right')
        ttk.Progressbar(win,maximum=100,variable=progress).pack(side='bottom',fill='x',padx=10,pady=(0,6))
        def selected_ports():
            return [port for port in tree.selection() if port in self.port_results]
        def selected_port():
            return next(iter(selected_ports()),None)
        def show_selection(event=None):
            port=selected_port()
            if port:
                row=self.port_results[port]
                details.set(f'{port}: {row.get("probe_status","Not checked")}. {row.get("description","")}')
        tree.bind('<<TreeviewSelect>>',show_selection)
        def serial_values(port):
            if speed.get()=='Auto (detected)':
                detail=self.port_results.get(port,{}).get('probe_status','')
                match=re.search(r'(?:at |\()(\d{4,7})(?:\)|\b)',detail)
                rate=int(match.group(1)) if match else 9600
                return dict(baud=rate,parity='N',stopbits=1,flow='None',timeout=60)
            if speed.get()=='115200 / 8N1':return dict(baud=115200,parity='N',stopbits=1,flow='None',timeout=60)
            if speed.get()=='Custom...':return dict(custom)
            return dict(baud=9600,parity='N',stopbits=1,flow='None',timeout=60)
        def render():
            if not win.winfo_exists():return
            known=self.port_results
            for port,row in sorted(known.items(),key=lambda x:int(x[0][3:]) if x[0][3:].isdigit() else 9999):
                parent='group:'+row.get('category','Other / Unknown')
                if not tree.exists(parent):parent='group:Other / Unknown'
                sess=next((s for s in self.sessions.values() if s.profile.get('port','').upper()==port and s.ser),None)
                hostname=(sess.cli_hostname if sess and sess.cli_hostname else row.get('hostname')) or 'Unknown'
                values=(port,hostname,self._operational_status(port,row),row.get('description',''))
                if not tree.exists(port):tree.insert(parent,'end',iid=port,text='',values=values)
                else:
                    if tree.parent(port)!=parent:tree.move(port,parent,'end')
                    if tuple(tree.item(port,'values'))!=values:tree.item(port,values=values)
            total=getattr(self,'_scan_total',0);done=getattr(self,'_scan_done',0)
            value=round(done*100/max(1,total)) if total else 0
            progress.set(value);pct.configure(text=f'{value}%')
            progress_label.set(f'Probing {done}/{total} ports' if self.port_scan_active else f'{len(known)} known port(s) · scan complete' if total else 'Ready')
            win.after(350,render)
        def discover():
            self._scan_ports()
            details.set('Checking ports with bounded Enter retries. Login may be required; no passwords are sent.')
        def connect_port():
            ports=selected_ports()
            if not ports:return
            successes=[];failed=[]
            for port in ports:
                if not self.port_results[port].get('present'):
                    failed.append(port+': not present')
                    continue
                try:
                    if self.connect_discovered_port(port,serial_values(port)):
                        successes.append(port)
                    else:
                        failed.append(port+': could not open')
                except Exception as exc:
                    failed.append(port+': '+str(exc))
            details.set(f'Connected {len(successes)}/{len(ports)} selected port(s).' +
                        (' Errors: '+'; '.join(failed) if failed else ''))
            if len(successes)>1:
                details.set(f'Opened {len(successes)} console tabs. '+('; '.join(failed) if failed else ''))
        def disconnect_port():
            port=selected_port()
            if not port:return
            session=next((s for s in self.sessions.values() if s.profile.get('port','').upper()==port and s.ser),None)
            if session:
                if session.profile['id'] in self.jobs:
                    messagebox.showwarning('Busy','Command capture is running on '+port,parent=win);return
                session.close()
                self.port_results[port]['disconnected']=True
                details.set(port+' disconnected.')
        def check_response():
            """One-click response probe: no preceding Connect action required."""
            port=selected_port()
            if not port:return
            if not self.port_results.get(port,{}).get('present'):
                details.set(f'{port}: Not reported by Windows. Run Discover Ports.');return
            if self.port_scan_active or getattr(self,'single_probe_active',False):
                details.set('A probe is already running.');return
            session=next((s for s in self.sessions.values() if s.profile.get('port','').upper()==port and s.ser),None)
            if session:
                if session.profile['id'] in self.jobs:
                    details.set(port+' is running a command capture; probe skipped.');return
                # The already-connected terminal owns this port. Do not open
                # another Serial object or read its data from a worker thread.
                baseline=session.rx_bytes
                remaining={'count':0}
                self.single_probe_active=True
                def attempt():
                    if not session.ser:
                        self.single_probe_active=False
                        details.set(port+': Session disconnected during probe.');return
                    if session.rx_bytes>baseline:
                        self.single_probe_active=False
                        self.port_results.setdefault(port,{})['probe_status']='Response received in active session'
                        if session.cli_hostname:self.port_results[port]['hostname']=session.cli_hostname
                        details.set(port+': Response received'+(' — '+session.cli_hostname if session.cli_hostname else ' — hostname unknown'))
                        return
                    if remaining['count']>=4:
                        self.single_probe_active=False
                        details.set(port+': No response after 4 Enter attempts. Check cable and baud rate.');return
                    remaining['count']+=1
                    details.set(f'{port}: Sending Enter ({remaining["count"]}/4)...')
                    try:session.send(b'\r')
                    except Exception as exc:
                        self.single_probe_active=False;details.set(port+': '+str(exc));return
                    win.after(750,attempt)
                attempt()
            else:
                # Idle ports are probed in a background worker, then released.
                self.single_probe_active=True
                details.set(port+': Checking response (up to 4 Enter attempts per speed)...')
                snapshot=[dict(p) for p in self.legacy_profiles]
                for name,setting in self.serial_settings.items():
                    snapshot.append(dict(port=name,**setting))
                # Put the currently selected speed first, then fall back to
                # previously successful candidates and the usual 9600 8N1.
                selected=serial_values(port)
                preferred=(selected['baud'],selected['parity'],selected['stopbits'])
                candidates=[preferred]+[x for x in candidates_for(port,snapshot) if x!=preferred]
                result=Queue()
                def worker():
                    try:result.put(probe_port(port,candidates))
                    except Exception as exc:result.put((None,'Probe error: '+str(exc)[:120]))
                threading.Thread(target=worker,daemon=True).start()
                def finish():
                    try:hostname,detail=result.get_nowait()
                    except Empty:
                        if win.winfo_exists():win.after(120,finish)
                        else:self.single_probe_active=False
                        return
                    self.single_probe_active=False
                    record=self.port_results.setdefault(port,{})
                    if hostname:record['hostname']=hostname
                    record['probe_status']=detail
                    details.set(f'{port}: {detail}')
                win.after(120,finish)
        buttons=ttk.Frame(win,padding=(10,4));buttons.pack(fill='x')
        ttk.Button(buttons,text='Discover Ports',command=discover).pack(side='left',padx=3)
        ttk.Button(buttons,text='Connect Selected (Ctrl/Shift)',command=connect_port).pack(side='left',padx=3)
        ttk.Button(buttons,text='Check Response',command=check_response).pack(side='left',padx=3)
        ttk.Button(buttons,text='Disconnect',command=disconnect_port).pack(side='left',padx=3)
        ttk.Button(buttons,text='Close',command=win.withdraw).pack(side='right',padx=3)
        render()

    @staticmethod
    def _device_label(profile, session):
        symbol='●' if session and session.ser else '○'
        host=(session.cli_hostname or '') if session else ''
        name=profile.get('name') or profile.get('port') or 'Device'
        return f'{symbol} {name}' + (f' · {host}' if host and host.casefold()!=name.casefold() else '')

    def refresh_recent_captures(self):
        """Refresh only on demand or after a completed run; do not scan every tick."""
        if not hasattr(self,'recent_capture_list'):
            return
        self._recent_runs=list_capture_runs(BASE/'captures')[:40]
        self.recent_capture_list.configure(state='normal')
        self.recent_capture_list.delete(0,'end')
        for folder,data in self._recent_runs:
            host=str(data.get('cli_hostname') or data.get('device') or 'Unknown')
            group=str(data.get('group') or 'Capture')
            port=str(data.get('com_port') or '?')
            self.recent_capture_list.insert('end',f'{host[:19]} · {port} · {group[:12]}')
        self.recent_count.set(f'{len(self._recent_runs)} most recent capture(s)')
        if not self._recent_runs:
            self.recent_capture_list.insert('end','No saved captures yet')
            self.recent_capture_list.configure(state='disabled')
        else:
            self.recent_capture_list.configure(state='normal')

    def open_selected_capture(self):
        """Open the original evidence folder; never mutate saved transcripts."""
        selected=self.recent_capture_list.curselection()
        if not selected or selected[0]>=len(self._recent_runs):
            self.status.set('Select a saved capture first.')
            return
        folder,_data=self._recent_runs[selected[0]]
        try:
            os.startfile(str(folder))
        except (OSError,AttributeError) as exc:
            self.show_error_details('Open capture folder',str(exc),parent=self.root)

    def _refresh_active_status_badge(self, profile, session):
        """Run status takes precedence; the text also describes connectivity."""
        pid=profile['id']
        is_open=bool(session and session.ser)
        if pid in self.jobs:
            text='Running commands' if is_open else 'Running · connection lost'
            color='#FCE3B6'
        elif pid in self.last_jobs:
            result=self.last_jobs[pid].get('final_status')
            if result=='completed':
                text='Run completed' + (' · connected' if is_open else ' · disconnected')
                color='#D5F0DB'
            else:
                text='Run ' + str(result or 'failed') + (' · connected' if is_open else ' · disconnected')
                color='#F8D7DA'
        elif is_open:
            text='Port open · console connected'
            color='#D9EAF8'
        else:
            text='Not connected'
            color='#E9EDF1'
        self.active_status_label.configure(text=text,bg=color,fg='#263E51')

    def refresh_profiles(self):
        self.profile_list.delete(0,'end')
        for p in self.profiles:
            session=self.sessions.get(p['id'])
            self.profile_list.insert('end',self._device_label(p,session))
        self.refresh_device_colors()
        if self.profiles:
            index=next((i for i,p in enumerate(self.profiles) if p['id']==self.selected),0)
            self.profile_list.selection_set(index); self.select_profile()
    def refresh_groups(self):
        names=[g['name'] for g in self.groups]
        self.group_box['values']=names
        if self.group_name.get() not in names:self.group_name.set(names[0] if names else '')
        if hasattr(self,'single_group_box'):
            self.single_group_box['values']=['Single command']+names
            if self.single_group.get() not in self.single_group_box['values']:
                self.single_group.set('Single command')
        self.update_target_visibility()

    def update_target_visibility(self,event=None):
        if not hasattr(self,'target_frame'):
            return
        group=next((g for g in self.groups if g['name']==self.group_name.get()),None)
        needed=bool(group and any('{interface}' in command for command in group.get('commands',[])))
        if needed:
            if not self.target_frame.winfo_manager():
                self.target_frame.pack(fill='x',before=self.group_box.master,pady=(0,9))
        elif self.target_frame.winfo_manager():
            self.target_frame.pack_forget()


    def get_profile(self): return next(p for p in self.profiles if p['id']==self.selected)
    def get_session(self): return self.sessions.get(self.selected)
    def select_profile(self,event=None):
        selection=self.profile_list.curselection()
        if not selection: return
        p=self.profiles[selection[0]]; self.selected=p['id']
        session=self.sessions.get(p['id'])
        self.active_port_label.configure(text='Port: '+(p.get('port') or 'Not assigned'))
        self.active_host_label.configure(text='Hostname: '+((session.cli_hostname if session else '') or 'Unknown'))
        self._refresh_active_status_badge(p,session)
        for key,var in self.fields.items(): var.set(str(p.get(key,'')))
        self.username.set(''); self.auto.set(False); self.password.set('')
        session=self.get_session()
        if session:
            self.tabs.select(session.frame)
        self.single.set('display version')
        if hasattr(self, 'queue_list'): self.refresh_queue()
    def tab_changed(self,event=None):
        current=self.tabs.select()
        for key,s in self.sessions.items():
            if str(s.frame)==current and self.selected!=key:
                for i,p in enumerate(self.profiles):
                    if p['id']==key:
                        self.profile_list.selection_clear(0,'end'); self.profile_list.selection_set(i); self.select_profile(); return
    def apply_interface(self, event=None, silent=True):
        """Record the target interface on the selected device without reconnecting.

        Empty is allowed: only a command referencing {interface} needs this value.
        Validation of a non-empty interface is deferred until command execution.
        """
        if not self.selected:
            return True
        value=self.fields['interface'].get().strip()
        p=self.get_profile()
        p['interface']=value
        session=self.get_session()
        if session:
            session.profile['interface']=value
        return True

    def connect(self):
        if self.busy(): return
        if not self.selected:return
        p=self.get_profile()
        active=next((s for s in self.sessions.values() if s.ser and s.profile['port'].casefold()==p['port'].casefold()),None)
        if active:
            self.tabs.select(active.frame); active.text.focus_set();return
        try:
            session=self.sessions.get(p['id'])
            if not session: session=Session(self,p); self.sessions[p['id']]=session
            session.close(); session.profile=dict(p)
            session.ser=serial.Serial(p['port'],p['baud'],bytesize=8,parity=p['parity'],stopbits=p['stopbits'],timeout=0,write_timeout=2,rtscts=p['flow']=='RTS/CTS',xonxoff=p['flow']=='XON/XOFF',dsrdtr=False)
            session.raw.clear(); session.sent.clear(); session.seen_failure=False
            session.rx_bytes=0;session.tx_bytes=0;session.cli_hostname=None
            session.password=''; session.auto_allowed=False
            session.status = ('COM port open (' + p['port'] + '). '
                              'Click the terminal and press Enter to request the CLI prompt. '
                              'If sending times out, check Flow control (usually None).')
            session.redraw()
            self.tabs.select(session.frame)
            self.update_terminal_appearance()
            session.text.focus_set()
            self.status.set(session.status)
        except Exception as exc:
            # Do not leave an apparently connected session after a failed open.
            if 'session' in locals():
                session.close()
            self.show_error_details('COM connection error',f'Operation: Opening COM port\nPort: {p.get("port")}\nException: {type(exc).__name__}\nError code: {getattr(exc, "winerror", None) or getattr(exc, "errno", "Not provided")}\nFull error: {exc}')
    def disconnect(self):
        if self.busy(): return
        s=self.get_session()
        if s:
            s.close()
            self.port_results.setdefault(s.profile['port'].upper(),{})['disconnected']=True
    def wake(self):
        if self.busy(): return
        try:
            s=self.get_session()
            if not s: raise ValueError('Connect first.')
            s.send(b'\r')
        except Exception as exc: messagebox.showerror('Console',str(exc))
    def update_terminal_appearance(self, event=None):
        for session in self.sessions.values():
            session.text.configure(bg='#101820', fg='#daf5e1', insertbackground='#daf5e1',
                                   font=('Consolas', int(self.terminal_font_size.get())))

    def refresh_queue(self, completed=None):
        if not hasattr(self,'queue_list'): return
        job = self.job or completed or getattr(self,'last_jobs',{}).get(getattr(self,'selected',None))
        self.queue_list.delete(0,'end')
        if not job:
            self.queue_list.insert('end','No active command run on selected device')
        else:
            for i, command in enumerate(job['commands']):
                if i < job['index']:
                    state = 'DONE'
                elif i == job['index'] and self.job:
                    state = job['state'].upper()
                elif not self.job and i >= job['index']:
                    state = 'NOT RUN'
                else:
                    state = 'PENDING'
                attempts = [r for r in job.get('results',[]) if r.get('order',-1)==i+1]
                if attempts and attempts[-1]['result'] != 'completed':
                    state = 'FAILED'
                self.queue_list.insert('end', f'{i+1}/{len(job["commands"])} [{state}] {command}')
            if self.job:
                self.queue_list.see(min(job['index'],len(job['commands'])-1))
        if hasattr(self, 'stop_button'):
            current=self.job
            self.stop_button.configure(state=('normal' if current and current.get('state') not in ('finished', 'stopped') else 'disabled'))
        if hasattr(self, 'profile_list') and hasattr(self,'profiles'):self.refresh_device_colors()
        if hasattr(self, 'all_jobs_label'):
            self.all_jobs_label.configure(text=(f'Selected: {job["name"]} — {min(job["index"]+1,len(job["commands"]))}/{len(job["commands"])}' if job else 'Selected device: no run'))

    def diagnostic_text(self):
        try:
            s=self.get_session()
            p=self.get_profile()
        except (StopIteration,AttributeError):
            return 'No selected device'
        if not p: return 'No selected device'
        connected=bool(s and s.ser and s.ser.is_open)
        lines=[f'Device: {p["name"]}',f'COM port: {p["port"]} | {"OPEN" if connected else "CLOSED"}',
               f'Baud: {p["baud"]} | {p["parity"]}/8/{p["stopbits"]} | Flow: {p["flow"]}',
               f'Detected hostname: {getattr(s,"cli_hostname",None) or "Unknown"}',
               f'CLI hostname: {getattr(s,"cli_hostname",None) or "Not detected"}',
               f'RX: {getattr(s,"rx_bytes",0)} bytes | TX: {getattr(s,"tx_bytes",0)} bytes']
        if s and s.last_error: lines.append('Last error: '+s.last_error)
        return '\n'.join(lines)

    def refresh_diagnostics(self):
        if hasattr(self,'diag_label'): self.diag_label.configure(text=self.diagnostic_text())

    def copy_diagnostics(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.diagnostic_text())
        self.status.set('Connection diagnostics copied to clipboard.')

    def run_group(self):
        if self.busy(): return
        group=next((g for g in self.groups if g['name']==self.group_name.get()),None)
        if group: self.start(group['name'],group['commands'])

    def run_single(self):
        if self.busy(): return
        self.start(self.single_group.get() or 'Single command',[self.single.get()])

    def run_single_multiple(self):
        available=[p for p in self.profiles if p['id'] in self.sessions and
                   self.sessions[p['id']].ser and p['id'] not in self.jobs]
        if not available:
            messagebox.showwarning('Single command','Connect at least one idle device first.')
            return
        win=tk.Toplevel(self.root);win.title('Capture one command on multiple devices')
        win.geometry('470x400')
        ttk.Label(win,text='Choose devices for this command:',padding=12).pack(anchor='w')
        options=[]
        for p in available:
            value=tk.BooleanVar(value=True)
            ttk.Checkbutton(win,text=p['name']+' ('+p['port']+')',variable=value).pack(anchor='w',padx=18,pady=3)
            options.append((p['id'],value))
        def launch():
            try:
                name=self.single_group.get() or 'Single command'
                command=self.single.get()
                prepared=[self.prepare_run(pid,name,[command]) for pid,var in options if var.get()]
                if not prepared:
                    messagebox.showwarning('Single command','Select at least one device.',parent=win);return
                win.destroy()
                self.launch_runs(prepared)
            except Exception as exc:
                self.show_error_details('Single-command capture',str(exc),parent=win)
        ttk.Button(win,text='Run and capture selected',command=launch).pack(pady=12)

    def run_multiple(self):
        """Launch independent runs; existing runs on other devices are unaffected."""
        available = [p for p in self.profiles if p['id'] in self.sessions and
                     self.sessions[p['id']].ser and p['id'] not in self.jobs]
        if not available:
            messagebox.showwarning('Parallel runs','Connect a device not already running a group.')
            return
        win = tk.Toplevel(self.root)
        win.title('Run command groups on multiple devices')
        win.geometry('610x380')
        ttk.Label(win,text='Select independent command groups for connected devices.',padding=12).pack(anchor='w')
        pane=ttk.Frame(win,padding=12);pane.pack(fill='both',expand=True)
        ttk.Label(pane,text='Run?').grid(row=0,column=0,sticky='w')
        ttk.Label(pane,text='Connected device').grid(row=0,column=1,sticky='w')
        ttk.Label(pane,text='Command group').grid(row=0,column=2,sticky='w')
        inputs=[]
        for i,p in enumerate(available,1):
            chosen=tk.BooleanVar(value=i<=2)
            group_var=tk.StringVar(value='Burn In' if any(g['name']=='Burn In' for g in self.groups) else self.groups[0]['name'])
            ttk.Checkbutton(pane,variable=chosen).grid(row=i,column=0,sticky='w')
            ttk.Label(pane,text=f"{p['name']} ({p['port']})").grid(row=i,column=1,sticky='w',padx=12,pady=4)
            ttk.Combobox(pane,values=[g['name'] for g in self.groups],textvariable=group_var,state='readonly',width=28).grid(row=i,column=2,sticky='w')
            inputs.append((p['id'],chosen,group_var))
        def launch():
            choices=[]
            for p_id,enabled,group_var in inputs:
                if not enabled.get(): continue
                group=next((g for g in self.groups if g['name']==group_var.get()),None)
                if group:choices.append((p_id,group['name'],group['commands']))
            if not choices:
                messagebox.showwarning('Parallel runs','Choose at least one device.',parent=win);return
            # Prepare all jobs before starting any; prevents partial starts from invalid configs.
            try:
                prepared=[self.prepare_run(p_id,name,commands) for p_id,name,commands in choices]
            except Exception as exc:
                messagebox.showerror('Parallel runs',str(exc),parent=win);return
            if len(prepared)!=len(choices):return  # user declined a hostname mismatch
            win.destroy()
            self.launch_runs(prepared)
        ttk.Button(win,text='Start selected runs',command=launch).pack(pady=10)

    def start(self,name,templates):
        try:
            self.apply_interface()
            prepared = self.prepare_run(self.selected,name,templates)
            if prepared: self.launch_runs([prepared])
        except Exception as exc: self.show_error_details('Run error',f'{type(exc).__name__}: {exc}')

    def prepare_run(self,p_id,name,templates):
        p=next((p for p in self.profiles if p['id']==p_id),None)
        s=self.sessions.get(p_id)
        if not p or not s or not s.ser:raise ValueError('Connect and log in to '+(p['name'] if p else 'device')+' first.')
        if p_id in self.jobs:raise ValueError(p['name']+' already has an active run.')
        kind,host=prompt_kind(s.visible)
        if kind!='cli':raise ValueError(p['name']+': wait for the device CLI prompt before automated capture.')
        # Only the selected device's target interface is editable in this panel.
        if p_id == self.selected:
            self.apply_interface()
        commands=[command_text(c,p) for c in templates]
        if not commands:raise ValueError('The group is empty.')
        return p_id,name,commands,host

    def launch_runs(self, prepared):
        jobs=[]
        for p_id,name,commands,host in prepared:
            p=next(p for p in self.profiles if p['id']==p_id)
            s=self.sessions[p_id]
            folder=BASE/'captures'/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+safe_name(p['name'])+'_'+safe_name(name))
            folder.mkdir(parents=True,exist_ok=False)
            for extension in ('PNG','TXT','BIN'): (folder/extension).mkdir()
            s.auto_allowed=False
            job=dict(profile_id=p_id,session=s,commands=commands,index=0,folder=folder,
                     results=[],state='next',stop=False,name=name,run_hostname=host,
                     started_at=datetime.now().astimezone().isoformat(),start_monotonic=time.monotonic(),
                     finished_at=None,used_names={},error=None)
            self.jobs[p_id]=job
            self.write_summary(job)
            jobs.append(job)
        self.refresh_queue()
        for j in jobs:self.next_command(j)

    def job_is_current(self, j):
        jobs=getattr(self,'jobs',None)
        return (jobs.get(j['profile_id']) is j if jobs is not None else self.job is j)

    def next_command(self,j=None):
        j=j or self.job
        if not j or not self.job_is_current(j):return
        if j['stop'] or j['index']>=len(j['commands']):self.finish_run(j);return
        s=j['session']
        if not s.ser or (getattr(s,'cli_hostname',None) and s.cli_hostname.casefold()!=j['run_hostname'].casefold()):
            j['state']='failed';self.failure('Connection or device identity changed',j=j);return
        try:
            s.ser.reset_input_buffer();s.raw.clear();s.redraw()
            j.update(state='running',started=time.monotonic(),pager=0,command=j['commands'][j['index']])
            self.refresh_queue()
            s.status='Running '+j['command'];s.send((j['command']+'\r').encode())
        except Exception as exc:self.failure(str(exc),j=j)

    def advance_job(self,j=None):
        j=j or self.job
        if not j or j['state']!='running':return
        s=j['session']
        if not s.ser:self.failure('Serial connection lost',j=j);return
        count=len(PAGER.findall(s.raw.decode('utf-8',errors='replace')))
        if count>j['pager']:
            j['pager']=count
            try:s.send(b' ')
            except Exception as exc:self.failure(str(exc),j=j);return
        kind,host=prompt_kind(s.visible)
        if kind=='cli' and time.monotonic()-s.last_rx>0.8:
            if host.casefold()!=j.get('run_hostname',s.profile['hostname']).casefold():
                self.failure('Hostname changed during automation',j=j);return
            if ERROR.search(s.visible):self.failure('Device reported a command error',j=j);return
            self.save_command('completed',j=j);return
        if kind in ('username','password'):self.failure('Device requested login during command',j=j);return
        if time.monotonic()-j['started']>int(s.profile['timeout']):
            self.failure('Command timeout; output may be incomplete',j=j)

    def save_command(self,result,j=None):
        j=j or self.job
        if not j:return
        s=j['session'];j['state']='capturing'
        self.refresh_queue()
        base=safe_name(j['command'])
        used=j.setdefault('used_names',{})
        used[base.casefold()]=used.get(base.casefold(),0)+1
        count=used[base.casefold()]
        stem=base if count==1 else f'{base}_{count}'
        value=s.visible
        (j['folder']/'TXT'/(stem+'.txt')).write_text(value,encoding='utf-8')
        raw=bytes(s.raw)
        if s.password:raw=raw.replace(s.password.encode(),b'[REDACTED]')
        (j['folder']/'BIN'/(stem+'.bin')).write_bytes(raw)
        record=dict(command=j['command'],order=j['index']+1,result=result,
                    time=datetime.now().astimezone().isoformat(),text='TXT/'+stem+'.txt',
                    binary='BIN/'+stem+'.bin',image='PNG/'+stem+'.png',images=[],
                    capture='Full terminal transcript rendered as PNG; independent of minimized window')
        j['results'].append(record);self.write_summary(j)
        def done(error,images):
            p_id=j.get('profile_id',getattr(self,'selected',None))
            if hasattr(self,'captures'):self.captures.pop(p_id,None)
            else:self.capture=None
            record['images']=['PNG/'+filename for filename in images]
            if images:record['image']=record['images'][0]
            if not self.job_is_current(j):return
            if error:
                record['screenshot_error']=error;record['result']='capture_failed'
                self.write_summary(j);self.failure('Screenshot failed: '+error,save_partial=False,j=j);return
            self.write_summary(j)
            if result=='completed':
                j['index']+=1;j['state']='next';self.refresh_queue()
                self.root.after(700,lambda:self.next_command(j))
            elif j['stop']:self.finish_run(j)
            else:self.failure_dialog(result,j=j)
        try:
            capture=Capture(self,s,j['folder']/'PNG'/(stem+'.png'),done)
            if hasattr(self,'captures'):self.captures[j['profile_id']]=capture
            else:self.capture=capture
        except Exception as exc:done(str(exc),[])

    def write_summary(self,j=None):
        j=j or self.job
        if not j:return
        ended=j.get('finished_at')
        elapsed = (j.get('finish_monotonic',time.monotonic())-j['start_monotonic'] if ended and 'start_monotonic' in j else None)
        save_json(j['folder']/'summary.json',dict(
            group=j['name'],device=j['session'].profile['name'],
            profile_id=j.get('profile_id'),com_port=j['session'].profile.get('port'),
            cli_hostname=j.get('run_hostname'),expected_hostname='',
            management_ip_reference=j['session'].profile.get('ip'),
            started_at=j.get('started_at'),completed_at=ended,duration_seconds=round(elapsed,2) if elapsed is not None else None,
            status=j.get('final_status',j.get('state')),last_error=j.get('error'),errors=j.get('errors',[]),results=j['results']))

    def failure(self,reason,save_partial=True,j=None):
        j=j or self.job
        if not j:return
        j['state']='failed';j['error']=reason
        entry=dict(time=datetime.now().astimezone().isoformat(),command=j.get('command'),command_order=j.get('index',0)+1,reason=str(reason),details=self.error_details(reason,j))
        j.setdefault('errors',[]).append(entry)
        self.write_summary(j)
        if save_partial and j['session'].visible and 'command' in j:self.save_command(reason,j=j)
        else:self.failure_dialog(reason,j=j)

    def failure_dialog(self,reason,j=None):
        j=j or self.job
        if not j or not self.job_is_current(j):return
        j['state']='paused';self.refresh_queue()
        win=tk.Toplevel(self.root);win.title(j['session'].profile['name']+' — Run paused')
        # No global grab: the other device's job continues and its controls remain usable.
        ttk.Label(win,text=reason+'\nRetry/Skip require the device to be back at its expected prompt.',padding=15,wraplength=500).pack()
        ttk.Button(win,text='View Error Details',command=lambda:self.show_error_details('Command error details',self.error_details(reason,j),parent=win)).pack(pady=4)
        def choose(action):
            s=j['session']
            if action!='stop' and (not s.ser or prompt_kind(s.visible)[0]!='cli' or prompt_kind(s.visible)[1]!=j['run_hostname']):
                messagebox.showwarning('Not ready','Stop this run or recover the CLI prompt.',parent=win);return
            win.destroy()
            if action=='stop':j['stop']=True;self.finish_run(j)
            else:
                if action=='skip':j['index']+=1
                j['state']='next';self.next_command(j)
        row=ttk.Frame(win);row.pack(pady=10)
        for label,action in [('Retry','retry'),('Skip','skip'),('Stop','stop')]:
            ttk.Button(row,text=label,command=lambda a=action:choose(a)).pack(side='left',padx=5)
        win.protocol('WM_DELETE_WINDOW',lambda:choose('stop'))

    def stop(self):
        """Cancel the selected command run without a blocking retry/error popup."""
        j=self.job
        if not j:return
        if j.get('stop'):return
        j['stop']=True
        if j['state']=='running':
            try:
                if j['session'].ser:j['session'].send(b'\x03')
            except Exception as exc:
                j.setdefault('errors',[]).append({'reason':'Cancel signal failed: '+str(exc)})
            try:self.save_command('cancelled',j=j)
            except Exception as exc:
                j.setdefault('errors',[]).append({'reason':'Partial capture failed: '+str(exc)})
                self.finish_run(j)
        elif j['state']=='capturing':
            # The capture completion callback already honors j['stop'].
            self.status.set('Cancelling after current screenshot is saved...')
        else:self.finish_run(j)
        self.refresh_queue()

    def stop_all(self):
        original=self.selected
        for profile_id in list(self.jobs):
            self.selected=profile_id
            self.stop()
        self.selected=original

    def finish_run(self,j=None):
        j=j or self.job
        if not j:return
        j['finished_at']=datetime.now().astimezone().isoformat()
        j['finish_monotonic']=time.monotonic()
        completed_orders={r.get('order') for r in j['results'] if r['result']=='completed'}
        j['final_status']='stopped' if j.get('stop') else ('completed' if len(completed_orders)==len(j['commands']) and not j.get('errors') else 'partial')
        self.write_summary(j)
        self.refresh_recent_captures()
        if hasattr(self,'jobs'):
            if self.jobs.get(j['profile_id']) is j:self.jobs.pop(j['profile_id'])
            self.last_jobs[j['profile_id']]=j
        else:self.job=None
        self.refresh_queue(completed=j if getattr(self,'selected',None)==j.get('profile_id',getattr(self,'selected',None)) else None)
        ok=len(completed_orders)
        j['session'].status=f"{j['name']} {j['final_status']}: {ok}/{len(j['commands'])} commands saved."
        if not getattr(self,'jobs',{}):
            messagebox.showinfo(j['session'].profile['name']+' — Run finished',
                f"{ok} completed command capture(s) on {j['session'].profile['name']}.\nSaved to:\n{j['folder']}")

    def open_word_export(self):
        from tkinter import filedialog
        root_dir=BASE/'captures'
        root_dir.mkdir(exist_ok=True)
        runs=list_capture_runs(root_dir)
        win=tk.Toplevel(self.root)
        win.title('Export Capture Evidence to Word')
        # Respect laptop screen heights and Windows display scaling.
        height=max(480,min(690,win.winfo_screenheight()-110))
        win.geometry(f'820x{height}')
        win.minsize(650,470)
        win.transient(self.root)

        # Pack the action footer before the scrollable content so it always
        # reserves visible space, regardless of capture-list or form height.
        footer=ttk.Frame(win,padding=(12,10,12,10))
        footer.pack(side='bottom',fill='x')
        ttk.Separator(win).pack(side='bottom',fill='x')

        content=ttk.Frame(win)
        content.pack(side='top',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(content,orient='vertical')
        scrollbar.pack(side='right',fill='y')
        canvas=tk.Canvas(content,highlightthickness=0,borderwidth=0,
                         yscrollcommand=scrollbar.set)
        canvas.pack(side='left',fill='both',expand=True)
        scrollbar.configure(command=canvas.yview)
        form=ttk.Frame(canvas)
        form_id=canvas.create_window((0,0),window=form,anchor='nw')
        form.bind('<Configure>',lambda _event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(form_id,width=event.width))

        def scroll_form(event):
            if event.delta:
                canvas.yview_scroll(-int(event.delta/120) or (-1 if event.delta>0 else 1),'units')
        # Only scroll the form while the pointer is inside non-editable
        # form areas; the capture list retains its own native wheel behavior.
        canvas.bind('<MouseWheel>',scroll_form)
        form.bind('<MouseWheel>',scroll_form)
        selection_info=tk.StringVar(value='Select a capture to export.')
        ttk.Label(footer,textvariable=selection_info,style='Counter.TLabel').pack(side='left')
        ttk.Label(form,text='CAPTURE HISTORY',style='SectionTitle.TLabel',padding=(12,12,12,4)).pack(anchor='w')
        ttk.Label(form,text='Select one or more runs (Ctrl / Shift). Search by hostname, COM port, group, status or date.',padding=(12,0,12,6)).pack(anchor='w')
        search_box=ttk.Frame(form,padding=(12,3,12,6));search_box.pack(fill='x')
        ttk.Label(search_box,text='Find captures:').pack(side='left',padx=(0,8))
        query=tk.StringVar(value='')
        ttk.Entry(search_box,textvariable=query).pack(side='left',fill='x',expand=True)
        result_count=tk.StringVar(value='')
        ttk.Label(form,textvariable=result_count,style='Counter.TLabel',padding=(12,0,12,3)).pack(anchor='w')
        listing=tk.Listbox(form,selectmode='extended',height=8,exportselection=False,font=('Consolas',10))
        listing.pack(fill='both',expand=True,padx=12)
        visible_indexes=[]
        def refill(*_):
            visible_indexes[:]=[i for i,run in enumerate(runs) if matches_capture(run,query.get())]
            listing.configure(state='normal')
            listing.delete(0,'end')
            for i in visible_indexes:
                folder,record=runs[i]
                listing.insert('end',f"{record.get('cli_hostname') or record.get('device') or 'Unknown'} | {record.get('com_port','?')} | {record.get('group','Group')} | {self.display_timestamp(record.get('started_at'))} | {len(record.get('results',[]))} captures")
            result_count.set(f'{len(visible_indexes)} matching run(s) · {len(runs)} saved')
            if visible_indexes:listing.selection_set(0)
            elif not runs:
                listing.insert('end','No saved capture runs found')
                listing.configure(state='disabled')
        def update_selection_info(_event=None):
            selected=len(listing.curselection()) if runs else 0
            selection_info.set(f'{selected} selected  ·  {len(visible_indexes)} visible capture(s)')
        listing.bind('<<ListboxSelect>>',update_selection_info)
        query.trace_add('write',refill)
        refill()
        update_selection_info()
        combined=tk.BooleanVar(value=False)
        ttk.Radiobutton(form,text='Separate documents — one document per selected run (default)',variable=combined,value=False).pack(anchor='w',padx=12,pady=(10,2))
        ttk.Radiobutton(form,text='Combined document — one inventory table and evidence tables per device',variable=combined,value=True).pack(anchor='w',padx=12)
        ttk.Separator(form).pack(fill='x',padx=12,pady=8)
        default_template=BASE/'templates'/'BurnIn-Template.docx'
        template_path=tk.StringVar(value=str(default_template) if default_template.is_file() else '')
        ttk.Label(form,text='Word template (.docx) · optional if not included').pack(anchor='w',padx=12)
        template_row=ttk.Frame(form);template_row.pack(fill='x',padx=12,pady=(2,6))
        ttk.Entry(template_row,textvariable=template_path).pack(side='left',fill='x',expand=True)
        def choose_template():
            selected=filedialog.askopenfilename(parent=win,title='Choose Word template',
                filetypes=[('Word document','*.docx')],initialdir=str(BASE/'templates'))
            if selected:template_path.set(selected)
        ttk.Button(template_row,text='Browse...',command=choose_template).pack(side='left',padx=(5,0))
        ttk.Label(form,text='Fields: DATE, LABELNO, HOSTNAME, SERIALNO, MODELNO, DEVICENAME. Table image markers: DISPLAYCLOCK, DISPLAYVERSION, DISPLAYESN, DISPLAYCPU, DISPLAYMEM, DISPLAYPOWER, DISPLAYTEMP, DISPLAYFAN, DISPLAYALARM.',
                  wraplength=720).pack(anchor='w',padx=12)
        ttk.Label(form,text='Optional metadata override (single run only):').pack(anchor='w',padx=12,pady=(7,2))
        overrides={key:tk.StringVar(value='') for key in ('DATE','LABELNO','HOSTNAME','SERIALNO','MODELNO','DEVICENAME')}
        meta_grid=ttk.Frame(form);meta_grid.pack(fill='x',padx=12,pady=(0,7))
        for i,key in enumerate(overrides):
            cell=ttk.Frame(meta_grid)
            cell.grid(row=i//3,column=i%3,sticky='ew',padx=(0,8),pady=2)
            meta_grid.columnconfigure(i%3,weight=1)
            ttk.Label(cell,text=key).pack(anchor='w')
            ttk.Entry(cell,textvariable=overrides[key],width=20).pack(fill='x')
        def export():
            indexes=[visible_indexes[i] for i in listing.curselection() if i < len(visible_indexes)] if runs else []
            if not indexes:
                messagebox.showwarning('Word export','Select at least one capture run.',parent=win)
                return
            (BASE/'reports').mkdir(exist_ok=True)
            output=filedialog.askdirectory(parent=win,title='Choose folder for Word reports',initialdir=str(BASE/'reports'))
            if not output:
                return
            try:
                if template_path.get().strip() and not Path(template_path.get()).is_file():
                    raise ValueError('The selected Word template does not exist.')
                provided={key:value.get().strip() for key,value in overrides.items() if value.get().strip()}
                if provided and len(indexes)!=1:
                    raise ValueError('Metadata overrides require exactly one selected run.')
                files=export_word([runs[i][0] for i in indexes],output,combined=combined.get(),
                                  template=template_path.get().strip() or None,metadata_override=provided)
                messagebox.showinfo('Word export',f"Created {len(files)} Word document(s):\n"+'\n'.join(str(f) for f in files),parent=win)
            except Exception as exc:
                self.show_error_details('Word export failed',f'{type(exc).__name__}: {exc}',parent=win)
        ttk.Button(footer,text='Cancel',command=win.destroy).pack(side='right',padx=(8,0))
        self.word_export_action=ttk.Button(
            footer,text='Export selected captures',command=export,
            style='Primary.Action.TButton')
        self.word_export_action.pack(side='right')

    def open_captures(self):
        folder = BASE / 'captures'
        folder.mkdir(exist_ok=True)
        os.startfile(folder)

    def preview_command_group(self):
        name = self.group_name.get()
        group = next((g for g in self.groups if g['name'] == name), None)

        if group is None:
            messagebox.showwarning('Warning', 'Please select a group.')
            return

        commands = group['commands']
        preview = "\n".join(
            f"{i}. {cmd}" for i, cmd in enumerate(commands, start=1)
        )
        messagebox.showinfo(f'Command Preview - {name}', preview)

    def edit_groups(self):
        """Edit one command per line, directly in the large editor.

        This dialog is deliberately non-modal: device terminal tabs stay
        interactive while command sets are being reviewed or edited.
        """
        win=tk.Toplevel(self.root)
        win.title('Command Set Editor')
        win.geometry('780x640')
        win.minsize(590,430)
        win.transient(self.root)
        panel=ttk.Frame(win,padding=12)
        panel.pack(fill='both',expand=True)
        ttk.Label(panel,text='COMMAND SET EDITOR',style='SectionTitle.TLabel').pack(anchor='w')
        ttk.Label(panel,text='Select a set or create a new one. Edit commands directly below: one command per line.').pack(anchor='w',pady=(4,10))
        picker=ttk.Combobox(panel,values=[g['name'] for g in self.groups],state='readonly')
        picker.pack(fill='x',pady=(0,10))
        ttk.Label(panel,text='Set name').pack(anchor='w')
        name=tk.StringVar()
        ttk.Entry(panel,textvariable=name).pack(fill='x',pady=(3,9))
        ttk.Label(panel,text='Commands  ·  one per line').pack(anchor='w')
        body=ttk.Frame(panel);body.pack(fill='both',expand=True,pady=(4,8))
        scrollbar=ttk.Scrollbar(body)
        scrollbar.pack(side='right',fill='y')
        editor=tk.Text(body,font=('Consolas',11),undo=True,wrap='none',
                       yscrollcommand=scrollbar.set,tabs=('28c',))
        editor.pack(side='left',fill='both',expand=True)
        scrollbar.configure(command=editor.yview)
        ttk.Label(panel,text='Tip: Huawei filters may use patterns such as | i (Serial|Model). Commands run individually, in order.',
                  wraplength=700).pack(anchor='w',pady=(0,10))
        editing={'name':None}
        def load(event=None):
            group=next((g for g in self.groups if g['name']==picker.get()),None)
            if not group:return
            editing['name']=group['name']
            name.set(group['name'])
            editor.delete('1.0','end')
            editor.insert('1.0','\n'.join(group['commands']))
        picker.bind('<<ComboboxSelected>>',load)
        def new_group():
            editing['name']=None
            picker.set('')
            name.set('')
            editor.delete('1.0','end')
            editor.focus_set()
        def save_group():
            title=name.get().strip()
            commands=[line.strip() for line in editor.get('1.0','end-1c').splitlines() if line.strip()]
            if not title or not commands:
                messagebox.showwarning('Command sets','Provide a name and at least one command.',parent=win)
                return
            if any(g['name']==title and g['name']!=editing['name'] for g in self.groups):
                messagebox.showerror('Command sets','This name already exists.',parent=win)
                return
            try:
                for command in commands:
                    command_text(command,{'interface':'MultiGE 1/0/1'})
            except ValueError as exc:
                messagebox.showerror('Command sets',str(exc),parent=win)
                return
            self.groups=[g for g in self.groups if g['name']!=editing['name']]
            self.groups.append({'name':title,'target':'Any','commands':commands})
            self.persist()
            self.refresh_groups()
            win.destroy()
        def delete_group():
            if editing['name'] and messagebox.askyesno('Delete command set',
                    'Delete '+editing['name']+'?',parent=win):
                self.groups=[g for g in self.groups if g['name']!=editing['name']]
                self.persist()
                self.refresh_groups()
                win.destroy()
        row=ttk.Frame(panel);row.pack(fill='x')
        ttk.Button(row,text='New set',command=new_group).pack(side='left')
        ttk.Button(row,text='Delete set',command=delete_group).pack(side='left',padx=8)
        ttk.Button(row,text='Close',command=win.destroy).pack(side='right')
        ttk.Button(row,text='Save changes',command=save_group,
                   style='Primary.Action.TButton').pack(side='right',padx=(0,8))
        if self.groups:
            picker.current(0)
            load()

    def tick(self):
        for s in list(self.sessions.values()):s.poll()
        jobs=list(getattr(self,'jobs',{}).values()) if hasattr(self,'jobs') else ([self.job] if self.job else [])
        for j in jobs:
            try:self.advance_job(j)
            except Exception as exc:
                if self.job_is_current(j):
                    j['state']='paused';self.failure_dialog('Collection error: '+str(exc),j=j)
        s=self.get_session()
        if s:
            j=self.job
            self.status.set(s.status if not j else s.status+' | '+j['state'])
        self.refresh_queue()
        self.refresh_diagnostics()
        connected=sum(bool(sess.ser) for sess in self.sessions.values())
        self.workspace_summary.set(f'{connected} connected   ·   {len(self.profiles)} devices   ·   {len(self.jobs)} running')
        self.device_count.set(f'{len(self.profiles)} device(s) · {connected} online')
        if jobs:
            total=sum(len(j['commands']) for j in jobs)
            complete=sum(min(j['index'],len(j['commands'])) for j in jobs)
            self.run_progress.set(100*complete/max(1,total))
            self.run_progress_label.set(f'{complete}/{total} commands')
            self.activity_summary.set(f'{len(jobs)} active command run(s)')
        else:
            self.run_progress.set(0)
            self.run_progress_label.set('Idle')
            self.activity_summary.set(self.status.get() or 'Ready')
        # Update operational indicators periodically without resetting list selection.
        self._sidebar_ticks=getattr(self,'_sidebar_ticks',0)+1
        if self._sidebar_ticks%10==0:
            for index,p in enumerate(self.profiles):
                session=self.sessions.get(p['id'])
                label=self._device_label(p,session)
                if index<self.profile_list.size() and self.profile_list.get(index)!=label:
                    self.profile_list.delete(index)
                    self.profile_list.insert(index,label)
                    if self.selected==p['id']:self.profile_list.selection_set(index)
            self.refresh_device_colors()
            if self.selected:
                p=self.get_profile()
                session=self.get_session()
                self.active_port_label.configure(text='Port: '+(p.get('port') or 'Not assigned'))
                self.active_host_label.configure(text='Hostname: '+((session.cli_hostname if session else '') or 'Unknown'))
                self._refresh_active_status_badge(p,session)
        self.root.after(100,self.tick)
    def close(self):
        if self.jobs or self.captures:
            messagebox.showinfo('Run in progress','Stop all runs and wait for capture to finish before closing.');return
        for s in self.sessions.values():s.close()
        self.root.destroy()

if __name__=='__main__':
    try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:pass
    App().root.mainloop()
