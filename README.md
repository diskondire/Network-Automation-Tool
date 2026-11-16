> **Development preview:** This branch is an experimental v7.7 operator-interface refresh. The stable v7.6.4 version remains on `main`. Do not deploy the preview to production systems until Windows console-hardware testing passes.

### What's new in this preview

- Windows-style workspace header and live activity/progress bar.
- Consolidated task panels for commands, queue, single commands and Word reports.
- Session list shows discovered hostnames.
- Search saved captures directly in the Word export dialog.
- Add-on modules `ui_theme.py` and `capture_catalog.py` and Windows CI regression tests.
- If the optional Burn-In Word template isn't installed locally, standard Word export remains available.

See [v7.7 preview acceptance checklist](docs/UX_REVIEW_V7_7.md) for testing requirements.

---

# Console Capture

**Current version: v7.6.4** · Windows desktop application · Editable Python source

Console Capture is a Python/Tkinter utility for working with network equipment over serial console ports. It discovers Windows COM ports, checks for console responses, runs selected CLI commands, saves command evidence, and exports reports to Microsoft Word.

It is primarily developed and tested around Huawei network equipment. Other vendors may behave differently, particularly with prompts and command syntax.

> **Distribution:** This repository contains **source code**, not a standalone EXE. Python 3.10+ is required. The included launcher creates a local virtual environment if necessary.

## Features

- Discover Windows serial ports grouped as **USB**, **Bluetooth**, and **Other / Unknown**.
- Probe ports by sending bounded Enter retries; distinguish response, login prompt, unavailable port, and no response.
- Connect to a device **without requiring a hostname**. Detect the hostname later when a recognizable CLI prompt becomes available.
- Use serial-speed presets or configure a custom serial connection.
- Run command groups or single commands, queue operations, capture text and screenshots, and cancel running command groups.
- Identify device-run status by background color: **white** = normal, **orange** = running, **green** = completed, **red** = failed/stopped. These colors reflect *command execution*, not port connectivity.
- Export one or more saved runs to Word; use your own compatible `.docx` report template.
- Review development history from **Help → Version History**.

## Installation (Windows)

1. Download or clone the repository and keep all source files in the same folder.
2. Install **Python 3.10 or newer**, with Tkinter available.
3. Run `START.bat`.
4. On first launch, the script creates `.venv` and installs dependencies from `requirements.txt` if needed.

The launcher uses the Windows Python launcher (`py -3`) or `python` on PATH. An invalid existing virtual environment is rebuilt automatically. Internet access may be necessary for the initial dependency installation.

**Requirements:** `pyserial==3.5`, `Pillow>=10,<13`, and `python-docx>=1.1,<2`. See `requirements.txt` for authoritative versions.

## Getting started

1. Open **Connection → Discover COM Ports** (the manager may also appear at startup).
2. Click **Discover Ports**. This lists Windows COM ports and probes eligible idle ports for a response.
3. Select a port; use **Check Response** to probe that port directly, even before connecting. If needed, select the serial parameters and click **Connect**.
4. If the device requires authentication, enter credentials **manually in the terminal**. Discovery does not submit saved credentials.
5. Select the connected device, choose a command group, and execute/capture commands.
6. Open **File → Open Captures Folder** to inspect saved evidence, or choose **File → Export Capture Evidence to Word**.

**Important:** Windows recognizing a USB/Bluetooth serial adapter does not prove a switch is connected. An adapter may report no response; a port may also be occupied by another application (for example, MobaXterm). COM port numbers can change when adapters are reconnected.

### Commands

The included `command_groups.json` defines **Display WAC**, **Display Switch**, and **Burn In** command sets.

- The `{interface}` placeholder uses the **Target Interface** field only for commands that reference it.
- A single command may use Huawei abbreviations and supported read-only output filters, e.g. `dis int transceiver | i Serial`.
- Multiline input and chained commands are rejected by the application.
- Command support still depends on the actual device and its operating system.

## Word report export

Select **Export to Word** in the right-hand panel (or use **File → Export Capture Evidence to Word**). Select saved capture runs, choose a destination folder, and optionally browse for a compatible `.docx` template.

The app suggests `templates/BurnIn-Template.docx` as a default template path, **but that file is not currently tracked in this repository**. Place an authorized template there or select one using **Browse**. The original template is not overwritten.

### Metadata identifiers

Your template can include the following standalone identifiers (plain text or double-braced, such as `{{HOSTNAME}}`):

| Identifier | Meaning |
| --- | --- |
| `DATE` | Capture date, formatted `DD-MM-YY (HH:MM)` |
| `LABELNO` | Device label; enter manually when not available |
| `HOSTNAME` | Detected CLI hostname |
| `SERIALNO` | Serial number/ESN extracted from captured text where recognizable |
| `MODELNO` | Model extracted from captured text, including supported Huawei `display version` uptime lines |
| `DEVICENAME` | Device name, initially based on detected hostname |
| `COMPORT` | Recorded COM port |
| `CAPTUREDATE` | Capture timestamp |
| `COMMANDGROUP` | Command group name |

Detection is **best-effort**, not guaranteed. When exporting a single run, the dialog allows manual overrides for `DATE`, `LABELNO`, `HOSTNAME`, `SERIALNO`, `MODELNO`, and `DEVICENAME`. Overrides are not supported for multiple selected runs.

### Screenshot markers in Word tables

Place each marker in the **cell intended to hold the screenshot**. The app matches the command to the saved capture, then inserts its screenshot in that cell, sized to fit the available cell width while preserving aspect ratio.

| Table marker | Captured CLI command |
| --- | --- |
| `DISPLAYCLOCK` | `display clock` |
| `DISPLAYVERSION` | `display version` |
| `DISPLAYESN` | `display device esn` |
| `DISPLAYCPU` | `display cpu-usage` |
| `DISPLAYMEM` | `display memory all` |
| `DISPLAYPOWER` | `display device power system` |
| `DISPLAYTEMP` | `display device temperature` |
| `DISPLAYFAN` | `display device fan` |
| `DISPLAYALARM` | `display alarm active` |

If an expected capture is missing, the export reports that inside the intended cell rather than inserting a screenshot from another command.

For other report layouts, the exporter also supports `CAPTURE_OUTPUTS` in its own body paragraph to append command evidence.

### Multiple devices in one document (v7.6.4)

Choose **Combined document — one inventory table and evidence tables per device**.

For a compatible Burn-In template:
- The first inventory table has **one row per device**, numbered 1, 2, 3, etc.
- The cover/introduction is **not repeated**.
- Each device's evidence tables and screenshots follow on new pages.
- Long captures may flow onto additional pages; review the result in Word.

Choose **Separate documents** for one report per selected run.

The combined-inventory layout expects a compatible template with an inventory table and evidence tables. Arbitrary Word layouts may require template adjustments.

## Application menus

| Menu | Actions |
| --- | --- |
| **File** | Export Capture Evidence to Word, Open Captures Folder, Exit |
| **Connection** | Discover COM Ports, Connection Diagnostics |
| **View** | Terminal Appearance |
| **Help** | Version History, About |

The right-side panel holds command execution, cancellation, and Word report export controls.

## Project files

| File | Purpose |
| --- | --- |
| `console_capture.py` | Tkinter UI, COM sessions, command execution and capture coordination |
| `discovery.py` | COM probing and CLI prompt/response discovery |
| `core.py` | Command validation, transcript and configuration helpers |
| `word_export.py` | DOCX generation, metadata substitution and screenshot placement |
| `command_groups.json` | Default command sets (editable) |
| `requirements.txt` | Python dependencies |
| `START.bat` | Windows launcher and local environment setup |
| `VERSION` | Project version |
| `CHANGELOG.md` | Documented version history |

Generated captures/reports and `.venv` should remain local rather than being committed.

## Development and safety

Edit the `.py` files directly in an editor such as VS Code, then restart `START.bat`. For changes intended for the shared project, use a feature branch and pull request so the stable version remains available.

Before sharing source or reports, review them for credentials, customer identifiers, sensitive IP addresses and console output. Avoid uploading confidential organization-specific Word templates without authorization.

This application is not a replacement for vendor-approved operational procedures. Test CLI commands on non-production equipment first, especially when executing a batch.

## History

Version **7.6.4** improves combined Burn-In reports (one inventory table, per-device evidence pages), date formatting and Windows-style menus. Earlier versions added response probing, command cancellation, run-state colors, CLI pipe filters and custom Word templates.

See [CHANGELOG.md](CHANGELOG.md) for the full documented milestone history.
