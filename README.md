# Console Capture v7.5.1 — Windows desktop application

This is a Python/Tkinter source distribution. It requires Windows, Python 3.10+ and access to pip when first launched. Extract the folder and run `START.bat`. No packaged executable is included.

## Workflow

1. Open **Discover / Connect COM Ports** in the left sidebar. The COM Manager also opens when the app launches.
2. Click **Discover Ports** to enumerate all COM ports reported by Windows and probe their serial responses without sending login credentials. The scan reuses the established v6.5/v7.2 probing method.
3. Ports appear under **USB**, **Bluetooth**, or **Other / Unknown**, based on Windows port metadata. The grouping cannot establish that a network device is physically attached.
4. Select a COM port and choose **Auto (detected)**, **9600 / 8N1**, **115200 / 8N1**, or **Custom...** settings. Click **Connect**. Only a successfully opened app-owned serial session is shown as Connected.
5. Select the device in the sidebar or its terminal tab. If the console stops at Username/Password, enter credentials manually in the application terminal; the hostname appears after a recognizable authenticated CLI prompt.
6. Choose a command set, run commands, inspect captured output, and export Word documents.

## Changes from v7.3

- Device Profiles editor, Role field, and hard-coded Switch/WAC connection presets are removed from the visible workflow.
- The COM Manager retains its results when closed (hidden) and reopened during the current application process. Starting a new process requires a new discovery scan.
- USB, Bluetooth, and Other grouping; one operational Status column; technical probe details shown below the list.
- Single-port Connect/Disconnect/Check Response controls; no ambiguous multi-select commands.
- Discovered hostname is not required. Login-required devices remain usable for manual login; the app never infers hostname from a generic password prompt.
- Session-specific serial speed is independent of device type. Connection-speed presets are editable directly in the manager.
- Command sets remain independent of device sessions. Existing Huawei command sets and Word export are retained.
- The right-hand login panel is removed; authentication remains manual in the terminal until login handling is redesigned.
- Old `device_profiles.json` is not distributed, and fresh sessions are temporary. If one is present locally, it is read only as a source of known serial parameters for probing.

## Important limitations

- **Detected** means registered with Windows, not necessarily an attached, responsive console. A port may be occupied by another application, including MobaXterm.
- The auto-detected speed relies on a recognized probe response. When unavailable, 9600 8N1 is the fallback; set another speed manually as needed.
- Single-line commands and Huawei `| i`, `| include`, `| exclude`, and `| begin` output filters are supported. Commands still require a visible CLI prompt for automated capture; test on each device OS.
- COM numbers can change when adapters are unplugged; cached hostnames refer only to the current application session and must be confirmed after cable changes.
- Do not export sensitive console banners, credentials, or private network configuration without reviewing captured evidence.
- Only source syntax checks and simulated graphical/serial tests were possible here; actual USB serial hardware and Word export should be verified on Windows before team deployment.

## Files

- `console_capture.py`: Tk interface, serial sessions and capture controller
- `discovery.py`: safe serial probing and prompt discovery
- `core.py`: transcript and command parsing
- `word_export.py`: DOCX report generation
- `command_groups.json`: initial Huawei command sets
- `requirements.txt` and `START.bat`: launch and dependencies


### v7.5 response probing
- **Discover Ports** now sends bounded Enter retries to idle ports, stopping when a response arrives or the retry limit is reached.
- Select any discovered port and click **Check Response** directly; no Connect step is required.
- An existing Console Capture session is probed through its existing serial connection, avoiding competing port owners.
- A banner or login prompt counts as a response even when the hostname is unknown.
- A non-responsive adapter is never assumed to be physically disconnected.

### v7.5.1 maintenance changes
- **CLI command validation:** Supports abbreviated Huawei commands (for example `dis int transceiver | i Serial`) and standard single-line diagnostic commands, including read-only pipe filters. Newlines and command chaining remain prohibited.
- **Login controls:** Removed the top-right login panel. Sign in manually using the terminal; automatic login is deferred for redesign.
- **Target Interface:** Optional editable parameter on the command panel. `{interface}` is substituted per device only when the chosen command references it. You do not need to apply it or reconnect; a blank value is permitted for commands without `{interface}`.
- **Compatibility:** Existing COM discovery, bounded response checks, console sessions, capture queue and Word export code are retained.


## v7.6 UI + Word template export

- Four operations now appear on the **top toolbar**: **Connection Diagnostics**, **Terminal Appearance**, **Discover COM Ports**, and **Open Captures Folder**. The corresponding controls were removed from the right-hand command panel and left footer.
- The working v7.5 serial discovery, response probing, manual terminal login, command queue and CLI filter handling remain unchanged.
- **Export to Word** now offers an optional `.docx` template. The bundled sample is `templates/ConsoleCapture_Report_Template.docx`.
- Place `{{HOSTNAME}}`, `{{SERIALNO}}`, `{{MODELNO}}`, `{{COMPORT}}`, `{{CAPTUREDATE}}`, and `{{COMMANDGROUP}}` wherever metadata should appear. Standalone uppercase markers without braces are also supported. Put `{{CAPTURE_OUTPUTS}}` **alone in a body paragraph** where captured command text and PNG screenshots should be inserted (not inside a table).
- Hostname comes from the recorded CLI hostname in each capture's `summary.json`. The selected capture's TXT transcripts are scanned for recognizable serial and model labels such as `ESN:`, `Serial Number:`, `Model:` and `Product Model:`. If absent, values show **Not detected**, not guesses. When exporting exactly one run, you can override hostname, serial and model in the dialog.
- Existing Word export **without a template** continues to produce the original evidence format.
- Template replacement covers body paragraphs, table cells, headers and footers. Word text formatting can be simplified for paragraphs containing placeholders that span multiple differently formatted runs; place each placeholder in its own text run for best results.
- Review Word reports for sensitive console output before sharing. Text and screenshot evidence can contain network details.
- Windows hardware behavior and Word rendering with custom documents require testing on your computer.


## v7.6.1 — Custom Word burn-in templates

- **Export to Word...** is in the **right-hand WORD REPORT panel**, below the command execution controls.
- The export window defaults to the included `templates/BurnIn-Template.docx`, an unmodified copy of the supplied template. Click **Browse...** to choose any compatible `.docx` template.
- Metadata field markers (plain uppercase or `{{DOUBLE_BRACED}}`): `DATE`, `LABELNO`, `HOSTNAME`, `SERIALNO`, `MODELNO`, `DEVICENAME`. The export dialog provides manual overrides for all six fields when a single run is selected. `DATE` is the capture date; `LABELNO` needs manual entry if not recorded. The device hostname comes from the recorded CLI prompt; `DEVICENAME` initially defaults to that hostname. Unknown serial/model fields are never invented.
- To insert screenshots **inside the table cells**, use one of these markers as the entire cell paragraph: `DISPLAYCLOCK`, `DISPLAYVERSION`, `DISPLAYESN`, `DISPLAYCPU`, `DISPLAYMEM`, `DISPLAYPOWER`, `DISPLAYTEMP`, `DISPLAYFAN`, `DISPLAYALARM`. Captures are matched by command rather than capture ordering, with case-insensitive normalization and Huawei `dis` abbreviation support.
- When a capture is missing, the report displays `[No capture for ...]` or `[No screenshot for ...]` in the intended cell. Existing table borders, command labels, page headers and footers remain intact.
- Optional additional metadata fields: `COMPORT`, `CAPTUREDATE`, `COMMANDGROUP`. The previous `CAPTURE_OUTPUTS` body-paragraph insertion method remains available for other document layouts.
- Custom table-marker reports must be exported **one document per device/run**, to avoid inserting a different device's screenshots into the wrong table.
- The original template is never overwritten: exported reports are saved into the chosen output directory. Captured screenshots can include sensitive information; review reports before distribution.
- Testing: nine sample captures were inserted into the supplied template and rendered successfully. Real Windows console captures and unusually long screenshots should be verified on your equipment.


### v7.6.2 Word-template export adjustments
- Huawei models are detected from the `display version` uptime line, such as `HUAWEI CloudEngine S5755-H uptime is ...`. If no recognizable model is found, enter it manually in the export dialog.
- Screenshot evidence fills the usable width of its designated Word table cell, left-aligned rather than centered; image aspect ratio is maintained. The template's cell margins are respected.

## v7.6.3 changes

- Windows-style **File / Connection / View / Help** menus and a compact quick-access toolbar.
- **Help → Version History** shows documented project milestones (also in `CHANGELOG.md`).
- **Cancel Selected Run** appears beside Run. Cancelling sends Ctrl+C to the active console if running, saves available partial command evidence, stops subsequent commands and marks the run stopped. Do not assume Ctrl+C is always supported by every vendor console.
- Device list background: **white** no run, **orange** run in progress, **green** completed, **red** failed/partial/stopped. These are *command-run* statuses, not serial connectivity statuses.
- Export picker displays CLI hostname, COM port, group and `DD:MM:YY (HH:MM)` timestamps. Capture files continue retaining ISO timestamps for fidelity.
- **Combined Word export** repeats the complete selected user template for each device, including the per-device metadata table and command screenshot placeholders. Individual templates remain editable. Multiple runs do not share a single hostname. Word may add pages if images exceed available table space.
- Manual metadata overrides are supported for single-run exports, not multiple-run combined exports.


## v7.6.4 changes
- Combined custom Burn-In Word reports now use a single cover/inventory table with one row per device, numbered 1, 2, 3...
- Each device has its own evidence tables, starting on a new page. The cover and intro are not duplicated.
- Dates are shown as DD-MM-YY (HH:MM).
- The duplicate row of toolbar buttons has been removed; use File, Connection, View and Help menus.
- Existing individual-document export behavior remains.
