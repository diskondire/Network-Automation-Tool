import unittest
from core import command_text, prompt_kind, transcript


class CoreTests(unittest.TestCase):
    def test_huawei_filter_and_abbreviation(self):
        self.assertEqual(command_text('dis int transceiver | i Serial', {}), 'dis int transceiver | i Serial')

    def test_interface_placeholder(self):
        self.assertEqual(command_text('display interface {interface}', {'interface': '10GE 1/0/1'}),
                         'display interface 10GE 1/0/1')

    def test_missing_interface(self):
        with self.assertRaises(ValueError):
            command_text('display interface {interface}', {})

    def test_multiline_and_chaining_rejected(self):
        for value in ['display version\ndisplay clock', 'display version; reboot', 'display version | reboot']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                command_text(value, {})

    def test_huawei_prompt_and_login(self):
        self.assertEqual(prompt_kind('Welcome\n<PUB-SW01>'), ('cli', 'PUB-SW01'))
        self.assertEqual(prompt_kind('Welcome\nPassword:'), ('password', None))


    def test_nested_huawei_output_filter_patterns(self):
        cases = [
            'display interface transceiver verbose | i (transceiver|Manu. Serial Number)',
            'dis lldp nei | i (MultiGE|Power port class|Power type|PD requested power value|PSE allocated power value)',
        ]
        for command in cases:
            with self.subTest(command=command):
                self.assertEqual(command_text(command, {}), command)
        self.assertEqual(command_text('- dis lldp nei | i (MultiGE|Power port class)', {}),
                         'dis lldp nei | i (MultiGE|Power port class)')

    def test_malformed_filters_rejected(self):
        for command in ['display version | reboot', 'display version | i (broken',
                        'display version | i broken)']:
            with self.subTest(command=command), self.assertRaises(ValueError):
                command_text(command, {})

    def test_terminal_backspace(self):
        self.assertEqual(transcript(b'abc\b \bd\n'), 'abd\n')


if __name__ == '__main__':
    unittest.main()
