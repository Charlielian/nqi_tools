# -*- coding: utf-8 -*-
"""
首次运行引导模块
用于首次运行时配置用户名、密码等凭证
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os

from utils.config import get_app_path


class FirstRunWizard:
    """首次运行凭证配置向导。

    有父窗口时使用模态 Toplevel 并等待关闭；保存时只更新 YAML 的
    ``auth`` 节点，保留其他配置。当前实现把用户名和密码明文写入
    ``config.yaml``，界面中的“安全存储”不能理解为加密存储。
    """

    def __init__(self, parent=None):
        self.result = None
        self.credentials = None

        self.root = tk.Tk() if parent is None else tk.Toplevel(parent)
        self.root.title("NQI工具 - 初始配置")
        self.root.geometry("450x280")
        self.root.resizable(False, False)
        self.root.transient(parent) if parent else None

        # 居中显示
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (450 // 2)
        y = (self.root.winfo_screenheight() // 2) - (280 // 2)
        self.root.geometry(f'450x280+{x}+{y}')

        self._create_widgets()
        self._load_existing_credentials()

        if parent:
            self.root.grab_set()

    def _create_widgets(self):
        """创建向导组件"""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        ttk.Label(main_frame, text="首次运行配置",
                 font=("Arial", 14, "bold")).pack(pady=(0, 5))

        ttk.Label(main_frame, text="请输入您的NQI平台登录凭证",
                 foreground="gray").pack(pady=(0, 20))

        # 凭证输入框
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=10)

        ttk.Label(form_frame, text="用户名:").grid(row=0, column=0, sticky=tk.W, pady=10)
        self.username_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.username_var,
                 width=30).grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(form_frame, text="密码:").grid(row=1, column=0, sticky=tk.W, pady=10)
        self.password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.password_var,
                 width=30, show="*").grid(row=1, column=1, padx=10, pady=10)

        # 提示
        ttk.Label(main_frame, text="凭证将安全存储在本地配置文件中",
                 foreground="#666666", font=("Arial", 9)).pack(pady=(10, 0))

        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="保存并继续",
                  command=self._save_credentials,
                  width=12).pack(side=tk.LEFT, padx=10)

        ttk.Button(btn_frame, text="取消",
                  command=self._on_cancel,
                  width=10).pack(side=tk.LEFT)

    def _load_existing_credentials(self):
        """加载已保存的凭证"""
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                if config and 'auth' in config:
                    self.username_var.set(config['auth'].get('username', ''))
                    self.password_var.set(config['auth'].get('password', ''))
            except Exception:
                pass

    def _get_config_path(self):
        """获取配置文件路径"""
        return os.path.join(get_app_path(), 'config.yaml')

    def _save_credentials(self):
        """保存凭证到配置文件"""
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username:
            messagebox.showwarning("提示", "请输入用户名")
            return

        if not password:
            messagebox.showwarning("提示", "请输入密码")
            return

        try:
            config_path = self._get_config_path()
            import yaml

            # 读取现有配置或创建新配置
            config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                except Exception:
                    pass

            # 更新凭证
            if 'auth' not in config:
                config['auth'] = {}
            config['auth']['username'] = username
            config['auth']['password'] = password

            # 写入配置。这里没有加密或系统密钥环保护，保存的是明文 YAML；
            # 但只更新 auth 节点，避免覆盖用户已有的其他配置项。
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            self.credentials = {'username': username, 'password': password}
            self.result = True

            messagebox.showinfo("成功", "凭证已保存！")
            self.root.destroy()

        except Exception as e:
            messagebox.showerror("错误", f"保存凭证失败: {e}")

    def _on_cancel(self):
        """取消"""
        self.result = False
        self.root.destroy()

    def show(self):
        """显示向导并返回结果"""
        self.root.wait_window()
        return self.result, self.credentials


def check_first_run():
    """检查是否需要首次运行引导

    Returns:
        bool: True表示需要首次引导，False表示已配置过
    """
    config_path = os.path.join(get_app_path(), 'config.yaml')
    if not os.path.exists(config_path):
        return True

    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if config and 'auth' in config:
            username = config['auth'].get('username', '')
            password = config['auth'].get('password', '')
            # 检查是否是示例值
            if username and username != 'XXXXX' and password and password != 'XXXX':
                return False
    except Exception:
        pass

    return True


def show_first_run_wizard(parent=None):
    """显示首次运行向导

    Args:
        parent: 父窗口

    Returns:
        tuple: (success, credentials)
    """
    wizard = FirstRunWizard(parent)
    return wizard.show()
