# -*- coding: utf-8 -*-
"""
自定义 GUI 组件模块
提供可复用的增强组件
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Callable, Optional, Any
import re

from gui.theme import colors, fonts, spacing


class SearchableCombobox(ttk.Frame):
    """带搜索功能的组合框

    支持实时过滤下拉选项，适合大量选项（如20+报表）
    """

    def __init__(self, parent, values: List[str], width: int = 25,
                 placeholder: str = "", on_select: Optional[Callable] = None,
                 **kwargs):
        super().__init__(parent, **kwargs)

        self.values = values
        self.original_values = values
        self.on_select_callback = on_select

        # 搜索框
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            self, textvariable=self.search_var, width=width
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 占位符样式
        self._placeholder = placeholder
        if placeholder:
            self.search_entry.insert(0, placeholder)
            self.search_entry.config(foreground='gray')
            self.search_entry.bind('<FocusIn>', self._on_entry_focus_in)
            self.search_entry.bind('<FocusOut>', self._on_entry_focus_out)

        # 搜索触发
        self.search_var.trace('w', lambda *args: self._filter_values())

        # 下拉按钮
        self.dropdown_btn = ttk.Button(
            self, text="▼", width=3, command=self._toggle_dropdown
        )
        self.dropdown_btn.pack(side=tk.LEFT)

        # 下拉窗口
        self.dropdown_window = tk.Toplevel(self)
        self.dropdown_window.withdraw()
        self.dropdown_window.overrideredirect(True)
        self.dropdown_window.attributes('-topmost', True)

        # 搜索过滤器
        filter_frame = ttk.Frame(self.dropdown_window)
        filter_frame.pack(fill=tk.X, padx=4, pady=4)

        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var,
                                  font=('Microsoft YaHei UI', 9))
        filter_entry.pack(fill=tk.X)
        filter_entry.bind('<KeyRelease>', lambda e: self._filter_list())
        self.filter_var.trace('w', lambda *args: self._filter_list())

        # 列表框
        list_frame = ttk.Frame(self.dropdown_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_frame, font=('Microsoft YaHei UI', 9),
            yscrollcommand=scrollbar.set, height=8,
            selectbackground=colors.primary,
            selectforeground='white'
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # 填充初始值
        for val in self.values:
            self.listbox.insert(tk.END, val)

        # 事件绑定
        self.listbox.bind('<Double-Button-1>', lambda e: self._on_select())
        self.listbox.bind('<Return>', lambda e: self._on_select())
        self.listbox.bind('<Button-1>', self._on_list_click)

        # 选中索引
        self.selected_index = -1

    def _on_entry_focus_in(self, event):
        if self.search_entry.get() == self._placeholder:
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(foreground='black')

    def _on_entry_focus_out(self, event):
        if not self.search_entry.get():
            self.search_entry.insert(0, self._placeholder)
            self.search_entry.config(foreground='gray')

    def _filter_values(self):
        """过滤入口值（搜索框）"""
        search_term = self.search_var.get()
        if search_term == self._placeholder:
            return
        self.filter_var.set(search_term)

    def _filter_list(self):
        """过滤下拉列表"""
        filter_term = self.filter_var.get().lower()
        self.listbox.delete(0, tk.END)

        for val in self.original_values:
            if filter_term in val.lower():
                self.listbox.insert(tk.END, val)

        if not filter_term:
            for val in self.values:
                self.listbox.insert(tk.END, val)

    def _toggle_dropdown(self):
        """切换下拉显示"""
        if self.dropdown_window.winfo_viewable():
            self.dropdown_window.withdraw()
        else:
            self._show_dropdown()

    def _show_dropdown(self):
        """显示下拉窗口"""
        self.dropdown_window.update_idletasks()

        # 计算位置
        entry_x = self.winfo_rootx()
        entry_y = self.winfo_rooty() + self.winfo_height()

        # 获取尺寸
        dropdown_w = max(300, self.winfo_width())
        dropdown_h = 250

        # 屏幕边界检查
        screen_w = self.dropdown_window.winfo_screenwidth()
        screen_h = self.dropdown_window.winfo_screenheight()

        if entry_x + dropdown_w > screen_w:
            x = screen_w - dropdown_w - 10
        else:
            x = entry_x

        if entry_y + dropdown_h > screen_h:
            y = entry_y - dropdown_h - self.winfo_height()
        else:
            y = entry_y

        self.dropdown_window.geometry(f"{dropdown_w}x{dropdown_h}+{x}+{y}")
        self.dropdown_window.deiconify()
        self.dropdown_window.lift()
        self.filter_var.set('')
        self._filter_list()

    def _on_list_click(self, event):
        """列表点击"""
        pass

    def _on_select(self):
        """选择项"""
        selection = self.listbox.curselection()
        if selection:
            self.selected_index = selection[0]
            value = self.listbox.get(selection[0])
            self.search_var.set(value)
            self.search_entry.config(foreground='black')
            self.dropdown_window.withdraw()

            if self.on_select_callback:
                self.on_select_callback(value)

    def get(self) -> str:
        """获取当前值"""
        value = self.search_var.get()
        if value == self._placeholder:
            return ""
        return value

    def set(self, value: str):
        """设置值"""
        self.search_var.set(value)
        self.search_entry.config(foreground='black')

    def bind_select(self, callback: Callable):
        """绑定选择回调"""
        self.on_select_callback = callback


class CalendarDialog(tk.Toplevel):
    """日历选择对话框"""

    def __init__(self, parent, initial_date: str = "", title: str = "选择日期"):
        super().__init__(parent)

        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # 设置窗口位置
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 300) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 350) // 2
        self.geometry(f"300x350+{x}+{y}")

        self.selected_date = None
        self.current_year = None
        self.current_month = None

        # 解析初始日期
        if initial_date:
            try:
                from datetime import datetime
                dt = datetime.strptime(initial_date, "%Y-%m-%d")
                self.current_year = dt.year
                self.current_month = dt.month
            except ValueError:
                pass

        # 默认当前日期
        if not self.current_year:
            from datetime import datetime
            now = datetime.now()
            self.current_year = now.year
            self.current_month = now.month

        self._create_widgets()
        self._render_calendar()

    def _create_widgets(self):
        """创建组件"""
        # 标题栏
        header = tk.Frame(self, bg=colors.primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # 月份导航
        nav_frame = tk.Frame(header, bg=colors.primary)
        nav_frame.pack(expand=True)

        prev_btn = tk.Button(nav_frame, text="◀", font=('Arial', 12),
                            bg=colors.primary, fg='white', bd=0,
                            cursor='hand2', command=self._prev_month)
        prev_btn.pack(side=tk.LEFT, padx=10)

        self.month_label = tk.Label(nav_frame, font=(fonts.family, 14, 'bold'),
                                    bg=colors.primary, fg='white')
        self.month_label.pack(side=tk.LEFT, padx=10)

        next_btn = tk.Button(nav_frame, text="▶", font=('Arial', 12),
                            bg=colors.primary, fg='white', bd=0,
                            cursor='hand2', command=self._next_month)
        next_btn.pack(side=tk.LEFT, padx=10)

        # 星期标题
        week_frame = tk.Frame(self, bg=colors.gray_100)
        week_frame.pack(fill=tk.X, pady=(10, 0))

        weeks = ['一', '二', '三', '四', '五', '六', '日']
        for week in weeks:
            color = colors.error if week in ['六', '日'] else colors.gray_700
            tk.Label(week_frame, text=week, font=(fonts.family, 10),
                    bg=colors.gray_100, fg=color, width=4).pack(side=tk.LEFT, pady=5)

        # 日历网格
        self.calendar_frame = tk.Frame(self)
        self.calendar_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 底部按钮
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(btn_frame, text="今天", command=self._select_today,
                  font=(fonts.family, 10), bg=colors.gray_200,
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="取消", command=self.destroy,
                  font=(fonts.family, 10), bg=colors.gray_200,
                  relief='flat', cursor='hand2').pack(side=tk.RIGHT, padx=5)

    def _prev_month(self):
        """上个月"""
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._render_calendar()

    def _next_month(self):
        """下个月"""
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._render_calendar()

    def _render_calendar(self):
        """渲染日历"""
        # 清除旧组件
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # 更新月份标签
        month_names = ['一月', '二月', '三月', '四月', '五月', '六月',
                      '七月', '八月', '九月', '十月', '十一月', '十二月']
        self.month_label.config(text=f"{self.current_year} {month_names[self.current_month-1]}")

        # 计算第一天是星期几
        import calendar
        first_weekday, days_in_month = calendar.monthrange(
            self.current_year, self.current_month
        )

        # 转换为周一=0
        first_weekday = (first_weekday - 1) % 7

        # 创建日期按钮
        from datetime import datetime
        today = datetime.now()
        is_current_month = (self.current_year == today.year and
                           self.current_month == today.month)
        today_day = today.day if is_current_month else -1

        row = 0
        col = first_weekday

        for day in range(1, days_in_month + 1):
            is_weekend = col >= 5
            is_today = day == today_day

            btn = tk.Button(
                self.calendar_frame, text=str(day),
                font=(fonts.family, 10),
                width=4, height=1,
                bg=colors.primary if is_today else (colors.gray_100 if is_weekend else colors.white),
                fg=colors.error if is_weekend and not is_today else colors.gray_800,
                relief='flat' if not is_today else 'solid',
                cursor='hand2',
                command=lambda d=day: self._select_date(d)
            )
            btn.grid(row=row, column=col, padx=2, pady=2)

            col += 1
            if col > 6:
                col = 0
                row += 1

    def _select_date(self, day: int):
        """选择日期"""
        self.selected_date = f"{self.current_year:04d}-{self.current_month:02d}-{day:02d}"
        self.destroy()

    def _select_today(self):
        """选择今天"""
        from datetime import datetime
        self.selected_date = datetime.now().strftime("%Y-%m-%d")
        self.destroy()

    def show(self) -> Optional[str]:
        """显示对话框并返回选择的日期"""
        self.wait_window()
        return self.selected_date


class ValidationEntry(ttk.Entry):
    """带验证功能的输入框

    支持实时验证和错误提示
    """

    def __init__(self, parent, validator: Optional[Callable] = None,
                 error_message: str = "输入无效", **kwargs):
        super().__init__(parent, **kwargs)

        self.validator = validator
        self.error_message = error_message
        self.error_label = None
        self._is_valid = True

        # 绑定验证事件
        self.bind('<KeyRelease>', self._validate)
        self.bind('<FocusOut>', lambda e: self._validate(show_error=True))

    def set_error_label(self, label: tk.Label):
        """设置错误提示标签"""
        self.error_label = label

    def _validate(self, show_error: bool = False):
        """验证输入"""
        if not self.validator:
            return True

        value = self.get()
        is_valid = self.validator(value)
        self._is_valid = is_valid

        # 更新边框颜色
        if value:
            if is_valid:
                self.config(style='TEntry')
            else:
                self.config(style='Invalid.TEntry')

        # 显示错误信息
        if self.error_label:
            if not is_valid and show_error:
                self.error_label.config(text=self.error_message, fg=colors.error)
            else:
                self.error_label.config(text="", fg=colors.gray_500)

        return is_valid

    def is_valid(self) -> bool:
        """返回验证状态"""
        return self._is_valid


class Tooltip:
    """悬浮提示组件"""

    def __init__(self, widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip = None
        self.bundle_id = None

        widget.bind('<Enter>', lambda e: self._show())
        widget.bind('<Leave>', lambda e: self._hide())

    def _show(self):
        """显示提示"""
        self.bundle_id = self.widget.after(self.delay, self._show_tooltip)

    def _hide(self):
        """隐藏提示"""
        if self.bundle_id:
            self.widget.after_cancel(self.bundle_id)
            self.bundle_id = None
        self._destroy_tooltip()

    def _show_tooltip(self):
        """实际显示提示"""
        self._destroy_tooltip()

        # 创建提示窗口
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)

        # 设置位置
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tooltip.wm_geometry(f"+{x}+{y}")

        # 提示内容
        label = tk.Label(
            self.tooltip, text=self.text,
            font=(fonts.family, fonts.size_sm),
            bg='#ffffe0', fg=colors.gray_800,
            padx=8, pady=4,
            relief='solid', bd=1
        )
        label.pack()

    def _destroy_tooltip(self):
        """销毁提示"""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
