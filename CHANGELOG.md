## v7.7.0 preview (unreleased)
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
- Preserved v7.6.4 COM probing, command execution, screenshot generation and Word export behavior.

## v7.6.4
- Combined Word reports: one inventory table with multiple device rows, repeated evidence tables per device.
- Date display: DD-MM-YY (HH:MM).
- Removed redundant shortcut toolbar in favor of native Windows menus.

# Console Capture — documented version history

This history summarizes identifiable milestones. Early intermediate versions without verified records are not invented.

- **7.6.3** — Windows-style menu and Help → Version History; cancellation beside Run commands; run-state device colors (white idle, orange in progress, green completed, red failed/stopped); hostname and readable date in export picker; full user template repeated per device when exporting multiple runs into one Word document.
- **7.6.2** — Huawei CloudEngine model detection; screenshots sized to the width of Word table cells.
- **7.6.1** — User-owned `.docx` templates, metadata tokens and matching command screenshots in labelled cells.
- **7.6** — Top bar utilities and initial Word template export.
- **7.5.1** — Huawei CLI abbreviations and output filters, simplified login UI, optional target interface.
- **7.5** — Direct COM response probe with bounded Enter retries.
- **7.4** — USB/Bluetooth COM grouping, simpler statuses, preserved manager state, simplified serial settings.
- **7.3** — Connected-device controller and separate profile editing.
- **7.2** — Restored successful discovery probing from v6.5.
- **7.1** — Connection/response status and further probe controls.
- **7.0 trial** — Port-centric discovery with hostname-independent connections.
- **6.5** — Parallel command runs, cancellation control, Word evidence exports and COM Manager.
- **6.1** — Per-run screenshots/logs organized in PNG/TXT/BIN folders and summary metadata.
- **6.0** — Console navigation fixes, execution queue, diagnostics, Burn In group.
- **Earlier prototypes, including v3** — Python serial-console automation, captured output and screenshots.

For full details refer to individual project sources and change discussions. The above entries are milestones, not a claim that no other builds existed.
