# -*- coding: utf-8 -*-
"""
GUI组件模块
提供自定义的GUI组件和辅助类
"""

import tkinter as tk
from tkinter import ttk
import logging

# 导入字段配置
from gui.field_configs import (
    INTERFERENCE_5G_FIELDS, INTERFERENCE_4G_FIELDS,
    VOLTE_4G_VOICE_FIELDS, EPSFB_4G_VOICE_FIELDS,
    VOLTE_4G_VOICE_WARNING_FIELDS, EPSFB_4G_VOICE_WARNING_FIELDS,
    CAPACITY_5G_FIELDS, IMPORTANT_SCENE_FIELDS,
    GONGCAN_5G_FIELDS, GONGCAN_4G_FIELDS,
    MR_5G_FIELDS, MR_4G_FIELDS,
    VOLTE_WARNING_FIELDS, VONR_WARNING_FIELDS, EPSFB_WARNING_FIELDS,
    KPI_4G_FIELDS, KPI_5G_FIELDS,
    VOICE_5G_FIELDS,
)

# 导入硬编码Payload模板
from gui.payload_templates import (
    get_5g_interference_payload, get_4g_interference_payload,
    get_5g_capacity_payload, get_important_scene_payload,
    get_volte_warning_payload, get_epsfb_warning_payload, get_vonr_warning_payload,
    get_4g_wanchenglv_payload, get_5g_wanchenglv_payload,
    get_volte_payload, get_epsfb_payload, get_5g_voice_payload,
    get_5g_gongcan_payload, get_4g_gongcan_payload,
    get_5g_kpi_payload, get_4g_kpi_payload,
    get_5g_mr_payload, get_4g_mr_payload,
)


class LogTextHandler(logging.Handler):
    """日志处理器 - 将简洁日志输出到界面Text组件"""

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setLevel(logging.INFO)
        self.formatter = logging.Formatter('%(message)s')

    def emit(self, record):
        if record.levelno < logging.INFO:
            return

        msg = self.formatter.format(record)
        if not msg.endswith('\n'):
            msg += '\n'

        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg)

            color_map = {
                'WARNING': '#FFA500',
                'ERROR': '#FF0000',
                'CRITICAL': '#FF0000'
            }

            tag_name = f'tag_{record.levelname}'
            self.text_widget.tag_config(tag_name, foreground=color_map.get(record.levelname, '#333333'))

            last_line_num = self.text_widget.index(tk.END).split('.')[0]
            start_idx = f'{int(last_line_num)-1}.0'
            end_idx = f'{last_line_num}.end'
            self.text_widget.tag_add(tag_name, start_idx, end_idx)

            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')

            max_lines = 1000
            current_lines = int(self.text_widget.index(tk.END).split('.')[0])
            if current_lines > max_lines:
                self.text_widget.delete('1.0', f'{current_lines - max_lines}.0')

        try:
            self.text_widget.after(0, append)
        except Exception:
            pass


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
    """带复选框的下拉选择组件"""

    GD_CITIES = ['广州', '深圳', '东莞', '佛山', '中山', '珠海', '江门', '肇庆',
                 '惠州', '汕头', '潮州', '揭阳', '汕尾', '湛江', '茂名', '阳江',
                 '云浮', '韶关', '梅州', '河源', '清远']

    def __init__(self, parent, values, width=18, select_all=False):
        super().__init__(parent)
        self.values = values
        self.var_dict = {}
        self.var = tk.StringVar(value="")
        self._selected_order = []
        self.entry = ttk.Entry(self, textvariable=self.var, width=width, state='readonly')
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn = ttk.Button(self, text="▼", width=3, command=self._toggle_dropdown)
        self.btn.pack(side=tk.LEFT)
        self.dropdown = tk.Toplevel(self)
        self.dropdown.withdraw()
        self.dropdown.overrideredirect(True)
        self.dropdown.attributes('-topmost', True)
        self.check_frame = ttk.Frame(self.dropdown)
        self.check_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.check_vars = {}
        for val in values:
            var = tk.BooleanVar(value=False)
            self.check_vars[val] = var
            cb = ttk.Checkbutton(
                self.check_frame, text=val, variable=var,
                command=lambda v=val: self._on_check_change(v)
            )
            cb.pack(anchor=tk.W, padx=5, pady=1)
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
        """显示下拉框"""
        self.dropdown.update_idletasks()
        entry_x = self.entry.winfo_rootx()
        entry_y = self.entry.winfo_rooty()
        entry_h = self.entry.winfo_height()
        dropdown_w = self.dropdown.winfo_reqwidth()
        dropdown_h = self.dropdown.winfo_reqheight()
        screen_w = self.dropdown.winfo_screenwidth()
        screen_h = self.dropdown.winfo_screenheight()
        space_below = screen_h - (entry_y + entry_h)
        space_above = entry_y
        if space_below >= dropdown_h or space_below >= space_above:
            y = entry_y + entry_h
        else:
            y = entry_y - dropdown_h
        if entry_x + dropdown_w > screen_w:
            x = screen_w - dropdown_w
        else:
            x = entry_x
        if y < 0:
            y = 0
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
            self.var.set(','.join(selected))
        else:
            self.var.set("")
        self.dropdown.withdraw()

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
            self.var.set(','.join(values))
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
    """数据表配置类"""

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
    }

    @classmethod
    def get_table_names(cls):
        """获取所有数据表名称"""
        return list(cls.TABLE_CONFIGS.keys())

    @classmethod
    def get_table_config(cls, table_name):
        """获取指定数据表的配置"""
        return cls.TABLE_CONFIGS.get(table_name)

    @classmethod
    def get_all_configs(cls):
        """获取所有数据表配置"""
        return cls.TABLE_CONFIGS
