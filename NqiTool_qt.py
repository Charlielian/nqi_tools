# -*- coding: utf-8 -*-
"""
Qt6 版入口主程序
保持多版本共存：与 Tkinter 版 (NqiTool.py) 完全隔离，共用 core 与 utils 逻辑
"""

import os
import sys
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from utils.config import EXPIRY_DATE, LOG_DIR
from utils.logger import ensure_dirs, setup_report_logging


def check_expiry():
    """检查软件是否在有效期内"""
    try:
        expiry = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d")
        now = datetime.now()
        if now > expiry:
            return False, expiry
        return True, expiry
    except Exception:
        return False, None


def main():
    ensure_dirs()
    setup_report_logging(LOG_DIR, console=True)

    # 高分屏适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("NQI数据导出工具 (Qt6版)")

    # 有效期校验
    valid, expiry_date = check_expiry()
    if not valid:
        msg = f"软件已于 {EXPIRY_DATE} 到期，请联系管理员更新授权！" if expiry_date else "软件授权校验失败，请联系管理员！"
        QMessageBox.critical(None, "授权已过期", msg)
        sys.exit(1)

    # 启动主窗口 (主窗口内部会自动装载默认的白色系主题 light.qss，并支持一键切换暗色系)
    from qt_gui.main_window import QtMainWindow
    window = QtMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
