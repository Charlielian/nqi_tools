# -*- coding: utf-8 -*-
"""
NQI工具 - 主入口
NQI平台数据提取工具

授权说明：
1. 软件内置到期时间：2026-06-30
2. 启动时检查是否已过期
3. 简单快捷，无需激活

使用方法：
    python NqiTool.py
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

from utils.config import EXPIRY_DATE
from gui.main_window import NqiToolGUI


def check_expiry():
    """检查软件是否已过期"""
    try:
        expiry = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d")
        now = datetime.now()
        if now > expiry:
            return False, expiry
        return True, expiry
    except Exception:
        # 解析失败，默认未过期
        return True, datetime(2099, 12, 31)


def show_expiry_dialog(expiry_date):
    """显示过期提示对话框"""
    root = tk.Tk()
    root.title("软件已过期")
    root.geometry("400x200")
    root.resizable(False, False)

    # 居中显示
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w - 400) // 2
    y = (screen_h - 200) // 2
    root.geometry(f"400x200+{x}+{y}")

    # 警告图标和文字
    tk.Label(root, text="⚠️",
            font=('Arial', 48),
            fg='#ef4444').pack(pady=(30, 10))

    tk.Label(root, text="软件已过期",
            font=('Microsoft YaHei UI', 18, 'bold'),
            fg='#374151').pack()

    tk.Label(root, text=f"到期时间：{expiry_date.strftime('%Y-%m-%d')}",
            font=('Microsoft YaHei UI', 10),
            fg='#6b7280').pack(pady=5)

    def on_ok():
        root.destroy()
        sys.exit(0)

    tk.Button(root, text="确定",
             font=('Microsoft YaHei UI', 11),
             bg='#dc2626', fg='white',
             cursor='hand2', relief='raised', padx=30, pady=6,
             command=on_ok).pack(pady=20)

    root.protocol("WM_DELETE_WINDOW", on_ok)
    root.mainloop()


def start_main_app(expiry_time):
    """启动主程序"""
    from gui.main_window import check_and_setup_credentials

    root = tk.Tk()

    # 检查是否需要首次运行设置
    needs_setup, new_credentials = check_and_setup_credentials(parent=root)
    if needs_setup and new_credentials is None:
        root.destroy()
        return

    app = NqiToolGUI(root, expiry_time, credentials=new_credentials)
    app.run()


def main():
    """主函数"""
    # 检查是否过期
    valid, expiry_date = check_expiry()

    if not valid:
        show_expiry_dialog(expiry_date)
    else:
        # 未过期，启动主程序
        start_main_app(expiry_date)


if __name__ == '__main__':
    main()
