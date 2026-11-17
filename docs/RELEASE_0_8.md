# Console Capture v0.8.0-alpha.1 — Offline USB Edition

This is a **pre-release** intended for testing on Windows x64 with supported serial adapters and Huawei equipment. The earlier v0.7 code is retained as a historical source release.

## New in 0.8
- USB distribution archive includes a signed official Python 3.13.17 Windows x64 installer.
- First run checks for an existing supported 64-bit Python (3.10–3.14) and skips Python installation if one is available.
- When Python is missing, a Yes/No prompt asks permission before launching the bundled installer.
- Dependencies can be installed without an internet connection using the bundled Windows wheelhouse.
- Console terminal displays a blinking visual cursor marker at the current rendered output position; it does not modify captured transcripts or the actual device stream.
- Appearance dialog adds optional dark mode, remembered between launches.
- v0.7 features including command-group editing, multi-COM selection, Word reports and Huawei CLI filters are retained.

## Download the correct file

For an offline USB drive, download **ConsoleCapture_v0.8.0_USB.zip** from the release Assets section. GitHub's auto-generated “Source code (zip)” is not an offline installer and contains no binary wheels.

Extract the whole ZIP to your USB drive and run **USB_START.bat**. For instructions and limitations, read **docs/USB_OFFLINE.md** inside the ZIP.

**Compatibility:** Windows 10/11 x64, Python 3.10–3.14 x64 (Python 3.13.17 installed on approval when none is available). USB drive must be writable and the PC must permit installer execution.

**Security:** The launcher validates the Python installer's Authenticode signature. It does not install Python without consent and does not use network access for dependencies. Captures may contain sensitive network data.

**Testing:** Automated tests cannot prove compatibility with your USB serial adapters, target Windows policies, or all Huawei OS versions. Test the bundle on a disconnected Windows machine before production use.
