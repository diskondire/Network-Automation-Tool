# Console Capture v7.5 — Windows desktop application

This is a Python/Tkinter source distribution. It requires Windows, Python 3.10+ and access to pip when first launched. Extract the folder and run `START.bat`. No packaged executable is included.

## Workflow

1. Open **Discover / Connect COM Ports** in the left sidebar. The COM Manager also opens when the app launches.
2. Click **Discover Ports** to enumerate all COM ports reported by Windows and probe their serial responses without sending login credentials. The scan reuses the established v6.5/v7.2 probing method.
3. Ports appear under **USB**, **Bluetooth**, or **Other / Unknown**, based on Windows port metadata. The grouping cannot establish that a network device is physically attached.
4. Select a COM port and choose **Auto (detected)**, **9600 / 8N1**, **115200 / 8N1**, or **Custom...** settings. Click **Connect**. Only a successfully opened app-owned serial session is shown as Connected.
5. Select the device in the sidebar or its terminal tab. If the console stops at Username/Password, enter credentials in the application terminal or right-hand login controls; the hostname appears after a recognizable authenticated CLI prompt.
6. Choose a command set, run commands, inspect captured output, and export Word documents.

## Changes from v7.3

- Device Profiles editor, Role field, and hard-coded Switch/WAC connection presets are removed from the visible workflow.
- The COM Manager retains its results when closed (hidden) and reopened during the current application process. Starting a new process requires a new discovery scan.
- USB, Bluetooth, and Other grouping; one operational Status column; technical probe details shown below the list.
- Single-port Connect/Disconnect/Check Response controls; no ambiguous multi-select commands.
- Discovered hostname is not required. Login-required devices remain usable for manual login; the app never infers hostname from a generic password prompt.
- Session-specific serial speed is independent of device type. Connection-speed presets are editable directly in the manager.
- Command sets remain independent of device sessions. Existing Huawei command sets and Word export are retained.
- Login credentials are session-only; not persisted in device profiles or the Windows credential vault.
- Old `device_profiles.json` is not distributed, and fresh sessions are temporary. If one is present locally, it is read only as a source of known serial parameters for probing.

## Important limitations

- **Detected** means registered with Windows, not necessarily an attached, responsive console. A port may be occupied by another application, including MobaXterm.
- The auto-detected speed relies on a recognized probe response. When unavailable, 9600 8N1 is the fallback; set another speed manually as needed.
- The command capture parser currently validates Huawei `display` commands; the command-set architecture has not yet been generalized to all vendors.
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
