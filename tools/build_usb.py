"""Create a self-contained Windows x64 Console Capture USB ZIP.

Run this on a networked Windows builder. The resulting ZIP includes:
- official signed Python installer
- predownloaded Windows x64 dependency wheels for Python 3.10-3.14
- the editable application source and an offline-only launcher

Nothing is fetched by the USB launcher on the target machine.
"""
import argparse
import hashlib
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PYTHON_VERSION = '3.13.17'
INSTALLER = f'python-{PYTHON_VERSION}-amd64.exe'
PYTHON_URL = f'https://www.python.org/ftp/python/{PYTHON_VERSION}/{INSTALLER}'
PYTHON_TARGETS = ('310', '311', '312', '313', '314')
FILES = [
    'console_capture.py', 'core.py', 'discovery.py', 'word_export.py',
    'capture_catalog.py', 'ui_theme.py', 'app_config.py', 'command_groups.json',
    'VERSION', 'requirements.txt', 'START.bat', 'USB_START.bat',
    'usb/launch_offline.ps1', 'README.md', 'CHANGELOG.md',
    'docs/HOW_IT_WORKS.md', 'docs/USB_OFFLINE.md',
]


def download_python(destination):
    request = urllib.request.Request(PYTHON_URL, headers={'User-Agent': 'ConsoleCapture-USB-builder/0.8'})
    with urllib.request.urlopen(request, timeout=90) as response, destination.open('wb') as target:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
    if destination.stat().st_size < 15 * 1024 * 1024:
        raise RuntimeError('Downloaded Python installer is unexpectedly small.')
    print('Bundled installer:', destination.stat().st_size, 'bytes')


def download_wheels(destination):
    for version in PYTHON_TARGETS:
        cmd = [
            sys.executable, '-m', 'pip', 'download', '--disable-pip-version-check',
            '--only-binary=:all:', '--dest', str(destination),
            '--platform', 'win_amd64', '--implementation', 'cp',
            '--python-version', version, '--abi', 'cp' + version,
            '-r', str(BASE / 'requirements.txt'),
        ]
        print('Downloading wheels for Python', version, flush=True)
        subprocess.run(cmd, check=True)
    wheels = list(destination.glob('*.whl'))
    if not wheels:
        raise RuntimeError('Wheel download returned no packages.')
    return wheels


def create_bundle(output):
    with tempfile.TemporaryDirectory(prefix='consolecapture-usb-') as temp:
        temporary = Path(temp)
        python_dir = temporary / 'offline' / 'python'
        wheels_dir = temporary / 'offline' / 'wheels'
        python_dir.mkdir(parents=True)
        wheels_dir.mkdir(parents=True)
        download_python(python_dir / INSTALLER)
        wheels = download_wheels(wheels_dir)
        root_name = 'ConsoleCapture_v0.8.0_USB'
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for item in FILES:
                source = BASE / item
                if not source.is_file():
                    raise FileNotFoundError(source)
                archive.write(source, f'{root_name}/{item}')
            for file in python_dir.iterdir():
                archive.write(file, f'{root_name}/offline/python/{file.name}')
            for file in wheels:
                archive.write(file, f'{root_name}/offline/wheels/{file.name}')
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('Created USB archive failed CRC validation.')
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        print('Created:', output)
        print('SHA256:', digest)
        print('Wheels:', len(wheels))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=BASE / 'ConsoleCapture_v0.8.0_USB.zip')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    create_bundle(args.output)
