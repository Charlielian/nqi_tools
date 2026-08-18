# -*- coding: utf-8 -*-
"""
gui - GUI组件模块
"""

from .widgets import LogTextHandler, ScrolledTextFrame, DateEntry, TableConfig
from .login_dialog import LoginDialog
from .first_run import check_first_run, show_first_run_wizard

__all__ = [
    'LogTextHandler', 'ScrolledTextFrame', 'DateEntry', 'TableConfig',
    'LoginDialog', 'NqiToolGUI', 'check_first_run', 'show_first_run_wizard',
]


def __getattr__(name):
    if name == 'NqiToolGUI':
        from .main_window import NqiToolGUI
        return NqiToolGUI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
