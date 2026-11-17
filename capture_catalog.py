"""Read-only index of saved console capture runs.

The catalog is intentionally independent of the GUI and network access.
"""
import json
from pathlib import Path


def list_capture_runs(folder):
    """Return (run directory, summary) pairs, newest first.

    Ignore corrupt or incomplete manifests; never follow external paths or
    change a saved capture as part of browsing.
    """
    root = Path(folder)
    if not root.is_dir():
        return []
    entries = []
    for manifest in root.glob('*/summary.json'):
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                continue
            results = data.get('results', [])
            if not isinstance(results, list):
                data['results'] = []
            entries.append((manifest.parent, data, manifest.stat().st_mtime))
        except (OSError, UnicodeError, ValueError):
            continue
    entries.sort(key=lambda item: item[2], reverse=True)
    return [(path, data) for path, data, _ in entries]


def matches_capture(run, search):
    """Match host, COM port, command group, time, and capture status."""
    _, data = run
    query = str(search or '').strip().casefold()
    if not query:
        return True
    words = [
        data.get('cli_hostname'), data.get('device'), data.get('com_port'),
        data.get('group'), data.get('started_at'), data.get('status'),
    ]
    return all(term in ' '.join(str(v or '') for v in words).casefold() for term in query.split())
