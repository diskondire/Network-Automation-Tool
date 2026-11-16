# Console Capture v7.6.4 — baseline

This branch starts from the last Windows-tested version reported working by the project owner.

## Initial source import
Upload **individual source files** extracted from the v7.6.4 ZIP to the root of this branch:
- console_capture.py
- core.py
- discovery.py
- word_export.py
- requirements.txt
- START.bat
- command_groups.json
- CHANGELOG.md

Do not upload virtual environments, captured outputs, reports or any user-specific secrets.
Review company/customer material before publishing. Do not upload the custom BurnIn template unless you are authorized to distribute it.

## Workflow
- Keep main as the stable branch.
- Develop changes on feature/* branches.
- Run syntax tests, GUI tests and physical serial-device checks before merging.
- Retain editable Python source; packaging is optional, not the source of truth.
- Use releases only after verifying each version.
