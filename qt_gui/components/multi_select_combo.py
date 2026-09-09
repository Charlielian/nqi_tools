# -*- coding: utf-8 -*-
"""
Qt6 下拉复选多选控件 (支持搜索过滤、全选、取消、确定回填)
"""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QDialog, QCheckBox, QScrollArea, QFrame, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal


class MultiSelectDialog(QDialog):
    """弹出多选复选列表对话框"""

    selection_confirmed = pyqtSignal(list)

    def __init__(self, parent=None, items: Optional[List[str]] = None,
                 selected_items: Optional[List[str]] = None, title: str = "请选择"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._items = items or []
        self._selected_set = set(selected_items or [])
        self._checkbox_map = {}

        self._init_ui(title)

    def _init_ui(self, title: str):
        container = QFrame(self)
        container.setObjectName("CardFrame")
        container.setFixedWidth(260)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(8)

        # 搜索过滤输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索关键词过滤...")
        self.search_input.textChanged.connect(self._filter_items)
        container_layout.addWidget(self.search_input)

        # 滚动多选列表区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(180)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(4, 4, 4, 4)
        self.list_layout.setSpacing(4)

        for item in self._items:
            cb = QCheckBox(item)
            cb.setChecked(item in self._selected_set)
            self.list_layout.addWidget(cb)
            self._checkbox_map[item] = cb

        self.list_layout.addStretch()
        scroll.setWidget(self.list_widget)
        container_layout.addWidget(scroll)

        # 底部快捷按钮与确定取消
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        btn_all = QPushButton("全选")
        btn_all.setObjectName("TagButton")
        btn_all.clicked.connect(self._select_all)

        btn_none = QPushButton("取消")
        btn_none.setObjectName("TagButton")
        btn_none.clicked.connect(self._deselect_all)

        btn_confirm = QPushButton("确定")
        btn_confirm.setObjectName("PrimaryButton")
        btn_confirm.clicked.connect(self._confirm)

        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_confirm)
        container_layout.addLayout(btn_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

    def _filter_items(self, text: str):
        kw = text.strip().lower()
        for item, cb in self._checkbox_map.items():
            cb.setVisible(kw in item.lower())

    def _select_all(self):
        for cb in self._checkbox_map.values():
            if cb.isVisible():
                cb.setChecked(True)

    def _deselect_all(self):
        for cb in self._checkbox_map.values():
            if cb.isVisible():
                cb.setChecked(False)

    def _confirm(self):
        selected = [item for item, cb in self._checkbox_map.items() if cb.isChecked()]
        self.selection_confirmed.emit(selected)
        self.accept()


class QtMultiSelectCombo(QWidget):
    """带复选与搜索的多选组合框"""

    selection_changed = pyqtSignal(list)

    GD_CITIES = [
        '广州', '深圳', '东莞', '佛山', '中山', '珠海', '江门', '肇庆',
        '惠州', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江',
        '云浮', '韶关', '梅州', '河源', '清远'
    ]

    def __init__(self, parent=None, items: Optional[List[str]] = None, placeholder: str = "请选择"):
        super().__init__(parent)
        self._items = items or []
        self._selected = []
        self._placeholder = placeholder

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.display_input = QLineEdit(self)
        self.display_input.setReadOnly(True)
        self.display_input.setPlaceholderText(self._placeholder)
        self.display_input.setCursor(Qt.CursorShape.PointingHandCursor)
        self.display_input.mousePressEvent = lambda e: self._open_popup()
        layout.addWidget(self.display_input)

        self.drop_btn = QPushButton("▼", self)
        self.drop_btn.setFixedWidth(28)
        self.drop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drop_btn.clicked.connect(self._open_popup)
        layout.addWidget(self.drop_btn)

    def _open_popup(self):
        dlg = MultiSelectDialog(self, self._items, self._selected)
        dlg.selection_confirmed.connect(self.set_selected)
        pos = self.mapToGlobal(self.rect().bottomLeft())
        dlg.move(pos.x(), pos.y() + 4)
        dlg.exec()

    def set_items(self, items: List[str]):
        self._items = items
        # 过滤掉不存在的项
        self._selected = [x for x in self._selected if x in items]
        self._refresh_display()

    def set_selected(self, selected: List[str]):
        self._selected = [x for x in selected if x in self._items]
        self._refresh_display()
        self.selection_changed.emit(self._selected)

    def get_selected(self) -> List[str]:
        return list(self._selected)

    def _refresh_display(self):
        if not self._selected:
            self.display_input.setText("")
        elif len(self._selected) <= 3:
            self.display_input.setText(", ".join(self._selected))
        else:
            self.display_input.setText(f"已选择 {len(self._selected)} 项")
