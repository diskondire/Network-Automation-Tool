# Console Capture v7.7 — Operator UX preview

This branch deliberately isolates an interface overhaul from the stable v7.6.4 release.

## What changed

- Classic Windows-style visual toolbar with real functions: COM Ports, Connect, Disconnect, Captures, Word Export, Diagnostics, Appearance and History.
- Device/Captures navigator: devices show run states, recent captures can open original evidence folders without changing files.
- Generated flat icon set and application icon, with no external graphic dependencies beyond the existing Pillow package.
- Informative, clickable home screen before the first console session.
- Task-oriented right panel separates command sets, execution queue, single commands, and Word export.
- A non-clickable overview header shows devices, open connections and running jobs.
- A bottom activity bar reports overall command progress, without adding another row of redundant menu buttons.
- The device list displays the detected hostname when available.
- Exporting Word reports now offers a searchable capture list by hostname, COM port, command group, date and status.
- If the optional Burn-In template is absent from the repository, the export picker starts without a selected template and can still use standard Word export.
- Internal helpers for visual style and capture indexing are separately testable.
- An automated Windows Python regression suite covers command filters, prompt parsing, capture indexing, model detection and combined Word output.

## Stability boundaries

The v7.6.4 serial discovery algorithm, bounded Enter probing, command engine, capture renderer and Word report generator are intentionally unchanged. The application is still editable Python source; no EXE is required.

## Hands-on acceptance checklist

- [ ] Windows launch through START.bat; app icon and toolbar icons display correctly and controls remain usable at 1366×768 and 1920×1080.
- [ ] USB and Bluetooth adapters appear correctly in COM Manager.
- [ ] COM port response test detects Huawei prompt and login-required banner.
- [ ] Two connected devices can execute independent Burn In groups; the status bar and device colors update.
- [ ] Cancel a running command; verify partial capture evidence and status.
- [ ] Recent Captures tab loads saved evidence, opens selected folder and refreshes after a command run.
- [ ] Toolbar buttons operate their named actions and do not interfere with native menus.
- [ ] Export picker search filters by hostname and returns the correct run after selection.
- [ ] Export one run using an authorized customer template and two runs as a combined report.
- [ ] Close/reopen COM Manager without losing current session state.
- [ ] No passwords are written to diagnostics, capture logs, or reports.

Do not merge before physical Windows hardware acceptance. These automated checks cannot substitute for real console testing.
