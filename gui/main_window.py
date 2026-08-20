# -*- coding: utf-8 -*-
"""
主窗口模块
提供应用程序的主界面
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import os
import queue
import calendar

from datetime import datetime, timedelta

from gui.widgets import LogTextHandler, TableConfig, MultiSelectDropdown
from gui.components import SearchableCombobox, CalendarDialog, Tooltip
from gui.theme import colors, fonts, spacing
from gui.first_run import check_first_run, show_first_run_wizard
from core.auth import LoginManager
from core.query import JXCXQuery
from core.workers import QueryWorker
from utils.logger import ensure_dirs, setup_report_logging, get_report_logger
from utils.config import (
    LOG_DIR, OUTPUT_DIR, EXPIRY_DATE, DEFAULT_USERNAME, DEFAULT_PASSWORD,
    LOGGING_DETAILED,
)


def _get_month_days(year, month):
    """返回指定年月的合法日期序列。"""
    return tuple(range(1, calendar.monthrange(year, month)[1] + 1))


def _parse_date_range(start_date, end_date):
    """解析并校验查询日期范围，返回两个 datetime 对象。"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")
    return start, end

def check_and_setup_credentials(parent=None):
    """检查并设置凭证，如需首次运行引导则显示向导

    Returns:
        tuple: (needs_setup, credentials_dict)
        - needs_setup=True: 需要显示设置向导，credentials_dict为None
        - needs_setup=False: 使用默认/已保存的凭证
    """
    if check_first_run():
        success, credentials = show_first_run_wizard(parent=parent)
        if not success:
            return True, None
        return False, credentials
    return False, None


# TODO: 本文件 1517 行仍然较大，建议进一步拆分：
#       1. 主窗口布局构建 → gui/layout.py
#       2. 计算列逻辑 → core/calculations.py（已在 gui/calculators/）
class NqiToolGUI:
    """NQI工具主窗口"""

    def __init__(self, root, expiry_time=None, credentials=None):
        self.root = root
        self.root.title("NQI工具")
        self.root.geometry("1100x800")
        self.root.minsize(800, 600)

        self.expiry_time = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d") if not expiry_time else expiry_time
        self.credentials = credentials or {}
        self.session = None
        self.jxcx = None
        self.query_thread = None
        self.is_querying = False
        self.log_queue = queue.Queue()

        # 进度预估时间相关
        self._progress_start_time = None  # 查询开始时间
        self._progress_last_update = None  # 上次更新时间
        self._progress_last_value = 0     # 上次进度值
        self._total_expected = 0           # 预期总进度

        # 标签搜索防抖
        self._label_search_after_id = None  # 防抖定时器 ID

        self._setup_logging()
        self._create_widgets()
        self._bind_events()

        self.logger.info("=" * 50)
        self.logger.info("NQI工具 GUI 启动")
        self.logger.info(f"日志文件: {self.log_file_path}")
        self.logger.info("=" * 50)

        self.load_config()

    def _setup_logging(self):
        """设置日志系统（简化版，避免重复添加 handler）

        根据 config.yaml 中 logging.detailed 的值控制详细程度：
        - True  → LogTextHandler 显示 DEBUG 级别（含详细调试信息）
        - False → LogTextHandler 显示 INFO 级别（仅关键信息）
        """
        import logging
        try:
            ensure_dirs()
            log_filename = f"NqiTool_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            self.log_file_path = os.path.join(LOG_DIR, log_filename)

            # 初始化报表日志系统（仅设置目录，不添加 handler）
            setup_report_logging(LOG_DIR, console=True)

            # 主窗口日志记录器
            self.logger = logging.getLogger('NqiTool')
            self.logger.setLevel(logging.DEBUG)
            self.logger.propagate = False  # 避免向 root logger 传播

            # 文件日志处理器（始终记录 DEBUG 级别）
            file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            self.logger.info("日志系统初始化完成")
            self.logger.info(f"日志根目录: {LOG_DIR}")
            self.logger.info(f"详细日志模式: {'开启' if LOGGING_DETAILED else '关闭'}")
        except Exception as e:
            self.logger = logging.getLogger('NqiTool')
            self.logger.setLevel(logging.DEBUG)
            self.logger.warning(f"初始化日志文件失败: {e}，日志将仅输出到界面")

    def _create_widgets(self):
        """创建界面组件 - 使用现代化设计"""
        # 顶部蓝色标题栏
        self.header = tk.Frame(self.root, bg='#165DFF', height=60)
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)

        # 标题栏左侧 - Logo和标题
        left_frame = tk.Frame(self.header, bg='#165DFF')
        left_frame.pack(side=tk.LEFT, padx=25, pady=12)

        icon_frame = tk.Frame(left_frame, bg='#1a6ce8', width=36, height=36)
        icon_frame.pack(side=tk.LEFT, padx=(0, 12))
        icon_frame.pack_propagate(False)
        icon_label = tk.Label(icon_frame, text="📊", font=('Segoe UI Emoji', 18),
                             bg='#1a6ce8', fg='white')
        icon_label.place(relx=0.5, rely=0.5, anchor='center')

        title_frame = tk.Frame(left_frame, bg='#165DFF')
        title_frame.pack(side=tk.LEFT)

        title = tk.Label(title_frame, text="NQI工具",
                        font=('Microsoft YaHei UI', 18, 'bold'),
                        bg='#165DFF', fg='white')
        title.pack(anchor='w')

        version = tk.Label(title_frame, text="NqiTool v1.1",
                          font=('Microsoft YaHei UI', 9),
                          bg='#1a6ce8', fg='white',
                          padx=8, pady=2)
        version.pack(anchor='w', pady=(2, 0))

        # 标题栏右侧 - 状态和授权时间
        self.right_frame = tk.Frame(self.header, bg='#165DFF')
        self.right_frame.pack(side=tk.RIGHT, padx=25, pady=12)

        # 授权过期时间标签
        self.license_label = tk.Label(self.right_frame, text="",
                              font=('Microsoft YaHei UI', 9),
                              bg='#165DFF', fg='#e0e7ff')
        self.license_label.pack(side=tk.LEFT, padx=(0, 15))

        # 状态指示器
        self.status_dot = tk.Label(self.right_frame, text="●", font=('Arial', 14),
                            bg='#165DFF', fg='#a5b4fc')
        self.status_dot.pack(side=tk.LEFT)
        self.status_text = tk.Label(self.right_frame, text="系统就绪",
                              font=('Microsoft YaHei UI', 10),
                              bg='#165DFF', fg='white')
        self.status_text.pack(side=tk.LEFT, padx=(6, 0))

        # 主内容区域
        self.main_container = tk.Frame(self.root, bg='#f9fafb')
        self.main_container.pack(fill=tk.BOTH, expand=True)

        content = tk.Frame(self.main_container, bg='#f9fafb')
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 登录配置卡片（放在Notebook外面，顶部）
        self._build_login_card(content)

        # 创建Notebook标签页
        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # 标签1：数据查询
        self.jxcx_frame = tk.Frame(self.notebook, bg='#f9fafb')
        self.notebook.add(self.jxcx_frame, text=" 📊 数据查询 ")
        self._build_jxcx_content(self.jxcx_frame)

        # 底部：进度和日志（放在Notebook外面）
        self._build_bottom_section(content)

        # 更新授权显示
        self._update_license_display()

    def _build_card(self, parent, title=None, **kwargs):
        """创建卡片容器
        Args:
            parent: 父容器
            title: 卡片标题（可选）
            compact: 是否紧凑模式（无标题边框）
        """
        card = tk.Frame(parent, bg='white', bd=0, relief='flat')

        if title:
            header = tk.Frame(card, bg='white')
            header.pack(fill=tk.X, padx=20, pady=(16, 0))

            label = tk.Label(header, text=title,
                            font=('Microsoft YaHei UI', 13, 'bold'),
                            bg='white', fg='#374151', anchor='w')
            label.pack(fill='x')

            separator = tk.Frame(card, bg='#f3f4f6', height=1)
            separator.pack(fill=tk.X, padx=20, pady=(12, 0))

        return card

    def _build_login_card(self, parent):
        """构建登录配置卡片（一行紧凑布局）"""
        card = self._build_card(parent, "🔐 登录配置")
        card.pack(fill=tk.X, pady=(0, 10))

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.X, padx=16, pady=10)

        # 单行布局：用户名 | 密码 | 登录状态 | 按钮
        row = tk.Frame(body, bg='white')
        row.pack(fill=tk.X)

        # 用户名
        user_frame = tk.Frame(row, bg='white')
        user_frame.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(user_frame, text="用户名", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(anchor='w')
        self.username_entry = tk.Entry(user_frame, font=('Microsoft YaHei UI', 10),
                             relief='flat', bg='#f8f9fa', bd=0, width=15)
        username = self.credentials.get('username', DEFAULT_USERNAME)
        password = self.credentials.get('password', DEFAULT_PASSWORD)
        self.username_entry.insert(0, username)
        self.username_entry.pack(fill=tk.X, pady=(2, 0), ipady=4)

        # 密码
        pass_frame = tk.Frame(row, bg='white')
        pass_frame.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(pass_frame, text="密码", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(anchor='w')
        self.password_entry = tk.Entry(pass_frame, font=('Microsoft YaHei UI', 10),
                             show="●", relief='flat', bg='#f8f9fa', bd=0, width=15)
        self.password_entry.insert(0, password)
        self.password_entry.pack(fill=tk.X, pady=(2, 0), ipady=4)

        # 登录状态图标和标签
        self.login_status_icon = tk.Label(row, text="○", font=('Arial', 12, 'bold'),
                              bg='white', fg='#80868b')
        self.login_status_icon.pack(side=tk.LEFT, padx=(10, 4), pady=0)

        self.login_status_lbl = tk.Label(row, text="未登录",
                             font=('Microsoft YaHei UI', 10, 'bold'),
                             bg='white', fg='#80868b')
        self.login_status_lbl.pack(side=tk.LEFT, padx=(0, 10), pady=0)

        # 登录按钮
        self.login_btn = tk.Button(row, text="登录",
                             font=('Microsoft YaHei UI', 10, 'bold'),
                             bg='#165DFF', fg='white', bd=1,
                             relief='raised',
                             cursor='arrow', padx=20, pady=6,
                             command=self._on_login)
        self.login_btn.pack(side=tk.LEFT)

    def _build_jxcx_content(self, parent):
        """构建数据查询标签页内容"""
        params_row = tk.Frame(parent, bg='#f9fafb')
        params_row.pack(fill=tk.X, pady=(0, 10), padx=0)

        # 左侧：查询参数卡片
        self._build_query_card(params_row)

        # 右侧：提取参数卡片
        self._build_params_card(params_row)

    def _build_query_card(self, parent):
        """构建查询参数卡片（紧凑布局）"""
        card = self._build_card(parent, "🔍 查询参数")
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # ========== 数据表选择（多选复选框）==========
        table_frame = tk.Frame(body, bg='white')
        table_frame.pack(fill=tk.X, pady=(0, 8))

        # 标签
        tk.Label(table_frame, text="数据表：", font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=(0, 6))

        # 所有可选数据表
        TABLE_CATEGORIES = {
            '干扰': ['5G干扰小区', '5G_干扰报表_自忙时', '4G干扰小区'],
            '容量': ['5G小区容量报表', '5G小区容量-周', '重要场景-天', '重要场景-周'],
            '工参': ['5G小区工参报表', '4G小区工参报表'],
            'MR覆盖': ['5GMR覆盖-小区天', '4GMR覆盖-小区天'],
            '语音报表': ['VoLTE小区监控预警', 'VONR小区监控预警', 'EPSFB小区监控预警'],
            '小区性能': ['5G小区性能KPI报表', '4G小区性能KPI报表', '通用性能报表-小区(天)v3'],
            '全程完好率': ['4G全程完好率报表', '5G全程完好率报表'],
            '语音小区': ['4G语音小区', '5G语音小区'],
            '流量热点': ['45G流量与热点评估物理站级'],
            '共站同覆盖': ['共站同覆盖小区_4g_5g'],
            '专项功能': ['合成45G流量表'],
        }

        all_tables = []
        for tables in TABLE_CATEGORIES.values():
            all_tables.extend(tables)

        # 使用 MultiSelectDropdown 实现多选（带复选框）
        self.table_dropdown = MultiSelectDropdown(
            table_frame,
            all_tables,
            width=16,
            select_all=False,
            max_dropdown_items=5,
            on_change_callback=self._on_table_selection_changed
        )
        self.table_dropdown.pack(side=tk.LEFT, padx=(0, 6))

        # 自定义字段选择
        custom_field_frame = tk.Frame(body, bg='white')
        custom_field_frame.pack(fill=tk.X, pady=(0, 8))

        self.custom_fields_var = tk.BooleanVar(value=False)
        custom_field_cb = tk.Checkbutton(custom_field_frame, text="自定义字段",
                                        variable=self.custom_fields_var,
                                        font=('Microsoft YaHei UI', 9, 'bold'),
                                        bg='white', fg='#202124',
                                        selectcolor='#165DFF',
                                        activebackground='white',
                                        activeforeground='#165DFF',
                                        cursor='arrow',
                                        command=self._on_custom_fields_toggle)
        custom_field_cb.pack(side=tk.LEFT, padx=(0, 6))

        self.select_fields_btn = tk.Button(custom_field_frame, text="选择字段",
                                         font=('Microsoft YaHei UI', 8, 'bold'),
                                         bg='#e8eaed', fg='#202124', bd=1,
                                         cursor='arrow', relief='raised',
                                         padx=10, pady=2,
                                         state=tk.DISABLED,
                                         command=self._show_field_selector)
        self.select_fields_btn.pack(side=tk.LEFT)

        # 存储选中的字段
        self.selected_fields = {}
        self.field_configs = {}

    def _build_params_card(self, parent):
        """构建提取参数卡片（紧凑布局，右侧显示）"""
        card = self._build_card(parent, "⚙ 提取参数")
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # 第一行：地市选择 + 快捷日期（水平排列）
        top_row = tk.Frame(body, bg='white')
        top_row.pack(fill=tk.X, pady=(0, 6))

        # 地市选择
        city_frame = tk.Frame(top_row, bg='white')
        city_frame.pack(side=tk.LEFT, padx=(0, 15))
        tk.Label(city_frame, text="地市选择", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(anchor='w')

        self.city_dropdown = MultiSelectDropdown(
            city_frame,
            MultiSelectDropdown.GD_CITIES,
            width=8,
            select_all=False
        )
        self.city_dropdown.pack(pady=(2, 0))
        self.city_dropdown.set_selected(['阳江'])

        # 快捷日期
        quick_frame = tk.Frame(top_row, bg='white')
        quick_frame.pack(side=tk.LEFT, padx=(0, 15))
        tk.Label(quick_frame, text="快捷日期", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(anchor='w')

        quick_inner = tk.Frame(quick_frame, bg='white')
        quick_inner.pack(pady=(2, 0))

        self.quick_date_btns = {}
        for text, days in [("昨天", 1), ("近7天", 7), ("近30天", 30)]:
            btn = tk.Button(quick_inner, text=text, font=('Microsoft YaHei UI', 8, 'bold'),
                           bg='#e8eaed', fg='#202124', bd=1, padx=10, pady=2,
                           cursor='arrow', relief='raised',
                           command=lambda d=days: self.set_quick_date(d))
            btn.pack(side=tk.LEFT, padx=(0, 3))
            self.quick_date_btns[days] = btn

        # 第二行：日期范围（单独一行）
        self.date_row = tk.Frame(body, bg='white')
        self.date_row.pack(fill=tk.X, pady=(0, 6))

        # 日期范围
        date_frame = tk.Frame(self.date_row, bg='white')
        date_frame.pack(side=tk.LEFT, padx=(0, 15))
        tk.Label(date_frame, text="日期范围", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(anchor='w')

        date_inner = tk.Frame(date_frame, bg='white')
        date_inner.pack(pady=(2, 0))

        self.start_year_var = tk.IntVar(value=datetime.now().year)
        self.start_month_var = tk.IntVar(value=datetime.now().month)
        self.start_day_var = tk.IntVar(value=1)

        yesterday = datetime.now() - timedelta(days=1)
        self.end_year_var = tk.IntVar(value=yesterday.year)
        self.end_month_var = tk.IntVar(value=yesterday.month)
        self.end_day_var = tk.IntVar(value=yesterday.day)

        start_frame = tk.Frame(date_inner, bg='white')
        start_frame.pack(side=tk.LEFT)

        current_year = datetime.now().year
        self.start_year_combo = ttk.Combobox(
            start_frame, textvariable=self.start_year_var,
            values=list(range(2020, current_year + 1)), width=4, state="readonly"
        )
        self.start_year_combo.pack(side=tk.LEFT)
        tk.Label(start_frame, text="-", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=1)
        self.start_month_combo = ttk.Combobox(
            start_frame, textvariable=self.start_month_var,
            values=list(range(1, 13)), width=2, state="readonly"
        )
        self.start_month_combo.pack(side=tk.LEFT)
        tk.Label(start_frame, text="-", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=1)
        self.start_day_combo = ttk.Combobox(
            start_frame, textvariable=self.start_day_var,
            values=list(range(1, 32)), width=2, state="readonly"
        )
        self.start_day_combo.pack(side=tk.LEFT)
        self.start_year_combo.bind('<<ComboboxSelected>>',
                                   lambda event: self._refresh_date_days('start'))
        self.start_month_combo.bind('<<ComboboxSelected>>',
                                    lambda event: self._refresh_date_days('start'))

        # 开始日期日历按钮
        start_cal_btn = tk.Button(start_frame, text="📅",
                                 font=('Arial', 10), bg='white', fg='#165DFF',
                                 bd=0, cursor='hand2', relief='flat',
                                 command=lambda: self._show_calendar('start'))
        start_cal_btn.pack(side=tk.LEFT, padx=(4, 0))
        Tooltip(start_cal_btn, "点击选择开始日期")

        tk.Label(date_inner, text=" 至 ", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=3)

        end_frame = tk.Frame(date_inner, bg='white')
        end_frame.pack(side=tk.LEFT)

        self.end_year_combo = ttk.Combobox(
            end_frame, textvariable=self.end_year_var,
            values=list(range(2020, current_year + 1)), width=4, state="readonly"
        )
        self.end_year_combo.pack(side=tk.LEFT)
        tk.Label(end_frame, text="-", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=1)
        self.end_month_combo = ttk.Combobox(
            end_frame, textvariable=self.end_month_var,
            values=list(range(1, 13)), width=2, state="readonly"
        )
        self.end_month_combo.pack(side=tk.LEFT)
        tk.Label(end_frame, text="-", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=1)
        self.end_day_combo = ttk.Combobox(
            end_frame, textvariable=self.end_day_var,
            values=list(range(1, 32)), width=2, state="readonly"
        )
        self.end_day_combo.pack(side=tk.LEFT)
        self.end_year_combo.bind('<<ComboboxSelected>>',
                                 lambda event: self._refresh_date_days('end'))
        self.end_month_combo.bind('<<ComboboxSelected>>',
                                  lambda event: self._refresh_date_days('end'))
        self._refresh_date_days('start')
        self._refresh_date_days('end')

        # 结束日期日历按钮
        end_cal_btn = tk.Button(end_frame, text="📅",
                               font=('Arial', 10), bg='white', fg='#165DFF',
                               bd=0, cursor='hand2', relief='flat',
                               command=lambda: self._show_calendar('end'))
        end_cal_btn.pack(side=tk.LEFT, padx=(4, 0))
        Tooltip(end_cal_btn, "点击选择结束日期")

        # 第三行：字段获取方式
        field_mode_row = tk.Frame(body, bg='white')
        field_mode_row.pack(fill=tk.X, pady=(0, 6))

        field_mode_frame = tk.Frame(field_mode_row, bg='white')
        field_mode_frame.pack(side=tk.LEFT, padx=(0, 15))
        tk.Label(field_mode_frame, text="字段获取方式", font=('Microsoft YaHei UI', 8),
                bg='white', fg='#5f6368').pack(anchor='w')

        field_mode_inner = tk.Frame(field_mode_frame, bg='white')
        field_mode_inner.pack(pady=(2, 0))

        self.field_mode_var = tk.StringVar(value='hardcode')
        hardcode_rb = tk.Radiobutton(field_mode_inner, text="硬编码",
                                     variable=self.field_mode_var, value='hardcode',
                                     font=('Microsoft YaHei UI', 8, 'bold'),
                                     bg='white', fg='#202124',
                                     activebackground='white',
                                     cursor='hand2',
                                     command=self._on_field_mode_changed)
        hardcode_rb.pack(side=tk.LEFT, padx=(0, 10))

        dynamic_rb = tk.Radiobutton(field_mode_inner, text="动态获取",
                                   variable=self.field_mode_var, value='dynamic',
                                   font=('Microsoft YaHei UI', 8, 'bold'),
                                   bg='white', fg='#202124',
                                   activebackground='white',
                                   cursor='hand2',
                                   command=self._on_field_mode_changed)
        dynamic_rb.pack(side=tk.LEFT)

        # 配置来源已固定为硬编码模式（YAML配置已禁用）
        self.config_source_var = tk.StringVar(value='old')

        # 第三行：多日模式选项（在日期范围下方，按钮上方）
        mode_row = tk.Frame(body, bg='white')
        mode_row.pack(fill=tk.X, pady=(0, 6))

        mode_frame = tk.Frame(mode_row, bg='white')
        mode_frame.pack(side=tk.LEFT, padx=(0, 0))

        self.multi_day_var = tk.BooleanVar(value=False)
        multi_day_cb = tk.Checkbutton(mode_frame, text="按日查询",
                                      variable=self.multi_day_var,
                                      font=('Microsoft YaHei UI', 8),
                                      bg='white', fg='#202124',
                                      selectcolor='#e8f0fe',
                                      activebackground='white',
                                      command=self._on_multi_day_toggle)
        multi_day_cb.pack(side=tk.LEFT)

        self.multi_day_per_sheet_var = tk.BooleanVar(value=False)
        multi_day_per_sheet_cb = tk.Checkbutton(mode_frame, text="按日分Sheet",
                                               variable=self.multi_day_per_sheet_var,
                                               font=('Microsoft YaHei UI', 8),
                                               bg='white', fg='#202124',
                                               selectcolor='#e8f0fe',
                                               activebackground='white',
                                               state=tk.DISABLED,
                                               command=self._on_multi_day_per_sheet_toggle)
        self.multi_day_per_sheet_cb = multi_day_per_sheet_cb
        multi_day_per_sheet_cb.pack(side=tk.LEFT, padx=(6, 0))

        self.multi_day_per_city_var = tk.BooleanVar(value=False)
        multi_day_per_city_cb = tk.Checkbutton(mode_frame, text="按日+按地市导出",
                                              variable=self.multi_day_per_city_var,
                                              font=('Microsoft YaHei UI', 8),
                                              bg='white', fg='#202124',
                                              selectcolor='#e8f0fe',
                                              activebackground='white',
                                              state=tk.DISABLED,
                                              command=self._on_multi_day_per_city_toggle)
        self.multi_day_per_city_cb = multi_day_per_city_cb
        multi_day_per_city_cb.pack(side=tk.LEFT, padx=(6, 0))

        self.single_city_parallel_var = tk.BooleanVar(value=False)
        single_city_parallel_cb = tk.Checkbutton(mode_frame, text="单地市多线程",
                                                variable=self.single_city_parallel_var,
                                                font=('Microsoft YaHei UI', 8),
                                                bg='white', fg='#202124',
                                                selectcolor='#e8f0fe',
                                                activebackground='white',
                                                command=self._on_single_city_parallel_toggle)
        self.single_city_parallel_cb = single_city_parallel_cb
        single_city_parallel_cb.pack(side=tk.LEFT, padx=(6, 0))

        # 第四行：操作按钮
        btn_row = tk.Frame(body, bg='white')
        btn_row.pack(fill=tk.X, pady=(4, 0))

        self.extract_btn = tk.Button(btn_row, text="▶ 开始提取",
                               font=('Microsoft YaHei UI', 10, 'bold'),
                               bg='#165DFF', fg='white', bd=1,
                               cursor='arrow', relief='raised', padx=22, pady=5,
                               state=tk.DISABLED, command=self._on_query)
        self.extract_btn.pack(side=tk.LEFT)

        self.stop_btn = tk.Button(btn_row, text="⏹ 停止",
                            font=('Microsoft YaHei UI', 9),
                            bg='#dc3545', fg='white', bd=1,
                            cursor='arrow', relief='raised', padx=14, pady=5,
                            state=tk.DISABLED, command=self._on_stop)
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(btn_row, text="📁 打开目录",
                 font=('Microsoft YaHei UI', 9),
                 bg='#f0f2f5', fg='#202124', bd=1,
                 cursor='arrow', relief='raised', padx=12, pady=5,
                 command=self.open_output_dir).pack(side=tk.RIGHT)

        # 周选择器容器（用于合成45G流量表时显示）
        self.week_selector_container = tk.Frame(body, bg='white')
        self.week_selector_container.pack(fill=tk.X, pady=(8, 0))
        self.week_selector_container.pack_forget()  # 默认隐藏

        from gui.widgets import WeekSelector
        self.week_selector = WeekSelector(self.week_selector_container)
        self.week_selector.pack(fill=tk.X)

    def _build_bottom_section(self, parent):
        """构建底部日志区域"""
        # 直接使用 Frame 作为容器，填满所有剩余空间
        bottom = tk.Frame(parent, bg='white')
        bottom.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        progress_area = tk.Frame(bottom, bg='white')
        progress_area.pack(fill=tk.X, padx=16, pady=(10, 6))

        progress_info = tk.Frame(progress_area, bg='white')
        progress_info.pack(fill=tk.X)

        self.progress_lbl_pct = tk.Label(progress_info, text="进度: 0%",
                          font=('Microsoft YaHei UI', 10, 'bold'),
                          bg='white', fg='#165DFF')
        self.progress_lbl_pct.pack(side=tk.LEFT)

        self.progress_lbl_detail = tk.Label(progress_info, text="就绪",
                             font=('Microsoft YaHei UI', 9),
                             bg='white', fg='#5f6368')
        self.progress_lbl_detail.pack(side=tk.RIGHT)

        # 预估剩余时间标签
        self.progress_lbl_eta = tk.Label(progress_info, text="",
                             font=('Microsoft YaHei UI', 9),
                             bg='white', fg='#6b7280')
        self.progress_lbl_eta.pack(side=tk.RIGHT, padx=(0, 10))

        # 圆角进度条
        self.progress_canvas = tk.Canvas(progress_area, height=8, bg='white', highlightthickness=0)
        self.progress_canvas.pack(fill=tk.X, pady=(6, 0))
        self.progress_bar = self.progress_canvas.create_rectangle(0, 0, 0, 8, fill='#165DFF', outline='')
        self.progress_bg = self.progress_canvas.create_rectangle(0, 0, 1000, 8, fill='#f0f2f5', outline='')
        self.progress_canvas_width = 0  # 动态获取

        # 日志输出
        log_area = tk.Frame(bottom, bg='white')
        log_area.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        self.log_text = scrolledtext.ScrolledText(log_area, height=15,
                                                  font=('Consolas', 9),
                                                  state='disabled',
                                                  bg='#f8f9fa',
                                                  relief='flat',
                                                  bd=1)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 添加日志处理器（根据配置控制详细程度）
        handler = LogTextHandler(self.log_text)
        handler.setLevel(logging.DEBUG if LOGGING_DETAILED else logging.INFO)
        self.logger.addHandler(handler)

    def _update_license_display(self):
        """更新授权时间显示"""
        if self.expiry_time:
            try:
                # 解析过期时间
                display_time = self.expiry_time.strftime("%Y-%m-%d")
                
                # 计算剩余天数
                current_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                days_left = (self.expiry_time - current_dt).days
                
                if days_left < 0:
                    self.license_label.config(text="授权已过期", fg='#fce8e6')
                elif days_left <= 7:
                    self.license_label.config(text=f"授权到期: {display_time} (剩{days_left}天)", fg='#fce8e6')
                elif days_left <= 30:
                    self.license_label.config(text=f"授权到期: {display_time} (剩{days_left}天)", fg='#fff3e0')
                else:
                    self.license_label.config(text=f"授权到期: {display_time}", fg='#e8f5e9')
            except Exception:
                self.license_label.config(text="", fg='#e8f5e9')

    def _bind_events(self):
        """绑定事件和快捷键"""
        # 绑定快捷键
        self.root.bind('<Control-l>', lambda e: self._on_login())
        self.root.bind('<Control-L>', lambda e: self._on_login())
        self.root.bind('<Control-s>', lambda e: self._on_start_export())
        self.root.bind('<Control-S>', lambda e: self._on_start_export())
        self.root.bind('<Escape>', lambda e: self._on_cancel_query() if self.is_querying else None)

        # F1 帮助
        self.root.bind('<F1>', lambda e: self._show_help())

        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # 绑定表格选择事件
        self.table_dropdown.entry.bind('<KeyRelease>', self._on_table_dropdown_change)
        self.table_dropdown.entry.bind('<ButtonRelease-1>', self._on_table_dropdown_change)

    def _on_table_dropdown_change(self, event=None):
        """表格下拉框内容变化时触发"""
        # 使用 after 方法延迟执行，避免过早触发
        self.root.after(100, self._check_synthesize_mode)

    def _check_synthesize_mode(self):
        """检查是否切换到合成45G流量表模式"""
        selected = self.table_dropdown.get_selected()

        # 检查是否选中了合成45G流量表
        is_synthesize = '合成45G流量表' in selected

        if is_synthesize:
            # 显示周选择器，隐藏日期选择器
            self.week_selector_container.pack(fill=tk.X, pady=(8, 0))
            # 可以考虑隐藏日期区域，但暂时保留
        else:
            # 隐藏周选择器
            self.week_selector_container.pack_forget()

    def _show_help(self):
        """显示帮助信息"""
        help_text = """
NQI工具 - 快捷键帮助
═══════════════════════════════

Ctrl+L    - 执行登录
Ctrl+S    - 开始导出
Escape    - 取消当前查询
F1        - 显示此帮助

状态说明:
  ● 绿色  - 登录成功
  ● 黄色  - 登录中
  ● 红色  - 登录失败

提示: 点击日期框旁边的日历图标可快速选择日期
        """
        from tkinter import messagebox
        messagebox.showinfo("快捷键帮助", help_text.strip())

    def _on_start_export(self):
        """Ctrl+S 快捷键触发查询。"""
        self._on_query()

    def _on_cancel_query(self):
        """取消查询（快捷键触发）"""
        if self.is_querying and hasattr(self, 'jxcx') and self.jxcx:
            self.jxcx.cancel_query()
            self.log("已发送取消请求...", "WARNING")

    def _update_login_failed_ui(self):
        """批量更新登录失败UI"""
        self.status_text.config(text="登录失败")
        self.status_dot.config(fg='#ef4444')
        self.login_status_icon.config(text="○", fg='#ef4444')
        self.login_status_lbl.config(text="登录失败", fg='#ef4444')

    def _update_login_error_ui(self, message):
        """批量更新登录异常UI"""
        self.status_text.config(text="登录异常")
        self.status_dot.config(fg='#ef4444')
        self.login_status_icon.config(text="○", fg='#ef4444')
        self.login_status_lbl.config(text="登录异常", fg='#ef4444')
        self.log(f"登录异常: {message}", "ERROR")

    def _on_category_changed(self, category):
        """数据分类选择事件"""
        self.log(f"选择了数据分类: {category}", "INFO")

    def _select_all_categories(self):
        """全选所有数据分类"""
        for var in self.category_vars.values():
            var.set(1)
        self.log("已全选所有数据分类", "INFO")

    def _deselect_all_categories(self):
        """取消全选所有数据分类"""
        for var in self.category_vars.values():
            var.set(0)
        self.log("已取消全选", "INFO")

    def _on_multi_day_toggle(self):
        """按日查询切换事件"""
        if self.multi_day_var.get():
            self.multi_day_per_sheet_cb.config(state=tk.NORMAL)
            self.multi_day_per_city_cb.config(state=tk.NORMAL)
            self.single_city_parallel_var.set(False)
            self.single_city_parallel_cb.config(state=tk.DISABLED)
        else:
            self.multi_day_per_sheet_var.set(False)
            self.multi_day_per_sheet_cb.config(state=tk.DISABLED)
            self.multi_day_per_city_var.set(False)
            self.multi_day_per_city_cb.config(state=tk.DISABLED)
            self.single_city_parallel_cb.config(state=tk.NORMAL)

    def _on_multi_day_per_sheet_toggle(self):
        """按日分Sheet切换事件"""
        if self.multi_day_per_sheet_var.get():
            # 按日分Sheet 与 按日+按地市导出 互斥
            self.multi_day_per_city_var.set(False)
            self.log("已切换为按日分Sheet模式", "INFO")

    def _on_multi_day_per_city_toggle(self):
        """按日+按地市导出切换事件"""
        if self.multi_day_per_city_var.get():
            # 按日+按地市 与 按日分Sheet 互斥
            self.multi_day_per_sheet_var.set(False)
            self.log("已切换为按日+按地市导出模式", "INFO")

    def _on_single_city_parallel_toggle(self):
        """单地市多线程切换事件"""
        if self.single_city_parallel_var.get():
            self.log("已启用单地市多线程模式", "INFO")

    def _on_custom_fields_toggle(self):
        """自定义字段切换事件"""
        if self.custom_fields_var.get():
            self.select_fields_btn.config(state=tk.NORMAL)
        else:
            self.select_fields_btn.config(state=tk.DISABLED)

    def _on_table_selection_changed(self, selected_tables):
        """表格选择变化事件"""
        # 检查是否选择了合成45G流量表
        if '合成45G流量表' in selected_tables:
            # 显示周选择器，隐藏日期选择器
            self.week_selector_container.pack(fill=tk.X, pady=(8, 0))
            self.date_row.pack_forget()  # 隐藏日期范围选择
        else:
            # 隐藏周选择器，显示日期选择器
            self.week_selector_container.pack_forget()
            self.date_row.pack(fill=tk.X, pady=(0, 6))  # 显示日期范围选择

    def _on_field_mode_changed(self):
        """字段获取方式切换事件"""
        mode = self.field_mode_var.get()
        mode_text = "硬编码" if mode == 'hardcode' else "动态获取"
        self.log(f"切换字段获取方式: {mode_text}", "INFO")

    def _on_config_source_changed(self):
        """配置来源切换事件 - 已禁用（YAML配置不可用）

        注意：YAML配置已确认存在过多问题被禁用，此方法保留但不再生效。
        """
        self.log("配置来源已固定为硬编码模式（YAML配置已禁用）", "WARNING")

    def _render_table_field_error(self, parent, table_name):
        """在字段选择窗口中渲染加载失败的提示"""
        frame = tk.Frame(parent, bg='white', bd=1, relief='solid')
        frame.pack(fill=tk.X, pady=5, padx=10)
        tk.Label(
            frame, text=table_name,
            font=('Microsoft YaHei UI', 10, 'bold'),
            bg='white', fg='#165DFF'
        ).pack(anchor='w', padx=5, pady=3)
        tk.Label(
            frame, text="（字段加载失败，请重试）",
            font=('Microsoft YaHei UI', 9),
            bg='#fef2f2', fg='#dc2626'
        ).pack(anchor='w', padx=5, pady=(0, 5))

    def _render_table_field_rows(self, parent, table_name, configs, field_vars):
        """在字段选择窗口中渲染一个表的字段复选框列表"""
        # 表格标题
        table_frame = tk.Frame(parent, bg='white', bd=1, relief='solid')
        table_frame.pack(fill=tk.X, pady=5, padx=10)
        tk.Label(
            table_frame, text=table_name,
            font=('Microsoft YaHei UI', 10, 'bold'),
            bg='white', fg='#165DFF'
        ).pack(anchor='w', padx=5, pady=3)

        # 字段选择
        fields_frame = tk.Frame(parent, bg='white')
        fields_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        # 按行排列，每行4个复选框
        row_frame = None
        for i, config in enumerate(configs):
            if i % 4 == 0:
                row_frame = tk.Frame(fields_frame, bg='white')
                row_frame.pack(fill=tk.X, pady=2)

            field_name = config.get('columnname_cn', config.get('columnname', ''))
            field_key = config.get('columnname', '')

            var = tk.BooleanVar(value=field_key in self.selected_fields.get(table_name, []))
            field_vars[(table_name, field_key)] = var

            tk.Checkbutton(
                row_frame, text=field_name,
                variable=var,
                font=('Microsoft YaHei UI', 9),
                bg='white', fg='#202124',
                selectcolor='#165DFF',
                activebackground='white',
                activeforeground='#165DFF',
                cursor='arrow'
            ).pack(side=tk.LEFT, padx=10, pady=1, fill=tk.X, expand=True)

    def _show_field_selector(self):
        """显示字段选择窗口（后台线程异步获取字段配置，避免阻塞UI）"""
        # 检查登录状态
        if not self.jxcx:
            messagebox.showwarning("警告", "请先登录后再选择字段")
            return

        selected_tables = self.table_dropdown.get_selected()
        if not selected_tables or not selected_tables[0]:
            messagebox.showwarning("警告", "请先选择数据表")
            return

        # 创建字段选择窗口
        field_window = tk.Toplevel(self.root)
        field_window.title("选择导出字段")
        field_window.geometry("600x400")
        field_window.resizable(True, True)

        # 设置窗口在主窗口中间
        self.root.update_idletasks()
        x = (self.root.winfo_width() - 600) // 2 + self.root.winfo_x()
        y = (self.root.winfo_height() - 400) // 2 + self.root.winfo_y()
        field_window.geometry(f"600x400+{x}+{y}")

        # 创建滚动区域
        canvas = tk.Canvas(field_window)
        scrollbar = ttk.Scrollbar(field_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 布局
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 加载提示
        loading_label = ttk.Label(
            scrollable_frame, text="正在加载字段配置...",
            font=('Microsoft YaHei UI', 10), foreground='#5f6368'
        )
        loading_label.pack(pady=20)

        # 全局字段状态（线程安全：仅通过 root.after 在主线程读写）
        field_vars = {}

        def _load_all_configs():
            """后台线程：批量获取所有表的字段配置"""
            results = {}
            for table_name in selected_tables:
                if table_name in self.field_configs:
                    results[table_name] = self.field_configs[table_name]
                    continue
                table_config = TableConfig.get_table_config(table_name)
                if not table_config:
                    results[table_name] = None
                    continue
                try:
                    configs = self.jxcx.get_field_config(
                        table_config['table_key'],
                        table_config['fieldtype'],
                        table_config['api_type'],
                        table_name=table_config.get('table_name')
                    )
                    results[table_name] = configs
                except Exception as e:
                    results[table_name] = {'__error__': str(e)}
            return results

        def _on_configs_loaded(results):
            """主线程：加载完成后渲染字段选择UI"""
            loading_label.destroy()
            for table_name in selected_tables:
                configs = results.get(table_name)
                if isinstance(configs, dict) and '__error__' in configs:
                    self.log(f"获取 {table_name} 字段配置异常: {configs['__error__']}", "ERROR")
                    self._render_table_field_error(scrollable_frame, table_name)
                    continue
                if configs:
                    self.field_configs[table_name] = configs
                    self.log(f"获取到 {table_name} 的 {len(configs)} 个字段", "SUCCESS")
                    self._render_table_field_rows(
                        scrollable_frame, table_name, configs, field_vars
                    )
                else:
                    self.log(f"获取 {table_name} 的字段配置失败，可能该报表不支持自定义字段", "WARNING")
                    self._render_table_field_error(scrollable_frame, table_name)

        def _fetch_worker():
            results = _load_all_configs()
            self.root.after(0, lambda: _on_configs_loaded(results))

        threading.Thread(target=_fetch_worker, daemon=True).start()

        # 按钮区域
        btn_frame = tk.Frame(field_window, bg='white')
        btn_frame.pack(fill=tk.X, pady=10, padx=10)

        def on_ok():
            selected_fields = {}
            for (table_name, field_key), var in field_vars.items():
                if var.get():
                    selected_fields.setdefault(table_name, []).append(field_key)

            self.selected_fields.clear()
            self.selected_fields.update(selected_fields)
            total_fields = sum(len(fields) for fields in self.selected_fields.values())
            self.log(f"已选择 {total_fields} 个字段", "INFO")
            field_window.destroy()

        def on_cancel():
            field_window.destroy()

        ttk.Button(btn_frame, text="确定", command=on_ok, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel, width=10).pack(side=tk.RIGHT, padx=5)

    def _refresh_date_days(self, date_type):
        """按年月刷新日期下拉框，只保留当月实际存在的日期。"""
        if date_type == 'start':
            year_var, month_var, day_var = (
                self.start_year_var, self.start_month_var, self.start_day_var
            )
            day_combo = self.start_day_combo
        else:
            year_var, month_var, day_var = (
                self.end_year_var, self.end_month_var, self.end_day_var
            )
            day_combo = self.end_day_combo

        try:
            valid_days = _get_month_days(year_var.get(), month_var.get())
        except (TypeError, ValueError):
            return

        day_combo['values'] = valid_days
        if day_var.get() > valid_days[-1]:
            day_var.set(valid_days[-1])

    def set_quick_date(self, days):
        """设置快捷日期"""
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=days-1)

        self.start_year_var.set(start_date.year)
        self.start_month_var.set(start_date.month)
        self.start_day_var.set(start_date.day)
        self._refresh_date_days('start')

        self.end_year_var.set(end_date.year)
        self.end_month_var.set(end_date.month)
        self.end_day_var.set(end_date.day)
        self._refresh_date_days('end')

        self.log(f"设置快捷日期: 近{days}天", "INFO")

    def _show_calendar(self, date_type):
        """显示日历选择对话框

        Args:
            date_type: 'start' 或 'end'，表示开始或结束日期
        """
        # 获取当前选中的日期
        if date_type == 'start':
            year = self.start_year_var.get()
            month = self.start_month_var.get()
            day = self.start_day_var.get()
            initial_date = f"{year:04d}-{month:02d}-{day:02d}"
        else:
            year = self.end_year_var.get()
            month = self.end_month_var.get()
            day = self.end_day_var.get()
            initial_date = f"{year:04d}-{month:02d}-{day:02d}"

        # 显示日历对话框
        dialog = CalendarDialog(self.root, initial_date=initial_date)
        selected_date = dialog.show()

        if selected_date:
            # 解析日期
            parts = selected_date.split('-')
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

            # 更新变量
            if date_type == 'start':
                self.start_year_var.set(year)
                self.start_month_var.set(month)
                self.start_day_var.set(day)
                self._refresh_date_days('start')
                self.log(f"选择开始日期: {selected_date}", "INFO")
            else:
                self.end_year_var.set(year)
                self.end_month_var.set(month)
                self.end_day_var.set(day)
                self._refresh_date_days('end')
                self.log(f"选择结束日期: {selected_date}", "INFO")

    def update_progress(self, current, total, detail=""):
        """更新进度条显示

        Args:
            current: 当前进度（0-100）
            total: 总数（用于计算百分比）
            detail: 详细描述文字
        """
        if total > 0:
            pct = int(current / total * 100)
        else:
            pct = 0

        # 计算预估剩余时间
        eta_text = self._calculate_eta(current, total, pct)
        self.root.after(0, lambda: self._update_progress_ui(pct, detail, eta_text))

    def _calculate_eta(self, current, total, pct):
        """计算预估剩余时间

        Returns:
            str: 预估剩余时间文本
        """
        from datetime import datetime

        if pct <= 0:
            self._progress_start_time = datetime.now()
            self._progress_last_update = datetime.now()
            self._progress_last_value = 0
            self._total_expected = total
            return ""

        now = datetime.now()

        if self._progress_start_time is None:
            self._progress_start_time = now
            self._progress_last_update = now
            self._progress_last_value = 0
            return ""

        # 计算进度变化率
        elapsed = (now - self._progress_start_time).total_seconds()
        progress_delta = pct - self._progress_last_value

        if progress_delta > 0 and elapsed > 5:
            # 估算剩余时间
            remaining_pct = 100 - pct
            eta_seconds = (remaining_pct / progress_delta) * elapsed
            self._progress_last_update = now
            self._progress_last_value = pct

            # 格式化时间
            if eta_seconds < 60:
                eta_text = f"剩余约 {int(eta_seconds)} 秒"
            elif eta_seconds < 3600:
                minutes = int(eta_seconds / 60)
                seconds = int(eta_seconds % 60)
                eta_text = f"剩余约 {minutes}分{seconds}秒"
            else:
                hours = int(eta_seconds / 3600)
                minutes = int((eta_seconds % 3600) / 60)
                eta_text = f"剩余约 {hours}小时{minutes}分"

            return eta_text

        self._progress_last_update = now
        self._progress_last_value = pct
        return ""

    def _update_progress_ui(self, pct, detail="", eta_text=""):
        """在主线程中更新进度条UI"""
        self.progress_lbl_pct.config(text=f"进度: {pct}%")
        if detail:
            self.progress_lbl_detail.config(text=detail)
        if eta_text:
            self.progress_lbl_eta.config(text=eta_text)

        self.progress_canvas.update_idletasks()
        canvas_width = self.progress_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 1000

        bar_width = int(canvas_width * pct / 100)
        self.progress_canvas.coords(self.progress_bar, 0, 0, bar_width, 8)

    def reset_progress(self):
        """重置进度条"""
        self.root.after(0, lambda: self._reset_progress_ui())

    def _reset_progress_ui(self):
        """在主线程中重置进度条UI"""
        self.progress_lbl_pct.config(text="进度: 0%")
        self.progress_lbl_detail.config(text="就绪")
        self.progress_lbl_eta.config(text="")
        self.progress_canvas.coords(self.progress_bar, 0, 0, 0, 8)
        # 重置预估时间相关变量
        self._progress_start_time = None
        self._progress_last_update = None
        self._progress_last_value = 0
        self._total_expected = 0

    def open_output_dir(self):
        """打开输出目录（跨平台）"""
        output_dir = OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        import subprocess
        import sys

        try:
            if sys.platform == 'win32':
                os.startfile(output_dir)
            elif sys.platform == 'darwin':
                subprocess.run(['open', output_dir], check=True)
            else:
                # Linux / other Unix
                subprocess.run(['xdg-open', output_dir], check=True)
            self.log(f"已打开输出目录: {output_dir}", "INFO")
        except Exception as e:
            self.log(f"打开输出目录失败: {e}", "ERROR")

    def _on_login(self):
        """登录按钮点击事件"""
        self.log("开始登录...", "INFO")
        self.status_text.config(text="登录中...")
        self.status_dot.config(fg='#fbbf24')  # 黄色
        thread = threading.Thread(target=self._login_worker)
        thread.daemon = True
        thread.start()

    def _login_worker(self):
        """登录工作线程"""
        try:
            username = self.username_entry.get().strip()
            password = self.password_entry.get().strip()
            login_mgr = LoginManager(username=username, password=password, parent=self.root)
            if login_mgr.login():
                self.session = login_mgr.sess
                self.jxcx = JXCXQuery(self.session)
                self._query_worker_inst = None
                self.root.after(0, self._on_login_success)
            else:
                self.root.after(0, self._update_login_failed_ui)
                self.root.after(0, lambda: self.log("登录失败", "ERROR"))
        except Exception as e:
            self.root.after(0, lambda msg=str(e): self._update_login_error_ui(msg))

    def _on_login_success(self):
        """登录成功回调"""
        self.log("登录成功！", "SUCCESS")
        self.extract_btn.config(state=tk.NORMAL)
        self.login_btn.config(state=tk.DISABLED, text="已登录")
        self.status_text.config(text="已登录")
        self.status_dot.config(fg='#22c55e')  # 绿色
        self.login_status_icon.config(text="●", fg='#22c55e')
        self.login_status_lbl.config(text="已登录", fg='#22c55e')

    def _on_query(self):
        """查询按钮点击事件"""
        if self.is_querying:
            self.log("正在查询中，请稍候...", "WARNING")
            return

        selected_tables = self.table_dropdown.get_selected()
        if not selected_tables:
            messagebox.showwarning("警告", "请选择要查询的数据表")
            return

        # 检查是否选择了合成45G流量表
        if '合成45G流量表' in selected_tables:
            if len(selected_tables) > 1:
                messagebox.showwarning("警告", "合成45G流量表必须单独选择，不能与其他表同时选择")
                return
            # 启动合成45G流量表流程
            self._on_synthesize_45g()
            return

        # 获取日期范围
        start_date = f"{self.start_year_var.get()}-{self.start_month_var.get():02d}-{self.start_day_var.get():02d}"
        end_date = f"{self.end_year_var.get()}-{self.end_month_var.get():02d}-{self.end_day_var.get():02d}"
        try:
            _parse_date_range(start_date, end_date)
        except ValueError as exc:
            messagebox.showwarning("日期无效", str(exc))
            return
        
        # 获取选中的地市
        selected_cities = self.city_dropdown.get_selected()
        city = ",".join(selected_cities) if selected_cities else ""

        self.is_querying = True
        self.extract_btn.config(state=tk.DISABLED, text="查询中...")
        self.stop_btn.config(state=tk.NORMAL)
        self.status_text.config(text="查询中...")
        self.status_dot.config(fg='#fbbf24')  # 黄色

        # 重置进度条
        self.reset_progress()
        self.update_progress(0, len(selected_tables), "开始查询...")

        self.log(f"开始查询: {', '.join(selected_tables)}", "INFO")
        self.log(f"日期范围: {start_date} 至 {end_date}", "INFO")
        if city:
            self.log(f"地市: {city}", "INFO")

        self.query_thread = threading.Thread(target=self._query_worker,
                                            args=(selected_tables, start_date, end_date, city))
        self.query_thread.daemon = True
        self.query_thread.start()

    def _on_synthesize_45g(self):
        """合成45G流量表入口"""
        # 检查是否已登录
        if not self.session or not self.jxcx:
            messagebox.showwarning("警告", "请先登录")
            return

        # 获取周选择器中的日期范围
        week_start = self.week_selector.get_week_start()
        if not week_start:
            messagebox.showwarning("警告", "请选择周")
            return

        # 获取选中的地市
        selected_cities = self.city_dropdown.get_selected()
        city = ",".join(selected_cities) if selected_cities else ""

        self.is_querying = True
        self.extract_btn.config(state=tk.DISABLED, text="合成中...")
        self.stop_btn.config(state=tk.NORMAL)
        self.status_text.config(text="合成中...")
        self.status_dot.config(fg='#fbbf24')  # 黄色

        # 重置进度条
        self.reset_progress()

        start_date, end_date = self.week_selector.get_date_range()
        self.log("=" * 60, "INFO")
        self.log("开始合成45G流量表", "INFO")
        self.log(f"周范围: {start_date} 至 {end_date}", "INFO")
        self.log(f"地市: {city if city else '全部'}", "INFO")
        self.log("=" * 60, "INFO")

        # 启动合成线程
        self.query_thread = threading.Thread(
            target=self._synthesize_worker,
            args=(week_start, city)
        )
        self.query_thread.daemon = True
        self.query_thread.start()

    def _synthesize_worker(self, week_start, city):
        """合成45G流量表工作线程"""
        try:
            from core.flow_table_builder import synthesize_45g_flow_table

            # 创建进度回调函数
            def progress_callback(message):
                self.root.after(0, lambda m=message: self.log(m, "INFO"))

            # 执行合成
            success = synthesize_45g_flow_table(
                self.session,
                city,
                week_start,
                progress_callback
            )

            self.root.after(0, lambda s=success: self._on_synthesize_complete(s))

        except Exception as e:
            import traceback
            error_text = traceback.format_exc()
            self.root.after(0, lambda e=error_text: self.log(e, "ERROR"))
            self.root.after(0, lambda: self._on_synthesize_complete(False))

    def _on_synthesize_complete(self, success):
        """合成完成回调"""
        self.is_querying = False
        self.extract_btn.config(state=tk.NORMAL, text="▶ 开始提取")
        self.stop_btn.config(state=tk.DISABLED)
        self.status_text.config(text="就绪")
        self.status_dot.config(fg='#a5b4fc')

        if success:
            self.log("=" * 60, "INFO")
            self.log("45G流量表合成完成！", "SUCCESS")
            self.log("=" * 60, "INFO")
            messagebox.showinfo("完成", "45G流量表合成完成！\n请查看输出目录。")
        else:
            self.log("45G流量表合成失败", "ERROR")
            messagebox.showerror("错误", "45G流量表合成失败，请查看日志。")

    def _on_stop(self):
        """停止查询"""
        self.log("正在停止查询...", "WARNING")
        # 调用查询模块的取消方法
        if hasattr(self, 'jxcx') and self.jxcx:
            self.jxcx.cancel_query()
        # 标记查询状态为已取消
        self.is_querying = False
        self.log("已发送取消请求，请等待当前批次完成...", "WARNING")

    def _query_worker(self, table_names, start_date, end_date, city):
        """查询工作线程（委托给 QueryWorker）"""
        self.jxcx.reset_cancel_flag()
        w = self._get_query_worker()
        w.query_worker(
            table_names, start_date, end_date, city,
            on_complete=self._on_query_complete,
            on_failed=self._on_query_failed
        )

    def _get_query_worker(self):
        """获取或创建 QueryWorker 实例"""
        worker = getattr(self, '_query_worker_inst', None)
        if worker is None or worker.session is not self.session or worker.jxcx is not self.jxcx:
            worker = QueryWorker(
                session=self.session,
                jxcx=self.jxcx,
                log_func=self.log,
                progress_func=self.update_progress,
                after_func=self.root.after,
                field_mode_var=getattr(self, 'field_mode_var', None),
                custom_fields_var=getattr(self, 'custom_fields_var', None),
                selected_fields=dict(getattr(self, 'selected_fields', {})),
                multi_day_var=getattr(self, 'multi_day_var', None),
                multi_day_per_sheet_var=getattr(self, 'multi_day_per_sheet_var', None),
                multi_day_per_city_var=getattr(self, 'multi_day_per_city_var', None),
                single_city_parallel_var=getattr(self, 'single_city_parallel_var', None),
            )
            self._query_worker_inst = worker
        else:
            worker.selected_fields = dict(getattr(self, 'selected_fields', {}))
        return worker

    def _apply_custom_fields(self, df, table_name):
        """应用自定义字段选择（委托给 QueryWorker）"""
        return self._get_query_worker().apply_custom_fields(df, table_name)

    def _query_tables_parallel(self, table_names, start_date, end_date, city):
        """单地市多表并行查询（委托给 QueryWorker）"""
        self._get_query_worker().query_tables_parallel(table_names, start_date, end_date, city)

    def _export_multi_sheet(self, filename, sheets_data, default_sheet):
        """导出多Sheet的Excel文件（委托给 QueryWorker）"""
        self._get_query_worker().export_multi_sheet(filename, sheets_data, default_sheet)

    def _query_4g_voice_table(self, table_config, start_date, end_date, city,
                               multi_day, multi_day_per_sheet, multi_day_per_city):
        """查询4G语音小区报表（委托给 QueryWorker）"""
        self._get_query_worker().query_4g_voice_table(
            table_config, start_date, end_date, city,
            multi_day, multi_day_per_sheet, multi_day_per_city
        )

    def _on_query_complete(self):
        """查询完成回调"""
        self.is_querying = False
        self.extract_btn.config(state=tk.NORMAL, text="▶ 开始提取")
        self.stop_btn.config(state=tk.DISABLED)
        self.status_text.config(text="查询完成")
        self.status_dot.config(fg='#22c55e')  # 绿色
        self.update_progress(100, 100, "查询完成")
        self.log("所有查询完成！", "SUCCESS")

    def _on_query_failed(self):
        """查询失败回调"""
        self.is_querying = False
        self.extract_btn.config(state=tk.NORMAL, text="▶ 开始提取")
        self.stop_btn.config(state=tk.DISABLED)
        self.status_text.config(text="查询失败")
        self.status_dot.config(fg='#ef4444')  # 红色
        self.reset_progress()

    def log(self, message, level="INFO"):
        """输出日志（线程安全，非主线程时自动通过 root.after 调度）"""
        # 检查是否在主线程中
        try:
            is_main = threading.current_thread() is threading.main_thread()
        except AttributeError:
            is_main = True

        if not is_main:
            # 非主线程：通过 root.after 调度到主线程执行
            self.root.after(0, self._do_log, message, level)
            return

        self._do_log(message, level)

    def _do_log(self, message, level="INFO"):
        """实际的日志写入操作（必须在主线程中调用）"""
        # 防御性检查：组件未创建时跳过（如 __init__ 早期调用 log()）
        log_text = getattr(self, 'log_text', None)
        if log_text is None or not log_text.winfo_exists():
            return

        log_text.config(state='normal')

        tag_map = {
            'INFO': 'INFO',
            'ERROR': 'ERROR',
            'WARNING': 'WARNING',
            'SUCCESS': 'SUCCESS'
        }

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"

        log_text.insert(tk.END, log_line, (tag_map.get(level, 'INFO'),))
        log_text.see(tk.END)
        log_text.config(state='disabled')

    def load_config(self):
        """加载配置"""
        # 配置来源已固定为硬编码模式（YAML配置已禁用）
        self.log("NQI工具已就绪", "INFO")
        self.log(f"支持的数据表: {', '.join(TableConfig.get_table_names())}", "INFO")
        self.log(f"配置共 {len(TableConfig.TABLE_CONFIGS)} 个表格（全部使用硬编码配置）", "INFO")

    def run(self):
        """运行应用"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _on_closing(self):
        """窗口关闭事件"""
        self.root.destroy()

    def _copy_to_clipboard(self, window, text):
        """复制到剪贴板"""
        window.clipboard_clear()
        window.clipboard_append(text)
        messagebox.showinfo("成功", "已复制到剪贴板")
