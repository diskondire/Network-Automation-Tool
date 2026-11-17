"""SSH transport adapter tests; no network or credentials required."""
import unittest
from unittest.mock import Mock, patch

from ssh_transport import SSHTransport, validate_ssh_endpoint, server_key_fingerprint


class SSHValidationTests(unittest.TestCase):
    def test_valid_endpoint(self):
        self.assertEqual(validate_ssh_endpoint('10.10.10.1', '22', 'admin'),
                         ('10.10.10.1', 22, 'admin'))

    def test_invalid_endpoint(self):
        for host, port, username in [
            ('', 22, 'admin'), ('host', 0, 'admin'),
            ('host', 65536, 'admin'), ('host', 'abc', 'admin'),
            ('host', 22, ''), ('host', 22, 'bad username'),
        ]:
            with self.subTest(host=host, port=port, user=username):
                with self.assertRaises(ValueError):
                    validate_ssh_endpoint(host, port, username)

    @patch('ssh_transport.paramiko.SSHClient')
    def test_connect_rejects_unknown_hosts_by_default(self, client_class):
        client = client_class.return_value
        client.invoke_shell.return_value = Mock(closed=False, active=True)
        connection=SSHTransport.connect('192.0.2.10',22,'admin','secret')
        self.assertIsInstance(connection, SSHTransport)
        policy=client.set_missing_host_key_policy.call_args.args[0]
        self.assertEqual(policy.__class__.__name__, 'RejectPolicy')
        kwargs=client.connect.call_args.kwargs
        self.assertFalse(kwargs['look_for_keys'])
        self.assertFalse(kwargs['allow_agent'])
        self.assertEqual(kwargs['password'], 'secret')
        connection.close()

    @patch('ssh_transport.paramiko.SSHClient')
    def test_failure_closes_client(self, client_class):
        client=client_class.return_value
        client.connect.side_effect=OSError('connection refused')
        with self.assertRaises(OSError):
            SSHTransport.connect('192.0.2.10',22,'admin','secret')
        client.close.assert_called_once()

    def test_channel_read_write_disconnect(self):
        client=Mock()
        channel=Mock(closed=False,active=True)
        channel.recv_ready.side_effect=[True,True,False]
        channel.recv.return_value=b'<HW-SW01>'
        transport=SSHTransport(client,channel)
        self.assertEqual(transport.in_waiting,65536)
        self.assertEqual(transport.read(4096), b'<HW-SW01>')
        self.assertEqual(transport.write(b'display version\r'),16)
        channel.sendall.assert_called_with(b'display version\r')
        transport.close()
        client.close.assert_called_once()
        self.assertFalse(transport.is_open)


if __name__ == '__main__':
    unittest.main()
