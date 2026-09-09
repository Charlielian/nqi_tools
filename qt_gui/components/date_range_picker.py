# -*- coding: utf-8 -*-
"""
Qt6 现代日期范围选择组件 (Element Plus / Arco Design 风格)
"""

from datetime import date, datetime, timedelta
from typing import Tuple

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QDialog, QCalendarWidget, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate


class DateRangeDialog(QDialog):
    """双日历并排弹出对话框，支持快捷日期选项"""

    range_selected = pyqtSignal(str, str)

    def __init__(self, parent=None, start_date=None, end_date=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._start_date = start_date or (date.today().replace(day=1))
        self._end_date = end_date or (date.today() - timedelta(days=1))
        self._pending_start = None

        self._init_ui()

    def _init_ui(self):
        container = QFrame(self)
        container.setObjectName("CardFrame")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(10)

        # 快捷按钮行
        shortcuts_layout = QHBoxLayout()
        shortcuts_layout.setSpacing(8)
        shortcuts = [
            ("昨天", self._set_yesterday),
            ("近7天", self._set_last_7_days),
            ("近30天", self._set_last_30_days),
            ("本月", self._set_this_month),
            ("上月", self._set_last_month),
        ]
        for text, slot in shortcuts:
            btn = QPushButton(text)
            btn.setObjectName("TagButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            shortcuts_layout.addWidget(btn)
        shortcuts_layout.addStretch()
        container_layout.addLayout(shortcuts_layout)

        # 双日历并排
        cal_layout = QHBoxLayout()
        cal_layout.setSpacing(16)

        # 左日历
        left_box = QVBoxLayout()
        left_lbl = QLabel("开始日期参考")
        left_lbl.setObjectName("SectionLabel")
        left_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cal_left = QCalendarWidget()
        self.cal_left.setGridVisible(True)
        self.cal_left.setSelectedDate(QDate(self._start_date.year, self._start_date.month, self._start_date.day))
        self.cal_left.clicked.connect(self._on_date_clicked)
        left_box.addWidget(left_lbl)
        left_box.addWidget(self.cal_left)
        cal_layout.addLayout(left_box)

        # 右日历
        right_box = QVBoxLayout()
        right_lbl = QLabel("结束日期参考")
        right_lbl.setObjectName("SectionLabel")
        right_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cal_right = QCalendarWidget()
        self.cal_right.setGridVisible(True)
        self.cal_right.setSelectedDate(QDate(self._end_date.year, self._end_date.month, self._end_date.day))
        self.cal_right.clicked.connect(self._on_date_clicked)
        right_box.addWidget(right_lbl)
        right_box.addWidget(self.cal_right)
        cal_layout.addLayout(right_box)

        container_layout.addLayout(cal_layout)

        # 底部信息及确认栏
        bottom_layout = QHBoxLayout()
        self.tip_label = QLabel("提示：点击第1次设为开始日期，点击第2次设为结束日期")
        self.tip_label.setObjectName("HintLabel")
        bottom_layout.addWidget(self.tip_label)
        bottom_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_confirm = QPushButton("确定")
        btn_confirm.setObjectName("PrimaryButton")
        btn_confirm.clicked.connect(self._confirm)

        bottom_layout.addWidget(btn_cancel)
        bottom_layout.addWidget(btn_confirm)
        container_layout.addLayout(bottom_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

    def _on_date_clicked(self, qdate: QDate):
        clicked_d = date(qdate.year(), qdate.month(), qdate.day())
        if self._pending_start is None:
            self._pending_start = clicked_d
            self.tip_label.setText(f"已选开始: {clicked_d.isoformat()}，请点击结束日期...")
        else:
            start_d, end_d = sorted((self._pending_start, clicked_d))
            self._start_date, self._end_date = start_d, end_d
            self._pending_start = None
            self._emit_and_close()

    def _confirm(self):
        if self._pending_start:
            if self._pending_start > self._end_date:
                self._start_date, self._end_date = self._end_date, self._pending_start
            else:
                self._start_date = self._pending_start
            self._pending_start = None
        self._emit_and_close()

    def _emit_and_close(self):
        s_str = self._start_date.strftime("%Y-%m-%d")
        e_str = self._end_date.strftime("%Y-%m-%d")
        self.range_selected.emit(s_str, e_str)
        self.accept()

    def _set_yesterday(self):
        y = date.today() - timedelta(days=1)
        self._start_date, self._end_date = y, y
        self._emit_and_close()

    def _set_last_7_days(self):
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=6)
        self._start_date, self._end_date = start, end
        self._emit_and_close()

    def _set_last_30_days(self):
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=29)
        self._start_date, self._end_date = start, end
        self._emit_and_close()

    def _set_this_month(self):
        today = date.today()
        start = today.replace(day=1)
        end = today
        self._start_date, self._end_date = start, end
        self._emit_and_close()

    def _set_last_month(self):
        today = date.today()
        first_this_month = today.replace(day=1)
        end = first_this_month - timedelta(days=1)
        start = end.replace(day=1)
        self._start_date, self._end_date = start, end
        self._emit_and_close()


class QtDateRangePicker(QWidget):
    """现代日期范围选择组件 (分段式输入展示 + 弹窗双日历)"""

    date_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_date = date.today().replace(day=1)
        self._end_date = date.today() - timedelta(days=1)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 开始日期
        self.start_edit = QLineEdit(self)
        self.start_edit.setReadOnly(True)
        self.start_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_edit.setFixedWidth(110)
        self.start_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_edit.mousePressEvent = lambda e: self._open_picker()
        layout.addWidget(self.start_edit)

        # 分隔符
        sep = QLabel("至", self)
        sep.setObjectName("SectionLabel")
        layout.addWidget(sep)

        # 结束日期
        self.end_edit = QLineEdit(self)
        self.end_edit.setReadOnly(True)
        self.end_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.end_edit.setFixedWidth(110)
        self.end_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.end_edit.mousePressEvent = lambda e: self._open_picker()
        layout.addWidget(self.end_edit)

        # 图标触发按钮
        self.btn_picker = QPushButton("📅", self)
        self.btn_picker.setFixedWidth(36)
        self.btn_picker.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_picker.clicked.connect(self._open_picker)
        layout.addWidget(self.btn_picker)

        self._refresh_display()

    def _open_picker(self):
        dlg = DateRangeDialog(self, self._start_date, self._end_date)
        dlg.range_selected.connect(self.set_range)
        # 定位在输入框下方
        pos = self.mapToGlobal(self.rect().bottomLeft())
        dlg.move(pos.x(), pos.y() + 4)
        dlg.exec()

    def _refresh_display(self):
        self.start_edit.setText(self._start_date.strftime("%Y-%m-%d"))
        self.end_edit.setText(self._end_date.strftime("%Y-%m-%d"))

    def get_range(self) -> Tuple[str, str]:
        return (
            self._start_date.strftime("%Y-%m-%d"),
            self._end_date.strftime("%Y-%m-%d"),
        )

    def set_range(self, start_date_val, end_date_val):
        if isinstance(start_date_val, str):
            self._start_date = datetime.strptime(start_date_val, "%Y-%m-%d").date()
        elif isinstance(start_date_val, datetime):
            self._start_date = start_date_val.date()
        else:
            self._start_date = start_date_val

        if isinstance(end_date_val, str):
            self._end_date = datetime.strptime(end_date_val, "%Y-%m-%d").date()
        elif isinstance(end_date_val, datetime):
            self._end_date = end_date_val.date()
        else:
            self._end_date = end_date_val

        if self._start_date > self._end_date:
            self._start_date, self._end_date = self._end_date, self._start_date

        self._refresh_display()
        self.date_changed.emit(
            self._start_date.strftime("%Y-%m-%d"),
            self._end_date.strftime("%Y-%m-%d"),
        )
