# -*- coding: utf-8 -*-
"""
GUI组件模块
提供自定义的GUI组件和辅助类
"""

import tkinter as tk
from tkinter import ttk
import logging
from datetime import datetime, timedelta

# 字段配置已迁移至 gui/field_configs.json（经 gui/field_configs.py 薄加载器动态加载），
# 修改字段配置只需编辑 JSON 文件，无需改代码。
# 导入字段配置
from gui.field_configs import (
    INTERFERENCE_5G_FIELDS, INTERFERENCE_4G_FIELDS, INTERFERENCE_5G_ZIMANG_FIELDS,
    VOLTE_4G_VOICE_FIELDS, EPSFB_4G_VOICE_FIELDS,
    VOLTE_4G_VOICE_WARNING_FIELDS, EPSFB_4G_VOICE_WARNING_FIELDS,
    CAPACITY_5G_FIELDS, CAPACITY_5G_WEEK_FIELDS,
    IMPORTANT_SCENE_FIELDS, IMPORTANT_SCENE_WEEK_FIELDS,
    GONGCAN_5G_FIELDS, GONGCAN_4G_FIELDS,
    MR_5G_FIELDS, MR_4G_FIELDS,
    VOLTE_WARNING_FIELDS, VONR_WARNING_FIELDS, EPSFB_WARNING_FIELDS,
    KPI_4G_FIELDS, KPI_5G_FIELDS,
    VOICE_5G_FIELDS,
    FLOW_HOT_SPOT_STATION_FIELDS,
    SECTORS_4G_5G_FIELDS,
    SYNTHESIZE_45G_CONFIG,
)

# 导入硬编码Payload模板
from gui.payload_templates import (
    get_5g_interference_payload, get_4g_interference_payload, get_5g_interference_zimang_payload,
    get_5g_capacity_payload, get_5g_capacity_week_payload,
    get_important_scene_payload, get_important_scene_week_payload,
    get_volte_warning_payload, get_epsfb_warning_payload, get_vonr_warning_payload,
    get_4g_wanchenglv_payload, get_5g_wanchenglv_payload,
    get_volte_payload, get_epsfb_payload, get_5g_voice_payload,
    get_5g_gongcan_payload, get_4g_gongcan_payload,
    get_5g_kpi_payload, get_4g_kpi_payload,
    get_5g_mr_payload, get_4g_mr_payload,
    get_flow_hot_spot_station_payload,
    get_common_pm_cell_day_v3_payload,
    get_sectors_4g_5g_payload,
)
from gui.city_table_configs import CITY_TABLE_CONFIGS


class LogTextHandler(logging.Handler):
    """日志处理器 - 将简洁日志输出到界面Text组件（优化版）

    优化点：
    1. 批量写入：使用队列缓存日志，批量写入减少UI线程压力
    2. 减少滚动：只在必要时滚动到底部
    3. 预定义标签：避免每次都调用 tag_config
    4. 防抖机制：合并短时间内的多次写入
    """

    # 预定义的标签颜色
    COLOR_MAP = {
        'WARNING': '#FFA500',
        'ERROR': '#FF0000',
        'CRITICAL': '#FF0000',
        'INFO': '#333333',
        'SUCCESS': '#00AA00',
    }

    def __init__(self, text_widget, batch_interval=50, max_lines=500):
        """
        Args:
            text_widget: tk.Text 组件
            batch_interval: 批量写入间隔（毫秒），默认50ms
            max_lines: 最大保留行数，默认500行
        """
        super().__init__()
        self.text_widget = text_widget
        self.setLevel(logging.INFO)
        self.formatter = logging.Formatter('%(message)s')
        self.batch_interval = batch_interval
        self.max_lines = max_lines

        # 批量写入相关
        self._pending_messages = []  # 待写入的消息队列
        self._after_id = None       # 定时器ID
        self._last_scroll_pos = 1.0  # 上次滚动位置（1.0=底部）

        # 预定义所有标签（避免运行时创建）
        self._setup_tags()

        # 绑定滚动事件，检测用户是否在底部
        self.text_widget.bind('<Configure>', self._on_widget_configure)
        self.text_widget.bind('<MouseWheel>', self._on_scroll)
        self.text_widget.bind('<ButtonPress>', self._on_scroll)
        self.text_widget.bind('<KeyRelease>', self._on_scroll)

    def _setup_tags(self):
        """预定义所有标签样式"""
        for name, color in self.COLOR_MAP.items():
            self.text_widget.tag_configure(name, foreground=color)

    def _on_widget_configure(self, event=None):
        """检测组件大小变化"""
        pass

    def _on_scroll(self, event=None):
        """用户滚动时记录位置"""
        try:
            # 获取当前滚动位置
            scrollinfo = self.text_widget.yview()
            self._last_scroll_pos = scrollinfo[1]  # 记录底部位置
        except Exception:
            pass

    def emit(self, record):
        """接收日志记录"""
        if record.levelno < logging.INFO:
            return

        try:
            msg = self.formatter.format(record)
            if not msg.endswith('\n'):
                msg += '\n'

            levelname = record.levelname
            if levelname not in self.COLOR_MAP:
                levelname = 'INFO'

            # 缓存消息
            self._pending_messages.append((msg, levelname))

            # 如果没有待执行的定时器，设置一个新的
            if self._after_id is None:
                self._after_id = self.text_widget.after(
                    self.batch_interval,
                    self._flush
                )
        except Exception:
            pass

    def _flush(self):
        """批量写入消息到 Text 组件"""
        if not self._pending_messages:
            self._after_id = None
            return

        # 取出所有待写入消息
        messages = self._pending_messages
        self._pending_messages = []
        self._after_id = None

        try:
            # 批量操作：先启用编辑
            self.text_widget.configure(state='normal')

            # 批量插入所有消息
            for msg, levelname in messages:
                # 获取当前末尾行号
                end_line = self.text_widget.index(tk.END).split('.')[0]
                start_idx = f'{int(end_line)}.0'

                # 插入文本
                self.text_widget.insert(tk.END, msg)

                # 应用标签
                end_idx = self.text_widget.index(tk.END)
                self.text_widget.tag_add(levelname, start_idx, end_idx)

            # 检查是否需要滚动到底部
            # 只有当用户之前在底部时才自动滚动
            if self._last_scroll_pos >= 0.99:
                self.text_widget.see(tk.END)

            # 限制行数：使用更高效的方式
            self._trim_lines()

            # 禁用编辑
            self.text_widget.configure(state='disabled')

        except Exception:
            try:
                self.text_widget.configure(state='disabled')
            except Exception:
                pass

    def _trim_lines(self):
        """修剪超过最大行数的旧日志"""
        current_lines = int(self.text_widget.index(tk.END).split('.')[0]) - 1
        if current_lines > self.max_lines:
            # 计算要删除的行数
            lines_to_delete = current_lines - self.max_lines
            delete_end = f'{lines_to_delete}.0'
            self.text_widget.delete('1.0', delete_end)

    def flush(self):
        """强制刷新所有待写入的消息"""
        if self._after_id is not None:
            try:
                self.text_widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._flush()

    def close(self):
        """关闭处理器"""
        self.flush()
        super().close()


class ScrolledTextFrame(ttk.Frame):
    """带滚动条的文本框组件"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent)

        self.text_widget = tk.Text(self, **kwargs)
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self, command=self.text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_widget.config(yscrollcommand=scrollbar.set)

        self._setup_tags()

    def _setup_tags(self):
        """设置文本标签样式"""
        self.text_widget.tag_configure('INFO', foreground='#000000')
        self.text_widget.tag_configure('WARNING', foreground='#FFA500')
        self.text_widget.tag_configure('ERROR', foreground='#FF0000')
        self.text_widget.tag_configure('SUCCESS', foreground='#00AA00')

    def append(self, message, tag=None):
        """添加文本"""
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, message + '\n', tag)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')

    def clear(self):
        """清空文本"""
        self.text_widget.configure(state='normal')
        self.text_widget.delete('1.0', tk.END)
        self.text_widget.configure(state='disabled')


class DateEntry(ttk.Entry):
    """日期输入组件"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<KeyRelease>', self._on_key_release)

        self._placeholder = 'YYYY-MM-DD'
        self._show_placeholder()

    def _show_placeholder(self):
        """显示占位符"""
        self.delete('0', tk.END)
        self.insert('0', self._placeholder)
        self.config(foreground='gray')

    def _hide_placeholder(self):
        """隐藏占位符"""
        if self.get() == self._placeholder:
            self.delete('0', tk.END)
            self.config(foreground='black')

    def _on_focus_in(self, event):
        """获取焦点时清除占位符"""
        self._hide_placeholder()

    def _on_key_release(self, event):
        """按键释放时检查是否为空"""
        if not self.get():
            self._show_placeholder()

    def get_date(self):
        """获取日期字符串"""
        value = self.get()
        if value == self._placeholder:
            return None
        return value


class MultiSelectDropdown(ttk.Frame):
    """带复选框和滚动区域的下拉选择组件。

    复选框变化只更新临时选择顺序，点击“确定”才更新显示值并触发业务
    回调；``set_selected`` 用于程序回填，不触发该回调。选择超过三项时
    只显示数量，内部仍保留完整的值列表。
    """

    # TODO: 广东地市列表硬编码在此，应改为配置项（config.yaml 或 YAML 配置）以便扩展
    GD_CITIES = ['广州', '深圳', '东莞', '佛山', '中山', '珠海', '江门', '肇庆',
                 '惠州', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江',
                 '云浮', '韶关', '梅州', '河源', '清远']

    def __init__(self, parent, values, width=18, select_all=False, max_dropdown_items=5,
                 on_change_callback=None):
        super().__init__(parent)
        self.values = values
        self.var_dict = {}
        self.var = tk.StringVar(value="")
        self._selected_order = []
        self._max_dropdown_items = max_dropdown_items  # 下拉列表最大显示项数
        self.on_change_callback = on_change_callback  # 选择变化回调

        # 输入框 + 下拉按钮
        self.entry = ttk.Entry(self, textvariable=self.var, width=width, state='readonly')
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn = ttk.Button(self, text="▼", width=3, command=self._toggle_dropdown)
        self.btn.pack(side=tk.LEFT)

        # 创建下拉窗口
        self.dropdown = tk.Toplevel(self)
        self.dropdown.withdraw()
        self.dropdown.overrideredirect(True)
        self.dropdown.attributes('-topmost', True)

        # 下拉内容区域（分为两部分：复选框列表 + 底部按钮）
        # 复选框区域（带滚动条）
        checkbox_area = ttk.Frame(self.dropdown)
        checkbox_area.pack(fill=tk.X)

        # 创建 Canvas + Scrollbar 实现滚动
        self.check_canvas = tk.Canvas(checkbox_area, bg='white', highlightthickness=1,
                                     highlightbackground='#cccccc', height=150)
        scrollbar = ttk.Scrollbar(checkbox_area, orient="vertical",
                                  command=self.check_canvas.yview)
        self.check_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.check_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 可滚动的内部框架
        self.check_frame = ttk.Frame(self.check_canvas)
        self.check_canvas.create_window((0, 0), window=self.check_frame, anchor='nw')

        # 绑定滚动区域配置
        def on_frame_configure(event):
            self.check_canvas.configure(scrollregion=self.check_canvas.bbox("all"))
            # 动态设置 Canvas 高度，确保内容可见
            frame_h = self.check_frame.winfo_reqheight()
            canvas_h = min(frame_h, self._max_dropdown_items * 22 + 10)
            self.check_canvas.configure(height=canvas_h)
        self.check_frame.bind("<Configure>", on_frame_configure)

        # 绑定鼠标滚轮事件
        def on_mousewheel(event):
            self.check_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        self.check_canvas.bind("<MouseWheel>", on_mousewheel)
        self.check_canvas.bind("<Enter>", lambda e: self.check_canvas.bind("<MouseWheel>", on_mousewheel))
        self.check_canvas.bind("<Leave>", lambda e: self.check_canvas.unbind("<MouseWheel>"))

        # 创建复选框
        self.check_vars = {}
        for val in values:
            var = tk.BooleanVar(value=False)
            self.check_vars[val] = var
            cb = ttk.Checkbutton(
                self.check_frame, text=val, variable=var,
                command=lambda v=val: self._on_check_change(v)
            )
            cb.pack(anchor=tk.W, padx=5, pady=1)

        # 底部按钮区域
        btn_frame = ttk.Frame(self.dropdown)
        btn_frame.pack(fill=tk.X, padx=2, pady=2)
        ttk.Button(btn_frame, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="取消", command=self._deselect_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="确定", command=self._confirm).pack(side=tk.RIGHT, padx=2)

        if select_all:
            self._select_all()

    def _toggle_dropdown(self):
        """切换下拉框显示"""
        if self.dropdown.winfo_viewable():
            self.dropdown.withdraw()
        else:
            self._show_dropdown()

    def _show_dropdown(self):
        """显示下拉框（限制最大高度）"""
        self.dropdown.update_idletasks()
        entry_x = self.entry.winfo_rootx()
        entry_y = self.entry.winfo_rooty()
        entry_h = self.entry.winfo_height()
        dropdown_w = self.dropdown.winfo_reqwidth()

        # 按钮区域高度 + padding
        btn_height = 50
        # Canvas 高度（固定值）
        canvas_h = 150

        dropdown_h = canvas_h + btn_height

        screen_w = self.dropdown.winfo_screenwidth()
        screen_h = self.dropdown.winfo_screenheight()
        space_below = screen_h - (entry_y + entry_h)
        space_above = entry_y

        if space_below >= dropdown_h or space_below >= space_above:
            y = entry_y + entry_h
        else:
            y = entry_y - dropdown_h
            if y < 0:
                y = 0

        if entry_x + dropdown_w > screen_w:
            x = screen_w - dropdown_w
        else:
            x = entry_x

        self.dropdown.geometry(f"{dropdown_w}x{dropdown_h}+{x}+{y}")
        self.dropdown.deiconify()
        self.dropdown.lift()

    def _on_check_change(self, val=None):
        """复选框状态变化"""
        if val is not None:
            var = self.check_vars.get(val)
            if var:
                if var.get():
                    if val not in self._selected_order:
                        self._selected_order.append(val)
                else:
                    if val in self._selected_order:
                        self._selected_order.remove(val)

    def _select_all(self):
        """全选"""
        self._selected_order = list(self.values)
        for var in self.check_vars.values():
            var.set(True)

    def _deselect_all(self):
        """取消全选"""
        self._selected_order = []
        for var in self.check_vars.values():
            var.set(False)

    def _confirm(self):
        """确认选择"""
        selected = [val for val in self._selected_order if val in self.check_vars and self.check_vars[val].get()]
        if selected:
            # 显示已选项（超过3项时显示"已选N项"，否则显示具体内容）
            if len(selected) > 3:
                display_text = f"已选 {len(selected)} 项"
            else:
                display_text = ','.join(selected)
            self.var.set(display_text)
        else:
            self.var.set("")
        self.dropdown.withdraw()
        
        # 触发选择变化回调
        if self.on_change_callback:
            self.on_change_callback(selected)

    def get_selected(self):
        """获取选中的值列表"""
        return [val for val, var in self.check_vars.items() if var.get()]

    def set_selected(self, values):
        """设置选中的值"""
        self._selected_order = []
        for val, var in self.check_vars.items():
            var.set(val in values)
            if val in values:
                self._selected_order.append(val)
        if values:
            # 显示已选项（超过3项时显示"已选N项"，否则显示具体内容）
            if len(values) > 3:
                display_text = f"已选 {len(values)} 项"
            else:
                display_text = ','.join(values)
            self.var.set(display_text)
        else:
            self.var.set("")

    def get_value(self):
        """获取选中值（逗号分隔字符串）"""
        return self.var.get()

    def set_value(self, value):
        """设置选中值（逗号分隔字符串）"""
        if value:
            values = [v.strip() for v in value.split(',')]
            self.set_selected(values)


class TableConfig:
    """数据表配置类 - 仅使用硬编码配置

    YAML配置已禁用（存在过多问题），所有表格配置均来自
    硬编码的 TABLE_CONFIGS 和 payload_templates 中的payload函数。

    TODO: 硬编码的 TABLE_CONFIGS 700+ 行导致修改配置需改代码，
          建议修复 YAML 配置机制的问题后重新启用，或改用数据库/配置中心。
    """

    # ========== YAML配置已移除 ==========
    # table_configs/ 和 custom_configs/ 目录及其加载器已删除。
    # 所有表格配置统一使用 TABLE_CONFIGS 硬编码 + field_configs.json 动态加载。
    force_source = 'old'

    # 旧配置（唯一配置源）
    TABLE_CONFIGS = {
        # ========== 干扰类 ==========
        '5G干扰小区': {
            'name': '5G干扰小区',
            'table_key': '5G干扰报表（忙时）',
            'table_name': 'appdbv3.a_interfere_nr_cell_zb2_d',
            'fieldtype': '5G干扰报表（忙时）',
            'api_type': 'search',
            'payload_func': get_5g_interference_payload,
            'default_conditions': [
                {'field': 'city', 'operator': 'like', 'value': '%%'},
            ],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'gnodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            },
            'fields': INTERFERENCE_5G_FIELDS,
        },
        '5G_干扰报表_自忙时': {
            'name': '5G_干扰报表_自忙时',
            'table_key': '5G_干扰报表_自忙时',
            'table_name': 'appdbv3.a_interfere_nrcell_zb4',
            'fieldtype': '5G_干扰报表_自忙时',
            'api_type': 'table',
            'payload_func': get_5g_interference_zimang_payload,
            'default_conditions': [
                {'field': 'city', 'operator': 'like', 'value': '%%'},
            ],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天、周',
                'enodebField': 'gnodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'nrcell',
                'cityField': 'city',
            },
            'fields': INTERFERENCE_5G_ZIMANG_FIELDS,
        },
        '4G干扰小区': {
            'name': '4G干扰小区',
            'table_key': '4G干扰报表（忙时）',
            'table_name': 'appdbv3.a_interfere_lte_cell_zb2_d',
            'fieldtype': '4G干扰报表（忙时）',
            'api_type': 'search',
            'payload_func': get_4g_interference_payload,
            'default_conditions': [
                {'field': 'city', 'operator': 'like', 'value': '%%'},
            ],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            },
            'fields': INTERFERENCE_4G_FIELDS,
        },
        '通用性能报表-小区(天)v3': {
            'name': '通用性能报表-小区(天)v3',
            'table_key': '通用性能报表-小区(天)v3',
            'table_name': 'appdbv3.a_common_pm_lte_cell_d',
            'fieldtype': '通用性能统计-小区(天)',
            'api_type': 'table',
            'payload_func': get_common_pm_cell_day_v3_payload,
            'fields': [],  # 使用payload中的result字段
            'default_conditions': [],
            'dimension': {
                'geographicdimension': 'city',
                'timedimension': '天粒度',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 容量类 ==========
        '5G小区容量报表': {
            'name': '5G小区容量报表',
            'table_key': '5G小区容量报表 - 天粒度',
            'table_name': 'appdbv3.a_adhoc_capacity_nr_nrcell_d',
            'fieldtype': '5G小区容量报表 - 天粒度',
            'api_type': 'table',
            'payload_func': get_5g_capacity_payload,
            'fields': CAPACITY_5G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'enodeb_id',
                'cgiField': 'ncgi',
                'timeField': 'starttime',
                'cellField': 'nrcell',
                'cityField': 'city',
            }
        },

        '5G小区容量-周': {
            'name': '5G小区容量-周',
            'table_key': '5G小区容量报表 - 周粒度',
            'table_name': 'appdbv3.a_adhoc_capacity_nr_nrcell_w',
            'fieldtype': '5G小区容量报表 - 周粒度',
            'api_type': 'table',
            'payload_func': get_5g_capacity_week_payload,
            'fields': CAPACITY_5G_WEEK_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '周',
                'enodebField': 'station_name',
                'cgiField': 'ncgi',
                'timeField': 'starttime',
                'cellField': 'nrcell_name',
                'cityField': 'city',
            }
        },

        '重要场景-天': {
            'name': '重要场景-天',
            'table_key': '重要场景-小区天',
            'table_name': 'appdbv3.a_overview_ispm_lte_cell_d',
            'fieldtype': '重要场景-小区天',
            'api_type': 'table',
            'payload_func': get_important_scene_payload,
            'fields': IMPORTANT_SCENE_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        '重要场景-周': {
            'name': '重要场景-周',
            'table_key': '重要场景-小区周',
            'table_name': 'appdbv3.a_overview_ispm_lte_cell_w',
            'fieldtype': '[管理视图]重要场景-小区周粒度',
            'api_type': 'table',
            'payload_func': get_important_scene_week_payload,
            'fields': IMPORTANT_SCENE_WEEK_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '周',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 工参类 ==========
        '5G小区工参报表': {
            'name': '5G小区工参报表',
            'table_key': 'appdbv3.a_common_cfg_nr_cellant_d',
            'table_name': 'appdbv3.a_common_cfg_nr_cellant_d',
            'fieldtype': '5G小区工参',
            'api_type': 'table',
            'payload_func': get_5g_gongcan_payload,
            'is_gongcan': True,
            'fields': GONGCAN_5G_FIELDS,
            'default_conditions': [
                {'field': 'curr_flag', 'operator': '=', 'value': '1'},
            ],
            'dimension': {
                'geographicdimension': '小区，网格，地市，分公司',
                'timedimension': '天粒度',
                'enodebField': 'gnodeb_id',
                'cgiField': 'ncgi',
                'timeField': 'starttime',
                'cellField': 'nrcell_name',
                'cityField': 'city',
            }
        },
        '4G小区工参报表': {
            'name': '4G小区工参报表',
            'table_key': 'appdbv3.v_a_common_cfg_lte_cellant_d',
            'table_name': 'appdbv3.v_a_common_cfg_lte_cellant_d',
            'fieldtype': '4G小区工参',
            'api_type': 'table',
            'payload_func': get_4g_gongcan_payload,
            'is_gongcan': True,
            'fields': GONGCAN_4G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区，网格，地市，分公司',
                'timedimension': '天粒度',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 共站同覆盖小区_4g_5g ==========
        '共站同覆盖小区_4g_5g': {
            'name': '共站同覆盖小区_4g_5g',
            'table_key': 'appdbv3.a_struct_sectors_d',
            'table_name': 'appdbv3.a_struct_sectors_d',
            'fieldtype': '共站同覆盖小区_4g_5g',
            'api_type': 'table',
            'payload_func': get_sectors_4g_5g_payload,
            'is_gongcan': True,
            'fields': SECTORS_4G_5G_FIELDS,
            'default_conditions': [
                {'field': 'curr_flag', 'operator': '=', 'value': '1'},
            ],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天粒度',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== MR覆盖类 ==========
        '5GMR覆盖-小区天': {
            'name': '5GMR覆盖-小区天',
            'table_key': 'appdbv3.a_common_mro_scssrsrp_nr_nrcell',
            'table_name': 'appdbv3.a_common_mro_scssrsrp_nr_nrcell',
            'fieldtype': '5GMR覆盖-小区天',
            'api_type': 'table',
            'payload_func': get_5g_mr_payload,
            'fields': MR_5G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区，网格，地市，分公司',
                'timedimension': '天、周、月粒度',
                'enodebField': 'gnodeb_id',
                'cgiField': 'ncgi',
                'timeField': 'starttime',
                'cellField': 'nrcell',
                'cityField': 'city',
            }
        },
        '4GMR覆盖-小区天': {
            'name': '4GMR覆盖-小区天',
            'table_key': 'appdbv3.a_common_mro_rsrp_lte_cell',
            'table_name': 'appdbv3.a_common_mro_rsrp_lte_cell',
            'fieldtype': '4G_MRO_RSRP基础性能_小区',
            'api_type': 'table',
            'payload_func': get_4g_mr_payload,
            'fields': MR_4G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区，网格，地市，分公司',
                'timedimension': '天、周、月',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 语音报表类 ==========
        'VoLTE小区监控预警': {
            'name': 'VoLTE小区监控预警',
            'table_key': 'VoLTE小区监控预警数据表-天',
            'table_name': 'csem.f_nk_volte_keykpi_cell_d',
            'fieldtype': 'VoLTE小区监控预警数据表-天',
            'api_type': 'table',
            'payload_func': get_volte_warning_payload,
            'fields': VOLTE_WARNING_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },
        'VONR小区监控预警': {
            'name': 'VONR小区监控预警',
            'table_key': 'VONR小区监控预警数据表-天',
            'table_name': 'csem.f_nk_vonr_keykpi_cell_d',
            'fieldtype': 'VONR小区监控预警数据表-天',
            'api_type': 'table',
            'payload_func': get_vonr_warning_payload,
            'fields': VONR_WARNING_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'gnodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },
        'EPSFB小区监控预警': {
            'name': 'EPSFB小区监控预警',
            'table_key': 'EPSFB小区监控预警数据表-天',
            'table_name': 'csem.f_nk_epsfb_keykpi_cell_d',
            'fieldtype': 'EPSFB小区监控预警数据表-天',
            'api_type': 'table',
            'payload_func': get_epsfb_warning_payload,
            'fields': EPSFB_WARNING_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': '---',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 小区性能类 ==========
        '5G小区性能KPI报表': {
            'name': '5G小区性能KPI报表',
            'table_key': 'appdbv3.a_common_pm_sacu',
            'table_name': 'appdbv3.a_common_pm_sacu',
            'fieldtype': 'SA_CU性能',
            'api_type': 'table',
            'payload_func': get_5g_kpi_payload,
            'fields': KPI_5G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'gnodeb_id',
                'cgiField': 'ncgi',
                'timeField': 'starttime',
                'cellField': 'nrcell',
                'cityField': 'city',
            }
        },
        '4G小区性能KPI报表': {
            'name': '4G小区性能KPI报表',
            'table_key': 'appdbv3.a_common_pm_lte',
            'table_name': 'appdbv3.a_common_pm_lte',
            'fieldtype': '公共_4G小区性能KPI报表_小区',
            'api_type': 'table',
            'payload_func': get_4g_kpi_payload,
            'fields': KPI_4G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 全程完好率类 ==========
        '4G全程完好率报表': {
            'name': '4G全程完好率报表',
            'table_key': 'appdbv3.a_common_pm_lte',
            'table_name': 'appdbv3.a_common_pm_lte',
            'fieldtype': '公共_4G小区性能KPI报表_小区',
            'api_type': 'table',
            'payload_func': get_4g_wanchenglv_payload,
            'calc_columns': ['4G全程完好率(%)', '4G无线接通率(%)', '4G切换成功率(%)', '4G_E-RAB掉线率(%)', '4G是否差小区'],
            'fields': KPI_4G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },
        '5G全程完好率报表': {
            'name': '5G全程完好率报表',
            'table_key': 'appdbv3.a_common_pm_sacu',
            'table_name': 'appdbv3.a_common_pm_sacu',
            'fieldtype': '公共_5G小区性能KPI报表_小区',
            'api_type': 'table',
            'payload_func': get_5g_wanchenglv_payload,
            'calc_columns': ['5G全程完好率(%)', 'SA无线接通率(%)', 'SA切换成功率(%)', 'SA无线掉线率(%)', '5G是否差小区'],
            'fields': KPI_5G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'gnodeb_id',
                'cgiField': 'ncgi',
                'timeField': 'starttime',
                'cellField': 'nrcell',
                'cityField': 'city',
            }
        },

        # ========== 语音小区类 ==========
        '4G语音小区': {
            'name': '4G语音小区',
            'table_key': 'VoLTE小区监控预警数据表-天',
            'table_name': 'csem.f_nk_volte_keykpi_cell_d',
            'fieldtype': 'VoLTE小区监控预警数据表-天',
            'api_type': 'table',
            'is_4g_voice': True,
            'is_4g_voice_warning': True,  # 标记为使用预警报表字段
            'volte_fields': VOLTE_4G_VOICE_WARNING_FIELDS,
            'epsfb_fields': EPSFB_4G_VOICE_WARNING_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'enodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },
        '5G语音小区': {
            'name': '5G语音小区',
            'table_key': 'VONR小区监控预警数据表-天',
            'table_name': 'csem.f_nk_vonr_keykpi_cell_d',
            'fieldtype': 'VONR小区监控预警数据表-天',
            'api_type': 'table',
            'payload_func': get_5g_voice_payload,
            'calc_columns': ['5G语音小区'],
            'fields': VOICE_5G_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天',
                'enodebField': 'gnodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 45G流量与热点评估类 ==========
        '45G流量与热点评估物理站级': {
            'name': '45G流量与热点评估物理站级',
            'table_key': '45G流量与热点评估物理站级',
            'table_name': 'appdbv3.a_cap_ltenr_station',
            'fieldtype': '45G流量与热点评估物理站级',
            'api_type': 'table',
            'payload_func': get_flow_hot_spot_station_payload,
            'fields': FLOW_HOT_SPOT_STATION_FIELDS,
            'default_conditions': [],
            'dimension': {
                'geographicdimension': '小区',
                'timedimension': '天、周',
                'enodebField': 'gnodeb_id',
                'cgiField': 'cgi',
                'timeField': 'starttime',
                'cellField': 'cell',
                'cityField': 'city',
            }
        },

        # ========== 专项功能：合成45G流量表 ==========
        '合成45G流量表': {
            'name': '合成45G流量表',
            'is_synthesize': True,
            'time_granularity': 'week',
            'source_tables': SYNTHESIZE_45G_CONFIG['source_tables'],
            'dimension': SYNTHESIZE_45G_CONFIG['dimension'],
        },
    }

    # 地市级报表配置单独维护，避免继续扩张本模块的主配置字典。
    TABLE_CONFIGS.update(CITY_TABLE_CONFIGS)

    # YAML加载器单例（已禁用，保留引用避免其他模块报错）
    _yaml_loader = None

    @classmethod
    def set_config_source(cls, source):
        """设置配置数据源（YAML已禁用，此方法保留但不再生效）

        Args:
            source: 数据源类型
        """
        # YAML配置已禁用，强制使用硬编码配置
        cls.force_source = 'old'

    @classmethod
    def _get_yaml_loader(cls):
        """获取YAML加载器（已禁用）

        YAML配置存在过多问题已被禁用，此方法返回None。
        所有配置均来自 TABLE_CONFIGS 硬编码。
        """
        return None

    @classmethod
    def get_table_names(cls):
        """获取所有数据表名称（仅硬编码配置）

        Returns:
            list: 所有表格名称，按字母排序
        """
        old_names = set(cls.TABLE_CONFIGS.keys())
        return sorted(old_names)

    @classmethod
    def get_table_config(cls, table_name):
        """获取指定数据表的配置

        YAML配置已禁用，仅从硬编码 TABLE_CONFIGS 获取配置。

        Args:
            table_name: 表格名称

        Returns:
            dict: 表格配置，如果不存在则返回None
        """
        # 根据 force_source 决定使用哪个数据源
        # YAML配置已禁用，仅从硬编码 TABLE_CONFIGS 获取配置
        return cls.TABLE_CONFIGS.get(table_name)

    @classmethod
    def get_all_configs(cls):
        """获取所有数据表配置（仅硬编码配置）

        Returns:
            dict: 所有表格配置
        """
        return dict(cls.TABLE_CONFIGS)

    @classmethod
    def build_payload_from_yaml(cls, table_name, start_date, end_date, city):
        """从YAML配置构建payload（已禁用）

        YAML配置已禁用，此方法返回None。
        请使用硬编码 payload_func 替代。

        Returns:
            None
        """
        return None

    @classmethod
    def reload_yaml_configs(cls):
        """重新加载YAML配置（已禁用，YAML配置不可用）"""
        pass


class WeekSelector(ttk.Frame):
    """周选择器组件 - 用于选择周的起始日期（周一）
    
    提供两种模式：
    1. 下拉选择：选择年内第几周
    2. 直接输入：直接指定周一日期
    """
    
    WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    
    def __init__(self, parent, width=20, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.var = tk.StringVar(value="")
        self._week_start_date = None
        
        # 创建组件
        content = ttk.Frame(self)
        content.pack(fill=tk.X, expand=True)
        
        # 周数下拉选择
        top_row = ttk.Frame(content)
        top_row.pack(fill=tk.X, pady=(0, 4))
        
        ttk.Label(top_row, text="选择周:", font=('Microsoft YaHei UI', 8)).pack(side=tk.LEFT, padx=(0, 4))
        
        # 生成周列表
        self.weeks = self._generate_week_options()
        self.week_var = tk.StringVar()
        week_combo = ttk.Combobox(top_row, textvariable=self.week_var, 
                                   values=[w[1] for w in self.weeks],
                                   width=12, state='readonly')
        week_combo.pack(side=tk.LEFT, padx=(0, 4))
        week_combo.bind('<<ComboboxSelected>>', self._on_week_selected)
        
        # 当前选中的周信息显示
        self.info_label = ttk.Label(top_row, text="", font=('Microsoft YaHei UI', 8))
        self.info_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 日期范围显示
        bottom_row = ttk.Frame(content)
        bottom_row.pack(fill=tk.X, pady=(4, 0))
        
        ttk.Label(bottom_row, text="日期范围:", font=('Microsoft YaHei UI', 8)).pack(side=tk.LEFT, padx=(0, 4))
        
        self.date_range_label = ttk.Label(bottom_row, text="-- 至 --", 
                                         font=('Microsoft YaHei UI', 9, 'bold'),
                                         foreground='#165DFF')
        self.date_range_label.pack(side=tk.LEFT)
        
        # 默认选中当前周
        self._select_current_week()
    
    def _generate_week_options(self):
        """生成周选项列表"""
        weeks = []
        current_year = datetime.now().year
        
        # 从1月1日开始计算
        jan1 = datetime(current_year, 1, 1)
        
        # 找到第一个周一
        days_since_monday = jan1.weekday()
        first_monday = jan1 - timedelta(days=days_since_monday)
        
        week_num = 1
        current_date = first_monday
        
        while current_date.year == current_year or (current_date + timedelta(days=6)).year == current_year:
            # 确保这一周至少有一天在当前年内
            if current_date.year == current_year:
                end_date = current_date + timedelta(days=6)
                end_year = end_date.year
                
                label = f"第{week_num}周 ({current_date.strftime('%m/%d')}-{end_date.strftime('%m/%d')})"
                weeks.append((current_date, label))
            
            current_date += timedelta(days=7)
            week_num += 1
            
            # 防止无限循环
            if week_num > 54:
                break
        
        return weeks
    
    def _select_current_week(self):
        """默认选中当前周"""
        today = datetime.now()
        
        # 找到当前天属于哪一周
        for i, (week_start, label) in enumerate(self.weeks):
            week_end = week_start + timedelta(days=6)
            if week_start <= today <= week_end:
                self.week_var.set(label)
                self._update_display(week_start)
                break
        else:
            # 如果没找到，尝试选中上一周
            if self.weeks:
                last_week = self.weeks[-1]
                self.week_var.set(last_week[1])
                self._update_display(last_week[0])
    
    def _on_week_selected(self, event=None):
        """周选择事件"""
        selected = self.week_var.get()
        for week_start, label in self.weeks:
            if label == selected:
                self._update_display(week_start)
                break
    
    def _update_display(self, week_start):
        """更新显示"""
        self._week_start_date = week_start
        week_end = week_start + timedelta(days=6)
        
        # 更新日期范围显示
        self.date_range_label.config(
            text=f"{week_start.strftime('%Y-%m-%d')} 至 {week_end.strftime('%Y-%m-%d')}"
        )
        
        # 更新周信息
        week_num = week_start.isocalendar()[1]
        self.info_label.config(text=f"周一~周日，共7天")
    
    def get_week_start(self):
        """获取选中的周开始日期（周一）
        
        Returns:
            datetime: 周开始日期
        """
        return self._week_start_date
    
    def get_date_range(self):
        """获取日期范围
        
        Returns:
            tuple: (start_date, end_date) 格式为 YYYY-MM-DD 字符串
        """
        if self._week_start_date:
            start = self._week_start_date.strftime('%Y-%m-%d')
            end = (self._week_start_date + timedelta(days=6)).strftime('%Y-%m-%d')
            return start, end
        return None, None
