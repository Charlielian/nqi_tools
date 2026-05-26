# -*- coding: utf-8 -*-
"""
NQI工具 - PyQt6 入口
NQI平台数据提取工具

使用方法：
    python NqiTool_qt.py
"""

import sys
import os
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from core.license import get_hw_info, generate_machine_code, verify_license, get_effective_expiry
from core.license import verify_serial_number, write_license_from_serial
from gui.qt_main_window import NqiToolMainWindow, NqiToolApp


def check_license():
    """检查授权"""
    hw_info = get_hw_info()
    machine_code = generate_machine_code(hw_info)
    valid, error = verify_license(machine_code)
    return valid, error, machine_code


def show_activate_dialog(machine_code):
    """显示激活对话框"""
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
    from PyQt6.QtCore import QTimer

    class ActivateDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("授权激活")
            self.setFixedSize(500, 350)

            layout = QVBoxLayout(self)
            layout.setSpacing(16)

            # 标题
            header = QLabel("⚠️ 授权验证失败")
            header.setStyleSheet("""
                QLabel {
                    background-color: #dc2626;
                    color: white;
                    font-size: 16pt;
                    font-weight: bold;
                    padding: 15px;
                    border-radius: 8px;
                }
            """)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(header)

            # 本机信息
            info_label = QLabel("📋 本机信息 - 机器码")
            info_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
            layout.addWidget(info_label)

            self.code_label = QLabel(machine_code)
            self.code_label.setStyleSheet("""
                QLabel {
                    background-color: #f8f9fa;
                    padding: 10px;
                    border-radius: 4px;
                    font-family: Consolas;
                    font-size: 10pt;
                    qproperty-wordWrap: true;
                }
            """)
            layout.addWidget(self.code_label)

            copy_btn = QPushButton("复制机器码")
            copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e9ecef;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #dee2e6; }
            """)
            copy_btn.clicked.connect(lambda checked, mc=machine_code: self._copy_to_clipboard(mc, copy_btn))
            layout.addWidget(copy_btn)

            # 序列号输入
            serial_label = QLabel("🎫 输入验证序列号")
            serial_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
            layout.addWidget(serial_label)

            self.serial_input = QLineEdit()
            self.serial_input.setPlaceholderText("格式示例：NQI-xxxx-xxxx-xxxx")
            self.serial_input.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 10px;
                    font-family: Consolas;
                    font-size: 11pt;
                }
            """)
            layout.addWidget(self.serial_input)

            self.hint_label = QLabel("")
            self.hint_label.setStyleSheet("color: #6c757d; font-size: 9pt;")
            layout.addWidget(self.hint_label)

            # 按钮
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            self.activate_btn = QPushButton("✅ 激活授权")
            self.activate_btn.setStyleSheet("""
                QPushButton {
                    background-color: #22c55e;
                    color: white;
                    font-weight: bold;
                    padding: 10px 24px;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #16a34a; }
            """)
            self.activate_btn.clicked.connect(self._on_activate)
            btn_layout.addWidget(self.activate_btn)

            exit_btn = QPushButton("退出")
            exit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e9ecef;
                    padding: 10px 24px;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #dee2e6; }
            """)
            exit_btn.clicked.connect(lambda: sys.exit(1))
            btn_layout.addWidget(exit_btn)

            layout.addLayout(btn_layout)

        def _copy_to_clipboard(self, text, btn):
            """复制到剪贴板"""
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            # 显示复制成功的提示
            original_text = btn.text()
            btn.setText("已复制!")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #22c55e;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
            """)
            # 2秒后恢复
            QTimer.singleShot(2000, lambda: self._restore_btn(btn, original_text))

        def _restore_btn(self, btn, original_text):
            """恢复按钮原状"""
            btn.setText(original_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e9ecef;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #dee2e6; }
            """)

        def _on_activate(self):
            serial = self.serial_input.text().strip()
            if not serial:
                self.hint_label.setText("请输入序列号")
                self.hint_label.setStyleSheet("color: #ef4444; font-size: 9pt;")
                return

            self.hint_label.setText("正在验证...")
            self.hint_label.setStyleSheet("color: #fbbf24; font-size: 9pt;")
            self.activate_btn.setEnabled(False)

            success, result = verify_serial_number(serial, machine_code)

            if success:
                write_success, msg = write_license_from_serial(result)
                if write_success:
                    self.hint_label.setText("激活成功！")
                    self.hint_label.setStyleSheet("color: #22c55e; font-size: 9pt;")
                    QMessageBox.information(self, "成功", "激活成功！")
                    self.accept()
                    start_main_app()
                else:
                    self.hint_label.setText(f"写入授权失败：{msg}")
                    self.hint_label.setStyleSheet("color: #ef4444; font-size: 9pt;")
                    self.activate_btn.setEnabled(True)
            else:
                self.hint_label.setText(result)
                self.hint_label.setStyleSheet("color: #ef4444; font-size: 9pt;")
                self.activate_btn.setEnabled(True)

    dialog = ActivateDialog()
    dialog.exec()


def start_main_app():
    """启动主程序"""
    app = NqiToolApp()
    sys.exit(app.run())


def main():
    """主函数"""
    valid, error, machine_code = check_license()
    if not valid:
        # Must create QApplication before any widget
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        show_activate_dialog(machine_code)
    else:
        start_main_app()


if __name__ == '__main__':
    main()
