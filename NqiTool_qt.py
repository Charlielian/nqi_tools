# -*- coding: utf-8 -*-
"""
NQI工具 - PyQt6 入口
NQI平台数据提取工具

使用方法：
    python NqiTool_qt.py
"""

import sys
from PyQt6.QtWidgets import QApplication

from utils.config import EXPIRY_DATE
from gui.qt_main_window import NqiToolMainWindow, NqiToolApp


def check_license():
    """检查授权 - 只验证 EXPIRY_DATE 是否过期"""
    from datetime import datetime
    try:
        expiry = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d")
        if datetime.now() > expiry:
            return False, f"程序已过期（{EXPIRY_DATE}）"
        return True, None
    except Exception as e:
        return False, f"日期解析错误: {e}"


def main():
    """主函数"""
    valid, error = check_license()
    if not valid:
        # Must create QApplication before any widget
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "授权验证", f"授权验证失败\n\n{error}\n\n程序将退出。")
        sys.exit(1)

    app = NqiToolApp()
    sys.exit(app.run())


if __name__ == '__main__':
    main()
