import json
import tempfile
import unittest
from pathlib import Path
from docx import Document
from PIL import Image
from word_export import export_word, extract_inventory, safe_image_path


class WordExportTests(unittest.TestCase):
    def _capture(self, root, hostname, serial, model):
        folder = root / hostname
        (folder / 'TXT').mkdir(parents=True)
        (folder / 'PNG').mkdir()
        output = (f'display version\nHUAWEI CloudEngine {model} uptime is 2 hours\n'
                  f'ESN: {serial}\n<{hostname}>')
        (folder / 'TXT' / 'display_version.txt').write_text(output, encoding='utf-8')
        Image.new('RGB', (640, 320), (240, 240, 240)).save(folder / 'PNG' / 'display_version.png')
        (folder / 'summary.json').write_text(json.dumps({
            'cli_hostname': hostname, 'device': hostname, 'group': 'Burn In',
            'com_port': 'COM12', 'started_at': '2026-11-16T12:00:00',
            'results': [{'command': 'display version', 'order': 1,
                         'result': 'completed', 'text': 'TXT/display_version.txt',
                         'images': ['PNG/display_version.png']}]
        }), encoding='utf-8')
        return folder

    def test_model_and_combined_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._capture(root, 'PUB-SW01', '12345678', 'S5755-H')
            second = self._capture(root, 'PUB-SW02', '22345678', 'S5755-H')
            details = extract_inventory(first, json.loads((first / 'summary.json').read_text()))
            self.assertEqual(details['MODELNO'], 'HUAWEI CloudEngine S5755-H')
            template = root / 'example.docx'
            doc = Document()
            doc.add_paragraph('Date: DATE')
            inventory = doc.add_table(rows=2, cols=4)
            for cell, name in zip(inventory.rows[0].cells, ['No', 'Hostname', 'Serial', 'Model']):
                cell.text = name
            for cell, value in zip(inventory.rows[1].cells, ['1', 'HOSTNAME', 'SERIALNO', 'MODELNO']):
                cell.text = value
            evidence = doc.add_table(rows=2, cols=1)
            evidence.cell(0, 0).text = 'display version'
            evidence.cell(1, 0).text = 'DISPLAYVERSION'
            doc.save(template)
            paths = export_word([first, second], root / 'reports', combined=True, template=template)
            self.assertEqual(len(paths), 1)
            generated = Document(paths[0])
            self.assertEqual(len(generated.tables[0].rows), 3)
            self.assertEqual(generated.tables[0].rows[1].cells[1].text, 'PUB-SW01')
            self.assertEqual(generated.tables[0].rows[2].cells[1].text, 'PUB-SW02')
            self.assertEqual(len(generated.inline_shapes), 2)

    def test_image_path_restriction(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                safe_image_path(Path(temporary), '../outside.png')


if __name__ == '__main__':
    unittest.main()
