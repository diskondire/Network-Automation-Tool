import json
import tempfile
import unittest
from pathlib import Path
from capture_catalog import list_capture_runs, matches_capture


class CaptureCatalogTests(unittest.TestCase):
    def test_search_and_invalid_manifests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            good = root / 'run-a'
            bad = root / 'run-b'
            good.mkdir(); bad.mkdir()
            (good / 'summary.json').write_text(json.dumps({
                'cli_hostname': 'PUB-SW01', 'com_port': 'COM12', 'group': 'Burn In',
                'started_at': '2026-11-16T10:20:00', 'status': 'completed',
                'results': [{'command': 'display version'}]}), encoding='utf-8')
            (bad / 'summary.json').write_text('{bad json', encoding='utf-8')
            runs = list_capture_runs(root)
            self.assertEqual(len(runs), 1)
            self.assertTrue(matches_capture(runs[0], 'pub-sw01 burn'))
            self.assertTrue(matches_capture(runs[0], 'COM12'))
            self.assertFalse(matches_capture(runs[0], 'COM9'))

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(list_capture_runs(Path(temporary) / 'missing'), [])


if __name__ == '__main__':
    unittest.main()
