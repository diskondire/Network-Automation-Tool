# Console Capture v0.7.8.0-alpha.1 — SSH support

This is an **alpha source release** based on the current `main` branch with the v0.7.7 features preserved. It does **not** contain the unstable v0.8 USB installer or the abandoned v0.9 desktop prototype.

## New in v0.7.8

- SSH connection button in the graphical toolbar and Devices sidebar
- SSH interactive terminal tabs with configurable hostname/IP, TCP port, username and password
- SSH connections run in a background worker to avoid blocking Tkinter while authenticating
- Host keys strictly checked against trusted OpenSSH known_hosts records; unknown/changed keys rejected
- No SSH passwords saved to profiles, captures or configuration files
- Existing CLI command automation, screenshots, evidence manifests and Word exports work through the same session API for SSH and serial ports
- Existing serial COM connections remain supported

## Getting started (Windows)

1. Download the source archive from this GitHub Release and extract it.
2. Run `START.bat`. Python 3.10+ must already be installed; missing libraries, including Paramiko, can be installed using pip. Internet access may be needed for first-run dependencies.
3. Verify your SSH device's host key **out of band** with your network administrator. If not already trusted, use Windows OpenSSH (`ssh username@host`) and compare the fingerprint before accepting the key into `~/.ssh/known_hosts`.
4. Open Console Capture and select **SSH**, enter the target's host, port, username and password, then connect.
5. Use the normal terminal, command set, capture and Word export workflows.

See [SSH Connections](https://github.com/diskondire/Network-Automation-Tool/blob/main/docs/SSH_CONNECTIONS.md) for details.

**Limitations:** First release supports interactive password authentication only; SSH keys and agent sign-in are future work. Captures still require a CLI prompt format recognized by Console Capture, primarily Huawei VRP. Real device/Windows SSH behavior is not validated by automated unit tests. Do not treat the alpha as production certified.
