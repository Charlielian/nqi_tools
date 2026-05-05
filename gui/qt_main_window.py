# -*- coding: utf-8 -*-
"""
PyQt6 主窗口模块
提供应用程序的主界面 - 现代化设计
"""

import sys
import pandas as pd
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QDateEdit, QProgressBar, QFrame, QScrollArea, QSizePolicy,
    QGraphicsDropShadowEffect, QCompleter, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QApplication, QDialog, QMessageBox, QStyle,
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import (
    Qt, QTimer, QDate, pyqtSignal, QSize, QThread, QObject, QRect,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QAction, QPainter, QBrush, QPen,
    QLinearGradient
)

import threading
import logging
import os
from datetime import datetime, timedelta
import queue

from core.auth import LoginManager
from core.query import JXCXQuery
from core.export import export_with_format
from core.license import TimeMonitor, verify_serial_number, write_license_from_serial, generate_machine_code, get_hw_info
from utils.logger import set_log_file, ensure_dirs
from utils.config import LOG_DIR, EXPIRY_DATE, DEFAULT_USERNAME, DEFAULT_PASSWORD
from gui.widgets import TableConfig


class NavButton(QPushButton):
    """导航按钮类"""
    clicked_nav = pyqtSignal(str)

    def __init__(self, icon, tooltip, nav_id, selected=False, parent=None):
        super().__init__(parent)
        self.nav_id = nav_id
        self.tooltip_text = tooltip
        self.is_selected = selected

        self.setFixedSize(54, 54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(icon)
        self.setToolTip(tooltip)

        # 设置字体 - 使用 Apple Color Emoji 支持 emoji
        font = QFont("Apple Color Emoji")
        font.setPointSize(14)
        self.setFont(font)

        self._update_style()

    def _update_style(self):
        """更新样式"""
        if self.is_selected:
            bg_color = "#252538"
        else:
            bg_color = "#1a1a2e"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 5px;
            }}
            QPushButton:hover {{
                background-color: #303050;
            }}
        """)

    def set_selected(self, selected):
        """设置选中状态"""
        self.is_selected = selected
        self._update_style()


class NoFocusRectDelegate(QStyledItemDelegate):
    """移除item焦点矩形的委托"""

    def paint(self, painter, option, index):
        option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, option, index)


class DateEdit(QDateEdit):
    """自定义日期输入框 - 点击任意位置弹出日历"""

    def mousePressEvent(self, event):
        """鼠标点击时弹出日历"""
        QTimer.singleShot(0, self._show_calendar)
        super().mousePressEvent(event)

    def _show_calendar(self):
        """显示日历"""
        self.setCalendarPopup(True)
        self.calendarWidget().setVisible(True)


class MultiSelectCombo(QWidget):
    """带复选框的多选下拉组件"""

    items_changed = pyqtSignal(list)

    CITIES = ['广州', '深圳', '东莞', '佛山', '中山', '珠海', '江门', '肇庆',
              '惠州', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江',
              '云浮', '韶关', '梅州', '河源', '清远']

    def __init__(self, items=None, parent=None, categories_map=None):
        super().__init__(parent)
        self.all_items = list(items) if items else []
        self.selected_items = []
        self._categories_map = categories_map or {}

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 主容器
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
            }
        """)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 输入框和按钮行
        input_layout = QHBoxLayout()
        input_layout.setSpacing(4)

        # 显示框
        self.display_label = QLabel("请选择...")
        self.display_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: none;
                padding: 6px 8px;
                border-radius: 4px;
                color: #6c757d;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 9pt;
            }
        """)
        self.display_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        input_layout.addWidget(self.display_label)

        # 下拉按钮
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedWidth(32)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #dee2e6;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle_popup)
        input_layout.addWidget(self.toggle_btn)

        main_layout.addLayout(input_layout)

        # 弹出面板
        self.popup = QFrame()
        self.popup.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.popup.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
            }
            QLineEdit {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #165DFF;
            }
            QPushButton {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 11px;
            }
        """)

        popup_layout = QVBoxLayout(self.popup)
        popup_layout.setContentsMargins(4, 4, 4, 4)
        popup_layout.setSpacing(4)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.textChanged.connect(self._filter_items)
        self.search_input.setMinimumHeight(36)
        popup_layout.addWidget(self.search_input)

        # 全选/取消按钮
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.setFixedHeight(32)
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                border: none;
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        select_all_btn.clicked.connect(self._select_all)

        clear_btn = QPushButton("清空")
        clear_btn.setFixedHeight(32)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                border: none;
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        clear_btn.clicked.connect(self._clear_all)

        confirm_btn = QPushButton("确定")
        confirm_btn.setFixedHeight(32)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #165DFF;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #3a7afe; }
        """)
        confirm_btn.clicked.connect(self._confirm)

        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(confirm_btn)
        popup_layout.addLayout(btn_row)

        # 复选框列表
        self.check_list = QListWidget()
        self.check_list.setSpacing(4)
        self.check_list.setItemDelegate(NoFocusRectDelegate())
        self.check_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: white;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
                min-height: 32px;
            }
            QListWidget::item:hover {
                background-color: #f0f4ff;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        popup_layout.addWidget(self.check_list)

        # 创建复选框项
        self.checkboxes = {}
        self._create_items()

        layout.addWidget(container)

    def _create_items(self):
        """创建复选框项"""
        self.check_list.clear()
        self.checkboxes.clear()

        for item in self.all_items:
            list_item = QListWidgetItem()
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

            checkbox = QCheckBox(item)
            checkbox.setStyleSheet("""
                QCheckBox {
                    spacing: 8px;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
                    font-size: 11px;
                    color: #495057;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 3px;
                    border: 1px solid #ced4da;
                    background-color: white;
                }
                QCheckBox::indicator:checked {
                    border: 1px solid #165DFF;
                    background-color: #165DFF;
                    image: none;
                }
                QCheckBox::indicator:checked::after {
                    content: "✓";
                    color: white;
                }
            """)
            checkbox.setChecked(item in self.selected_items)
            checkbox.stateChanged.connect(lambda s, cb=checkbox, it=item: self._on_check_changed(s, cb, it))

            self.check_list.addItem(list_item)
            self.check_list.setItemWidget(list_item, checkbox)
            self.checkboxes[item] = checkbox

    def _on_check_changed(self, state, checkbox, item):
        """复选框状态改变"""
        if state:
            if item not in self.selected_items:
                self.selected_items.append(item)
        else:
            if item in self.selected_items:
                self.selected_items.remove(item)

    def _filter_items(self, text):
        """过滤项目"""
        text = text.lower()
        for i in range(self.check_list.count()):
            item = self.check_list.item(i)
            widget = self.check_list.itemWidget(item)
            if widget:
                visible = text in widget.text().lower()
                item.setHidden(not visible)

    def _select_all(self):
        """全选"""
        for i in range(self.check_list.count()):
            item = self.check_list.item(i)
            widget = self.check_list.itemWidget(item)
            if widget:
                widget.setChecked(True)

    def _clear_all(self):
        """清空"""
        for i in range(self.check_list.count()):
            item = self.check_list.item(i)
            widget = self.check_list.itemWidget(item)
            if widget:
                widget.setChecked(False)

    def _confirm(self):
        """确认选择"""
        self.popup.hide()
        self._update_display()

    def _update_display(self):
        """更新显示"""
        if not self.selected_items:
            self.display_label.setText("请选择...")
            self.display_label.setStyleSheet("""
                QLabel {
                    background-color: #f8f9fa;
                    border: none;
                    padding: 6px 8px;
                    border-radius: 4px;
                    color: #6c757d;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                    font-size: 9pt;
                }
            """)
        else:
            count = len(self.selected_items)
            # 获取选中项目所属的分类
            selected_cats = []
            for cat, tables in self._categories_map.items():
                if any(t in self.selected_items for t in tables):
                    selected_cats.append(cat)

            if count <= 2:
                # 选中项少时显示具体名称
                text = ",".join(self.selected_items[:2])
                if count > 2:
                    text += f" +{count - 2}项"
            else:
                # 选中项多时显示数量和类别
                if selected_cats:
                    cat_text = ", ".join(selected_cats[:3])
                    if len(selected_cats) > 3:
                        cat_text += f" +{len(selected_cats) - 3}类"
                    text = f"已选 {count} 项 ({cat_text})"
                else:
                    text = f"已选 {count} 项"

            self.display_label.setText(text)
            self.display_label.setStyleSheet("""
                QLabel {
                    background-color: #f8f9fa;
                    border: none;
                    padding: 6px 8px;
                    border-radius: 4px;
                    color: #495057;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                    font-size: 9pt;
                }
            """)

    def _toggle_popup(self):
        """切换弹出窗口"""
        if self.popup.isVisible():
            self.popup.hide()
        else:
            self._show_popup()

    def _show_popup(self):
        """显示弹出窗口"""
        input_rect = self.display_label.rect()
        global_pos = self.display_label.mapToGlobal(input_rect.bottomLeft())
        self.popup.move(global_pos)
        self.popup.resize(max(280, self.width()), 400)
        self.popup.show()
        self.search_input.setFocus()

    def get_selected(self):
        """获取选中的项目"""
        return list(self.selected_items)

    def set_selected(self, items, trigger_callback=True):
        """设置选中的项目"""
        self.selected_items = list(items)
        for item, checkbox in self.checkboxes.items():
            checkbox.setChecked(item in items)
        self._update_display()

        if trigger_callback:
            self.items_changed.emit(self.selected_items)


class LogViewer(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                font-family: 'Consolas', 'Menlo', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)


class CardWidget(QFrame):
    """带阴影效果的卡片组件"""

    def __init__(self, title=None, icon=None, parent=None):
        super().__init__(parent)
        self.title = title
        self.icon = icon

        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e9ecef;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 标题栏
        if title:
            header = QFrame()
            header.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border-bottom: 1px solid #f1f3f5;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                }
            """)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(16, 12, 16, 8)

            if icon:
                icon_label = QLabel(icon)
                icon_label.setFont(QFont("Apple Color Emoji", 11))
                header_layout.addWidget(icon_label)

            title_label = QLabel(title)
            title_label.setStyleSheet("color: #1a1a2e; font-weight: bold; font-size: 10pt;")
            header_layout.addWidget(title_label)
            header_layout.addStretch()

            main_layout.addWidget(header)

        # 内容区域
        self.content_widget = QFrame()
        self.content_widget.setStyleSheet("background-color: white;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 8, 16, 16)
        self.content_layout.setSpacing(8)
        main_layout.addWidget(self.content_widget)

    def get_content_layout(self):
        """获取内容布局"""
        return self.content_layout


class NqiToolMainWindow(QMainWindow):
    """NQI工具主窗口 - PyQt6 现代化设计"""

    TABLE_CATEGORIES = {
        '干扰': ['5G干扰小区', '4G干扰小区'],
        '容量': ['5G小区容量报表', '重要场景-天'],
        '工参': ['5G小区工参报表', '4G小区工参报表'],
        'MR覆盖': ['5GMR覆盖-小区天', '4GMR覆盖-小区天'],
        '语音报表': ['VoLTE小区监控预警', 'VONR小区监控预警', 'EPSFB小区监控预警'],
        '小区性能': ['5G小区性能KPI报表', '4G小区性能KPI报表'],
        '全程完好率': ['4G全程完好率报表', '5G全程完好率报表'],
        '语音小区': ['4G语音小区', '5G语音小区'],
    }

    def __init__(self):
        super().__init__()

        # 初始化变量
        self.expiry_time = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d") if EXPIRY_DATE else None
        self.session = None
        self.jxcx = None
        self.is_querying = False
        self._stop_requested = False
        self.log_queue = queue.Queue()
        self.current_view = "home"

        # 日志系统
        self._setup_logging()

        # 设置UI
        self._setup_ui()

        # 启动时间监控
        self._time_monitor = TimeMonitor(interval=30, callback=self._on_time_rollback)
        self._time_monitor.start()

        self.logger.info("=" * 50)
        self.logger.info("NQI工具 GUI 启动 (PyQt6)")
        self.logger.info(f"日志文件: {self.log_file_path}")
        self.logger.info("=" * 50)

        # 加载配置
        self.load_config()

    def _setup_logging(self):
        """设置日志系统"""
        try:
            ensure_dirs()
            log_filename = f"NqiTool_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            self.log_file_path = os.path.join(LOG_DIR, log_filename)
            set_log_file(self.log_file_path)

            self.logger = logging.getLogger()
            self.logger.setLevel(logging.DEBUG)

            file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                        datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

            # 添加界面日志处理器
            log_handler = LogHandler(self)
            log_handler.setLevel(logging.INFO)
            log_handler.setFormatter(formatter)
            self.logger.addHandler(log_handler)
        except Exception as e:
            self.logger = logging.getLogger()
            self.logger.setLevel(logging.DEBUG)
            self.logger.warning(f"初始化日志文件失败: {e}")

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("NQI工具")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航栏
        self._create_sidebar(main_layout)

        # 右侧内容区
        content_area = QFrame()
        content_area.setStyleSheet("background-color: #e9ecef;")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(20, 10, 20, 10)
        content_layout.setSpacing(12)

        self.content_container = QFrame()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.content_container)

        main_layout.addWidget(content_area, 1)

        # 显示首页
        self._show_home_view()

    def _create_sidebar(self, parent_layout):
        """创建左侧导航栏"""
        sidebar = QFrame()
        sidebar.setFixedWidth(70)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo 区域
        logo_frame = QFrame()
        logo_frame.setFixedHeight(80)
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(0, 15, 0, 15)

        logo_label = QLabel("N")
        logo_label.setFixedSize(36, 36)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("""
            QLabel {
                background-color: #165DFF;
                color: white;
                font-family: Arial;
                font-size: 20px;
                font-weight: bold;
                border-radius: 6px;
            }
        """)
        logo_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo_frame)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2d2d44;")
        sidebar_layout.addWidget(sep)

        # 导航按钮区域
        nav_frame = QFrame()
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(8, 10, 8, 10)
        nav_layout.setSpacing(6)

        self.nav_buttons = {}
        nav_items = [
            {'icon': '🏠', 'id': 'home', 'tip': '首页'},
            {'icon': '📊', 'id': 'query', 'tip': '数据查询'},
            {'icon': '📁', 'id': 'export', 'tip': '导出管理'},
            {'icon': '⚙', 'id': 'settings', 'tip': '设置'},
            {'icon': 'ℹ', 'id': 'about', 'tip': '关于'},
        ]

        for i, item in enumerate(nav_items):
            btn = NavButton(item['icon'], item['tip'], item['id'], selected=(i == 0))
            btn.clicked_nav.connect(self._on_nav_click)
            nav_layout.addWidget(btn)
            self.nav_buttons[item['id']] = btn

        nav_layout.addStretch()
        sidebar_layout.addWidget(nav_frame, 1)

        # 底部状态
        bottom_frame = QFrame()
        bottom_frame.setFixedHeight(60)
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(0, 5, 0, 5)

        self.status_label = QLabel("●")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #22c55e; font-size: 10px;")
        bottom_layout.addWidget(self.status_label)

        activate_btn = QPushButton("激活")
        activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #165DFF;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 8pt;
            }
            QPushButton:hover { background-color: #3a7afe; }
        """)
        activate_btn.clicked.connect(self._show_activate_window)
        bottom_layout.addWidget(activate_btn, 0, Qt.AlignmentFlag.AlignCenter)

        sidebar_layout.addWidget(bottom_frame)
        parent_layout.addWidget(sidebar)

    def _on_nav_click(self, nav_id):
        for bid, btn in self.nav_buttons.items():
            btn.set_selected(bid == nav_id)
        self.current_view = nav_id
        if nav_id == 'home':
            self._show_home_view()
        elif nav_id == 'query':
            self._show_home_view()
        elif nav_id == 'export':
            self._show_export_view()
        elif nav_id == 'settings':
            self._show_settings_view()
        elif nav_id == 'about':
            self._show_about_view()

    def _show_home_view(self):
        """显示首页视图"""
        # 清空内容区
        while self.content_layout.count():
            widget = self.content_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()

        # 登录配置栏
        self._build_login_bar(self.content_layout)

        # 主体区域
        body_layout = QHBoxLayout()
        body_layout.setSpacing(16)

        # 左侧：查询参数 + 提取参数
        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: transparent;")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setSpacing(16)

        self._build_query_card(left_layout)
        self._build_params_card(left_layout)

        left_layout.addStretch()
        body_layout.addWidget(left_frame, 3)

        # 右侧：数据预览 + 日志
        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: transparent;")
        right_layout = QVBoxLayout(right_frame)
        right_layout.setSpacing(16)

        self._build_preview_card(right_layout)
        self._build_log_card(right_layout)

        body_layout.addWidget(right_frame, 7)
        self.content_layout.addLayout(body_layout, 1)

        self._build_progress_section(self.content_layout)

    def _show_export_view(self):
        while self.content_layout.count():
            widget = self.content_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        card = CardWidget("📁 导出管理")
        layout = card.get_content_layout()
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef; border: none; border-radius: 4px;
                padding: 6px 16px; font-size: 9pt;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        refresh_btn.clicked.connect(self._refresh_export_list)
        toolbar.addWidget(refresh_btn)
        open_btn = QPushButton("📂 打开目录")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef; border: none; border-radius: 4px;
                padding: 6px 16px; font-size: 9pt;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        open_btn.clicked.connect(self.open_output_dir)
        toolbar.addWidget(open_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.export_table = QTableWidget()
        self.export_table.setStyleSheet("""
            QTableWidget {
                border: none; font-size: 9pt; gridline-color: #e9ecef; background-color: white;
            }
            QTableWidget::item { padding: 4px 8px; }
            QHeaderView::section {
                background-color: #f8f9fa; padding: 6px 8px; border: none;
                border-bottom: 1px solid #dee2e6; font-weight: bold; font-size: 8pt;
            }
        """)
        self.export_table.setAlternatingRowColors(True)
        self.export_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.export_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.export_table.horizontalHeader().setStretchLastSection(True)
        self.export_table.verticalHeader().setVisible(False)
        layout.addWidget(self.export_table, 1)
        self.content_layout.addWidget(card, 1)
        self._refresh_export_list()

    def _refresh_export_list(self):
        if not hasattr(self, 'export_table'):
            return
        output_dir = os.path.join(os.getcwd(), 'data_output')
        files = []
        if os.path.exists(output_dir):
            for f in sorted(os.listdir(output_dir), reverse=True):
                filepath = os.path.join(output_dir, f)
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    if size > 1024 * 1024:
                        size_str = f"{size / 1024 / 1024:.1f} MB"
                    else:
                        size_str = f"{size / 1024:.1f} KB"
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S')
                    files.append((f, size_str, mtime))
        self.export_table.setRowCount(len(files))
        self.export_table.setColumnCount(3)
        self.export_table.setHorizontalHeaderLabels(['文件名', '大小', '修改时间'])
        for i, (name, size, mtime) in enumerate(files):
            self.export_table.setItem(i, 0, QTableWidgetItem(name))
            self.export_table.setItem(i, 1, QTableWidgetItem(size))
            self.export_table.setItem(i, 2, QTableWidgetItem(mtime))

    def open_output_dir(self):
        import webbrowser
        output_dir = os.path.join(os.getcwd(), 'data_output')
        os.makedirs(output_dir, exist_ok=True)
        webbrowser.open(output_dir)

    def _show_settings_view(self):
        while self.content_layout.count():
            widget = self.content_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        card = CardWidget("⚙ 设置")
        layout = card.get_content_layout()
        dir_label = QLabel("输出目录")
        dir_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        layout.addWidget(dir_label)
        dir_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(os.path.join(os.getcwd(), 'data_output'))
        self.output_dir_input.setStyleSheet("""
            QLineEdit {
                background-color: #f8f9fa; border: 1px solid #dee2e6;
                border-radius: 4px; padding: 6px 8px;
            }
        """)
        dir_row.addWidget(self.output_dir_input, 1)
        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef; border: none; border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        browse_btn.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)
        layout.addSpacing(20)
        save_btn = QPushButton("保存设置")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #165DFF; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3a7afe; }
        """)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()
        self.content_layout.addWidget(card, 1)

    def _browse_output_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.output_dir_input.setText(directory)

    def _save_settings(self):
        self.logger.info("设置已保存")

    def _show_about_view(self):
        while self.content_layout.count():
            widget = self.content_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        card = CardWidget("ℹ 关于")
        layout = card.get_content_layout()
        layout.addStretch()
        logo = QLabel("N")
        logo.setFixedSize(60, 60)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("""
            QLabel {
                background-color: #165DFF; color: white;
                font-family: Arial; font-size: 28px; font-weight: bold; border-radius: 10px;
            }
        """)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignCenter)
        title = QLabel("NQI数据提取工具")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #1a1a2e;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        version = QLabel("版本 2.0.0")
        version.setStyleSheet("font-size: 10pt; color: #6c757d;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        desc = QLabel("NQI平台数据提取与导出工具")
        desc.setStyleSheet("font-size: 9pt; color: #adb5bd;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        if self.expiry_time:
            expiry_label = QLabel(f"授权到期: {self.expiry_time.strftime('%Y-%m-%d')}")
            expiry_label.setStyleSheet("font-size: 9pt; color: #6c757d;")
            expiry_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(expiry_label)
        layout.addStretch()
        self.content_layout.addWidget(card, 1)

    def _build_login_bar(self, parent):
        """构建登录栏"""
        bar = QFrame()
        bar.setFixedHeight(70)
        bar.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e9ecef;
            }
        """)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(20, 12, 20, 12)
        bar_layout.setSpacing(20)

        # 用户名
        user_layout = QVBoxLayout()
        user_layout.setSpacing(2)
        user_label = QLabel("用户名")
        user_label.setStyleSheet("font-size: 8pt; color: #6c757d;")
        self.username_input = QLineEdit()
        self.username_input.setText(DEFAULT_USERNAME)
        self.username_input.setStyleSheet("""
            QLineEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #165DFF;
            }
        """)
        self.username_input.setFixedWidth(130)
        self.username_input.setFixedHeight(32)
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.username_input)
        bar_layout.addLayout(user_layout)

        # 密码
        pass_layout = QVBoxLayout()
        pass_layout.setSpacing(2)
        pass_label = QLabel("密码")
        pass_label.setStyleSheet("font-size: 8pt; color: #6c757d;")
        pass_input_row = QHBoxLayout()
        pass_input_row.setSpacing(4)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #165DFF;
            }
        """)
        self.password_input.setFixedWidth(110)
        self.password_input.setFixedHeight(32)
        pass_input_row.addWidget(self.password_input)

        self.toggle_pwd_btn = QPushButton("👁")
        self.toggle_pwd_btn.setFixedSize(32, 32)
        self.toggle_pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        self.toggle_pwd_btn.setCheckable(True)
        self.toggle_pwd_btn.toggled.connect(self._toggle_password_visibility)
        pass_input_row.addWidget(self.toggle_pwd_btn)

        pass_layout.addWidget(pass_label)
        pass_layout.addLayout(pass_input_row)
        bar_layout.addLayout(pass_layout)

        # 登录按钮
        self.login_btn = QPushButton("登录")
        self.login_btn.setFixedSize(80, 50)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #165DFF;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover { background-color: #3a7afe; }
        """)
        self.login_btn.clicked.connect(self._on_login)
        bar_layout.addWidget(self.login_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # 分隔线
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #dee2e6;")
        bar_layout.addWidget(sep)

        # 登录状态
        status_layout = QVBoxLayout()
        status_layout.setSpacing(4)
        status_title = QLabel("登录状态")
        status_title.setStyleSheet("font-size: 8pt; color: #6c757d;")
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.login_status_dot = QLabel("○")
        self.login_status_dot.setStyleSheet("font-size: 16px;")
        self.login_status_label = QLabel("未登录")
        self.login_status_label.setStyleSheet("font-size: 9pt; color: #fd7e14;")
        status_row.addWidget(self.login_status_dot)
        status_row.addWidget(self.login_status_label)
        status_row.addStretch()
        status_layout.addWidget(status_title)
        status_layout.addLayout(status_row)
        bar_layout.addLayout(status_layout)

        # 分隔线
        sep2 = QFrame()
        sep2.setFixedWidth(1)
        sep2.setStyleSheet("background-color: #dee2e6;")
        bar_layout.addWidget(sep2)

        # 授权状态
        license_layout = QVBoxLayout()
        license_layout.setSpacing(4)
        license_title = QLabel("授权状态")
        license_title.setStyleSheet("font-size: 8pt; color: #6c757d;")
        self.license_status_label = QLabel()
        self.license_status_label.setStyleSheet("font-size: 9pt; font-weight: 500;")
        self._update_license_display()
        license_layout.addWidget(license_title)
        license_layout.addWidget(self.license_status_label)
        bar_layout.addLayout(license_layout)

        bar_layout.addStretch()
        parent.addWidget(bar)

    def _build_query_card(self, parent):
        """构建查询参数卡片"""
        card = CardWidget("🔍 查询参数")
        layout = card.get_content_layout()

        # 数据表分类
        cat_layout = QHBoxLayout()
        cat_label = QLabel("数据表分类")
        cat_label.setStyleSheet("font-weight: bold; font-size: 8pt;")
        cat_layout.addWidget(cat_label)
        layout.addLayout(cat_layout)

        # 分类按钮网格
        self.category_btns = {}
        self.category_vars = {}

        grid_layout = QGridLayout()
        grid_layout.setSpacing(4)
        categories = list(self.TABLE_CATEGORIES.keys())

        for i, cat in enumerate(categories):
            row = i // 3
            col = i % 3
            var = QCheckBox(cat)
            var.setStyleSheet("""
                QCheckBox {
                    spacing: 4px;
                    font-size: 8pt;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    border-radius: 3px;
                }
                QCheckBox::indicator:unchecked {
                    border: 1px solid #dee2e6;
                    background-color: #f8f9fa;
                }
                QCheckBox::indicator:checked {
                    border: 1px solid #165DFF;
                    background-color: #165DFF;
                }
            """)
            var.toggled.connect(lambda s, c=cat: self._on_category_toggled(c, s))
            grid_layout.addWidget(var, row, col)
            self.category_btns[cat] = var
            self.category_vars[cat] = var

        layout.addLayout(grid_layout)

        # 数据表选择
        table_label = QLabel("数据表选择")
        table_label.setStyleSheet("font-weight: bold; font-size: 8pt;")
        layout.addWidget(table_label)

        all_tables = []
        for tables in self.TABLE_CATEGORIES.values():
            all_tables.extend(tables)
        self.table_dropdown = MultiSelectCombo(all_tables, categories_map=self.TABLE_CATEGORIES)
        self.table_dropdown.items_changed.connect(self._on_tables_changed)
        layout.addWidget(self.table_dropdown)

        parent.addWidget(card)

    def _build_params_card(self, parent):
        """构建提取参数卡片"""
        card = CardWidget("⚙ 提取参数")
        layout = card.get_content_layout()

        # 地市选择
        city_layout = QHBoxLayout()
        city_label = QLabel("地市")
        city_label.setStyleSheet("font-weight: bold; font-size: 8pt;")
        city_layout.addWidget(city_label)
        city_layout.addSpacing(8)
        self.city_dropdown = MultiSelectCombo(MultiSelectCombo.CITIES)
        self.city_dropdown.set_selected(['阳江'])
        city_layout.addWidget(self.city_dropdown, 1)
        city_layout.addStretch()
        layout.addLayout(city_layout)

        quick_layout = QHBoxLayout()
        quick_label = QLabel("快捷")
        quick_label.setStyleSheet("font-size: 8pt; color: #6c757d;")
        quick_layout.addWidget(quick_label)
        for text, days in [("昨天", 1), ("7天", 7), ("30天", 30)]:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e9ecef; border: none; border-radius: 4px;
                    padding: 2px 6px; font-size: 7pt;
                }
                QPushButton:hover { background-color: #dee2e6; }
            """)
            btn.clicked.connect(lambda s, d=days: self.set_quick_date(d))
            quick_layout.addWidget(btn)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        # 日期范围
        date_layout = QHBoxLayout()
        date_label = QLabel("日期范围")
        date_label.setStyleSheet("font-weight: bold; font-size: 8pt;")
        date_layout.addWidget(date_label)
        date_layout.addSpacing(8)

        yesterday = QDate.currentDate().addDays(-1)
        start_date = QDate.currentDate().addDays(-7)

        self.start_date = DateEdit()
        self.start_date.setDate(start_date)
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setFixedWidth(120)
        self.start_date.setStyleSheet("""
            QDateEdit {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: white;
            }
        """)
        date_layout.addWidget(self.start_date)

        date_layout.addWidget(QLabel("至"))

        self.end_date = DateEdit()
        self.end_date.setDate(yesterday)
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setFixedWidth(120)
        self.end_date.setStyleSheet("""
            QDateEdit {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: white;
            }
        """)
        date_layout.addWidget(self.end_date)
        date_layout.addStretch()

        layout.addLayout(date_layout)

        # 多日模式选项
        mode_layout = QHBoxLayout()
        self.multi_day_cb = QCheckBox("多日模式")
        self.multi_day_cb.setStyleSheet("""
            QCheckBox {
                spacing: 6px;
                font-size: 8pt;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #dee2e6;
                background-color: #f8f9fa;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #165DFF;
                background-color: #165DFF;
            }
        """)
        self.multi_day_cb.toggled.connect(self._on_multi_day_toggled)
        mode_layout.addWidget(self.multi_day_cb)

        self.per_sheet_cb = QCheckBox("按日分Sheet")
        self.per_sheet_cb.setEnabled(False)
        self.per_sheet_cb.setStyleSheet("""
            QCheckBox {
                spacing: 6px;
                font-size: 8pt;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #dee2e6;
                background-color: #f8f9fa;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #165DFF;
                background-color: #165DFF;
            }
        """)
        self.per_sheet_cb.toggled.connect(self._on_per_sheet_toggled)
        mode_layout.addWidget(self.per_sheet_cb)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        parent.addWidget(card)

    def _on_multi_day_toggled(self, checked):
        """多日模式切换"""
        self.per_sheet_cb.setEnabled(checked)
        if not checked:
            self.per_sheet_cb.setChecked(False)

    def _on_per_sheet_toggled(self, checked):
        """按日分Sheet切换"""
        pass

    def _build_preview_card(self, parent):
        card = CardWidget("📊 数据预览")
        layout = card.get_content_layout()

        self.preview_stats_label = QLabel("请先登录并执行查询")
        self.preview_stats_label.setStyleSheet("font-size: 9pt; color: #adb5bd; padding: 10px;")
        layout.addWidget(self.preview_stats_label)

        self.preview_table = QTableWidget()
        self.preview_table.setStyleSheet("""
            QTableWidget {
                border: none;
                font-family: 'Menlo', 'Consolas', monospace;
                font-size: 9pt;
                gridline-color: #e9ecef;
                background-color: white;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid #dee2e6;
                font-weight: bold;
                font-size: 8pt;
            }
        """)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_table, 1)

        parent.addWidget(card, 1)

    def update_preview(self, df, table_name=""):
        """更新数据预览 - 显示前20行"""
        if df is None or df.empty:
            self.preview_table.setRowCount(0)
            return

        # 显示前20行数据
        preview_df = df.head(20)
        rows = len(preview_df)
        cols = len(preview_df.columns)

        self.preview_table.setRowCount(rows)
        self.preview_table.setColumnCount(cols)
        self.preview_table.setHorizontalHeaderLabels(list(preview_df.columns))

        for i, (_, row) in enumerate(preview_df.iterrows()):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value) if pd.notna(value) else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.preview_table.setItem(i, j, item)

        # 调整列宽
        self.preview_table.resizeColumnsToContents()
        # 限制最大列宽，防止过宽
        for col in range(min(cols, 10)):
            if self.preview_table.columnWidth(col) > 150:
                self.preview_table.setColumnWidth(col, 150)

    def _build_log_card(self, parent):
        card = CardWidget("📋 运行日志")

        toolbar = QHBoxLayout()
        self.log_search_input = QLineEdit()
        self.log_search_input.setPlaceholderText("搜索日志...")
        self.log_search_input.setFixedHeight(28)
        self.log_search_input.setStyleSheet("""
            QLineEdit {
                background-color: #f8f9fa; border: 1px solid #dee2e6;
                border-radius: 4px; padding: 4px 8px; font-size: 9pt;
            }
            QLineEdit:focus { border: 1px solid #165DFF; }
        """)
        self.log_search_input.textChanged.connect(self._on_log_search)
        toolbar.addWidget(self.log_search_input, 1)

        clear_btn = QPushButton("清空")
        clear_btn.setFixedHeight(28)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef; border: none; border-radius: 4px;
                padding: 6px 16px; font-size: 8pt;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        clear_btn.clicked.connect(self._clear_log)
        toolbar.addWidget(clear_btn)

        self._log_auto_scroll = True
        self.auto_scroll_label = QLabel("")
        self.auto_scroll_label.setStyleSheet("color: #fd7e14; font-size: 8pt;")
        toolbar.addWidget(self.auto_scroll_label)

        card.get_content_layout().addLayout(toolbar)

        self.log_viewer = LogViewer()
        self.log_viewer.verticalScrollBar().valueChanged.connect(self._on_log_scroll_changed)
        card.get_content_layout().addWidget(self.log_viewer, 1)

        parent.addWidget(card, 1)

    def _build_progress_section(self, parent):
        """构建进度条区域"""
        progress_frame = QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e9ecef;
            }
        """)
        progress_layout = QHBoxLayout(progress_frame)
        progress_layout.setContentsMargins(16, 8, 16, 8)
        progress_layout.setSpacing(12)

        self.query_btn = QPushButton("🔍 查询")
        self.query_btn.setStyleSheet("""
            QPushButton {
                background-color: #165DFF;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3a7afe; }
        """)
        self.query_btn.clicked.connect(self._on_query)
        progress_layout.addWidget(self.query_btn)

        self.export_btn = QPushButton("📥 导出")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                color: #6c757d;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
        """)
        self.export_btn.clicked.connect(self._on_export)
        progress_layout.addWidget(self.export_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #e9ecef;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #165DFF;
            }
        """)
        progress_layout.addWidget(self.progress_bar, 1)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("font-size: 8pt; color: #6c757d;")
        progress_layout.addWidget(self.progress_label)

        parent.addWidget(progress_frame)

    # ==================== 事件处理 ====================

    def _on_category_toggled(self, category, checked):
        """分类按钮切换"""
        if checked:
            tables = self.TABLE_CATEGORIES.get(category, [])
            current = self.table_dropdown.get_selected()
            new_selection = list(set(current + tables))
            self.table_dropdown.set_selected(new_selection)
        else:
            tables = self.TABLE_CATEGORIES.get(category, [])
            current = self.table_dropdown.get_selected()
            new_selection = [t for t in current if t not in tables]
            self.table_dropdown.set_selected(new_selection)

    def _on_tables_changed(self, selected):
        """数据表选择变化"""
        pass  # 可扩展

    def _on_login(self):
        """登录处理"""
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        # 更新为登录中状态（橙色闪烁）
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        self.login_status_dot.setText("◐")
        self.login_status_dot.setStyleSheet("color: #fd7e14; font-size: 14px; font-weight: bold;")
        self.login_status_label.setText("登录中...")
        self.login_status_label.setStyleSheet("color: #fd7e14; font-size: 9pt;")

        def do_login():
            try:
                login_mgr = LoginManager()
                session = login_mgr.login(username, password)

                def on_success():
                    self.session = session
                    self.jxcx = JXCXQuery(session)
                    self.login_btn.setText("已登录")
                    self.login_btn.setStyleSheet("""
                        QPushButton {
                            background-color: #22c55e;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 6px 16px;
                        }
                    """)
                    self.login_btn.setEnabled(False)
                    # 更新状态为已登录（绿色）
                    self.login_status_dot.setText("●")
                    self.login_status_dot.setStyleSheet("color: #22c55e; font-size: 14px; font-weight: bold;")
                    self.login_status_label.setText("已登录")
                    self.login_status_label.setStyleSheet("color: #22c55e; font-size: 9pt;")
                    self.status_label.setStyleSheet("color: #22c55e; font-size: 10px;")
                    self.logger.info(f"用户 {username} 登录成功")

                def on_error(msg):
                    self.login_btn.setEnabled(True)
                    self.login_btn.setText("登录")
                    # 更新状态为失败（红色）
                    self.login_status_dot.setText("○")
                    self.login_status_dot.setStyleSheet("color: #dc3545; font-size: 14px; font-weight: bold;")
                    self.login_status_label.setText("登录失败")
                    self.login_status_label.setStyleSheet("color: #dc3545; font-size: 9pt;")
                    QMessageBox.warning(self, "登录失败", msg)

                QTimer.singleShot(0, on_success)
            except Exception as e:
                def on_exc():
                    self.login_btn.setEnabled(True)
                    self.login_btn.setText("登录")
                    # 更新状态为异常（红色）
                    self.login_status_dot.setText("○")
                    self.login_status_dot.setStyleSheet("color: #dc3545; font-size: 14px; font-weight: bold;")
                    self.login_status_label.setText("登录异常")
                    self.login_status_label.setStyleSheet("color: #dc3545; font-size: 9pt;")
                    QMessageBox.critical(self, "错误", str(e))
                QTimer.singleShot(0, on_exc)

        threading.Thread(target=do_login, daemon=True).start()

    def _toggle_password_visibility(self, checked):
        if checked:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_pwd_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent; border: none; font-size: 12px; color: #165DFF;
                }
                QPushButton:hover { color: #3a7afe; }
            """)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_pwd_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent; border: none; font-size: 12px; color: #6c757d;
                }
                QPushButton:hover { color: #165DFF; }
            """)

    def _on_query(self):
        """查询处理"""
        if self.is_querying:
            return

        if not self.session:
            QMessageBox.warning(self, "提示", "请先登录")
            return

        cities = self.city_dropdown.get_selected()
        if not cities:
            QMessageBox.warning(self, "提示", "请选择至少一个地市")
            return

        tables = self.table_dropdown.get_selected()
        if not tables:
            QMessageBox.warning(self, "提示", "请选择至少一个数据表")
            return

        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")

        self._save_user_config()
        self.is_querying = True
        self._stop_requested = False
        self.query_btn.setEnabled(False)
        self.query_btn.setText("查询中...")
        self.progress_bar.setValue(20)
        self.progress_label.setText("正在查询数据...")

        def do_query():
            try:
                results = {}
                total = len(tables)

                self.logger.info(f"选择的表格: {tables}")
                self.logger.info(f"选择的地市: {cities}")
                self.logger.info(f"日期范围: {start_date} 至 {end_date}")
                self.logger.info("-" * 40)

                for i, table in enumerate(tables):
                    if self._stop_requested:
                        self.logger.warning("查询已被用户停止")
                        break
                    self.logger.info(f"正在查询: {table} ({i+1}/{total})")
                    QTimer.singleShot(0, lambda idx=i, t=total, n=table: self._update_progress_detail(idx, t, n))
                    data = self.jxcx.search(
                        table_name=table,
                        cities=cities,
                        start_date=start_date,
                        end_date=end_date
                    )
                    results[table] = data

                    progress = 20 + int((i + 1) / total * 60)
                    QTimer.singleShot(0, lambda p=progress: self.progress_bar.setValue(p))

                QTimer.singleShot(0, lambda: self._on_query_complete(results))
            except Exception as e:
                self.logger.error(f"查询失败: {e}")
                QTimer.singleShot(0, lambda: self._on_query_error(str(e)))

        threading.Thread(target=do_query, daemon=True).start()

    def _on_query_complete(self, results):
        self.is_querying = False
        self._stop_requested = False
        self.query_btn.setEnabled(True)
        self.query_btn.setText("🔍 查询")
        self.progress_bar.setValue(100)
        self.progress_label.setText("查询完成")

        total_rows = 0
        for table, data in results.items():
            if isinstance(data, pd.DataFrame):
                total_rows += len(data)
            elif isinstance(data, list):
                total_rows += len(data)

        self.preview_stats_label.setText(f"查询完成，共获取 {total_rows} 条记录")

        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(3)
        self.preview_table.setHorizontalHeaderLabels(['数据表', '记录数', '状态'])
        for i, (table, data) in enumerate(results.items()):
            count = len(data) if data else 0
            self.preview_table.insertRow(i)
            self.preview_table.setItem(i, 0, QTableWidgetItem(table))
            self.preview_table.setItem(i, 1, QTableWidgetItem(str(count)))
            self.preview_table.setItem(i, 2, QTableWidgetItem("完成"))

        self.export_btn.setEnabled(True)
        self.current_results = results

    def _on_query_error(self, error_msg):
        self.is_querying = False
        self._stop_requested = False
        self.query_btn.setEnabled(True)
        self.query_btn.setText("🔍 查询")
        self.progress_bar.setValue(0)
        self.progress_label.setText("查询失败")
        QMessageBox.critical(self, "查询失败", error_msg)

    def _update_progress_detail(self, current, total, table_name):
        pct = 20 + int((current + 1) / total * 60)
        self.progress_bar.setValue(pct)
        self.progress_label.setText(f"正在查询: {table_name} ({current+1}/{total})")

    def _on_export(self):
        """导出处理"""
        if not hasattr(self, 'current_results'):
            return

        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", "export.xlsx", "Excel Files (*.xlsx);;All Files (*)"
        )

        if file_path:
            try:
                export_with_format(self.current_results, file_path)
                QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def set_quick_date(self, days):
        """设置快捷日期"""
        end = QDate.currentDate().addDays(-1)
        start = QDate.currentDate().addDays(-days)
        self.start_date.setDate(start)
        self.end_date.setDate(end)

    def _show_activate_window(self):
        """显示激活窗口"""
        dialog = ActivateDialog(self)
        dialog.exec()

    def _on_time_rollback(self):
        """时间回拨检测"""
        QMessageBox.critical(self, "错误", "检测到系统时间被回拨，授权已失效")
        self.close()

    def _save_user_config(self):
        import json
        try:
            config = {}
            if hasattr(self, 'city_dropdown'):
                config['cities'] = self.city_dropdown.get_selected()
            if hasattr(self, 'table_dropdown'):
                config['tables'] = self.table_dropdown.get_selected()
            if hasattr(self, 'start_date'):
                config['start_date'] = self.start_date.date().toString('yyyy-MM-dd')
            if hasattr(self, 'end_date'):
                config['end_date'] = self.end_date.date().toString('yyyy-MM-dd')
            config_path = os.path.join(os.getcwd(), 'user_config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"保存配置失败: {e}")

    def _load_user_config(self):
        import json
        try:
            config_path = os.path.join(os.getcwd(), 'user_config.json')
            if not os.path.exists(config_path):
                return
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if 'cities' in config and hasattr(self, 'city_dropdown'):
                self.city_dropdown.set_selected(config['cities'], trigger_callback=False)
            if 'tables' in config and hasattr(self, 'table_dropdown'):
                self.table_dropdown.set_selected(config['tables'], trigger_callback=False)
            if 'start_date' in config and hasattr(self, 'start_date'):
                self.start_date.setDate(QDate.fromString(config['start_date'], 'yyyy-MM-dd'))
            if 'end_date' in config and hasattr(self, 'end_date'):
                self.end_date.setDate(QDate.fromString(config['end_date'], 'yyyy-MM-dd'))
            self.logger.info("已加载上次配置")
        except Exception as e:
            self.logger.warning(f"加载配置失败: {e}")

    def load_config(self):
        self._update_license_display()
        self._load_user_config()

    def _update_license_display(self):
        """更新授权状态显示"""
        if self.expiry_time:
            try:
                display_time = self.expiry_time.strftime("%Y-%m-%d")
                current_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                days_left = (self.expiry_time - current_dt).days

                if days_left < 0:
                    self.license_status_label.setText("授权已过期")
                    self.license_status_label.setStyleSheet("font-size: 9pt; font-weight: 500; color: #dc3545;")
                elif days_left <= 7:
                    self.license_status_label.setText(f"到期: {display_time} (剩{days_left}天)")
                    self.license_status_label.setStyleSheet("font-size: 9pt; font-weight: 500; color: #fd7e14;")
                elif days_left <= 30:
                    self.license_status_label.setText(f"到期: {display_time} (剩{days_left}天)")
                    self.license_status_label.setStyleSheet("font-size: 9pt; font-weight: 500; color: #fd7e14;")
                else:
                    self.license_status_label.setText(f"到期: {display_time}")
                    self.license_status_label.setStyleSheet("font-size: 9pt; font-weight: 500; color: #22c55e;")
            except Exception:
                self.license_status_label.setText("授权状态未知")
                self.license_status_label.setStyleSheet("font-size: 9pt; font-weight: 500; color: #6c757d;")
        else:
            self.license_status_label.setText("未激活")
            self.license_status_label.setStyleSheet("font-size: 9pt; font-weight: 500; color: #dc3545;")

    def _on_log_search(self, text):
        pass

    def _clear_log(self):
        self.log_viewer.clear()

    def _on_log_scroll_changed(self, value):
        scrollbar = self.log_viewer.verticalScrollBar()
        if value < scrollbar.maximum() - 10:
            if self._log_auto_scroll:
                self._log_auto_scroll = False
                self.auto_scroll_label.setText("自动滚动已暂停")
        else:
            if not self._log_auto_scroll:
                self._log_auto_scroll = True
                self.auto_scroll_label.setText("")

    def append_log(self, message):
        self.log_viewer.append(message)
        if self._log_auto_scroll:
            cursor = self.log_viewer.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_viewer.setTextCursor(cursor)

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, '_time_monitor'):
            self._time_monitor.stop()
        event.accept()


class LogHandler(logging.Handler):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def emit(self, record):
        msg = self.format(record)
        msg = msg.replace('<', '&lt;').replace('>', '&gt;')
        if record.levelno >= logging.ERROR:
            msg = f'<span style="color: #dc3545;">{msg}</span>'
        elif record.levelno >= logging.WARNING:
            msg = f'<span style="color: #fd7e14;">{msg}</span>'
        elif record.levelno >= logging.INFO:
            msg = f'<span style="color: #165DFF;">{msg}</span>'
        QTimer.singleShot(0, lambda: self.window.append_log(msg))


class ActivateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("授权激活")
        self.setFixedSize(500, 380)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        from core.license import generate_machine_code, get_hw_info
        hw_info = get_hw_info()
        self.machine_code = generate_machine_code(hw_info)

        info_label = QLabel("📋 本机信息 - 机器码")
        info_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        layout.addWidget(info_label)

        code_row = QHBoxLayout()
        self.code_label = QLabel(self.machine_code[:40] + "...")
        self.code_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa; padding: 8px;
                border-radius: 4px; font-family: Consolas; font-size: 9pt;
            }
        """)
        code_row.addWidget(self.code_label, 1)
        copy_btn = QPushButton("复制")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef; border: none;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #dee2e6; }
        """)
        copy_btn.clicked.connect(self._copy_machine_code)
        code_row.addWidget(copy_btn)
        layout.addLayout(code_row)

        serial_label = QLabel("🎫 输入验证序列号")
        serial_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        layout.addWidget(serial_label)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("格式示例：NQI-xxxx-xxxx-xxxx")
        self.serial_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #dee2e6; border-radius: 4px;
                padding: 4px 8px; font-family: Consolas; font-size: 10pt;
            }
        """)
        layout.addWidget(self.serial_input)

        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color: #6c757d; font-size: 8pt;")
        layout.addWidget(self.hint_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef; border: none;
                border-radius: 4px; padding: 6px 16px;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        self.activate_btn = QPushButton("✅ 激活授权")
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #165DFF; color: white; font-weight: bold;
                border: none; border-radius: 6px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #3a7afe; }
        """)
        self.activate_btn.clicked.connect(self._on_activate)
        btn_layout.addWidget(self.activate_btn)
        layout.addLayout(btn_layout)

        self.serial_input.setFocus()
        self.serial_input.returnPressed.connect(self.activate_btn.click)

    def _copy_machine_code(self):
        QApplication.clipboard().setText(self.machine_code)
        self.hint_label.setText("机器码已复制到剪贴板")
        self.hint_label.setStyleSheet("color: #22c55e; font-size: 8pt;")

    def _on_activate(self):
        serial = self.serial_input.text().strip()
        if not serial:
            self.hint_label.setText("请输入序列号")
            self.hint_label.setStyleSheet("color: #dc3545; font-size: 8pt;")
            return
        self.hint_label.setText("正在验证...")
        self.hint_label.setStyleSheet("color: #fd7e14; font-size: 8pt;")
        self.activate_btn.setEnabled(False)
        success, result = verify_serial_number(serial, self.machine_code)
        if success:
            write_success, msg = write_license_from_serial(result)
            if write_success:
                self.hint_label.setText("激活成功！")
                self.hint_label.setStyleSheet("color: #22c55e; font-size: 8pt;")
                QMessageBox.information(self, "成功", f"授权激活成功！\n\n过期时间：{result['expiry_time']}")
                self.accept()
            else:
                self.hint_label.setText(f"写入授权失败：{msg}")
                self.hint_label.setStyleSheet("color: #dc3545; font-size: 8pt;")
                self.activate_btn.setEnabled(True)
        else:
            self.hint_label.setText(result)
            self.hint_label.setStyleSheet("color: #dc3545; font-size: 8pt;")
            self.activate_btn.setEnabled(True)


class NqiToolApp:
    """应用程序入口"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self._setup_stylesheet()

        self.window = NqiToolMainWindow()

    def _setup_stylesheet(self):
        """设置全局样式"""
        self.app.setStyle("Fusion")
        self.app.setFont(QFont())  # 使用系统默认字体

    def run(self):
        """运行应用"""
        self.window.show()
        return self.app.exec()


def main():
    app = NqiToolApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
