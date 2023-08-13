"""
Determine whether operating system is in dark mode.

This module builds on answers to [this StackOverflow
question](https://stackoverflow.com/questions/65294987/detect-os-dark-mode-in-python)
and [the darkdetect package](https://github.com/albertosottile/darkdetect). The
latter seems both over- and under-engineered. In contrast, this module provides
the one interesting bit, is the system in dark mode, as just that.
"""

import sys


def is_darkmode() -> None | bool:
    try:
        if sys.platform in ('win32', 'cygwin'):
            return _is_darkmode_windows()
        elif sys.platform == 'darwin':
            return _is_darkmode_macos()
        elif sys.platform == 'linux':
            return _is_darkmode_linux()
        else:
            return False
    except:
        return None


def _is_darkmode_windows() -> bool:
    import winreg

    with winreg.OpenKey(  # type: ignore[attr-defined]
        winreg.HKEY_CURRENT_USER,  # type: ignore[attr-defined]
        "Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
    ) as key:
        return not winreg.QueryValueEx(  # type: ignore[attr-defined]
            key,
            "AppsUseLightTheme"
        )[0]


def _is_darkmode_macos() -> bool:
    import subprocess

    # Use DEVNULL so that output of command isn't shown
    return not subprocess.run(
        ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode


def _is_darkmode_linux() -> bool:
    import subprocess

    result = subprocess.run(
        ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
        capture_output=True,
        encoding='utf8',
    )
    if result.stdout == '':
        result = subprocess.run(
            ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
            capture_output=True,
            encoding='utf8',
        )
    return result.stdout.strip().strip("'").endswith('-dark')
