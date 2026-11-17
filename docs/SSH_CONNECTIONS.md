# SSH connections — v0.7.8 alpha

Console Capture supports the original Windows COM serial terminals **and** password-authenticated SSH sessions on TCP port 22 (custom port supported).

## Connecting

1. Verify that the destination switch/WAC/firewall has SSH enabled, is reachable, and your account is authorized.
2. **Verify and trust the host key first**. On Windows with OpenSSH, run `ssh username@host` once and independently compare the displayed server fingerprint with the device administrator's approved fingerprint before accepting it. For a nonstandard port, use `ssh -p 2222 username@host`.
3. In Console Capture, click **SSH** on the toolbar (or **New SSH session** in the sidebar).
4. Enter the device hostname/IP, SSH port, username and password. The password is not saved to disk.
5. Click **Connect SSH**. The SSH connection is established in a worker thread so the GUI remains responsive.
6. Select the new SSH terminal tab. Type and use Enter, arrows, Tab and Ctrl+C as with a serial console.
7. Use the same command sets, single-command capture, evidence storage and Word report exporter.

The **Connect** button reconnects a selected SSH session and asks for its password again. **Disconnect** closes the session. Serial connections remain available via **COM Ports**.

## Security

- Strict host-key verification is enforced. Unknown and changed host keys are rejected; there is no "accept any key" option.
- SSH passwords are used for the active connection only; they are not written to JSON settings, captures or logs.
- SSH password login is supported in this first version. Private-key and SSH-agent login are not yet supported.
- The initial profile is temporary and exists only while Console Capture is running.
- Host-key files use Paramiko's standard OpenSSH system/user `known_hosts` handling. Keep the trusted keys up to date.
- Some network devices display prompts or ANSI terminal sequences differently. Device-side CLI command behavior and timeouts still apply.

## Troubleshooting

**Host key unknown / not found**: Connect once using Windows OpenSSH and verify the actual fingerprint with an independent trusted source. Do not automatically trust a `ssh-keyscan` result.

**Authentication failed**: Verify username/password, network permissions and whether password authentication is enabled on the device.

**No CLI prompt**: Click the terminal and press Enter. Automatic command capture requires a recognized Huawei-style `<hostname>` or `[hostname]` prompt.

**SSH connection closes**: Check SSH access control, management IP reachability, idle timeout and SSH service logs.

**Missing SSH module**: Run `START.bat`; it installs dependencies from `requirements.txt` when required. For source installs: `python -m pip install -r requirements.txt`.

This is an **alpha** addition; test interactive terminals, command sets, reports and reconnection on your actual hardware before production use.
