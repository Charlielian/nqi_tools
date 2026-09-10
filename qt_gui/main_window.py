# -*- coding: utf-8 -*-
"""
Qt6 主窗口模块
保持多版本共存：逻辑与数据层与 Tk 版本共享，界面采用全现代卡片式布局与 QSS 主题
"""

import os
import sys
import threading
from datetime import datetime, timedelta
from typing import List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QRadioButton, QButtonGroup, QCheckBox,
    QProgressBar, QMessageBox, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap

from qt_gui.components.date_range_picker import QtDateRangePicker
from qt_gui.components.multi_select_combo import QtMultiSelectCombo
from qt_gui.components.log_panel import QtLogViewer
from qt_gui.components.week_selector import QtWeekSelector

from gui.widgets import TableConfig
from core.auth import LoginManager
from core.query import JXCXQuery
from utils.config import OUTPUT_DIR, EXPIRY_DATE

try:
    from core.workers import QueryWorker
except (ImportError, TypeError):
    QueryWorker = None


class WorkerBridge(QObject):
    """跨线程信号桥梁：安全地将后台工作线程状态转交 Qt 主线程刷新"""
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(float, float, str)
    finished_signal = pyqtSignal(bool)
    main_call_signal = pyqtSignal(object)


class QtMainWindow(QMainWindow):
    """NQI 现代化 Qt6 桌面主界面"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NQI 数据导出工具 (Qt6 现代化桌面版)")
        self.resize(1120, 820)
        self.setMinimumSize(980, 720)

        # 核心业务状态 (与 Tk 版本 100% 对齐复用)
        self.session = None
        self.jxcx = None
        self.login_manager = LoginManager()
        self.worker = None
        self.worker_thread = None
        self.is_querying = False
        self.current_theme = "light"  # 默认白色系

        self.bridge = WorkerBridge()
        self.bridge.log_signal.connect(self._on_log_received)
        self.bridge.progress_signal.connect(self._on_progress_received)
        self.bridge.finished_signal.connect(self._on_query_finished)
        self.bridge.main_call_signal.connect(lambda fn: fn())

        self._init_ui()
        self._init_state()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 顶部卡片：系统状态与登录
        main_layout.addWidget(self._create_header_card())

        # 中间配置区域卡片
        main_layout.addWidget(self._create_config_card())

        # 操作控制与进度条
        main_layout.addWidget(self._create_action_card())

        # 底部彩色日志卡片 (占满剩余高度)
        self.log_viewer = QtLogViewer(self)
        main_layout.addWidget(self.log_viewer, stretch=1)

    def _create_header_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # 标题与徽章
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("NQI 数据自动提取平台")
        title.setObjectName("MainTitle")
        sub_title = QLabel(f"版本: v2.0 (Qt6 现代版)  |  有效期至: {EXPIRY_DATE}")
        sub_title.setObjectName("HintLabel")
        title_box.addWidget(title)
        title_box.addWidget(sub_title)
        layout.addLayout(title_box)

        layout.addStretch()

        # 主题切换胶囊 (亮色 / 暗色)
        self.btn_theme_toggle = QPushButton("☀️ 浅色系")
        self.btn_theme_toggle.setObjectName("TagButton")
        self.btn_theme_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_toggle.setToolTip("点击在 [亮面白皙] 与 [极客深黑] 主题间无缝切换")
        self.btn_theme_toggle.clicked.connect(self._toggle_theme)

        # 登录认证状态区
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #FF7D00; font-size: 16px;")
        self.status_text = QLabel("正在初始化认证...")
        self.status_text.setObjectName("SectionLabel")

        self.btn_login = QPushButton("🔑 执行登录")
        self.btn_login.setObjectName("PrimaryButton")
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self._do_login)

        layout.addWidget(self.btn_theme_toggle)
        layout.addWidget(self.status_dot)
        layout.addWidget(self.status_text)
        layout.addWidget(self.btn_login)

        return card

    def _create_config_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # 第一行：数据表分类与表格多选
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # 报表大类
        col_cat = QVBoxLayout()
        lbl_cat = QLabel("报表大类筛选")
        lbl_cat.setObjectName("SectionLabel")
        self.combo_cat = QtMultiSelectCombo(self, items=['全部'] + list(self._get_categories().keys()), placeholder="全部类别")
        self.combo_cat.set_selected(['全部'])
        self.combo_cat.selection_changed.connect(self._on_category_changed)
        col_cat.addWidget(lbl_cat)
        col_cat.addWidget(self.combo_cat)
        row1.addLayout(col_cat, stretch=1)

        # 数据表多选
        col_tables = QVBoxLayout()
        lbl_tables = QLabel("目标数据表 (支持多选)")
        lbl_tables.setObjectName("SectionLabel")
        self.combo_tables = QtMultiSelectCombo(self, items=TableConfig.get_table_names(), placeholder="请勾选需要导出的数据表")
        self.combo_tables.set_selected(['4GMR覆盖-小区天'])
        self.combo_tables.selection_changed.connect(self._on_table_selection_changed)
        col_tables.addWidget(lbl_tables)
        col_tables.addWidget(self.combo_tables)
        row1.addLayout(col_tables, stretch=2)

        layout.addLayout(row1)

        # 第二行：地市选择、快捷选项与日期范围选择（或周选择器）
        self.row2_widget = QWidget()
        row2 = QHBoxLayout(self.row2_widget)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(16)

        # 地市
        col_city = QVBoxLayout()
        lbl_city = QLabel("地市范围")
        lbl_city.setObjectName("SectionLabel")
        self.combo_city = QtMultiSelectCombo(self, items=QtMultiSelectCombo.GD_CITIES, placeholder="请选择地市")
        self.combo_city.set_selected(['阳江'])
        col_city.addWidget(lbl_city)
        col_city.addWidget(self.combo_city)
        row2.addLayout(col_city, stretch=1)

        # 快捷日期胶囊
        col_shortcuts = QVBoxLayout()
        lbl_quick = QLabel("快捷日期")
        lbl_quick.setObjectName("SectionLabel")
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(6)
        for label, tag in [("昨天", "昨天"), ("近7天", "近7天"), ("近30天", "近30天"), ("本月", "本月"), ("上月", "上月")]:
            btn = QPushButton(label)
            btn.setObjectName("TagButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=tag: self._apply_quick_date(t))
            quick_layout.addWidget(btn)
        col_shortcuts.addWidget(lbl_quick)
        col_shortcuts.addLayout(quick_layout)
        row2.addLayout(col_shortcuts, stretch=2)

        # 日期范围组件
        col_date = QVBoxLayout()
        lbl_date = QLabel("查询日期区间 (开始 至 结束)")
        lbl_date.setObjectName("SectionLabel")
        self.date_picker = QtDateRangePicker(self)
        col_date.addWidget(lbl_date)
        col_date.addWidget(self.date_picker)
        row2.addLayout(col_date, stretch=2)

        layout.addWidget(self.row2_widget)

        # 周选择器容器 (平时隐藏，选合成45G流量表时显示)
        self.week_selector = QtWeekSelector(self)
        self.week_selector.setVisible(False)
        layout.addWidget(self.week_selector)

        # 第三行：参数模式与选项
        row3 = QHBoxLayout()
        row3.setSpacing(20)

        mode_lbl = QLabel("字段获取模式:")
        mode_lbl.setObjectName("SectionLabel")
        row3.addWidget(mode_lbl)

        self.radio_hardcode = QRadioButton("硬编码模板 (极速稳定)")
        self.radio_hardcode.setChecked(True)
        self.radio_dynamic = QRadioButton("动态在线探测")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_hardcode)
        self.mode_group.addButton(self.radio_dynamic)
        row3.addWidget(self.radio_hardcode)
        row3.addWidget(self.radio_dynamic)

        row3.addSpacing(30)
        self.chk_per_day = QCheckBox("按日查询")
        self.chk_per_day.setChecked(False)
        self.chk_per_day.toggled.connect(self._on_per_day_toggled)
        row3.addWidget(self.chk_per_day)

        self.chk_per_sheet = QCheckBox("按日分Sheet")
        self.chk_per_sheet.setEnabled(False)
        self.chk_per_sheet.toggled.connect(self._on_per_sheet_toggled)
        row3.addWidget(self.chk_per_sheet)

        self.chk_per_city = QCheckBox("按日+按地市导出")
        self.chk_per_city.setEnabled(False)
        self.chk_per_city.toggled.connect(self._on_per_city_toggled)
        row3.addWidget(self.chk_per_city)

        row3.addSpacing(20)
        self.chk_single_city_parallel = QCheckBox("单地市多线程")
        row3.addWidget(self.chk_single_city_parallel)

        row3.addStretch()
        layout.addLayout(row3)

        return card

    def _on_per_day_toggled(self, checked: bool):
        """按日查询切换：启用/禁用子选项，与 单地市多线程 互斥"""
        self.chk_per_sheet.setEnabled(checked)
        self.chk_per_city.setEnabled(checked)
        if checked:
            self.chk_single_city_parallel.setChecked(False)
            self.chk_single_city_parallel.setEnabled(False)
            self.log_viewer.append_log("已启用按日查询模式，可进一步勾选按日分Sheet或按日+按地市", "INFO")
        else:
            self.chk_per_sheet.setChecked(False)
            self.chk_per_city.setChecked(False)
            self.chk_single_city_parallel.setEnabled(True)

    def _on_per_sheet_toggled(self, checked: bool):
        """按日分Sheet 与 按日+按地市 导出互斥"""
        if checked and self.chk_per_city.isChecked():
            self.chk_per_city.setChecked(False)
        if checked:
            self.log_viewer.append_log("已切换为按日分Sheet导出模式", "INFO")

    def _on_per_city_toggled(self, checked: bool):
        """按日+按地市 与 按日分Sheet 互斥"""
        if checked and self.chk_per_sheet.isChecked():
            self.chk_per_sheet.setChecked(False)
        if checked:
            self.log_viewer.append_log("已切换为按日+按地市导出模式", "INFO")

    def _create_action_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # 操作按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_start = QPushButton("▶ 开始提取并导出")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.setFixedHeight(36)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._on_start_query)

        self.btn_stop = QPushButton("⏹ 停止任务")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self._on_stop_query)

        self.btn_open_folder = QPushButton("📂 打开导出目录")
        self.btn_open_folder.setFixedHeight(36)
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_output_dir)

        self.btn_open_logs = QPushButton("📜 打开日志目录")
        self.btn_open_logs.setFixedHeight(36)
        self.btn_open_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_logs.clicked.connect(self._open_logs_dir)

        btn_layout.addWidget(self.btn_start, stretch=2)
        btn_layout.addWidget(self.btn_stop, stretch=1)
        btn_layout.addWidget(self.btn_open_folder, stretch=1)
        btn_layout.addWidget(self.btn_open_logs, stretch=1)
        layout.addLayout(btn_layout)

        # 进度条与状态详情
        prog_layout = QHBoxLayout()
        prog_layout.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.lbl_progress_detail = QLabel("准备就绪")
        self.lbl_progress_detail.setObjectName("HintLabel")
        prog_layout.addWidget(self.progress_bar, stretch=3)
        prog_layout.addWidget(self.lbl_progress_detail, stretch=1)
        layout.addLayout(prog_layout)

        return card

    def _init_state(self):
        # 初始装载亮色主题
        self._apply_theme("light")
        self.log_viewer.append_log("Qt6 现代化桌面界面已加载", "SUCCESS")
        self.log_viewer.append_log(f"当前支持 {len(TableConfig.TABLE_CONFIGS)} 张基础报表与合成报表", "INFO")
        # 尝试自动快速登录
        self._do_login()

    def _toggle_theme(self):
        new_theme = "dark" if self.current_theme == "light" else "light"
        self._apply_theme(new_theme)

    def _apply_theme(self, theme_name: str):
        self.current_theme = theme_name
        styles_dir = os.path.join(os.path.dirname(__file__), 'styles')
        qss_file = os.path.join(styles_dir, f"{theme_name}.qss")
        if os.path.exists(qss_file):
            from PyQt6.QtWidgets import QApplication
            with open(qss_file, 'r', encoding='utf-8') as f:
                qss_content = f.read()
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(qss_content)

        if theme_name == "dark":
            self.btn_theme_toggle.setText("🌙 极客暗")
            if hasattr(self, 'log_viewer'):
                self.log_viewer.append_log("界面已切换至 [深邃极客暗] 主题", "INFO")
        else:
            self.btn_theme_toggle.setText("☀️ 现代白")
            if hasattr(self, 'log_viewer'):
                self.log_viewer.append_log("界面已切换至 [纯白素雅] 主题", "INFO")

    def _get_categories(self):
        return {
            '5G容量': ['5G小区容量报表', '5G小区容量-周', '5G小区容量-月'],
            '4G容量': ['4G小区容量报表-天', '4G小区容量报表-周', '4G小区容量报表-月'],
            'MR覆盖': ['5GMR覆盖-小区天', '4GMR覆盖-小区天', '4G覆盖-月'],
            '语音报表': ['5G语音业务-小区', 'VOLTE语音业务-天', 'EPSFB语音业务-天'],
            '干扰报表': ['5G干扰小区报表', '4G干扰小区报表', '5G干扰小区-子盲'],
            'KPI报表': ['5G小区性能KPI报表', '4G小区性能KPI报表-地市'],
            '工参数据': ['5G小区工参', '4G小区工参', '共站同覆盖小区_4g_5g'],
            '特殊分析': ['重要场景-天', '重要场景-周', '重要场景-月', '流量热点基站', 'NR过晚节电小区']
        }

    def _on_category_changed(self, categories: List[str]):
        all_cats = self._get_categories()
        if not categories or '全部' in categories:
            self.combo_tables.set_items(TableConfig.get_table_names())
            return
        matched = []
        for cat in categories:
            if cat in all_cats:
                matched.extend(all_cats[cat])
        self.combo_tables.set_items(matched)

    def _on_table_selection_changed(self, selected_tables: List[str]):
        """表格选中变化：如果包含合成45G流量表则显示周选择器并隐藏普通日期选择"""
        is_synthesize = '合成45G流量表' in selected_tables
        self.week_selector.setVisible(is_synthesize)
        self.row2_widget.setVisible(not is_synthesize)

    def _apply_quick_date(self, tag: str):
        today = datetime.now().date()
        if tag == "昨天":
            y = today - timedelta(days=1)
            self.date_picker.set_range(y, y)
        elif tag == "近7天":
            end = today - timedelta(days=1)
            self.date_picker.set_range(end - timedelta(days=6), end)
        elif tag == "近30天":
            end = today - timedelta(days=1)
            self.date_picker.set_range(end - timedelta(days=29), end)
        elif tag == "本月":
            self.date_picker.set_range(today.replace(day=1), today)
        elif tag == "上月":
            first = today.replace(day=1)
            end = first - timedelta(days=1)
            self.date_picker.set_range(end.replace(day=1), end)
        self.log_viewer.append_log(f"已设置快捷日期: {tag}", "INFO")

    def _do_login(self):
        """执行登录逻辑：先尝试复用保存的 Cookie，若失效则弹出 Qt6 图形+短信安全验证码对话框"""
        self.status_dot.setStyleSheet("color: #FF7D00; font-size: 16px;")
        self.status_text.setText("正在检查登录状态...")
        self.btn_login.setEnabled(False)

        def _bg_check():
            from core.auth import load_cookie
            saved_cookie = load_cookie(self.login_manager.username)
            if saved_cookie:
                self.login_manager.sess.cookies = saved_cookie
                # 用更严谨的 JXCX 可访问性校验（进入即席查询模块成功才算有效）
                probe_query = JXCXQuery(session=self.login_manager.sess)
                if probe_query.enter_jxcx():
                    self.session = self.login_manager.sess
                    self.jxcx = probe_query
                    self.bridge.log_signal.emit("✓ 使用已保存的Cookie成功免密登录！", "SUCCESS")
                    QTimer.singleShot(0, self._on_login_ui_success)
                    return

            # 需要弹窗完成图形验证码 + 短信验证码
            QTimer.singleShot(0, self._open_login_dialog)

        threading.Thread(target=_bg_check, daemon=True).start()

    def _open_login_dialog(self):
        """弹出图形验证码与短信验证码登录窗口"""
        from qt_gui.components.login_dialog import QtLoginDialog
        dlg = QtLoginDialog(
            parent=self,
            username=self.login_manager.username,
            password=self.login_manager.password,
            session=self.login_manager.sess
        )
        if dlg.exec():
            # 用户在弹窗中通过了图形码 + 短信码验证
            self.session = self.login_manager.sess
            self.jxcx = JXCXQuery(session=self.session)
            from utils.helpers import save_cookie
            # 注意：save_cookie 参数顺序是 (cookie_jar, username)
            save_cookie(self.session.cookies, self.login_manager.username)
            self._on_login_ui_success()
            self.log_viewer.append_log("统一认证通过，登录凭据已保存！", "SUCCESS")
        else:
            self.status_dot.setStyleSheet("color: #F53F3F; font-size: 16px;")
            self.status_text.setText("登录取消或失败")
            self.btn_login.setEnabled(True)
            self.log_viewer.append_log("用户取消了登录或安全认证失败", "WARNING")

    def _on_login_ui_success(self):
        self.status_dot.setStyleSheet("color: #00B42A; font-size: 16px;")
        self.status_text.setText(f"已登录: {self.login_manager.username}")
        self.btn_login.setText("✓ 重新登录")
        self.btn_login.setEnabled(True)

    def _on_start_query(self):
        """开始提取任务"""
        if self.is_querying:
            return

        tables = self.combo_tables.get_selected()
        if not tables:
            QMessageBox.warning(self, "提示", "请勾选至少一个要导出的数据表！")
            return

        # 检查是否包含合成45G流量表
        if '合成45G流量表' in tables:
            if len(tables) > 1:
                QMessageBox.warning(self, "提示", "合成45G流量表必须单独选择，不能与其他普通数据表同时勾选！")
                return
            self._on_start_synthesize()
            return

        cities = self.combo_city.get_selected()
        city_str = ",".join(cities) if cities else ""

        start_date, end_date = self.date_picker.get_range()
        multi_day = self.chk_per_day.isChecked()
        multi_day_per_sheet = self.chk_per_sheet.isChecked()
        multi_day_per_city = self.chk_per_city.isChecked()
        single_city_parallel = self.chk_single_city_parallel.isChecked()

        self.is_querying = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.lbl_progress_detail.setText("任务启动中...")

        self.log_viewer.append_log(f"开始执行批量导出: {', '.join(tables)}", "INFO")
        mode_desc = []
        if multi_day:
            if multi_day_per_sheet:
                mode_desc.append("按日分Sheet")
            elif multi_day_per_city:
                mode_desc.append("按日+按地市")
            else:
                mode_desc.append("按日合并")
        elif single_city_parallel:
            mode_desc.append("单地市多线程")
        self.log_viewer.append_log(
            f"日期范围: {start_date} 至 {end_date} | 地市: {city_str or '全部'} | 模式: {'/'.join(mode_desc) or '标准'}",
            "INFO"
        )

        # 使用与 Tk 版本一致的 QueryWorker 完整查询工作流（传入 var-like 快照对象）
        class _Var:
            """模拟 tk.BooleanVar / tk.StringVar 的 .get() 快照，便于与 core.workers 无缝复用"""
            def __init__(self, val):
                self._val = val

            def get(self):
                return self._val

        def _schedule_main(ms, fn, *args):
            """后台工作线程调度：通过 Qt 信号槽安全将回调函数投递回主线程执行"""
            def _target():
                try:
                    fn(*args)
                except Exception:
                    import traceback
                    self.bridge.log_signal.emit(traceback.format_exc(), "ERROR")
            self.bridge.main_call_signal.emit(_target)

        self.query_worker = QueryWorker(
            session=self.session,
            jxcx=self.jxcx,
            log_func=lambda msg, lvl="INFO": self._safe_log_emit(msg, lvl),
            progress_func=lambda cur, tot, det="": self.bridge.progress_signal.emit(cur, tot, det),
            after_func=_schedule_main,
            field_mode_var=_Var('hardcode' if self.radio_hardcode.isChecked() else 'dynamic'),
            custom_fields_var=_Var(False),
            selected_fields={},
            multi_day_var=_Var(multi_day),
            multi_day_per_sheet_var=_Var(multi_day_per_sheet),
            multi_day_per_city_var=_Var(multi_day_per_city),
            single_city_parallel_var=_Var(single_city_parallel),
        )

        def _bg_run():
            try:
                self.query_worker.query_worker(
                    tables, start_date, end_date, city_str,
                    on_complete=lambda: self.bridge.finished_signal.emit(True),
                    on_failed=lambda: self.bridge.finished_signal.emit(False),
                )
            except Exception:
                import traceback
                self.bridge.log_signal.emit(f"查询流程异常: {traceback.format_exc()}", "ERROR")
                self.bridge.finished_signal.emit(False)

        self.worker_thread = threading.Thread(target=_bg_run, daemon=True)
        self.worker_thread.start()

    def _safe_log_emit(self, msg, lvl="INFO"):
        """从后台线程安全地发射日志信号到 Qt 主线程"""
        try:
            self.bridge.log_signal.emit(str(msg), lvl)
        except Exception:
            import traceback
            self.bridge.log_signal.emit(f"日志回调异常: {traceback.format_exc()}", "ERROR")

    def _on_start_synthesize(self):
        """合成45G流量表任务"""
        if not self.session:
            QMessageBox.warning(self, "提示", "请先登录统一认证平台！")
            return

        week_start = self.week_selector.get_week_start()
        cities = self.combo_city.get_selected()
        city_str = ",".join(cities) if cities else ""
        mon_str, sun_str = self.week_selector.get_date_range()

        self.is_querying = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_progress_detail.setText("合成任务执行中...")

        self.log_viewer.append_log("=" * 50, "INFO")
        self.log_viewer.append_log("开始执行合成 45G 流量表业务流程", "INFO")
        self.log_viewer.append_log(f"周区间: {mon_str} 至 {sun_str} | 地市: {city_str or '全部'}", "INFO")
        self.log_viewer.append_log("=" * 50, "INFO")

        def _worker():
            try:
                from core.flow_table_builder import synthesize_45g_flow_table
                success = synthesize_45g_flow_table(
                    self.session,
                    city_str,
                    week_start,
                    progress_callback=lambda m: self.bridge.log_signal.emit(m, "INFO")
                )
                self.bridge.finished_signal.emit(success)
            except Exception as e:
                import traceback
                self.bridge.log_signal.emit(f"合成异常: {traceback.format_exc()}", "ERROR")
                self.bridge.finished_signal.emit(False)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_stop_query(self):
        if self.worker and self.is_querying:
            self.worker.stop()
            self.log_viewer.append_log("已请求中断当前导出任务...", "WARNING")
            self.btn_stop.setEnabled(False)

    def _on_log_received(self, msg: str, lvl: str):
        self.log_viewer.append_log(msg, lvl)

    def _on_progress_received(self, current: float, total: float, detail: str):
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(min(100, max(0, pct)))
            self.lbl_progress_detail.setText(f"{detail} ({pct}%)")

    def _on_query_finished(self, success: bool):
        self.is_querying = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            self.lbl_progress_detail.setText("全部导出完成！")
            self.log_viewer.append_log("全部任务提取并导出完毕！", "SUCCESS")
        else:
            self.lbl_progress_detail.setText("任务失败或已中止")
            self.log_viewer.append_log("任务未全部完成或已中止", "WARNING")

    def _open_output_dir(self):
        import subprocess
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if sys.platform == 'darwin':
            subprocess.run(['open', OUTPUT_DIR])
        elif sys.platform == 'win32':
            os.startfile(OUTPUT_DIR)
        else:
            subprocess.run(['xdg-open', OUTPUT_DIR])

    def _open_logs_dir(self):
        import subprocess
        from utils.config import LOG_DIR
        os.makedirs(LOG_DIR, exist_ok=True)
        if sys.platform == 'darwin':
            subprocess.run(['open', LOG_DIR])
        elif sys.platform == 'win32':
            os.startfile(LOG_DIR)
        else:
            subprocess.run(['xdg-open', LOG_DIR])
