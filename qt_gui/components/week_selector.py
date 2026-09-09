# -*- coding: utf-8 -*-
"""
Qt6 周选择器组件 - 用于合成45G流量表等需要指定周一～周日周期的高级报表
"""

from datetime import date, datetime, timedelta
from typing import Tuple, List

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


class QtWeekSelector(QWidget):
    """现代周选择器 (选择近 12 周，展示周次与日期区间)"""

    week_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.weeks_info = self._generate_weeks()
        self._init_ui()

    def _generate_weeks(self) -> List[Tuple[date, date, str]]:
        """生成最近 12 周的周一开始日期与展示标签"""
        today = date.today()
        # 找到本周一 (weekday: 0=周一, 6=周日)
        current_monday = today - timedelta(days=today.weekday())
        weeks = []
        for i in range(12):
            monday = current_monday - timedelta(weeks=i)
            sunday = monday + timedelta(days=6)
            week_num = monday.isocalendar()[1]
            label = f"{monday.year}年 第{week_num:02d}周 ({monday.strftime('%m.%d')} ~ {sunday.strftime('%m.%d')})"
            weeks.append((monday, sunday, label))
        return weeks

    def _init_ui(self):
        container = QFrame(self)
        container.setObjectName("CardFrame")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        lbl = QLabel("📅 周期选择 (周):")
        lbl.setObjectName("SectionLabel")
        layout.addWidget(lbl)

        self.combo = QComboBox(self)
        for _, _, label in self.weeks_info:
            self.combo.addItem(label)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo, stretch=2)

        self.lbl_detail = QLabel()
        self.lbl_detail.setObjectName("HintLabel")
        layout.addWidget(self.lbl_detail, stretch=3)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        self._on_combo_changed(0)

    def _on_combo_changed(self, idx: int):
        if 0 <= idx < len(self.weeks_info):
            mon, sun, _ = self.weeks_info[idx]
            self.lbl_detail.setText(f"生效区间: {mon.strftime('%Y-%m-%d')} 至 {sun.strftime('%Y-%m-%d')}")
            self.week_changed.emit(mon.strftime('%Y-%m-%d'), sun.strftime('%Y-%m-%d'))

    def get_week_start(self) -> date:
        idx = max(0, self.combo.currentIndex())
        mon, _, _ = self.weeks_info[idx]
        return mon

    def get_date_range(self) -> Tuple[str, str]:
        idx = max(0, self.combo.currentIndex())
        mon, sun, _ = self.weeks_info[idx]
        return mon.strftime('%Y-%m-%d'), sun.strftime('%Y-%m-%d')
