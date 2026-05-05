# -*- coding: utf-8 -*-
"""
免审批导出工具 - 授权文件生成器 GUI 版本
用于为用户生成 license.dat 授权文件

功能：
- RSA 非对称加密签名，保证授权信息无法伪造
- AES 加密存储授权时间，避免明文篡改
- 机器码绑定授权
- 授权记录管理

使用方法：
    1. 用户运行 NqiTool_gui.py，获取机器码
    2. 用户将机器码发给管理员
    3. 管理员运行本脚本，输入机器码和授权截止时间
    4. 管理员将 license.dat 发给用户
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import base64
import struct
import json
import webbrowser
from datetime import datetime, timedelta

# 加密依赖
try:
    from Crypto.Cipher import AES as AES_Cipher
    from Crypto.Util.Padding import pad
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256
    from Crypto.Signature import pkcs1_15
except ModuleNotFoundError:
    from Cryptodome.Cipher import AES as AES_Cipher
    from Cryptodome.Util.Padding import pad
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Hash import SHA256
    from Cryptodome.Signature import pkcs1_15

# 配置
LICENSE_FILE = "license.dat"
PRIVATE_KEY_FILE = "private_key.pem"
LICENSE_AES_KEY = b"GMCCLicenseV2Key"  # 必须与 universal_extractor_gui.py 一致
RECORDS_FILE = "license_records.json"


class LicenseCreatorGUI:
    """授权文件生成器 GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("授权文件生成器")
        self.root.geometry("700x580")
        self.root.minsize(600, 500)
        self.root.resizable(True, True)

        # 加载授权记录
        self.records = self._load_records()

        self._create_widgets()
        self._check_prerequisites()
        self._load_records_to_list()

    def _create_widgets(self):
        """创建界面组件"""
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
        icon_label = tk.Label(icon_frame, text="🔑", font=('Segoe UI Emoji', 18),
                             bg='#1a6ce8', fg='white')
        icon_label.place(relx=0.5, rely=0.5, anchor='center')

        title_frame = tk.Frame(left_frame, bg='#165DFF')
        title_frame.pack(side=tk.LEFT)

        title = tk.Label(title_frame, text="授权文件生成器",
                        font=('Microsoft YaHei UI', 18, 'bold'),
                        bg='#165DFF', fg='white')
        title.pack(anchor='w')

        version = tk.Label(title_frame, text="License Creator v1.2",
                          font=('Microsoft YaHei UI', 9),
                          bg='#1a6ce8', fg='white',
                          padx=8, pady=2)
        version.pack(anchor='w', pady=(2, 0))

        # 标题栏右侧 - 状态
        self.right_frame = tk.Frame(self.header, bg='#165DFF')
        self.right_frame.pack(side=tk.RIGHT, padx=25, pady=12)

        self.status_dot = tk.Label(self.right_frame, text="●", font=('Arial', 14),
                            bg='#165DFF', fg='#a5b4fc')
        self.status_dot.pack(side=tk.LEFT)
        self.status_text = tk.Label(self.right_frame, text="就绪",
                              font=('Microsoft YaHei UI', 10),
                              bg='#165DFF', fg='white')
        self.status_text.pack(side=tk.LEFT, padx=(6, 0))

        # 主内容区域 - 标签页
        self.main_container = tk.Frame(self.root, bg='#f9fafb')
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 创建标签页
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 标签页1：授权生成
        self.tab_generate = tk.Frame(self.notebook, bg='#f9fafb')
        self.notebook.add(self.tab_generate, text="  🔒 生成授权 ")
        self._build_generate_tab()

        # 标签页2：授权记录
        self.tab_records = tk.Frame(self.notebook, bg='#f9fafb')
        self.notebook.add(self.tab_records, text="  📜 授权记录 ")
        self._build_records_tab()

        # 标签页3：读取授权
        self.tab_read = tk.Frame(self.notebook, bg='#f9fafb')
        self.notebook.add(self.tab_read, text="  📖 读取授权 ")
        self._build_read_tab()

    def _build_card(self, parent, title=None, **kwargs):
        """创建卡片容器"""
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

    def _build_generate_tab(self):
        """构建授权生成标签页"""
        content = tk.Frame(self.tab_generate, bg='#f9fafb')
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 状态信息卡片
        self._build_status_card(content)

        # 输入信息卡片
        self._build_input_card(content)

        # 快捷设置卡片
        self._build_quick_settings_card(content)

        # 操作按钮卡片
        self._build_action_card(content)

    def _build_status_card(self, parent):
        """构建状态信息卡片"""
        card = self._build_card(parent, "📋 状态信息")
        card.pack(fill=tk.X, pady=(0, 10))

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.X, padx=16, pady=12)

        # 获取授权工具根目录
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # 私钥文件状态
        key_frame = tk.Frame(body, bg='white')
        key_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(key_frame, text="私钥文件：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(side=tk.LEFT)

        self.key_status_label = tk.Label(key_frame, text="检查中...",
                                        font=('Microsoft YaHei UI', 9),
                                        bg='white', fg='#80868b')
        self.key_status_label.pack(side=tk.LEFT, padx=(0, 10))

        self.key_status_icon = tk.Label(key_frame, text="○", font=('Arial', 10, 'bold'),
                              bg='white', fg='#80868b')
        self.key_status_icon.pack(side=tk.LEFT)

        # 输出目录（固定为授权工具根目录）
        output_frame = tk.Frame(body, bg='white')
        output_frame.pack(fill=tk.X)

        tk.Label(output_frame, text="输出目录：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(side=tk.LEFT)

        self.output_path_label = tk.Label(output_frame, text=script_dir,
                                        font=('Microsoft YaHei UI', 9),
                                        bg='white', fg='#5f6368')
        self.output_path_label.pack(side=tk.LEFT, padx=(0, 5))

        # 打开目录按钮
        tk.Button(output_frame, text="📁 打开目录",
                 font=('Microsoft YaHei UI', 8),
                 bg='#f0f2f5', fg='#202124', bd=1,
                 cursor='arrow', relief='raised', padx=8, pady=2,
                 command=self._open_output_dir).pack(side=tk.LEFT)

        # 记录数量
        records_count_frame = tk.Frame(body, bg='white')
        records_count_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Label(records_count_frame, text="授权记录：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(side=tk.LEFT)

        self.records_count_label = tk.Label(records_count_frame, text=f"共 {len(self.records)} 条记录",
                                        font=('Microsoft YaHei UI', 9),
                                        bg='white', fg='#165DFF')
        self.records_count_label.pack(side=tk.LEFT, padx=(5, 0))

    def _build_input_card(self, parent):
        """构建输入信息卡片"""
        card = self._build_card(parent, "📝 授权信息")
        card.pack(fill=tk.X, pady=(0, 10))

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.X, padx=16, pady=12)

        # 机器码输入
        machine_frame = tk.Frame(body, bg='white')
        machine_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(machine_frame, text="机器码：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(anchor='w')

        self.machine_code_entry = tk.Entry(machine_frame,
                                          font=('Consolas', 10),
                                          relief='flat', bg='#f8f9fa', bd=0)
        self.machine_code_entry.pack(fill=tk.X, pady=(4, 0), ipady=6)

        tk.Label(machine_frame, text="（用户提供的64位十六进制机器码）",
                font=('Microsoft YaHei UI', 8),
                bg='white', fg='#9ca3af').pack(anchor='w', pady=(2, 0))

        # 备注输入
        note_frame = tk.Frame(body, bg='white')
        note_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(note_frame, text="备注：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(anchor='w')

        self.note_entry = tk.Entry(note_frame,
                                  font=('Microsoft YaHei UI', 10),
                                  relief='flat', bg='#f8f9fa', bd=0)
        self.note_entry.pack(fill=tk.X, pady=(4, 0), ipady=6)

        tk.Label(note_frame, text="（可选，用于标识此授权，如：姓名、设备名等）",
                font=('Microsoft YaHei UI', 8),
                bg='white', fg='#9ca3af').pack(anchor='w', pady=(2, 0))

        # 过期日期输入
        expiry_frame = tk.Frame(body, bg='white')
        expiry_frame.pack(fill=tk.X)

        tk.Label(expiry_frame, text="授权截止日期：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(anchor='w')

        date_row = tk.Frame(expiry_frame, bg='white')
        date_row.pack(pady=(4, 0))

        # 年份
        self.expiry_year_var = tk.IntVar(value=datetime.now().year)
        year_combo = ttk.Combobox(date_row, textvariable=self.expiry_year_var,
                                 values=list(range(2024, 2031)),
                                 width=5, state="readonly")
        year_combo.pack(side=tk.LEFT)

        tk.Label(date_row, text="年", font=('Microsoft YaHei UI', 9),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=(2, 8))

        # 月份
        self.expiry_month_var = tk.IntVar(value=datetime.now().month)
        month_combo = ttk.Combobox(date_row, textvariable=self.expiry_month_var,
                                   values=list(range(1, 13)),
                                   width=3, state="readonly")
        month_combo.pack(side=tk.LEFT)

        tk.Label(date_row, text="月", font=('Microsoft YaHei UI', 9),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=(2, 8))

        # 日期
        self.expiry_day_var = tk.IntVar(value=min(datetime.now().day, 28))
        day_combo = ttk.Combobox(date_row, textvariable=self.expiry_day_var,
                                 values=list(range(1, 32)),
                                 width=3, state="readonly")
        day_combo.pack(side=tk.LEFT)

        tk.Label(date_row, text="日", font=('Microsoft YaHei UI', 9),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=(2, 0))

        # 日期快捷按钮
        quick_date_row = tk.Frame(expiry_frame, bg='white')
        quick_date_row.pack(pady=(6, 0))

        tk.Label(quick_date_row, text="快捷设置：",
                font=('Microsoft YaHei UI', 8),
                bg='white', fg='#9ca3af').pack(side=tk.LEFT, padx=(0, 5))

        quick_btns = [
            ("+1个月", 1),
            ("+3个月", 3),
            ("+6个月", 6),
            ("+1年", 12),
            ("永久", 999),
        ]

        for text, months in quick_btns:
            tk.Button(quick_date_row, text=text, font=('Microsoft YaHei UI', 8),
                     bg='#e8eaed', fg='#202124', bd=1, padx=8, pady=2,
                     cursor='arrow', relief='raised',
                     command=lambda m=months: self._set_quick_expiry(m)).pack(side=tk.LEFT, padx=2)

    def _build_quick_settings_card(self, parent):
        """构建快捷设置卡片"""
        card = self._build_card(parent, "⚙ 批量授权预设")
        card.pack(fill=tk.X, pady=(0, 10))

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.X, padx=16, pady=12)

        # 预设选择
        preset_frame = tk.Frame(body, bg='white')
        preset_frame.pack(fill=tk.X)

        tk.Label(preset_frame, text="常用预设：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=(0, 10))

        presets = [
            ("试用版(7天)", 7),
            ("月度授权(30天)", 30),
            ("季度授权(90天)", 90),
            ("年度授权(365天)", 365),
        ]

        self.preset_btns = []
        for text, days in presets:
            btn = tk.Button(preset_frame, text=text, font=('Microsoft YaHei UI', 8),
                           bg='#e8f0fe', fg='#165DFF', bd=1, padx=10, pady=4,
                           cursor='hand2', relief='raised',
                           command=lambda d=days: self._apply_preset(d))
            btn.pack(side=tk.LEFT, padx=3)
            self.preset_btns.append(btn)

        # 提示信息
        hint_frame = tk.Frame(body, bg='white')
        hint_frame.pack(fill=tk.X, pady=(8, 0))

        self.hint_label = tk.Label(hint_frame, text="💡 提示：选择预设将自动计算过期日期",
                                   font=('Microsoft YaHei UI', 8),
                                   bg='white', fg='#9ca3af')
        self.hint_label.pack(side=tk.LEFT)

    def _build_action_card(self, parent):
        """构建操作按钮卡片"""
        card = tk.Frame(parent, bg='white')
        card.pack(fill=tk.X)

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.X, padx=16, pady=12)

        # 模式选择
        mode_frame = tk.Frame(body, bg='white')
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(mode_frame, text="输出模式：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(side=tk.LEFT)

        self.output_mode_var = tk.StringVar(value="serial")  # 默认序列号模式

        serial_rb = tk.Radiobutton(mode_frame, text="🔑 生成序列号（推荐）",
                                  variable=self.output_mode_var, value="serial",
                                  font=('Microsoft YaHei UI', 9),
                                  bg='white', fg='#202124',
                                  command=self._on_mode_changed)
        serial_rb.pack(side=tk.LEFT, padx=(10, 15))

        zip_rb = tk.Radiobutton(mode_frame, text="📦 生成压缩包",
                                variable=self.output_mode_var, value="zip",
                                font=('Microsoft YaHei UI', 9),
                                bg='white', fg='#202124',
                                command=self._on_mode_changed)
        zip_rb.pack(side=tk.LEFT)

        # 序列号输出区域（默认隐藏，序列号模式时显示）
        self.serial_output_frame = tk.Frame(body, bg='white')
        self.serial_output_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(self.serial_output_frame, text="验证序列号：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(anchor='w')

        output_frame = tk.Frame(self.serial_output_frame, bg='#f8f9fa')
        output_frame.pack(fill=tk.X, pady=(5, 0))

        self.serial_output = tk.Text(output_frame, height=3, font=('Consolas', 9),
                                   relief='flat', bg='#f8f9fa', wrap=tk.WORD)
        self.serial_output.pack(fill=tk.X, padx=5, pady=5)
        self.serial_output.insert("1.0", "生成后将显示验证序列号，请复制给用户")
        self.serial_output.config(state='disabled', fg='#9ca3af')

        # 复制按钮
        copy_row = tk.Frame(self.serial_output_frame, bg='white')
        copy_row.pack(fill=tk.X)

        tk.Button(copy_row, text="📋 复制序列号",
                 font=('Microsoft YaHei UI', 9),
                 bg='#f0f2f5', fg='#202124', bd=1,
                 cursor='arrow', relief='raised', padx=10, pady=4,
                 command=self._copy_serial_number).pack(side=tk.LEFT)

        # 生成按钮
        btn_frame = tk.Frame(body, bg='white')
        btn_frame.pack(fill=tk.X)

        self.generate_btn = tk.Button(btn_frame, text="🔑 生成序列号",
                               font=('Microsoft YaHei UI', 11, 'bold'),
                               bg='#165DFF', fg='white', bd=1,
                               cursor='hand2', relief='raised', padx=25, pady=8,
                               command=self._on_generate)
        self.generate_btn.pack(side=tk.LEFT)

        # 清除按钮
        tk.Button(btn_frame, text="🔄 重置",
                 font=('Microsoft YaHei UI', 10),
                 bg='#f0f2f5', fg='#202124', bd=1,
                 cursor='arrow', relief='raised', padx=18, pady=8,
                 command=self._on_reset).pack(side=tk.LEFT, padx=(10, 0))

        # 打开目录按钮
        tk.Button(btn_frame, text="📁 打开目录",
                 font=('Microsoft YaHei UI', 10),
                 bg='#f0f2f5', fg='#202124', bd=1,
                 cursor='arrow', relief='raised', padx=14, pady=8,
                 command=self._open_output_dir).pack(side=tk.RIGHT)

    def _on_mode_changed(self):
        """模式切换事件"""
        mode = self.output_mode_var.get()
        if mode == "serial":
            self.generate_btn.config(text="🔑 生成序列号")
            self.serial_output_frame.pack(fill=tk.X, pady=(0, 10))
        else:
            self.generate_btn.config(text="📦 生成压缩包")
            self.serial_output_frame.pack_forget()

    def _build_records_tab(self):
        """构建授权记录标签页"""
        content = tk.Frame(self.tab_records, bg='#f9fafb')
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 工具栏
        toolbar = tk.Frame(content, bg='white')
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # 统计信息
        stats_frame = tk.Frame(toolbar, bg='white')
        stats_frame.pack(side=tk.LEFT)

        tk.Label(stats_frame, text="📜 授权历史记录",
                font=('Microsoft YaHei UI', 14, 'bold'),
                bg='white', fg='#374151').pack(side=tk.LEFT, padx=(0, 10))

        self.records_count_label_tab = tk.Label(stats_frame, text=f"共 {len(self.records)} 条记录",
                                        font=('Microsoft YaHei UI', 10),
                                        bg='white', fg='#165DFF')
        self.records_count_label_tab.pack(side=tk.LEFT)

        # 按钮组
        btn_group = tk.Frame(toolbar, bg='white')
        btn_group.pack(side=tk.RIGHT)

        tk.Button(btn_group, text="🔄 刷新",
                 font=('Microsoft YaHei UI', 9),
                 bg='#f0f2f5', fg='#202124', bd=1,
                 cursor='arrow', relief='raised', padx=12, pady=4,
                 command=self._refresh_records).pack(side=tk.LEFT, padx=3)

        tk.Button(btn_group, text="📤 导出Excel",
                 font=('Microsoft YaHei UI', 9),
                 bg='#22c55e', fg='white', bd=1,
                 cursor='arrow', relief='raised', padx=12, pady=4,
                 command=self._export_records).pack(side=tk.LEFT, padx=3)

        tk.Button(btn_group, text="🗑 清空记录",
                 font=('Microsoft YaHei UI', 9),
                 bg='#fee2e2', fg='#dc2626', bd=1,
                 cursor='arrow', relief='raised', padx=12, pady=4,
                 command=self._clear_records).pack(side=tk.LEFT, padx=3)

        # 搜索框
        search_frame = tk.Frame(content, bg='white')
        search_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(search_frame, text="🔍 搜索：",
                font=('Microsoft YaHei UI', 9),
                bg='white', fg='#5f6368').pack(side=tk.LEFT, padx=(0, 5))

        self.search_entry = tk.Entry(search_frame, font=('Microsoft YaHei UI', 10),
                               relief='flat', bg='#f8f9fa', bd=0, width=30)
        self.search_entry.pack(side=tk.LEFT, ipady=4)
        self.search_entry.bind('<KeyRelease>', self._on_search_change)

        # 表格容器
        table_container = tk.Frame(content, bg='white')
        table_container.pack(fill=tk.BOTH, expand=True)

        # 创建表格
        columns = ('序号', '机器码', '备注', '过期时间', '首次授权', '最近授权', '次数')
        self.records_tree = ttk.Treeview(table_container, columns=columns, show='headings')

        # 设置列
        self.records_tree.heading('序号', text='序号')
        self.records_tree.heading('机器码', text='机器码')
        self.records_tree.heading('备注', text='备注')
        self.records_tree.heading('过期时间', text='过期时间')
        self.records_tree.heading('首次授权', text='首次授权')
        self.records_tree.heading('最近授权', text='最近授权')
        self.records_tree.heading('次数', text='次数')

        self.records_tree.column('序号', width=50, anchor='center')
        self.records_tree.column('机器码', width=200)
        self.records_tree.column('备注', width=100)
        self.records_tree.column('过期时间', width=90)
        self.records_tree.column('首次授权', width=130)
        self.records_tree.column('最近授权', width=130)
        self.records_tree.column('次数', width=50, anchor='center')

        # 滚动条
        v_scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.records_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_container, orient="horizontal", command=self.records_tree.xview)
        self.records_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.records_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # 绑定事件
        self.records_tree.bind('<Double-1>', self._on_record_double_click)
        self.records_tree.bind('<Button-3>', self._show_context_menu)

    def _check_prerequisites(self):
        """检查前置条件"""
        if os.path.exists(PRIVATE_KEY_FILE):
            self.key_status_label.config(text=PRIVATE_KEY_FILE, fg='#22c55e')
            self.key_status_icon.config(text="●", fg='#22c55e')
            self._update_status("就绪", '#22c55e')
        else:
            self.key_status_label.config(
                text=f"未找到 {PRIVATE_KEY_FILE}，请先运行 generate_rsa_keys.py 生成密钥",
                fg='#ef4444'
            )
            self.key_status_icon.config(text="○", fg='#ef4444')
            self._update_status("私钥缺失", '#ef4444')
            self.generate_btn.config(state=tk.DISABLED)

    def _update_status(self, text, color='#fbbf24'):
        """更新状态显示"""
        self.status_text.config(text=text)
        self.status_dot.config(fg=color)

    def _set_quick_expiry(self, months):
        """设置快捷过期日期"""
        if months == 999:  # 永久
            self.expiry_year_var.set(2099)
            self.expiry_month_var.set(12)
            self.expiry_day_var.set(31)
            self.hint_label.config(text="💡 已设置为永久授权")
        else:
            new_date = datetime.now() + relativedelta(months=months)
            self.expiry_year_var.set(new_date.year)
            self.expiry_month_var.set(new_date.month)
            self.expiry_day_var.set(new_date.day)
            self.hint_label.config(text=f"💡 已设置为 +{months} 个月后过期")

    def _apply_preset(self, days):
        """应用预设"""
        new_date = datetime.now() + timedelta(days=days)
        self.expiry_year_var.set(new_date.year)
        self.expiry_month_var.set(new_date.month)
        self.expiry_day_var.set(new_date.day)
        self.hint_label.config(text=f"💡 已应用预设：{days}天后过期 ({new_date.strftime('%Y-%m-%d')})")

    def _on_reset(self):
        """重置表单"""
        self.machine_code_entry.delete(0, tk.END)
        self.note_entry.delete(0, tk.END)
        self.expiry_year_var.set(datetime.now().year)
        self.expiry_month_var.set(datetime.now().month)
        self.expiry_day_var.set(datetime.now().day)
        self.hint_label.config(text="💡 提示：选择预设将自动计算过期日期")
        # 重置序列号输出框
        self.serial_output.config(state='normal')
        self.serial_output.delete("1.0", tk.END)
        self.serial_output.insert("1.0", "生成后将显示验证序列号，请复制给用户")
        self.serial_output.config(state='disabled', fg='#9ca3af')
        self._check_prerequisites()

    def _open_output_dir(self):
        """打开输出目录"""
        output_dir = self.output_path_label.cget("text")
        if os.path.exists(output_dir):
            webbrowser.open(output_dir)
        else:
            os.makedirs(output_dir, exist_ok=True)
            webbrowser.open(output_dir)

    def _load_records(self):
        """加载授权记录"""
        try:
            if os.path.exists(RECORDS_FILE):
                with open(RECORDS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载记录失败: {e}")
        return []

    def _save_records(self):
        """保存授权记录"""
        try:
            with open(RECORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
            self.records_count_label.config(text=f"共 {len(self.records)} 条记录")
            self.records_count_label_tab.config(text=f"共 {len(self.records)} 条记录")
        except Exception as e:
            messagebox.showerror("错误", f"保存记录失败: {e}")

    def _add_record(self, machine_code, note):
        """添加授权记录"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 查找是否已存在该机器码的记录
        existing = None
        for i, record in enumerate(self.records):
            if record['machine_code'] == machine_code:
                existing = i
                break

        if existing is not None:
            # 更新现有记录
            self.records[existing]['last_generate_time'] = now
            self.records[existing]['count'] += 1
            if note:
                self.records[existing]['note'] = note
        else:
            # 添加新记录
            self.records.insert(0, {
                'machine_code': machine_code,
                'first_generate_time': now,
                'last_generate_time': now,
                'count': 1,
                'note': note or ''
            })

        self._save_records()
        self._load_records_to_list()

    def _load_records_to_list(self, search_text=""):
        """加载记录到列表"""
        # 清空现有数据
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)

        search_text = search_text.lower().strip()

        for i, record in enumerate(self.records, 1):
            machine_code = record['machine_code']
            note = record.get('note', '')
            first_time = record['first_generate_time']
            last_time = record['last_generate_time']
            count = record['count']

            # 搜索过滤
            if search_text:
                if (search_text not in machine_code.lower() and
                    search_text not in note.lower() and
                    search_text not in str(count)):
                    continue

            # 截取机器码显示
            display_code = f"{machine_code[:8]}...{machine_code[-8:]}"

            self.records_tree.insert('', tk.END, values=(
                i, display_code, note, "（见license）", first_time[:10], last_time[:10], count
            ))

        self.records_count_label.config(text=f"共 {len(self.records)} 条记录")
        self.records_count_label_tab.config(text=f"共 {len(self.records)} 条记录")

    def _on_search_change(self, event=None):
        """搜索变化"""
        search_text = self.search_entry.get()
        self._load_records_to_list(search_text)

    def _refresh_records(self):
        """刷新记录"""
        self.records = self._load_records()
        self.search_entry.delete(0, tk.END)
        self._load_records_to_list()

    def _clear_records(self):
        """清空记录"""
        if not self.records:
            messagebox.showinfo("提示", "暂无记录可清空")
            return

        result = messagebox.askyesno("确认清空", "确定要清空所有授权记录吗？\n此操作不可恢复。")
        if result:
            self.records = []
            self._save_records()
            self._load_records_to_list()
            messagebox.showinfo("成功", "记录已清空")

    def _show_context_menu(self, event):
        """显示右键菜单"""
        item = self.records_tree.identify_row(event.y)
        if item:
            self.records_tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            record_idx = int(self.records_tree.item(item)['values'][0]) - 1
            record = self.records[record_idx]
            menu.add_command(label="📋 复制机器码",
                           command=lambda: self._copy_to_clipboard(record['machine_code']))
            menu.add_command(label="📋 复制完整信息",
                           command=lambda: self._copy_full_info(record))
            menu.add_separator()
            menu.add_command(label="🗑 删除记录",
                           command=lambda: self._delete_single_record(record_idx))
            menu.post(event.x_root, event.y_root)

    def _copy_to_clipboard(self, text):
        """复制到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("成功", "已复制到剪贴板")

    def _copy_full_info(self, record):
        """复制完整信息"""
        info = f"""机器码：{record['machine_code']}
备注：{record.get('note', '无')}
首次授权：{record['first_generate_time']}
最近授权：{record['last_generate_time']}
授权次数：{record['count']}"""
        self._copy_to_clipboard(info)

    def _delete_single_record(self, idx):
        """删除单条记录"""
        result = messagebox.askyesno("确认删除", "确定要删除这条记录吗？")
        if result:
            del self.records[idx]
            self._save_records()
            self._load_records_to_list()

    def _on_record_double_click(self, event):
        """双击记录填充机器码"""
        selection = self.records_tree.selection()
        if selection:
            item = self.records_tree.item(selection[0])
            values = item['values']
            if values:
                # 查找完整机器码
                idx = int(values[0]) - 1
                if 0 <= idx < len(self.records):
                    record = self.records[idx]
                    # 切换到生成标签页
                    self.notebook.select(0)
                    # 填充数据
                    self.machine_code_entry.delete(0, tk.END)
                    self.machine_code_entry.insert(0, record['machine_code'])
                    self.note_entry.delete(0, tk.END)
                    self.note_entry.insert(0, record.get('note', ''))

    def _validate_machine_code(self, machine_code):
        """验证机器码格式"""
        machine_code = machine_code.strip()
        if len(machine_code) != 64:
            return False, f"机器码长度应为64位，当前为{len(machine_code)}位"
        try:
            int(machine_code, 16)
            return True, None
        except ValueError:
            return False, "机器码包含非法字符（非十六进制）"

    def _load_private_key(self):
        """加载RSA私钥"""
        if not os.path.exists(PRIVATE_KEY_FILE):
            return None
        with open(PRIVATE_KEY_FILE, "rb") as f:
            return RSA.import_key(f.read())

    def _aes_encrypt(self, plain_text, key):
        """AES加密"""
        import os
        iv = os.urandom(16)
        cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
        padded_data = pad(plain_text.encode("utf-8"), 16)
        encrypted_data = cipher.encrypt(padded_data)
        return iv + encrypted_data

    def _rsa_sign(self, data, private_key):
        """RSA签名"""
        h = SHA256.new(data.encode("utf-8"))
        signature = pkcs1_15.new(private_key).sign(h)
        return base64.b64encode(signature).decode("utf-8")

    def _create_license(self, machine_code, expiry_date):
        """生成授权文件"""
        import zipfile

        # 验证机器码
        valid, error = self._validate_machine_code(machine_code)
        if not valid:
            return False, error

        # 加载私钥
        private_key = self._load_private_key()
        if not private_key:
            return False, f"未找到私钥文件 {PRIVATE_KEY_FILE}，请先运行 generate_rsa_keys.py 生成密钥"

        # 生成授权时间字符串
        expiry_time_str = expiry_date.strftime("%Y-%m-%d 23:59:59")

        # 首次运行时间（生成授权时的时间）
        first_run_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. 用AES加密（新格式：过期时间|首次运行时间）
        encrypted_data = self._aes_encrypt(f"{expiry_time_str}|{first_run_time_str}", LICENSE_AES_KEY)

        # 2. 对机器码(SN)进行RSA签名
        signature = self._rsa_sign(machine_code, private_key)

        # 3. 组装license文件格式：SN长度(4字节) + SN + 签名 + | + AES加密(过期时间|首次运行时间)
        sn_bytes = machine_code.encode("utf-8")
        sn_len = len(sn_bytes)
        license_data = struct.pack(">I", sn_len) + sn_bytes + signature.encode("utf-8") + b"|" + encrypted_data

        # 4. 获取授权工具根目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = script_dir

        # 5. 创建以机器码命名的压缩包
        zip_filename = f"{machine_code}.zip"
        zip_path = os.path.join(output_dir, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr(LICENSE_FILE, license_data)

        return True, f"授权文件已生成：{os.path.abspath(zip_path)}\n\n压缩包内容：license.dat\n机器码：{machine_code}\n过期时间：{expiry_time_str}\n\n📌 请将 {zip_filename} 发送给用户"

    def _create_serial_number(self, machine_code, expiry_date):
        """生成验证序列号"""
        import json

        # 验证机器码
        valid, error = self._validate_machine_code(machine_code)
        if not valid:
            return False, error

        # 加载私钥
        private_key = self._load_private_key()
        if not private_key:
            return False, f"未找到私钥文件 {PRIVATE_KEY_FILE}，请先运行 generate_rsa_keys.py 生成密钥"

        # 生成授权时间字符串
        expiry_time_str = expiry_date.strftime("%Y-%m-%d 23:59:59")

        # 首次运行时间（生成授权时的时间）
        first_run_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建授权数据
        version = "1"
        auth_data = {
            "v": version,
            "sn": machine_code,
            "exp": expiry_time_str,
            "first": first_run_time_str
        }

        # JSON 序列化为字符串
        data_str = json.dumps(auth_data, separators=(',', ':'))

        # AES 加密
        encrypted_data = self._aes_encrypt(data_str, LICENSE_AES_KEY)

        # 对机器码进行 RSA 签名
        signature = self._rsa_sign(machine_code, private_key)

        # 组装数据：版本(1) + 签名长度(4) + 签名 + 加密数据
        signature_bytes = signature.encode('utf-8')
        signature_len_bytes = struct.pack(">I", len(signature_bytes))

        combined = b'\x01' + signature_len_bytes + signature_bytes + encrypted_data

        # Base64 编码
        encoded = base64.b64encode(combined).decode('utf-8')

        # 格式化序列号（每8位加一杠）
        parts = [encoded[i:i+8] for i in range(0, len(encoded), 8)]
        serial_number = "NQI-" + "-".join(parts)

        # 返回纯序列号（适合显示和复制）
        return True, serial_number

    def _on_generate(self):
        """生成按钮点击事件"""
        machine_code = self.machine_code_entry.get().strip()
        note = self.note_entry.get().strip()

        # 验证机器码
        if not machine_code:
            messagebox.showwarning("输入错误", "请输入机器码")
            return

        valid, error = self._validate_machine_code(machine_code)
        if not valid:
            messagebox.showerror("机器码错误", error)
            return

        # 获取过期日期
        try:
            expiry_date = datetime(
                self.expiry_year_var.get(),
                self.expiry_month_var.get(),
                self.expiry_day_var.get()
            )
        except ValueError as e:
            messagebox.showerror("日期错误", f"日期无效：{e}")
            return

        # 检查私钥
        if not os.path.exists(PRIVATE_KEY_FILE):
            messagebox.showerror("错误", f"未找到私钥文件 {PRIVATE_KEY_FILE}，请先运行 generate_rsa_keys.py 生成密钥")
            return

        # 禁用按钮，显示正在生成
        mode = self.output_mode_var.get()
        self.generate_btn.config(state=tk.DISABLED, text="正在生成...")
        self._update_status("生成中...", '#fbbf24')

        # 根据模式生成
        if mode == "serial":
            success, message = self._create_serial_number(machine_code, expiry_date)
        else:
            success, message = self._create_license(machine_code, expiry_date)

        if success:
            # 添加授权记录
            self._add_record(machine_code, note)
            self._update_status("生成成功", '#22c55e')
            self.key_status_icon.config(text="●", fg='#22c55e')

            # 序列号模式：输出到文本框
            if mode == "serial":
                self.serial_output.config(state='normal')
                self.serial_output.delete("1.0", tk.END)
                self.serial_output.insert("1.0", message)
                self.serial_output.config(fg='#202124')
                messagebox.showinfo("成功", "验证序列号已生成，请在下方复制")
            else:
                messagebox.showinfo("成功", message)
        else:
            self._update_status("生成失败", '#ef4444')
            messagebox.showerror("失败", message)

        # 恢复按钮
        self.generate_btn.config(state=tk.NORMAL)

    def _export_records(self):
        """导出记录到Excel"""
        try:
            import pandas as pd
        except ImportError:
            messagebox.showerror("错误", "需要安装 pandas 库才能导出 Excel")
            return

        # 收集所有记录数据
        data = []
        for record in self.records:
            data.append({
                '机器码': record['machine_code'],
                '备注': record.get('note', ''),
                '首次授权时间': record['first_generate_time'],
                '最近授权时间': record['last_generate_time'],
                '授权次数': record['count']
            })

        if not data:
            messagebox.showinfo("提示", "暂无记录可导出")
            return

        # 选择保存位置
        file_path = filedialog.asksaveasfilename(
            title="保存授权记录",
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")],
            initialfile=f"授权记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if file_path:
            try:
                df = pd.DataFrame(data)
                df.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo("成功", f"记录已导出到：\n{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败：{e}")

    def _copy_serial_number(self):
        """复制序列号到剪贴板"""
        serial = self.serial_output.get("1.0", tk.END).strip()
        if serial and serial != "生成后将显示验证序列号，请复制给用户":
            self.root.clipboard_clear()
            self.root.clipboard_append(serial)
            messagebox.showinfo("成功", "序列号已复制到剪贴板")
        else:
            messagebox.showwarning("提示", "没有可复制的序列号")

    def _build_read_tab(self):
        """构建读取授权标签页"""
        content = tk.Frame(self.tab_read, bg='#f9fafb')
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 标题
        title_frame = tk.Frame(content, bg='white')
        title_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(title_frame, text="📖 读取授权文件",
                font=('Microsoft YaHei UI', 16, 'bold'),
                bg='white', fg='#374151').pack(side=tk.LEFT, padx=10, pady=10)

        tk.Label(title_frame, text="导入 license.dat 文件查看授权信息",
                font=('Microsoft YaHei UI', 10),
                bg='white', fg='#9ca3af').pack(side=tk.RIGHT, padx=10, pady=10)

        # 文件选择卡片
        card = self._build_card(content, "📂 选择文件")
        card.pack(fill=tk.X, pady=(0, 15))

        body = tk.Frame(card, bg='white')
        body.pack(fill=tk.X, padx=16, pady=12)

        # 文件路径显示和选择
        file_frame = tk.Frame(body, bg='white')
        file_frame.pack(fill=tk.X)

        tk.Label(file_frame, text="授权文件：",
                font=('Microsoft YaHei UI', 9, 'bold'),
                bg='white', fg='#5f6368').pack(side=tk.LEFT)

        self.license_file_label = tk.Label(file_frame, text="未选择文件",
                                        font=('Microsoft YaHei UI', 9),
                                        bg='white', fg='#80868b', width=40)
        self.license_file_label.pack(side=tk.LEFT, padx=(5, 10))

        tk.Button(file_frame, text="📂 浏览...",
                 font=('Microsoft YaHei UI', 9),
                 bg='#165DFF', fg='white', bd=1,
                 cursor='hand2', relief='raised', padx=15, pady=4,
                 command=self._browse_license_file).pack(side=tk.LEFT)

        # 读取按钮
        btn_frame = tk.Frame(body, bg='white')
        btn_frame.pack(fill=tk.X, pady=(15, 0))

        self.read_btn = tk.Button(btn_frame, text="🔍 读取授权信息",
                 font=('Microsoft YaHei UI', 11, 'bold'),
                 bg='#165DFF', fg='white', bd=1,
                 cursor='hand2', relief='raised', padx=25, pady=8,
                 command=self._read_license_info)
        self.read_btn.pack(side=tk.LEFT)

        tk.Button(btn_frame, text="🔄 清空",
                 font=('Microsoft YaHei UI', 10),
                 bg='#f0f2f5', fg='#202124', bd=1,
                 cursor='arrow', relief='raised', padx=18, pady=8,
                 command=self._clear_license_info).pack(side=tk.LEFT, padx=(10, 0))

        # 授权信息显示卡片
        self.info_card = self._build_card(content, "📋 授权信息")
        self.info_card.pack(fill=tk.X, pady=(0, 15))

        info_body = tk.Frame(self.info_card, bg='white')
        info_body.pack(fill=tk.X, padx=16, pady=12)

        # 存储控件引用
        self.license_info_labels = {}

        info_items = [
            ('machine_code', '机器码：', '未读取'),
            ('expiry_date', '过期时间：', '未读取'),
            ('first_run_time', '首次运行时间：', '未读取'),
            ('status', '授权状态：', '未读取'),
        ]

        for key, label_text, default_value in info_items:
            row_frame = tk.Frame(info_body, bg='white')
            row_frame.pack(fill=tk.X, pady=(0, 8))

            tk.Label(row_frame, text=label_text,
                    font=('Microsoft YaHei UI', 9, 'bold'),
                    bg='white', fg='#5f6368', width=15, anchor='w').pack(side=tk.LEFT)

            value_label = tk.Label(row_frame, text=default_value,
                                  font=('Microsoft YaHei UI', 10),
                                  bg='white', fg='#374151')
            value_label.pack(side=tk.LEFT)
            self.license_info_labels[key] = value_label

        # 机器码特殊处理（显示完整）
        self.license_info_labels['machine_code'].config(font=('Consolas', 9), fg='#5f6368')

    def _browse_license_file(self):
        """浏览授权文件"""
        file_path = filedialog.askopenfilename(
            title="选择授权文件",
            filetypes=[("License 文件", "*.dat *.zip"), ("所有文件", "*.*")]
        )
        if file_path:
            self.selected_license_path = file_path
            self.license_file_label.config(text=file_path, fg='#374151')

    def _read_license_info(self):
        """读取授权文件信息"""
        if not hasattr(self, 'selected_license_path') or not self.selected_license_path:
            messagebox.showwarning("提示", "请先选择授权文件")
            return

        license_path = self.selected_license_path
        if not os.path.exists(license_path):
            messagebox.showerror("错误", "文件不存在")
            return

        try:
            # 如果是zip文件，先解压
            import zipfile
            if license_path.endswith('.zip'):
                with zipfile.ZipFile(license_path, 'r') as zipf:
                    if 'license.dat' in zipf.namelist():
                        license_data = zipf.read('license.dat')
                    else:
                        messagebox.showerror("错误", "压缩包中未找到 license.dat 文件")
                        return
            else:
                with open(license_path, 'rb') as f:
                    license_data = f.read()

            # 解析license数据
            parts = license_data.split(b'|')
            if len(parts) < 2:
                messagebox.showerror("错误", "授权文件格式错误")
                return

            # 解析机器码
            sn_len_bytes = parts[0][:4]
            sn_len = struct.unpack(">I", sn_len_bytes)[0]
            sn = parts[0][4:4+sn_len].decode('utf-8')
            signature = parts[0][4+sn_len:].decode('utf-8')
            encrypted_data = parts[1]

            # 解密过期时间
            encrypted_bytes = base64.b64decode(encrypted_data)
            decrypted = self._aes_decrypt_internal(encrypted_bytes, LICENSE_AES_KEY)
            expiry_str, first_run_str = decrypted.split('|')

            # 更新界面
            self.license_info_labels['machine_code'].config(text=sn)
            self.license_info_labels['expiry_date'].config(text=expiry_str)
            self.license_info_labels['first_run_time'].config(text=first_run_str)

            # 检查授权状态
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expiry_date:
                status_text = "已过期"
                status_color = '#dc2626'
            else:
                remaining = (expiry_date - datetime.now()).days
                status_text = f"有效（剩余 {remaining} 天）"
                status_color = '#22c55e'

            self.license_info_labels['status'].config(text=status_text, fg=status_color)

        except Exception as e:
            messagebox.showerror("错误", f"读取授权文件失败：{str(e)}")

    def _aes_decrypt_internal(self, encrypted_data, key):
        """内部AES解密方法"""
        iv = encrypted_data[:16]
        cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
        decrypted_data = cipher.decrypt(encrypted_data[16:])
        return self._unpad(decrypted_data, 16).decode('utf-8')

    def _unpad(self, data, block_size):
        """移除PKCS7 padding"""
        padding_len = data[-1]
        if padding_len > block_size:
            raise ValueError("Invalid padding")
        return data[:-padding_len]

    def _clear_license_info(self):
        """清空授权信息"""
        if hasattr(self, 'selected_license_path'):
            delattr(self, 'selected_license_path')
        self.license_file_label.config(text="未选择文件", fg='#80868b')
        self.license_info_labels['machine_code'].config(text="未读取")
        self.license_info_labels['expiry_date'].config(text="未读取")
        self.license_info_labels['first_run_time'].config(text="未读取")
        self.license_info_labels['status'].config(text="未读取", fg='#374151')


def main():
    """主函数"""
    # 尝试导入 dateutil，如果失败则使用内置实现
    try:
        from dateutil.relativedelta import relativedelta
    except ImportError:
        from datetime import date
        class relativedelta:
            def __init__(self, months=0, days=0):
                self.months = months
                self.days = days

            def __radd__(self, other):
                if isinstance(other, datetime):
                    result = other
                    # 简单月份计算
                    month = result.month + self.months
                    year = result.year + (month - 1) // 12
                    month = (month - 1) % 12 + 1
                    day = min(result.day, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
                    if month == 2 and (year % 4 == 0 and year % 100 != 0 or year % 400 == 0):
                        day = 29
                    return result.replace(year=year, month=month, day=day) + timedelta(days=self.days)
                return other

    root = tk.Tk()
    app = LicenseCreatorGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
