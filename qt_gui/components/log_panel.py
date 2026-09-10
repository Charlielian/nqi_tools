# -*- coding: utf-8 -*-
"""
Qt6 彩色高性能日志控制台组件
"""

from datetime import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
from PyQt6.QtCore import Qt, pyqtSlot


class QtLogViewer(QWidget):
    """带级别彩色高亮、自动滚动与一键清空复制的日志面板"""

    # 亮色主题下使用深色正文 + 清晰色块，保证白底可读
    COLOR_MAP = {
        'DEBUG': QColor('#71717A'),     # 调试灰
        'INFO': QColor('#1D4ED8'),      # 深蓝（白底可读）
        'SUCCESS': QColor('#15803D'),   # 深绿（白底可读）
        'WARNING': QColor('#B45309'),   # 深橙（白底可读）
        'ERROR': QColor('#DC2626'),     # 深红（白底可读）
    }
    # 消息正文颜色（白底主题下为深灰，暗色主题下由暗色 QSS 覆盖为亮色）
    MESSAGE_COLOR = QColor('#1F2328')

    def __init__(self, parent=None, max_lines: int = 3000):
        super().__init__(parent)
        self.max_lines = max_lines
        self._show_debug = True  # 默认显示全量调试信息
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 头部操作栏
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("运行实时日志")
        title.setObjectName("CardTitle")
        header.addWidget(title)
        header.addStretch()

        btn_copy = QPushButton("复制日志")
        btn_copy.setObjectName("TagButton")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_all)

        btn_clear = QPushButton("清空")
        btn_clear.setObjectName("TagButton")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self.clear)

        header.addWidget(btn_copy)
        header.addWidget(btn_clear)
        layout.addLayout(header)

        # 日志文本展示框
        self.editor = QPlainTextEdit(self)
        self.editor.setObjectName("LogView")
        self.editor.setReadOnly(True)
        self.editor.setMaximumBlockCount(self.max_lines)
        layout.addWidget(self.editor)

    @pyqtSlot(str, str)
    def append_log(self, message: str, level: str = "INFO"):
        """追加单行格式化日志"""
        now_str = datetime.now().strftime('%H:%M:%S')
        lvl = level.upper()
        color = self.COLOR_MAP.get(lvl, QColor('#86909C'))

        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # 时间戳灰字
        fmt_time = QTextCharFormat()
        fmt_time.setForeground(QColor('#86909C'))
        cursor.insertText(f"[{now_str}] ", fmt_time)

        # 级别徽标着色
        fmt_lvl = QTextCharFormat()
        fmt_lvl.setForeground(color)
        fmt_lvl.setFontWeight(600)
        cursor.insertText(f"[{lvl}] ", fmt_lvl)

        # 消息正文
        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(self.MESSAGE_COLOR)
        cursor.insertText(f"{message}\n", fmt_msg)

        # 滚至末尾
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    def clear(self):
        self.editor.clear()

    def _copy_all(self):
        text = self.editor.toPlainText()
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.append_log("日志已复制到系统剪贴板", "SUCCESS")
