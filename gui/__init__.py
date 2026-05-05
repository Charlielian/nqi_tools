# -*- coding: utf-8 -*-
"""
gui - GUI组件模块
"""

from .widgets import TableConfig

def get_login_dialog():
    """懒加载 LoginDialog（tkinter 版本）"""
    from .login_dialog import LoginDialog
    return LoginDialog

def get_main_window():
    """懒加载 NqiToolGUI（tkinter 版本）"""
    from .main_window import NqiToolGUI
    return NqiToolGUI
