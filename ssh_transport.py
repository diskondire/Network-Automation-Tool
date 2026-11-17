"""SSH channel adapter exposing the small serial-like interface used by sessions.

Host-key verification is mandatory; unknown or changed host keys are rejected.
Credentials are provided at connection time and are never persisted.
"""
import hashlib
import re
import socket

import paramiko


def validate_ssh_endpoint(host, port, username):
    host = str(host).strip()
    username = str(username).strip()
    try:
        port = int(port)
    except (TypeError, ValueError) as exc:
        raise ValueError('SSH port must be a number.') from exc
    if not host or len(host) > 253 or not re.fullmatch(r'[A-Za-z0-9_.:\[\]-]+', host):
        raise ValueError('Enter a valid SSH hostname or IP address.')
    if not 1 <= port <= 65535:
        raise ValueError('SSH port must be between 1 and 65535.')
    if not username or len(username) > 128 or any(c.isspace() for c in username):
        raise ValueError('Enter an SSH username without whitespace.')
    return host, port, username


def server_key_fingerprint(key):
    """SHA-256 host-key fingerprint for independent verification."""
    import base64
    digest = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode('ascii')
    return 'SHA256:' + digest.rstrip('=')


class SSHTransport:
    """Paramiko interactive shell wrapped for the existing session API."""

    def __init__(self, client, channel):
        self.client = client
        self.channel = channel
        self._open = True

    @classmethod
    def connect(cls, host, port, username, password, *, timeout=10, hostkey_policy=None):
        host, port, username = validate_ssh_endpoint(host, port, username)
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        try:
            client.load_host_keys(str(__import__('pathlib').Path.home() / '.ssh' / 'known_hosts'))
        except OSError:
            pass
        client.set_missing_host_key_policy(hostkey_policy or paramiko.RejectPolicy())
        try:
            client.connect(
                hostname=host, port=port, username=username, password=password,
                look_for_keys=False, allow_agent=False,
                timeout=timeout, auth_timeout=timeout, banner_timeout=timeout,
            )
            channel = client.invoke_shell(term='vt100', width=120, height=36)
            channel.settimeout(0.0)
            return cls(client, channel)
        except Exception:
            client.close()
            raise

    @property
    def is_open(self):
        return self._open and not self.channel.closed and self.channel.active

    @property
    def in_waiting(self):
        return 65536 if self.is_open and self.channel.recv_ready() else 0

    def read(self, count):
        if not count or not self.is_open or not self.channel.recv_ready():
            return b''
        try:
            return self.channel.recv(min(count, 65536))
        except (socket.timeout, BlockingIOError):
            return b''

    def write(self, data):
        if not self.is_open:
            raise OSError('SSH connection is closed.')
        # Paramiko send() can write fewer bytes than requested.
        self.channel.sendall(data)
        return len(data)

    def reset_input_buffer(self):
        """Drain pending terminal output, without discarding the connection."""
        while self.is_open and self.channel.recv_ready():
            if not self.channel.recv(65536):
                break

    def close(self):
        self._open = False
        try:
            self.channel.close()
        finally:
            self.client.close()
