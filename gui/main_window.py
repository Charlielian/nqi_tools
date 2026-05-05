# -*- coding: utf-8 -*-
"""
主窗口模块
提供应用程序的主界面 - 现代化设计
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import os
from datetime import datetime, timedelta
import queue

from gui.widgets import LogTextHandler, TableConfig, MultiSelectDropdown
from core.auth import LoginManager
from core.query import JXCXQuery
from core.export import export_with_format
from core.license import TimeMonitor, invalidate_license, verify_serial_number, write_license_from_serial
from utils.logger import set_log_file, ensure_dirs
from utils.config import LOG_DIR, EXPIRY_DATE, DEFAULT_USERNAME, DEFAULT_PASSWORD


class NavButton:
    """导航按钮类"""
    def __init__(self, parent, icon, tooltip, nav_id, selected=False):
        self.frame = tk.Frame(parent, bg='#252538' if selected else '#1a1a2e',
                             cursor='hand2', width=54, height=54)
        self.icon_label = tk.Label(self.frame, text=icon,
                                 font=('Segoe UI Emoji', 18),
                                 bg='#252538' if selected else '#1a1a2e',
                                 fg='white')
        self.icon_label.pack(pady=8)
        self.selected = selected
        self.nav_id = nav_id
        self.tooltip = tooltip

        # 绑定事件
        self.frame.bind('<Button-1>', lambda e: self._on_click())
        self.frame.bind('<Enter>', lambda e: self._on_enter())
        self.frame.bind('<Leave>', lambda e: self._on_leave())

    def _on_click(self):
        if self.frame.winfo_exists():
            self.frame.event_generate('<<NavClick>>', when='head')

    def _on_enter(self):
        if not self.selected and self.frame.winfo_exists():
            self.frame.config(bg='#303050')
            self.icon_label.config(bg='#303050')

    def _on_leave(self):
        if not self.selected and self.frame.winfo_exists():
            self.frame.config(bg='#1a1a2e')
            self.icon_label.config(bg='#1a1a2e')

    def set_selected(self, selected):
        self.selected = selected
        if self.frame.winfo_exists():
            if selected:
                self.frame.config(bg='#252538')
                self.icon_label.config(bg='#252538')
            else:
                self.frame.config(bg='#1a1a2e')
                self.icon_label.config(bg='#1a1a2e')


class NqiToolGUI:
    """NQI工具主窗口 - 现代化设计"""

    def __init__(self, root, expiry_time=None):
        self.root = root
        self.root.title("NQI工具")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # 配置全局 ttk 样式，解决 tkcalendar 白板问题
        try:
            style = ttk.Style()
            style.theme_use('clam')
            # 确保 Calendar 弹出窗口有正确的背景色
            style.configure('DateEntry.', background='white', fieldbackground='white')
            style.map('DateEntry.', fieldbackground=['readonly', 'white'])
        except:
            pass

        self.expiry_time = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d") if not expiry_time else expiry_time
        self.session = None
        self.jxcx = None
        self.query_thread = None
        self.is_querying = False
        self._stop_requested = False
        self.log_queue = queue.Queue()

        # 当前选中的侧边栏功能
        self.current_view = "home"
        self.nav_buttons = {}

        self._setup_logging()
        self._create_widgets()
        self._bind_events()

        # 启动时间监控（后台运行，检测时间回拨）
        self._time_monitor = TimeMonitor(interval=30, callback=self._on_time_rollback)
        self._time_monitor.start()

        self.logger.info("=" * 50)
        self.logger.info("NQI工具 GUI 启动")
        self.logger.info(f"日志文件: {self.log_file_path}")
        self.logger.info("=" * 50)

        self.load_config()

    def _setup_logging(self):
        """设置日志系统"""
        import logging
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
        except Exception as e:
            self.logger = logging.getLogger()
            self.logger.setLevel(logging.DEBUG)
            self.logger.warning(f"初始化日志文件失败: {e}，日志将仅输出到界面")

    def _create_widgets(self):
        """创建界面组件 - 现代化设计"""
        # 主容器（水平分割：侧边栏 + 内容区）
        self.main_container = tk.Frame(self.root, bg='#e9ecef')
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 左侧工具栏（深色）
        self._create_sidebar()

        # 右侧内容区
        self._create_content_area()

    def _create_sidebar(self):
        """创建左侧深色工具栏"""
        # 侧边栏容器
        self.sidebar = tk.Frame(self.main_container, bg='#1a1a2e', width=70)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # 顶部Logo区域
        logo_frame = tk.Frame(self.sidebar, bg='#1a1a2e', height=80)
        logo_frame.pack(fill=tk.X)
        logo_frame.pack_propagate(False)

        # Logo图标
        logo_icon = tk.Label(logo_frame, text="N",
                           font=('Arial', 24, 'bold'),
                           bg='#165DFF', fg='white',
                           width=3, height=1)
        logo_icon.pack(pady=15)

        # 分割线
        sep = tk.Frame(self.sidebar, bg='#2d2d44', height=1)
        sep.pack(fill=tk.X, padx=10)

        # 导航按钮区域
        nav_frame = tk.Frame(self.sidebar, bg='#1a1a2e')
        nav_frame.pack(fill=tk.Y, expand=False, pady=10)

        # 导航按钮配置
        nav_items = [
            {'icon': '🏠', 'id': 'home', 'tip': '首页'},
            {'icon': '📊', 'id': 'query', 'tip': '数据查询'},
            {'icon': '📁', 'id': 'export', 'tip': '导出管理'},
            {'icon': '⚙', 'id': 'settings', 'tip': '设置'},
            {'icon': 'ℹ', 'id': 'about', 'tip': '关于'},
        ]

        for i, item in enumerate(nav_items):
            btn = NavButton(nav_frame, item['icon'], item['tip'], item['id'], selected=(i == 0))
            btn.frame.pack(pady=3)
            # 绑定导航事件
            btn.frame.bind('<<NavClick>>', lambda e, bid=item['id']: self._on_nav_click(bid))
            self.nav_buttons[item['id']] = btn

        # 底部状态区域
        bottom_frame = tk.Frame(self.sidebar, bg='#1a1a2e', height=60)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_frame.pack_propagate(False)

        # 授权状态指示
        self.sidebar_status = tk.Label(bottom_frame, text="●",
                                      font=('Arial', 10),
                                      bg='#1a1a2e', fg='#22c55e')
        self.sidebar_status.pack(pady=5)

        # 激活按钮
        activate_btn = tk.Button(bottom_frame, text="激活",
                                font=('Microsoft YaHei UI', 8),
                                bg='#165DFF', fg='white', bd=0,
                                cursor='hand2', padx=15, pady=4,
                                command=self._show_activate_window)
        activate_btn.pack(pady=5)

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

    def _create_content_area(self):
        """创建右侧内容区域"""
        # 内容区容器
        self.content_area = tk.Frame(self.main_container, bg='#e9ecef')
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 内容页面容器
        self.content_pages = tk.Frame(self.content_area, bg='#e9ecef')
        self.content_pages.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 10))

        # 显示首页
        self._show_home_view()

    def _show_home_view(self):
        """显示首页视图"""
        # 清空并重建内容
        for widget in self.content_pages.winfo_children():
            widget.destroy()

        # 登录配置卡片（顶部）
        self._build_login_card_new()

        # 下半部分：使用grid布局实现左右分栏
        bottom_frame = tk.Frame(self.content_pages, bg='#e9ecef')
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        # 配置左右两列的权重比例（左侧30%，右侧70%）
        bottom_frame.grid_rowconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(0, weight=3)  # 左侧3份
        bottom_frame.grid_columnconfigure(1, weight=7)  # 右侧7份

        # 左侧区域：查询参数 + 提取参数
        left_frame = tk.Frame(bottom_frame, bg='#e9ecef')
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

        # 查询参数卡片
        self._build_query_card_new(left_frame)

        # 提取参数卡片
        self._build_params_card_new(left_frame)

        # 右侧区域：数据预览 + 日志
        right_frame = tk.Frame(bottom_frame, bg='#e9ecef')
        right_frame.grid(row=0, column=1, sticky='nsew')

        # 数据预览卡片
        self._build_preview_card(right_frame)

        # 日志卡片
        self._build_log_card(right_frame)

        # 底部进度条（占满宽度）
        self._build_progress_section()

    def _show_query_view(self):
        self._show_home_view()

    def _show_export_view(self):
        for widget in self.content_pages.winfo_children():
            widget.destroy()
        card = self._build_card_shadow(self.content_pages, "📁 导出管理", "📁")
        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        toolbar = tk.Frame(body, bg='white')
        toolbar.pack(fill=tk.X, pady=(0, 8))
        tk.Button(toolbar, text="🔄 刷新", font=('Microsoft YaHei UI', 8), bg='#e9ecef', fg='#495057', bd=0, cursor='hand2', padx=10, pady=3, command=self._refresh_export_list).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(toolbar, text="📂 打开目录", font=('Microsoft YaHei UI', 8), bg='#e9ecef', fg='#495057', bd=0, cursor='hand2', padx=10, pady=3, command=self.open_output_dir).pack(side=tk.LEFT)

        columns = ('文件名', '大小', '修改时间')
        tree = ttk.Treeview(body, columns=columns, show='headings', height=15)
        tree.heading('文件名', text='文件名')
        tree.heading('大小', text='大小')
        tree.heading('修改时间', text='修改时间')
        tree.column('文件名', width=300)
        tree.column('大小', width=100)
        tree.column('修改时间', width=180)
        tree.pack(fill=tk.BOTH, expand=True)
        self.export_tree = tree
        self._refresh_export_list()

    def _refresh_export_list(self):
        if not hasattr(self, 'export_tree'):
            return
        for item in self.export_tree.get_children():
            self.export_tree.delete(item)
        output_dir = os.path.join(os.getcwd(), 'data_output')
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
                    self.export_tree.insert('', 'end', values=(f, size_str, mtime))

    def _show_settings_view(self):
        for widget in self.content_pages.winfo_children():
            widget.destroy()
        card = self._build_card_shadow(self.content_pages, "⚙ 设置", "⚙")
        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        dir_frame = tk.Frame(body, bg='white')
        dir_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(dir_frame, text="输出目录", font=('Microsoft YaHei UI', 9, 'bold'), bg='white', fg='#495057').pack(anchor='w')
        dir_inner = tk.Frame(dir_frame, bg='white')
        dir_inner.pack(fill=tk.X, pady=(4, 0))
        self.output_dir_var = tk.StringVar(value=os.path.join(os.getcwd(), 'data_output'))
        tk.Entry(dir_inner, textvariable=self.output_dir_var, font=('Microsoft YaHei UI', 9), bg='#f8f9fa', relief='flat', bd=0).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 6))
        tk.Button(dir_inner, text="浏览", font=('Microsoft YaHei UI', 8), bg='#e9ecef', fg='#495057', bd=0, cursor='hand2', padx=10, pady=3, command=self._browse_output_dir).pack(side=tk.LEFT)

        city_frame = tk.Frame(body, bg='white')
        city_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(city_frame, text="默认地市", font=('Microsoft YaHei UI', 9, 'bold'), bg='white', fg='#495057').pack(anchor='w')

        tk.Button(body, text="保存设置", font=('Microsoft YaHei UI', 9, 'bold'), bg='#165DFF', fg='white', bd=0, cursor='hand2', padx=20, pady=6, command=self._save_settings).pack(anchor='w', pady=(12, 0))

    def _browse_output_dir(self):
        from tkinter import filedialog
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)

    def _save_settings(self):
        self.log("设置已保存", "SUCCESS")

    def _show_about_view(self):
        for widget in self.content_pages.winfo_children():
            widget.destroy()
        card = self._build_card_shadow(self.content_pages, "ℹ 关于", "ℹ")
        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        center = tk.Frame(body, bg='white')
        center.place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(center, text="N", font=('Arial', 36, 'bold'), bg='#165DFF', fg='white', width=2, height=1).pack(pady=(0, 15))
        tk.Label(center, text="NQI数据提取工具", font=('Microsoft YaHei UI', 16, 'bold'), bg='white', fg='#1a1a2e').pack()
        tk.Label(center, text="版本 2.0.0", font=('Microsoft YaHei UI', 10), bg='white', fg='#6c757d').pack(pady=(4, 0))
        tk.Label(center, text="NQI平台数据提取与导出工具", font=('Microsoft YaHei UI', 9), bg='white', fg='#adb5bd').pack(pady=(8, 0))
        if self.expiry_time:
            tk.Label(center, text=f"授权到期: {self.expiry_time.strftime('%Y-%m-%d')}", font=('Microsoft YaHei UI', 9), bg='white', fg='#6c757d').pack(pady=(4, 0))

    def _build_card_shadow(self, parent, title=None, icon=None):
        """创建带阴影效果的卡片容器"""
        # 外层阴影框架
        shadow_frame = tk.Frame(parent, bg='#dee2e6')
        shadow_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # 白色内容卡片
        card = tk.Frame(shadow_frame, bg='white')
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        if title:
            header = tk.Frame(card, bg='white')
            header.pack(fill=tk.X, padx=16, pady=(12, 0))

            title_frame = tk.Frame(header, bg='white')
            title_frame.pack(side=tk.LEFT)

            if icon:
                icon_lbl = tk.Label(title_frame, text=icon,
                                   font=('Segoe UI Emoji', 11),
                                   bg='white')
                icon_lbl.pack(side=tk.LEFT, padx=(0, 6))

            title_lbl = tk.Label(title_frame, text=title,
                                font=('Microsoft YaHei UI', 12, 'bold'),
                                bg='white', fg='#1a1a2e')
            title_lbl.pack(side=tk.LEFT)

            separator = tk.Frame(card, bg='#f1f3f5', height=1)
            separator.pack(fill=tk.X, padx=16, pady=(8, 0))

        return card

    def _build_login_card_new(self):
        """构建登录配置卡片（顶部栏）"""
        # 登录栏背景
        login_bar = tk.Frame(self.content_pages, bg='white', height=60)
        login_bar.pack(fill=tk.X)
        login_bar.pack_propagate(False)

        # 左侧：用户名密码
        left_area = tk.Frame(login_bar, bg='white')
        left_area.pack(side=tk.LEFT, padx=20, pady=10)

        # 用户名
        user_frame = tk.Frame(left_area, bg='white')
        user_frame.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(user_frame, text="用户名",
                font=('Microsoft YaHei UI', 8),
                bg='white', fg='#6c757d').pack(anchor='w')

        user_entry_frame = tk.Frame(user_frame, bg='#f8f9fa', bd=1,
                                   relief='solid', highlightthickness=0)
        user_entry_frame.pack(pady=(2, 0), ipady=1)

        self.username_entry = tk.Entry(user_entry_frame,
                             font=('Microsoft YaHei UI', 9),
                             relief='flat', bg='#f8f9fa', bd=0, width=14)
        self.username_entry.insert(0, DEFAULT_USERNAME)
        self.username_entry.pack(padx=8, pady=2)

        # 密码
        pass_frame = tk.Frame(left_area, bg='white')
        pass_frame.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(pass_frame, text="密码",
                font=('Microsoft YaHei UI', 8),
                bg='white', fg='#6c757d').pack(anchor='w')

        pass_entry_frame = tk.Frame(pass_frame, bg='#f8f9fa', bd=1,
                                   relief='solid', highlightthickness=0)
        pass_entry_frame.pack(pady=(2, 0), ipady=1)

        self.password_entry = tk.Entry(pass_entry_frame,
                             font=('Microsoft YaHei UI', 9),
                             show="●", relief='flat', bg='#f8f9fa', bd=0, width=12)
        self.password_entry.insert(0, DEFAULT_PASSWORD)
        self.password_entry.pack(side=tk.LEFT, padx=(8, 0), pady=2)

        self._password_visible = False
        self.toggle_pwd_btn = tk.Label(pass_entry_frame, text="👁",
                                      font=('Segoe UI Emoji', 9),
                                      bg='#f8f9fa', fg='#6c757d',
                                      cursor='hand2')
        self.toggle_pwd_btn.pack(side=tk.LEFT, padx=(2, 8), pady=2)
        self.toggle_pwd_btn.bind('<Button-1>', lambda e: self._toggle_password_visibility())

        # 中间区域
        center_area = tk.Frame(login_bar, bg='white')
        center_area.pack(side=tk.LEFT, padx=(0, 20), pady=10)

        # 登录状态
        status_inner = tk.Frame(center_area, bg='white')
        status_inner.pack()

        self.login_dot = tk.Label(status_inner, text="○",
                                 font=('Arial', 10, 'bold'),
                                 bg='white', fg='#adb5bd')
        self.login_dot.pack(side=tk.LEFT)

        self.login_status_lbl = tk.Label(status_inner, text="未登录",
                                        font=('Microsoft YaHei UI', 9),
                                        bg='white', fg='#6c757d')
        self.login_status_lbl.pack(side=tk.LEFT, padx=(4, 0))

        # 右侧区域
        right_area = tk.Frame(login_bar, bg='white')
        right_area.pack(side=tk.RIGHT, padx=20, pady=10)

        # 登录按钮
        self.login_btn = tk.Button(right_area, text="登录",
                             font=('Microsoft YaHei UI', 9, 'bold'),
                             bg='#165DFF', fg='white', bd=0,
                             cursor='hand2', padx=20, pady=4,
                             command=self._on_login)
        self.login_btn.pack(side=tk.LEFT)

        # 授权信息（登录按钮后）
        self.license_label = tk.Label(right_area, text="",
                              font=('Microsoft YaHei UI', 8),
                              bg='white', fg='#6c757d')
        self.license_label.pack(side=tk.LEFT, padx=(10, 0))

        self._update_license_display()

    def _toggle_password_visibility(self):
        self._password_visible = not self._password_visible
        if self._password_visible:
            self.password_entry.config(show="")
            self.toggle_pwd_btn.config(fg='#165DFF')
        else:
            self.password_entry.config(show="●")
            self.toggle_pwd_btn.config(fg='#6c757d')

    # 数据分类与数据表的映射关系
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

    def _build_query_card_new(self, parent):
        """构建查询参数卡片"""
        card = self._build_card_shadow(parent, "查询参数", "🔍")

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        # 数据分类
        cat_label = tk.Label(body, text="数据分类",
                           font=('Microsoft YaHei UI', 8, 'bold'),
                           bg='white', fg='#495057')
        cat_label.pack(anchor='w', pady=(0, 4))

        # 分类按钮组 - 使用简单的按钮样式
        self.category_vars = {}
        self.category_btns = {}
        categories = ["干扰", "容量", "工参", "MR覆盖", "语音报表", "小区性能", "全程完好率", "语音小区"]

        cat_btn_frame = tk.Frame(body, bg='white')
        cat_btn_frame.pack(fill=tk.X, pady=(0, 6))

        for i, name in enumerate(categories):
            var = tk.IntVar(value=0)
            self.category_vars[name] = var

            btn = tk.Checkbutton(cat_btn_frame, text=name,
                               variable=var,
                               font=('Microsoft YaHei UI', 7),
                               bg='#e9ecef', fg='#495057',
                               selectcolor='#165DFF',
                               activebackground='#d0d5dc',
                               activeforeground='white',
                               cursor='hand2', padx=8, pady=4,
                               indicatoron=0,
                               command=lambda cat=name: self._on_category_click(cat))
            btn.grid(row=i // 4, column=i % 4, sticky='ew', padx=2, pady=2)
            cat_btn_frame.grid_columnconfigure(i % 4, weight=1)

            self.category_btns[name] = btn

        # 数据表选择
        table_label = tk.Label(body, text="选择数据表",
                              font=('Microsoft YaHei UI', 8, 'bold'),
                              bg='white', fg='#495057')
        table_label.pack(anchor='w', pady=(2, 4))

        # 收集所有数据表
        all_tables = []
        for tables in self.TABLE_CATEGORIES.values():
            all_tables.extend(tables)

        # 创建数据表下拉选择（带搜索功能）
        self.table_dropdown = MultiSelectDropdown(
            body,
            all_tables,
            width=20,
            select_all=False,
            on_change_callback=self._on_tables_changed
        )
        self.table_dropdown.pack(fill=tk.X, pady=(0, 4))

        # 自定义字段选择
        custom_row = tk.Frame(body, bg='white')
        custom_row.pack(fill=tk.X, pady=(0, 2))

        self.custom_fields_var = tk.BooleanVar(value=False)
        custom_field_cb = tk.Checkbutton(custom_row, text="自定义字段",
                                        variable=self.custom_fields_var,
                                        font=('Microsoft YaHei UI', 7),
                                        bg='white', fg='#495057',
                                        selectcolor='#165DFF',
                                        activebackground='white',
                                        activeforeground='#165DFF',
                                        cursor='hand2',
                                        padx=4,
                                        command=self._on_custom_fields_toggle)
        custom_field_cb.pack(side=tk.LEFT, padx=(0, 4))

        self.select_fields_btn = tk.Button(custom_row, text="选择",
                                         font=('Microsoft YaHei UI', 7),
                                         bg='#e9ecef', fg='#495057', bd=0,
                                         cursor='hand2', padx=6, pady=1,
                                         state=tk.DISABLED,
                                         command=self._show_field_selector)
        self.select_fields_btn.pack(side=tk.LEFT)

        # 存储选中的字段
        self.selected_fields = {}
        self.field_configs = {}

    def _on_category_click(self, category):
        var = self.category_vars[category]
        new_value = 1 - var.get()
        var.set(new_value)
        btn = self.category_btns[category]
        if new_value == 1:
            btn.config(bg='#165DFF', fg='white')
        else:
            btn.config(bg='#e9ecef', fg='#495057')
        self._sync_tables_from_categories()

    def _on_tables_changed(self):
        """数据表选择变化时的回调 - 同步更新分类按钮状态"""
        if not hasattr(self, 'table_dropdown') or not hasattr(self, 'category_vars'):
            return

        # 防止循环调用
        if getattr(self, '_is_syncing_tables', False):
            return
        self._is_syncing_tables = True

        # 收集需要更新的分类
        selected_tables = set(self.table_dropdown.get_selected())

        for cat_name, cat_var in self.category_vars.items():
            cat_tables = set(self.TABLE_CATEGORIES.get(cat_name, []))
            has_selected = bool(selected_tables & cat_tables)
            current_state = cat_var.get()

            if has_selected and current_state == 0:
                cat_var.set(1)
                self.category_btns[cat_name].config(bg='#165DFF', fg='white')
            elif not has_selected and current_state == 1:
                cat_var.set(0)
                self.category_btns[cat_name].config(bg='#e9ecef', fg='#495057')

        self._is_syncing_tables = False

    def _build_params_card_new(self, parent):
        """构建提取参数卡片"""
        # 动态导入 tkcalendar
        try:
            from tkcalendar import DateEntry
            self._use_tkcalendar = True
        except ImportError:
            self._use_tkcalendar = False

        card = self._build_card_shadow(parent, "提取参数", "⚙")

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        city_frame = tk.Frame(body, bg='white')
        city_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(city_frame, text="地市",
                font=('Microsoft YaHei UI', 8, 'bold'),
                bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=(0, 8))

        self.city_dropdown = MultiSelectDropdown(
            city_frame,
            MultiSelectDropdown.GD_CITIES,
            width=20,
            select_all=False
        )
        self.city_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.city_dropdown.set_selected(['阳江'])

        quick_frame = tk.Frame(body, bg='white')
        quick_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(quick_frame, text="快捷",
                font=('Microsoft YaHei UI', 8, 'bold'),
                bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=(0, 8))

        self.quick_date_btns = {}
        for text, days in [("昨天", 1), ("7天", 7), ("30天", 30)]:
            btn = tk.Button(quick_frame, text=text,
                           font=('Microsoft YaHei UI', 7),
                           bg='#e9ecef', fg='#495057', bd=0,
                           cursor='hand2', padx=6, pady=2,
                           command=lambda d=days: self.set_quick_date(d))
            btn.pack(side=tk.LEFT, padx=(0, 2))
            self.quick_date_btns[days] = btn

        # 第二行：日期范围
        date_row = tk.Frame(body, bg='white')
        date_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(date_row, text="日期",
                font=('Microsoft YaHei UI', 8, 'bold'),
                bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=(0, 8))

        yesterday = datetime.now() - timedelta(days=1)
        start_date = datetime.now() - timedelta(days=7)

        if self._use_tkcalendar:
            # 使用 tkcalendar 日历选择器
            self.start_date_entry = DateEntry(
                date_row,
                width=10,
                font=('Microsoft YaHei UI', 9),
                date_pattern='yyyy-mm-dd',
                showweeknumbers=False
            )
            self.start_date_entry.pack(side=tk.LEFT, padx=(0, 4))
            self.start_date_entry.set_date(start_date)

            tk.Label(date_row, text="至", font=('Microsoft YaHei UI', 7),
                    bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=(0, 4))

            self.end_date_entry = DateEntry(
                date_row,
                width=10,
                font=('Microsoft YaHei UI', 9),
                date_pattern='yyyy-mm-dd',
                showweeknumbers=False
            )
            self.end_date_entry.pack(side=tk.LEFT)
            self.end_date_entry.set_date(yesterday)

            # 绑定日期变化事件
            self.start_date_entry.bind('<<DateEntrySelected>>', lambda e: self._on_date_changed())
            self.end_date_entry.bind('<<DateEntrySelected>>', lambda e: self._on_date_changed())
        else:
            # 降级使用下拉框
            self.start_year_var = tk.IntVar(value=start_date.year)
            self.start_month_var = tk.IntVar(value=start_date.month)
            self.start_day_var = tk.IntVar(value=start_date.day)

            self.end_year_var = tk.IntVar(value=yesterday.year)
            self.end_month_var = tk.IntVar(value=yesterday.month)
            self.end_day_var = tk.IntVar(value=yesterday.day)

            start_frame = tk.Frame(date_row, bg='white')
            start_frame.pack(side=tk.LEFT)

            current_year = datetime.now().year
            ttk.Combobox(start_frame, textvariable=self.start_year_var,
                       values=list(range(2020, current_year + 1)),
                       width=4, state="readonly", font=('Microsoft YaHei UI', 7)).pack(side=tk.LEFT)
            tk.Label(start_frame, text="-", font=('Microsoft YaHei UI', 7),
                    bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=1)
            ttk.Combobox(start_frame, textvariable=self.start_month_var,
                       values=[f"{i:02d}" for i in range(1, 13)],
                       width=2, state="readonly", font=('Microsoft YaHei UI', 7)).pack(side=tk.LEFT)
            tk.Label(start_frame, text="-", font=('Microsoft YaHei UI', 7),
                    bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=1)
            ttk.Combobox(start_frame, textvariable=self.start_day_var,
                       values=[f"{i:02d}" for i in range(1, 32)],
                       width=2, state="readonly", font=('Microsoft YaHei UI', 7)).pack(side=tk.LEFT)

            tk.Label(date_row, text="至", font=('Microsoft YaHei UI', 7),
                    bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=4)

            end_frame = tk.Frame(date_row, bg='white')
            end_frame.pack(side=tk.LEFT)

            ttk.Combobox(end_frame, textvariable=self.end_year_var,
                       values=list(range(2020, current_year + 1)),
                       width=4, state="readonly", font=('Microsoft YaHei UI', 7)).pack(side=tk.LEFT)
            tk.Label(end_frame, text="-", font=('Microsoft YaHei UI', 7),
                    bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=1)
            ttk.Combobox(end_frame, textvariable=self.end_month_var,
                       values=[f"{i:02d}" for i in range(1, 13)],
                       width=2, state="readonly", font=('Microsoft YaHei UI', 7)).pack(side=tk.LEFT)
            tk.Label(end_frame, text="-", font=('Microsoft YaHei UI', 7),
                    bg='white', fg='#6c757d').pack(side=tk.LEFT, padx=1)
            ttk.Combobox(end_frame, textvariable=self.end_day_var,
                       values=[f"{i:02d}" for i in range(1, 32)],
                       width=2, state="readonly", font=('Microsoft YaHei UI', 7)).pack(side=tk.LEFT)

        # 第三行：多日模式
        mode_row = tk.Frame(body, bg='white')
        mode_row.pack(fill=tk.X, pady=(0, 6))

        self.multi_day_var = tk.BooleanVar(value=False)
        multi_day_cb = tk.Checkbutton(mode_row, text="多日模式",
                                      variable=self.multi_day_var,
                                      font=('Microsoft YaHei UI', 7),
                                      bg='white', fg='#495057',
                                      selectcolor='#e9ecef',
                                      activebackground='white',
                                      padx=4,
                                      command=self._on_multi_day_toggle)
        multi_day_cb.pack(side=tk.LEFT)

        self.multi_day_per_sheet_var = tk.BooleanVar(value=False)
        self.multi_day_per_sheet_cb = tk.Checkbutton(mode_row, text="按日分Sheet",
                                               variable=self.multi_day_per_sheet_var,
                                               font=('Microsoft YaHei UI', 7),
                                               bg='white', fg='#495057',
                                               selectcolor='#e9ecef',
                                               activebackground='white',
                                               state=tk.DISABLED,
                                               padx=4,
                                               command=self._on_multi_day_per_sheet_toggle)
        self.multi_day_per_sheet_cb.pack(side=tk.LEFT)

        # 第四行：操作按钮
        btn_row = tk.Frame(body, bg='white')
        btn_row.pack(fill=tk.X)

        self.extract_btn = tk.Button(btn_row, text="▶ 开始提取",
                               font=('Microsoft YaHei UI', 9, 'bold'),
                               bg='#165DFF', fg='white', bd=0,
                               cursor='hand2', padx=16, pady=5,
                               state=tk.DISABLED, command=self._on_query)
        self.extract_btn.pack(side=tk.LEFT)

        self.stop_btn = tk.Button(btn_row, text="⏹",
                            font=('Microsoft YaHei UI', 8),
                            bg='#dc3545', fg='white', bd=0,
                            cursor='hand2', padx=10, pady=5,
                            state=tk.DISABLED, command=self._on_stop)
        self.stop_btn.pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(btn_row, text="📁",
                 font=('Microsoft YaHei UI', 8),
                 bg='#e9ecef', fg='#495057', bd=0,
                 cursor='hand2', padx=8, pady=5,
                 command=self.open_output_dir).pack(side=tk.LEFT, padx=(6, 0))

    def _on_date_changed(self):
        """日期变化事件"""
        pass

    def _build_preview_card(self, parent):
        card = self._build_card_shadow(parent, "数据预览", "📋")

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        self.preview_stats = tk.Frame(body, bg='white')
        self.preview_stats.pack(fill=tk.X)
        self.preview_stats_label = tk.Label(self.preview_stats, text="",
                                           font=('Microsoft YaHei UI', 8),
                                           bg='white', fg='#6c757d')
        self.preview_stats_label.pack(side=tk.LEFT)
        self.preview_stats.pack_forget()

        guide_frame = tk.Frame(body, bg='white')
        guide_frame.pack(fill=tk.BOTH, expand=True, pady=20)

        steps = [
            ("1", "登录账号", "输入用户名密码并点击登录"),
            ("2", "选择数据表", "选择需要查询的数据分类和表"),
            ("3", "设置参数", "选择地市和日期范围"),
            ("4", "开始提取", "点击开始提取按钮获取数据"),
        ]
        for i, (num, title, desc) in enumerate(steps):
            step_frame = tk.Frame(guide_frame, bg='white')
            step_frame.pack(fill=tk.X, pady=4, padx=20)

            num_label = tk.Label(step_frame, text=num,
                               font=('Microsoft YaHei UI', 10, 'bold'),
                               bg='#165DFF', fg='white',
                               width=2, height=1)
            num_label.pack(side=tk.LEFT, padx=(0, 10))

            text_frame = tk.Frame(step_frame, bg='white')
            text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(text_frame, text=title,
                    font=('Microsoft YaHei UI', 9, 'bold'),
                    bg='white', fg='#1a1a2e').pack(anchor='w')
            tk.Label(text_frame, text=desc,
                    font=('Microsoft YaHei UI', 7),
                    bg='white', fg='#adb5bd').pack(anchor='w')

        self.preview_guide = guide_frame

        columns = ('文件名', '记录数', '状态')
        self.preview_tree = ttk.Treeview(body, columns=columns, show='headings', height=6)
        self.preview_tree.heading('文件名', text='文件名')
        self.preview_tree.heading('记录数', text='记录数')
        self.preview_tree.heading('状态', text='状态')
        self.preview_tree.column('文件名', width=200)
        self.preview_tree.column('记录数', width=80)
        self.preview_tree.column('状态', width=80)
        self.preview_tree.pack_forget()

    def _build_log_card(self, parent):
        card = self._build_card_shadow(parent, "运行日志", "📝")

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        toolbar = tk.Frame(body, bg='white')
        toolbar.pack(fill=tk.X, pady=(0, 4))

        search_frame = tk.Frame(toolbar, bg='#f8f9fa', bd=1, relief='solid')
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.log_search_var = tk.StringVar()
        self.log_search_entry = tk.Entry(search_frame, textvariable=self.log_search_var,
                                        font=('Microsoft YaHei UI', 7),
                                        relief='flat', bg='#f8f9fa', bd=0, width=12)
        self.log_search_entry.pack(side=tk.LEFT, padx=4, pady=2)
        self.log_search_entry.insert(0, "搜索日志...")
        self.log_search_entry.bind('<FocusIn>', lambda e: self._on_log_search_focus_in())
        self.log_search_entry.bind('<FocusOut>', lambda e: self._on_log_search_focus_out())
        self.log_search_entry.bind('<KeyRelease>', lambda e: self._on_log_search())

        tk.Button(search_frame, text="✕",
                 font=('Microsoft YaHei UI', 7),
                 bg='#f8f9fa', fg='#6c757d', bd=0,
                 cursor='hand2', padx=4,
                 command=self._clear_log_search).pack(side=tk.RIGHT, padx=2)

        self._log_auto_scroll = True
        self.auto_scroll_label = tk.Label(toolbar, text="", font=('Microsoft YaHei UI', 7),
                                         bg='white', fg='#fd7e14')
        self.auto_scroll_label.pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(toolbar, text="清空",
                 font=('Microsoft YaHei UI', 7),
                 bg='#e9ecef', fg='#495057', bd=0,
                 cursor='hand2', padx=6, pady=1,
                 command=self._clear_log).pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(body,
                                                   font=('Consolas', 8),
                                                   state='disabled',
                                                   bg='#f8f9fa',
                                                   relief='flat',
                                                   bd=0)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_configure('INFO', foreground='#212529')
        self.log_text.tag_configure('ERROR', foreground='#dc3545')
        self.log_text.tag_configure('WARNING', foreground='#fd7e14')
        self.log_text.tag_configure('SUCCESS', foreground='#22c55e')
        self.log_text.tag_configure('search_highlight', background='#fff3cd', foreground='#856404')
        self.log_text.tag_configure('dim', foreground='#ced4da')

        self.log_text.bind('<MouseWheel>', self._on_log_scroll)
        self.log_text.bind('<Button-4>', self._on_log_scroll)
        self.log_text.bind('<Button-5>', self._on_log_scroll)

        handler = LogTextHandler(self.log_text)
        handler.setLevel(logging.INFO)
        self.logger.addHandler(handler)

    def _on_log_search_focus_in(self):
        if self.log_search_entry.get() == "搜索日志...":
            self.log_search_entry.delete(0, tk.END)
            self.log_search_entry.config(fg='#212529')

    def _on_log_search_focus_out(self):
        if not self.log_search_entry.get():
            self.log_search_entry.insert(0, "搜索日志...")
            self.log_search_entry.config(fg='#adb5bd')

    def _clear_log_search(self):
        self.log_search_var.set("")
        self.log_text.tag_remove('search_highlight', '1.0', tk.END)
        self.log_text.tag_remove('dim', '1.0', tk.END)

    def _on_log_search(self):
        keyword = self.log_search_var.get().strip()
        self.log_text.tag_remove('search_highlight', '1.0', tk.END)
        self.log_text.tag_remove('dim', '1.0', tk.END)
        if not keyword or keyword == "搜索日志...":
            return
        start = '1.0'
        while True:
            pos = self.log_text.search(keyword, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(keyword)}c"
            self.log_text.tag_add('search_highlight', pos, end)
            start = end

    def _clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state='disabled')

    def _on_log_scroll(self, event=None):
        if not self._log_auto_scroll:
            return
        self._log_auto_scroll = False
        self.auto_scroll_label.config(text="自动滚动已暂停")
        self.log_text.bind('<Double-Button-1>', lambda e: self._resume_auto_scroll())

    def _resume_auto_scroll(self):
        self._log_auto_scroll = True
        self.auto_scroll_label.config(text="")
        self.log_text.unbind('<Double-Button-1>')
        self.log_text.see(tk.END)

    def _build_progress_section(self):
        """构建底部进度条区域"""
        # 进度条容器（占满宽度）
        progress_container = tk.Frame(self.content_pages, bg='white', height=50)
        progress_container.pack(fill=tk.X, pady=(12, 0))
        progress_container.pack_propagate(False)

        progress_inner = tk.Frame(progress_container, bg='white')
        progress_inner.pack(fill=tk.BOTH, padx=16, pady=8)

        progress_top = tk.Frame(progress_inner, bg='white')
        progress_top.pack(fill=tk.X)

        self.progress_lbl_pct = tk.Label(progress_top, text="进度: 0%",
                          font=('Microsoft YaHei UI', 9, 'bold'),
                          bg='white', fg='#165DFF')
        self.progress_lbl_pct.pack(side=tk.LEFT)

        self.progress_lbl_detail = tk.Label(progress_top, text="就绪",
                             font=('Microsoft YaHei UI', 9),
                             bg='white', fg='#6c757d')
        self.progress_lbl_detail.pack(side=tk.RIGHT)

        # 圆角进度条
        self.progress_canvas = tk.Canvas(progress_inner, height=6, bg='white', highlightthickness=0)
        self.progress_canvas.pack(fill=tk.X, pady=(6, 0))
        self.progress_bar = self.progress_canvas.create_rectangle(0, 0, 0, 6, fill='#165DFF', outline='')
        self.progress_bg = self.progress_canvas.create_rectangle(0, 0, 1000, 6, fill='#e9ecef', outline='')

    def _update_license_display(self):
        """更新授权时间显示"""
        if self.expiry_time:
            try:
                display_time = self.expiry_time.strftime("%Y-%m-%d")
                current_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                days_left = (self.expiry_time - current_dt).days

                if days_left < 0:
                    self.license_label.config(text="授权已过期", fg='#dc3545')
                    self.sidebar_status.config(fg='#dc3545', text="○")
                elif days_left <= 7:
                    self.license_label.config(text=f"到期: {display_time} (剩{days_left}天)", fg='#fd7e14')
                    self.sidebar_status.config(fg='#fd7e14', text="●")
                elif days_left <= 30:
                    self.license_label.config(text=f"到期: {display_time} (剩{days_left}天)", fg='#fd7e14')
                    self.sidebar_status.config(fg='#fd7e14', text="●")
                else:
                    self.license_label.config(text=f"到期: {display_time}", fg='#22c55e')
                    self.sidebar_status.config(fg='#22c55e', text="●")
            except:
                self.license_label.config(text="", fg='#6c757d')

    def _bind_events(self):
        """绑定事件"""
        pass

    def _on_time_rollback(self):
        """检测到时间回拨时的处理"""
        invalidate_license()
        self.root.after(0, self._force_exit)

    def _force_exit(self):
        """强制退出程序"""
        import os
        os._exit(1)

    def _sync_tables_from_categories(self):
        """根据选中的分类同步数据表选择"""
        # 根据选中的分类收集所有需要选中的数据表
        tables_to_select = []

        for cat_name, var in self.category_vars.items():
            if var.get() == 1:  # 该分类被选中
                if cat_name in self.TABLE_CATEGORIES:
                    tables_to_select.extend(self.TABLE_CATEGORIES[cat_name])

        # 更新数据表下拉选择（不触发回调，避免循环）
        if tables_to_select:
            self.table_dropdown.set_selected(tables_to_select, trigger_callback=False)
        else:
            # 如果没有选中任何分类，清空数据表选择
            self.table_dropdown.set_selected([], trigger_callback=False)

    def _on_multi_day_toggle(self):
        """多日模式切换事件"""
        if self.multi_day_var.get():
            self.multi_day_per_sheet_cb.config(state=tk.NORMAL)
        else:
            self.multi_day_per_sheet_var.set(False)
            self.multi_day_per_sheet_cb.config(state=tk.DISABLED)

    def _on_multi_day_per_sheet_toggle(self):
        """按日分Sheet切换事件"""
        pass

    def _on_custom_fields_toggle(self):
        """自定义字段切换事件"""
        if self.custom_fields_var.get():
            self.select_fields_btn.config(state=tk.NORMAL)
        else:
            self.select_fields_btn.config(state=tk.DISABLED)

    def _show_field_selector(self):
        """显示字段选择窗口"""
        if not self.jxcx:
            messagebox.showwarning("警告", "请先登录后再选择字段")
            return

        selected_tables = self.table_dropdown.get_selected()
        if not selected_tables:
            messagebox.showwarning("警告", "请先选择数据表")
            return

        field_window = tk.Toplevel(self.root)
        field_window.title("选择导出字段")
        field_window.geometry("600x400")
        field_window.resizable(True, True)

        self.root.update_idletasks()
        x = (self.root.winfo_width() - 600) // 2 + self.root.winfo_x()
        y = (self.root.winfo_height() - 400) // 2 + self.root.winfo_y()
        field_window.geometry(f"600x400+{x}+{y}")

        canvas = tk.Canvas(field_window)
        scrollbar = ttk.Scrollbar(field_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        field_vars = {}
        for table_name in selected_tables:
            if table_name not in self.field_configs and self.jxcx:
                table_config = TableConfig.get_table_config(table_name)
                if table_config:
                    try:
                        self.log(f"正在获取 {table_name} 的字段配置...", "INFO")
                        configs = self.jxcx.get_field_config(
                            table_config['table_key'],
                            table_config['fieldtype'],
                            table_config['api_type']
                        )
                        if configs:
                            self.field_configs[table_name] = configs
                            self.log(f"获取到 {table_name} 的 {len(configs)} 个字段", "SUCCESS")
                        else:
                            self.log(f"获取 {table_name} 的字段配置失败", "WARNING")
                    except Exception as e:
                        self.log(f"获取字段配置异常: {e}", "ERROR")

            if table_name in self.field_configs:
                configs = self.field_configs[table_name]

                table_frame = tk.Frame(scrollable_frame, bg='white', bd=1, relief='solid')
                table_frame.pack(fill=tk.X, pady=5, padx=10)

                table_title = tk.Label(table_frame, text=table_name,
                                     font=('Microsoft YaHei UI', 10, 'bold'),
                                     bg='white', fg='#165DFF')
                table_title.pack(anchor='w', padx=5, pady=3)

                fields_frame = tk.Frame(scrollable_frame, bg='white')
                fields_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

                row_frame = None
                for i, config in enumerate(configs):
                    if i % 4 == 0:
                        row_frame = tk.Frame(fields_frame, bg='white')
                        row_frame.pack(fill=tk.X, pady=2)

                    field_name = config.get('columnname_cn', config.get('columnname', ''))
                    field_key = config.get('columnname', '')

                    var = tk.BooleanVar(value=True)
                    field_vars[(table_name, field_key)] = var

                    cb = tk.Checkbutton(row_frame, text=field_name,
                                       variable=var,
                                       font=('Microsoft YaHei UI', 9),
                                       bg='white', fg='#495057',
                                       selectcolor='#165DFF',
                                       activebackground='white',
                                       activeforeground='#165DFF',
                                       cursor='hand2')
                    cb.pack(side=tk.LEFT, padx=10, pady=1, fill=tk.X, expand=True)

        btn_frame = tk.Frame(field_window, bg='white')
        btn_frame.pack(fill=tk.X, pady=10, padx=10)

        def on_ok():
            self.selected_fields = {}
            for (table_name, field_key), var in field_vars.items():
                if var.get():
                    if table_name not in self.selected_fields:
                        self.selected_fields[table_name] = []
                    self.selected_fields[table_name].append(field_key)

            total_fields = sum(len(fields) for fields in self.selected_fields.values())
            self.log(f"已选择 {total_fields} 个字段", "INFO")
            field_window.destroy()

        def on_cancel():
            field_window.destroy()

        ttk.Button(btn_frame, text="确定", command=on_ok, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=on_cancel, width=10).pack(side=tk.RIGHT, padx=5)

    def set_quick_date(self, days):
        """设置快捷日期"""
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=days-1)

        if self._use_tkcalendar and hasattr(self, 'start_date_entry'):
            # 使用 tkcalendar
            self.start_date_entry.set_date(start_date)
            self.end_date_entry.set_date(end_date)
        else:
            # 使用下拉框
            self.start_year_var.set(start_date.year)
            self.start_month_var.set(start_date.month)
            self.start_day_var.set(start_date.day)

            self.end_year_var.set(end_date.year)
            self.end_month_var.set(end_date.month)
            self.end_day_var.set(end_date.day)

        self.log(f"设置快捷日期: 近{days}天", "INFO")

    def open_output_dir(self):
        """打开输出目录"""
        import webbrowser
        output_dir = os.path.join(os.getcwd(), 'data_output')
        os.makedirs(output_dir, exist_ok=True)
        webbrowser.open(output_dir)

    def _on_login(self):
        """登录按钮点击事件"""
        self.log("开始登录...", "INFO")
        self.login_dot.config(text="◐", fg='#fd7e14')
        self.login_status_lbl.config(text="登录中...", fg='#fd7e14')
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
        self.login_dot.config(text="●", fg='#22c55e')
        self.login_status_lbl.config(text="已登录", fg='#22c55e')

    def _update_login_failed_ui(self):
        """批量更新登录失败UI"""
        self.login_dot.config(text="○", fg='#dc3545')
        self.login_status_lbl.config(text="登录失败", fg='#dc3545')

    def _update_login_error_ui(self, message):
        """批量更新登录异常UI"""
        self.login_dot.config(text="○", fg='#dc3545')
        self.login_status_lbl.config(text="登录异常", fg='#dc3545')
        self.log(f"登录异常: {message}", "ERROR")

    def _on_query(self):
        """查询按钮点击事件"""
        if self.is_querying:
            self.log("正在查询中，请稍候...", "WARNING")
            return

        selected_tables = self.table_dropdown.get_selected()
        if not selected_tables:
            messagebox.showwarning("警告", "请选择要查询的数据表")
            return

        # 兼容日历选择器和下拉框
        if self._use_tkcalendar and hasattr(self, 'start_date_entry'):
            start_date = self.start_date_entry.get_date().strftime('%Y-%m-%d')
            end_date = self.end_date_entry.get_date().strftime('%Y-%m-%d')
        else:
            start_date = f"{self.start_year_var.get()}-{self.start_month_var.get():02d}-{self.start_day_var.get():02d}"
            end_date = f"{self.end_year_var.get()}-{self.end_month_var.get():02d}-{self.end_day_var.get():02d}"

        selected_cities = self.city_dropdown.get_selected()
        city = ",".join(selected_cities) if selected_cities else ""

        self._save_user_config()
        self.is_querying = True
        self._stop_requested = False
        self.extract_btn.config(state=tk.DISABLED, text="查询中...")
        self.stop_btn.config(state=tk.NORMAL)

        self.log(f"开始查询: {', '.join(selected_tables)}", "INFO")
        self.log(f"日期范围: {start_date} 至 {end_date}", "INFO")
        if city:
            self.log(f"地市: {city}", "INFO")

        self.query_thread = threading.Thread(target=self._query_worker,
                                            args=(selected_tables, start_date, end_date, city))
        self.query_thread.daemon = True
        self.query_thread.start()

    def _on_stop(self):
        if not self.is_querying:
            return
        if messagebox.askyesno("确认", "确定要停止当前查询吗？\n已获取的数据将被保留。"):
            self._stop_requested = True
            self.log("正在停止查询...", "WARNING")

    def _query_worker(self, table_names, start_date, end_date, city):
        try:
            total = len(table_names)
            for idx, table_name in enumerate(table_names):
                if self._stop_requested:
                    self.log("查询已被用户停止", "WARNING")
                    break
                self.log(f"正在查询: {table_name} ({idx+1}/{total})", "INFO")
                self.root.after(0, lambda i=idx, t=total, n=table_name: self._update_progress_detail(i, t, n))
                table_config = TableConfig.get_table_config(table_name)
                if table_config:
                    self.jxcx.enter_jxcx()
                    dimension = table_config.get('dimension', {})
                    fields = table_config.get('fields', None)
                    conditions = table_config.get('default_conditions', []).copy()
                    is_gongcan = table_config.get('is_gongcan', False)
                    if not is_gongcan:
                        conditions.append({'field': 'starttime', 'operator': '>=', 'value': start_date})
                        conditions.append({'field': 'starttime', 'operator': '<=', 'value': end_date})
                    if city:
                        conditions.append({'field': 'city', 'operator': 'in', 'value': city})
                    payload = self.jxcx.build_payload_from_config(
                        table_config['table_key'],
                        table_config['fieldtype'],
                        conditions,
                        table_config['api_type'],
                        dimension_override=dimension if dimension else None,
                        fields_override=fields
                    )
                    if payload:
                        df = self.jxcx.get_table(payload)
                        if not df.empty:
                            if self.custom_fields_var.get() and table_name in self.selected_fields:
                                selected_field_keys = self.selected_fields[table_name]
                                available_fields = [col for col in df.columns if col in selected_field_keys]
                                if not available_fields and table_name in self.field_configs:
                                    config_map = {c.get('columnname'): c.get('columnname') for c in self.field_configs[table_name]}
                                    for col in df.columns:
                                        if col in config_map and config_map[col] in selected_field_keys:
                                            available_fields.append(col)
                                if available_fields:
                                    df = df[available_fields]
                                    self.log(f"应用自定义字段: {len(available_fields)} 个字段", "INFO")
                                else:
                                    self.log(f"没有选中的字段可用，将导出全部字段", "WARNING")
                            import os
                            from core.export import export_with_format
                            filename = f"{table_name}_{start_date}_{end_date}.xlsx"
                            filepath = export_with_format(df, filename, table_name)
                            if filepath:
                                self.log(f"数据已导出到: {os.path.basename(filepath)}", "SUCCESS")
                                self.root.after(0, lambda fn=table_name, fc=len(df): self._add_preview_row(fn, fc))
                            else:
                                self.log(f"导出失败: {table_name}", "ERROR")
                        else:
                            self.log(f"查询结果为空: {table_name}", "WARNING")
                        self.log(f"查询完成: {table_name}", "SUCCESS")
                    progress_pct = int((idx + 1) / total * 100)
                    self.root.after(0, lambda p=progress_pct: self._update_progress_bar(p))
            self.root.after(0, self._on_query_complete)
        except Exception as e:
            self.root.after(0, lambda: self.log(f"查询异常: {e}", "ERROR"))
            self.root.after(0, self._on_query_failed)

    def _add_preview_row(self, filename, count):
        if hasattr(self, 'preview_guide') and self.preview_guide.winfo_exists():
            self.preview_guide.pack_forget()
        if not self.preview_tree.winfo_ismapped():
            self.preview_tree.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.preview_tree.insert('', 0, values=(filename, count, '完成'))
        self._update_preview_stats()

    def _update_preview_stats(self):
        if not hasattr(self, 'preview_stats'):
            return
        total_items = len(self.preview_tree.get_children())
        total_records = 0
        for item in self.preview_tree.get_children():
            values = self.preview_tree.item(item, 'values')
            try:
                total_records += int(values[1])
            except (ValueError, IndexError):
                pass
        self.preview_stats.pack(fill=tk.X, pady=(0, 4))
        self.preview_stats_label.config(text=f"共 {total_items} 个表, {total_records} 条记录")

    def _on_query_complete(self):
        self.is_querying = False
        self._stop_requested = False
        self.extract_btn.config(state=tk.NORMAL, text="▶ 开始提取")
        self.stop_btn.config(state=tk.DISABLED)
        self._update_preview_stats()
        self._update_progress_bar(100)
        self.progress_lbl_detail.config(text="查询完成")
        self.log("所有查询完成！", "SUCCESS")

    def _on_query_failed(self):
        self.is_querying = False
        self._stop_requested = False
        self.extract_btn.config(state=tk.NORMAL, text="▶ 开始提取")
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_lbl_detail.config(text="查询失败")

    def _update_progress_detail(self, current, total, table_name):
        pct = int((current + 1) / total * 100)
        self.progress_lbl_pct.config(text=f"进度: {pct}%")
        self.progress_lbl_detail.config(text=f"正在查询: {table_name} ({current+1}/{total})")
        self._update_progress_bar(pct)

    def _update_progress_bar(self, pct):
        if not hasattr(self, 'progress_canvas') or not self.progress_canvas.winfo_exists():
            return
        self.progress_canvas.update_idletasks()
        canvas_width = self.progress_canvas.winfo_width()
        bar_width = int(canvas_width * pct / 100)
        self.progress_canvas.coords(self.progress_bg, 0, 0, canvas_width, 6)
        self.progress_canvas.coords(self.progress_bar, 0, 0, bar_width, 6)

    def log(self, message, level="INFO"):
        tag_map = {
            'INFO': 'INFO',
            'ERROR': 'ERROR',
            'WARNING': 'WARNING',
            'SUCCESS': 'SUCCESS'
        }
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {message}\n"
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, log_line, (tag_map.get(level, 'INFO'),))
        if self._log_auto_scroll:
            self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def load_config(self):
        self.log("NQI工具已就绪", "INFO")
        self.log(f"支持的数据表: {', '.join(TableConfig.get_table_names())}", "INFO")
        self._load_user_config()

    def _save_user_config(self):
        import json
        try:
            config = {}
            if hasattr(self, 'city_dropdown'):
                config['cities'] = self.city_dropdown.get_selected()
            if hasattr(self, 'table_dropdown'):
                config['tables'] = self.table_dropdown.get_selected()
            if self._use_tkcalendar and hasattr(self, 'start_date_entry'):
                config['start_date'] = self.start_date_entry.get_date().strftime('%Y-%m-%d')
                config['end_date'] = self.end_date_entry.get_date().strftime('%Y-%m-%d')
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
            if 'start_date' in config and self._use_tkcalendar and hasattr(self, 'start_date_entry'):
                from datetime import datetime as dt
                self.start_date_entry.set_date(dt.strptime(config['start_date'], '%Y-%m-%d'))
            if 'end_date' in config and self._use_tkcalendar and hasattr(self, 'end_date_entry'):
                from datetime import datetime as dt
                self.end_date_entry.set_date(dt.strptime(config['end_date'], '%Y-%m-%d'))
            self.log("已加载上次配置", "INFO")
        except Exception as e:
            self.logger.warning(f"加载配置失败: {e}")

    def run(self):
        """运行应用"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.mainloop()

    def _on_closing(self):
        """窗口关闭事件"""
        if hasattr(self, '_time_monitor'):
            self._time_monitor.stop()
        self.root.destroy()

    def _show_activate_window(self):
        """显示序列号激活窗口"""
        from core.license import generate_machine_code, get_hw_info

        hw_info = get_hw_info()
        machine_code = generate_machine_code(hw_info)

        activate_win = tk.Toplevel(self.root)
        activate_win.title("授权激活")
        activate_win.geometry("500x380")
        activate_win.resizable(False, False)

        self.root.update_idletasks()
        x = (self.root.winfo_width() - 500) // 2 + self.root.winfo_x()
        y = (self.root.winfo_height() - 380) // 2 + self.root.winfo_y()
        activate_win.geometry(f"500x380+{x}+{y}")

        activate_win.transient(self.root)
        activate_win.grab_set()

        content = tk.Frame(activate_win, bg='#f8f9fa')
        content.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)

        title = tk.Label(content, text="授权激活",
                        font=('Microsoft YaHei UI', 18, 'bold'),
                        bg='#f8f9fa', fg='#1a1a2e')
        title.pack(pady=(0, 20))

        info_card = tk.Frame(content, bg='white')
        info_card.pack(fill=tk.X, pady=(0, 15))

        tk.Label(info_card, text="本机信息",
                font=('Microsoft YaHei UI', 12, 'bold'),
                bg='white', fg='#1a1a2e', anchor='w').pack(padx=15, pady=(12, 8))

        machine_frame = tk.Frame(info_card, bg='white')
        machine_frame.pack(fill=tk.X, padx=15, pady=(0, 12))

        tk.Label(machine_frame, text="机器码：",
                font=('Microsoft YaHei UI', 9),
                bg='white', fg='#6c757d').pack(side=tk.LEFT)

        machine_code_label = tk.Label(machine_frame, text=machine_code,
                                    font=('Consolas', 9),
                                    bg='white', fg='#495057')
        machine_code_label.pack(side=tk.LEFT, padx=(5, 0))

        tk.Button(machine_frame, text="复制",
                font=('Microsoft YaHei UI', 8),
                bg='#e9ecef', fg='#495057', bd=0,
                cursor='hand2', padx=10, pady=3,
                command=lambda: self._copy_to_clipboard(activate_win, machine_code)).pack(side=tk.RIGHT)

        input_card = tk.Frame(content, bg='white')
        input_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(input_card, text="输入序列号",
                font=('Microsoft YaHei UI', 12, 'bold'),
                bg='white', fg='#1a1a2e', anchor='w').pack(padx=15, pady=(12, 5))

        tk.Label(input_card, text="请输入管理员提供的验证序列号：",
                font=('Microsoft YaHei UI', 9),
                bg='white', fg='#6c757d', anchor='w').pack(padx=15, pady=(0, 8))

        serial_frame = tk.Frame(input_card, bg='white')
        serial_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        serial_entry = tk.Entry(serial_frame,
                              font=('Consolas', 11),
                              relief='flat', bg='#f8f9fa', bd=0)
        serial_entry.pack(fill=tk.X, ipady=10)

        tk.Label(serial_frame, text="格式示例：NQI-xxxx-xxxx-xxxx",
                font=('Microsoft YaHei UI', 8),
                bg='white', fg='#adb5bd').pack(anchor='w', pady=(4, 0))

        btn_frame = tk.Frame(content, bg='#f8f9fa')
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        activate_btn = tk.Button(btn_frame, text="激活授权",
                 font=('Microsoft YaHei UI', 11, 'bold'),
                 bg='#165DFF', fg='white', bd=0,
                 cursor='hand2', padx=25, pady=8,
                 command=lambda: self._do_activate(serial_entry.get(), machine_code, activate_win))
        activate_btn.pack(side=tk.LEFT)

        tk.Button(btn_frame, text="取消",
                 font=('Microsoft YaHei UI', 10),
                 bg='#e9ecef', fg='#495057', bd=0,
                 cursor='hand2', padx=18, pady=8,
                 command=activate_win.destroy).pack(side=tk.RIGHT)

        serial_entry.focus()
        serial_entry.bind('<Return>', lambda e: activate_btn.invoke())

    def _do_activate(self, serial_number, machine_code, window):
        """执行激活操作"""
        if not serial_number or not serial_number.strip():
            messagebox.showwarning("提示", "请输入序列号")
            return

        serial_number = serial_number.strip()

        success, result = verify_serial_number(serial_number, machine_code)

        if success:
            write_success, write_msg = write_license_from_serial(result)
            if write_success:
                window.destroy()
                messagebox.showinfo("成功", f"授权激活成功！\n\n过期时间：{result['expiry_time']}")
                self._reload_license()
            else:
                messagebox.showerror("错误", f"写入授权文件失败：{write_msg}")
        else:
            messagebox.showerror("激活失败", result)

    def _reload_license(self):
        """重新加载授权信息"""
        from core.license import get_effective_expiry, verify_license, generate_machine_code

        new_expiry = get_effective_expiry()
        self.expiry_time = new_expiry

        from core.license import get_hw_info
        hw_info = get_hw_info()
        machine_code = generate_machine_code(hw_info)

        valid, error = verify_license(machine_code)

        if valid:
            self._update_license_display()
            self.sidebar_status.config(fg='#22c55e')
        else:
            self.sidebar_status.config(fg='#fd7e14')

    def _copy_to_clipboard(self, window, text):
        """复制到剪贴板"""
        window.clipboard_clear()
        window.clipboard_append(text)
        messagebox.showinfo("成功", "已复制到剪贴板")
