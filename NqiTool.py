# -*- coding: utf-8 -*-
"""
NQI工具 - 主入口
NQI平台数据提取工具

融合方案授权流程：
1. 程序启动时检查用户码文件
2. 解密用户码验证机器码和过期时间
3. 不依赖 license.dat 文件存储
4. 每次启动都重新验证

使用方法：
    python NqiTool.py
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import time

from core.license import (
    get_hw_info, generate_machine_code,
    verify_with_user_code, save_user_code, decrypt_user_code,
    load_user_code
)
from gui.main_window import NqiToolGUI


def check_license():
    """检查授权（新融合方案）"""
    hw_info = get_hw_info()
    machine_code = generate_machine_code(hw_info)
    valid, result = verify_with_user_code(machine_code)
    return valid, result, machine_code


def show_activate_dialog(machine_code):
    """显示激活对话框（新融合方案）"""
    root = tk.Tk()
    root.title("授权激活")
    root.geometry("600x500")
    root.resizable(False, False)

    # 居中显示
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w - 600) // 2
    y = (screen_h - 500) // 2
    root.geometry(f"600x500+{x}+{y}")

    # 顶部标题
    header = tk.Frame(root, bg='#dc2626', height=50)
    header.pack(fill=tk.X)
    header.pack_propagate(False)

    tk.Label(header, text="⚠️ 授权验证失败",
            font=('Microsoft YaHei UI', 16, 'bold'),
            bg='#dc2626', fg='white').pack(pady=12)

    # 主内容
    content = tk.Frame(root, bg='#f9fafb')
    content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # 本机信息卡片
    info_card = tk.Frame(content, bg='white')
    info_card.pack(fill=tk.X, pady=(0, 15))

    tk.Label(info_card, text="📋 本机信息",
            font=('Microsoft YaHei UI', 12, 'bold'),
            bg='white', fg='#374151', anchor='w').pack(padx=15, pady=(12, 5))

    tk.Label(info_card, text="您的机器码（发送给管理员获取授权）：",
            font=('Microsoft YaHei UI', 9),
            bg='white', fg='#9ca3af', anchor='w').pack(padx=15, pady=(0, 5))

    machine_frame = tk.Frame(info_card, bg='white')
    machine_frame.pack(fill=tk.X, padx=15, pady=(0, 12))

    code_var = tk.StringVar(value=machine_code)
    code_entry = tk.Entry(machine_frame, textvariable=code_var,
                         font=('Consolas', 8),
                         relief='flat', bg='#f8f9fa', bd=0)
    code_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

    def copy_code():
        root.clipboard_clear()
        root.clipboard_append(machine_code)
        copy_btn.config(text="已复制!")
        root.after(1500, lambda: copy_btn.config(text="复制"))

    copy_btn = tk.Button(machine_frame, text="复制",
                        font=('Microsoft YaHei UI', 8),
                        bg='#f0f2f5', fg='#202124', bd=1,
                        cursor='arrow', relief='raised', padx=10, pady=2,
                        command=copy_code)
    copy_btn.pack(side=tk.LEFT, padx=(5, 0))

    # 激活输入卡片
    input_card = tk.Frame(content, bg='white')
    input_card.pack(fill=tk.BOTH, expand=True)

    tk.Label(input_card, text="🎫 输入用户码",
            font=('Microsoft YaHei UI', 12, 'bold'),
            bg='white', fg='#374151', anchor='w').pack(padx=15, pady=(12, 5))

    tk.Label(input_card, text="如果管理员已提供用户码，请在此输入：",
            font=('Microsoft YaHei UI', 9),
            bg='white', fg='#9ca3af', anchor='w').pack(padx=15, pady=(0, 8))

    serial_frame = tk.Frame(input_card, bg='white')
    serial_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

    serial_entry = tk.Entry(serial_frame,
                          font=('Consolas', 10),
                          relief='flat', bg='#f8f9fa', bd=0)
    serial_entry.pack(fill=tk.X, ipady=8)

    tk.Label(serial_frame, text="用户码为 Base64 编码的字符串",
            font=('Microsoft YaHei UI', 8),
            bg='white', fg='#9ca3af').pack(anchor='w', pady=(4, 0))

    # 提示信息
    hint_label = tk.Label(input_card, text="",
            font=('Microsoft YaHei UI', 9),
            bg='white', fg='#9ca3af')
    hint_label.pack(padx=15, pady=(0, 10))

    # 按钮
    btn_frame = tk.Frame(content, bg='#f9fafb')
    btn_frame.pack(fill=tk.X, pady=(10, 0))

    activate_btn = tk.Button(btn_frame, text="✅ 激活授权",
             font=('Microsoft YaHei UI', 11, 'bold'),
             bg='#22c55e', fg='white', bd=1,
             cursor='hand2', relief='raised', padx=20, pady=8,
             command=lambda: do_activate(serial_entry.get(), machine_code))
    activate_btn.pack(side=tk.LEFT)

    tk.Button(btn_frame, text="退出",
             font=('Microsoft YaHei UI', 10),
             bg='#f0f2f5', fg='#202124', bd=1,
             cursor='arrow', relief='raised', padx=18, pady=8,
             command=lambda: sys.exit(1)).pack(side=tk.RIGHT)

    serial_entry.focus()

    # 存储 root 引用用于关闭
    app_root = root

    def do_activate(user_code, current_machine_code):
        """执行激活操作"""
        if not user_code or not user_code.strip():
            hint_label.config(text="请输入用户码", fg='#ef4444')
            return

        user_code = user_code.strip()
        hint_label.config(text="正在验证...", fg='#fbbf24')
        activate_btn.config(state='disabled')

        # 验证用户码
        success, expiry_timestamp, auth_machine_code = decrypt_user_code(user_code)

        if not success:
            hint_label.config(text="用户码格式错误或解密失败", fg='#ef4444')
            activate_btn.config(state='normal')
            return

        # 验证机器码匹配
        if auth_machine_code != current_machine_code:
            hint_label.config(text="用户码与本机机器码不匹配", fg='#ef4444')
            activate_btn.config(state='normal')
            return

        # 检查是否过期
        if expiry_timestamp != 0:
            expiry_date = datetime.fromtimestamp(expiry_timestamp).strftime('%Y-%m-%d')
            if expiry_timestamp < int(time.time()):
                hint_label.config(text=f"用户码已过期（{expiry_date}）", fg='#ef4444')
                activate_btn.config(state='normal')
                return

        # 保存用户码
        if save_user_code(user_code):
            hint_label.config(text="激活成功！正在启动...", fg='#22c55e')
            app_root.destroy()
            # 启动主程序
            start_main_app()
        else:
            hint_label.config(text="保存用户码失败", fg='#ef4444')
            activate_btn.config(state='normal')

    serial_entry.bind('<Return>', lambda e: do_activate(serial_entry.get(), machine_code))

    def on_closing():
        sys.exit(1)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


def start_main_app():
    """启动主程序"""
    from gui.main_window import check_and_setup_credentials

    # 获取授权信息作为过期时间
    hw_info = get_hw_info()
    machine_code = generate_machine_code(hw_info)
    valid, result = verify_with_user_code(machine_code)

    if valid and result.get('days_left') != -1:
        expiry_time = datetime.fromtimestamp(result['expiry_timestamp'])
    elif valid and result.get('days_left') == -1:
        expiry_time = datetime(2099, 12, 31)  # 永久授权
    else:
        expiry_time = datetime.now()  # 默认值

    root = tk.Tk()

    # 检查是否需要首次运行设置
    needs_setup, new_credentials = check_and_setup_credentials()
    if needs_setup and new_credentials is None:
        # 用户取消设置向导
        root.destroy()
        return

    app = NqiToolGUI(root, expiry_time)
    app.run()


def main():
    """主函数"""
    valid, result, machine_code = check_license()
    if not valid:
        show_activate_dialog(machine_code)
    else:
        start_main_app()


if __name__ == '__main__':
    main()