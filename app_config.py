"""Editable application identity and alpha version information.

Modify APP_NAME or APP_SUBTITLE to customize header text.
The VERSION file is the single source of truth for the release version.
"""
from pathlib import Path

APP_NAME = 'Console Capture'
APP_SUBTITLE = 'Made by Tom Chan'
DEFAULT_VERSION = '0.7.7.0-alpha.2'


def app_version():
    version_file = Path(__file__).resolve().parent / 'VERSION'
    try:
        return version_file.read_text(encoding='utf-8').strip() or DEFAULT_VERSION
    except OSError:
        return DEFAULT_VERSION


def window_title():
    return f'{APP_NAME} v{app_version()} — Alpha Preview'
