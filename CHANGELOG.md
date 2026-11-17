## v0.8.0-alpha.1 (USB prerelease)
- Bundled offline USB launcher checks for existing 64-bit Python 3.10–3.14 and asks user consent before installing bundled signed Python 3.13.17.
- Offline dependency wheels ship in the Windows release ZIP and install using pip --no-index; no internet needed on target PC.
- Added a blinking UI-only CLI cursor marker which never modifies captured transcripts or Word screenshots.
- Appearance dialog offers dark/light mode, saved in local ui_settings.json, with themed application and terminal surfaces.
- Added Windows release automation and offline dependency smoke test; retained 0.7 prerelease history.
- Kept v0.7 command sets, multi-COM connection, capture and Word export workflows intact.

## v0.7.7.0-alpha.2 (unreleased)
- Fixed Command Set Editor controls: permanently visible Save/Add/Delete/Close footer, direct Add/Edit/Remove command buttons, and window-size-aware editor sizing.
- Redesigned target-port field to appear only for interface-specific commands.
- Added single-command evidence under an existing command set and a multi-device capture option.
- Removed redundant native menu; retained the graphic Windows-style ribbon.
- Added Ctrl/Shift multi-select and batch Connect Selected in the COM Manager.
- Allowed Huawei filter regex alternatives inside parentheses and leading bulleted commands.
- Replaced the command set's separate input field with a direct multiline editor.
- Kept the command-set editor non-modal so terminals remain interactive while editing.
- Retained serial Tab transmission; local predictive CLI completion is deferred.
- Prefixed displayed and documented versions with 0. for the alpha series.
- Fixed the Word export dialog action bar: Export selected captures and Cancel now remain visible at the bottom, with a scrollable capture/template form and screen-height-aware window sizing.
- Added a classic Windows-style icon ribbon, application logo, Devices/Captures sidebar, per-device status indicator, and actionable home screen.
- All toolbar shortcuts invoke existing application commands; native menus remain accessible.
- Icons are generated in Python using Pillow so the source remains editable and self-contained.
- Added icon-rendering unit tests and recent evidence navigation.
- Redesigned the operator workspace with an informational device overview and live command-progress bar.
- Grouped command automation, execution queue, single-command capture, and Word reports into distinct right-side panels.
- Added detected hostnames to device-session labels.
- Made the Word export picker searchable by hostname, port, command set, date and status.
- Word export gracefully falls back to standard reports when no optional template is bundled.
- Added unit tests, a Windows Actions verification workflow and an operator acceptance checklist.
- Preserved v0.7.6.4 COM probing, command execution, screenshot generation and Word export behavior.

## v0.7.6.4
- Combined Word reports: one inventory table with multiple device rows, repeated evidence tables per device.
- Date display: DD-MM-YY (HH:MM).
- Removed redundant shortcut toolbar in favor of native Windows menus.

# Console Capture — documented version history

This history summarizes identifiable milestones. Early intermediate versions without verified records are not invented.

- **0.7.6.3** — Windows-style menu and Help → Version History; cancellation beside Run commands; run-state device colors (white idle, orange in progress, green completed, red failed/stopped); hostname and readable date in export picker; full user template repeated per device when exporting multiple runs into one Word document.
- **0.7.6.2** — Huawei CloudEngine model detection; screenshots sized to the width of Word table cells.
- **0.7.6.1** — User-owned `.docx` templates, metadata tokens and matching command screenshots in labelled cells.
- **0.7.6** — Top bar utilities and initial Word template export.
- **0.7.5.1** — Huawei CLI abbreviations and output filters, simplified login UI, optional target interface.
- **0.7.5** — Direct COM response probe with bounded Enter retries.
- **0.7.4** — USB/Bluetooth COM grouping, simpler statuses, preserved manager state, simplified serial settings.
- **0.7.3** — Connected-device controller and separate profile editing.
- **0.7.2** — Restored successful discovery probing from v0.6.5.
- **0.7.1** — Connection/response status and further probe controls.
- **7.0 trial** — Port-centric discovery with hostname-independent connections.
- **0.6.5** — Parallel command runs, cancellation control, Word evidence exports and COM Manager.
- **0.6.1** — Per-run screenshots/logs organized in PNG/TXT/BIN folders and summary metadata.
- **0.6.0** — Console navigation fixes, execution queue, diagnostics, Burn In group.
- **Earlier prototypes, including v0.3** — Python serial-console automation, captured output and screenshots.

For full details refer to individual project sources and change discussions. The above entries are milestones, not a claim that no other builds existed.
