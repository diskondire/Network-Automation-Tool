# How Console Capture works — v0.7.7.0 alpha

Console Capture is an editable-source Windows/Tkinter program that opens a USB/serial console, runs commands and stores evidence for reports.

## Application flow

1. **START.bat** checks for Python 3.10+, creates a local virtual environment if needed and installs `requirements.txt` dependencies.
2. **console_capture.py** creates the Windows UI, terminal tabs, command queue and capture controller.
3. **discovery.py** enumerates Windows COM adapters and probes eligible ports with bounded Enter attempts. A response or login prompt is not the same as a completed authenticated CLI session.
4. Once connected, each COM port is owned by exactly one in-app **Session**. Received bytes are converted to readable terminal text using `core.transcript`; a recognizable Huawei prompt may yield a hostname.
5. **Command sets** come from `command_groups.json` and can be edited directly in the multiline Command Set Editor. The editor is non-modal, so console tabs remain usable while the editor is open. It is **not** safe to inject manual keystrokes into a device while that same device is executing an automated capture.
6. **core.command_text** validates each command, expands an optional `{interface}` placeholder, and accepts Huawei output-filter patterns such as `| i (MultiGE|Power type)`. This is a single-command check and does not guarantee commands are non-destructive.
7. A **Capture job** sends commands one at a time and saves TXT, BIN, PNG and `summary.json` under a per-run folder in `captures/`. Multiple devices can have independent jobs.
8. **word_export.py** reads saved capture manifests and image evidence. It fills compatible user Word templates, including combined inventory rows plus separate evidence tables for each device.
9. **app_config.py** centralizes the editable application name and subtitle, while **VERSION** supplies the title-bar/header version.
10. **capture_catalog.py** indexes saved runs for the Recent Captures and Word export search views; **ui_theme.py** draws the self-contained toolbar icon set.

## Practical controls

- **COM Manager:** Discover ports, Ctrl/Shift select multiple rows and **Connect Selected**; each successful connection creates or reuses a console session tab. Use **Check Response** on one port for a targeted probe.
- **Target port:** The target-port input is only shown when a selected command set or single command uses `{interface}`. Commands without the placeholder do not need it. For example, `display interface {interface}` substitutes the chosen port; `display version` does not.
- **Single command:** Enter a command, optionally choose a command-set name for evidence organization, then capture it on one device or select several connected devices to run it separately.
- **Command Set Editor:** Edit directly in the large multiline box, one command per line. Save changes to `command_groups.json`.
- **Terminal keyboard:** Return, arrow keys and Tab send native key sequences to the attached console when the device is idle. Tab completion depends on device firmware; local suggestion/autocomplete is not implemented.
- **Versioning:** The project is pre-1.0. Current development version is **0.7.7.0-alpha.2**. Previous documented milestone numbers receive a leading 0 for consistent alpha naming.

## Safety and limitations

- Detection is a Windows COM adapter listing; it does not prove a console cable reaches an operational device.
- Do not select ports owned by another terminal program. Connections are independent and may fail individually.
- Authentication remains manual in the interactive terminal.
- A command set may be edited while devices remain connected. However, automated capture reserves its device's serial input until that job completes or is cancelled.
- A successful simulation or CI test does not replace Windows USB-adapter and switch hardware testing.
- Save capture evidence locally; review TXT and Word outputs for confidential network details before sharing.
- Windows native menu was removed because equivalent toolbar buttons exist, but Windows' *title bar* remains managed by the operating system.
- Portable USB/offline Python installation is not part of this alpha change set.
