# -*- coding: utf-8 -*-
"""
登录对话框模块
提供图形界面的登录验证功能
"""

import tkinter as tk
from tkinter import ttk
import json

# 确保 PIL 和 tkinter 相关模块被打包
from PIL import Image, ImageTk

from utils.config import LOGIN_URL, CAPTCHA_URL, GET_CONFIG_URL, SEND_CODE_URL, HEADERS, HEADERS_JSON
from utils.crypto import rsa_encrypt


class LoginDialog:
    """图形登录状态机。

    图形验证码通过后才允许发送短信，最终以 CASTGC Cookie 判定登录成功；
    HTTP 200 只代表请求有响应，不能替代接口返回的业务标志。当前网络
    请求仍在 Tk 主线程事件回调中执行，``verify=False`` 只是企业证书兼容
    的技术债务，不构成安全传输保证。
    """

    def __init__(self, parent, username, password, session):
        self.username = username
        self.password = password
        self.sess = session
        self.result = False
        self.msg_code = None

        # 确保 session 禁用 SSL 验证
        # TODO: self.sess.verify = False 在全项目 5+ 处重复，应统一在 Session 创建时设置一次
        self.sess.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("登录验证")
        self.dialog.geometry("400x480")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (480 // 2)
        self.dialog.geometry(f'400x480+{x}+{y}')

        self._create_widgets()
        self._fetch_captcha()

        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        """创建对话框组件"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="请完成安全验证",
                 font=("Arial", 12, "bold")).pack(pady=(0, 15))

        captcha_frame = ttk.LabelFrame(main_frame, text="图形验证码", padding="10")
        captcha_frame.pack(fill=tk.X, pady=10)

        self.captcha_label = ttk.Label(captcha_frame)
        self.captcha_label.pack()

        captcha_input_frame = ttk.Frame(captcha_frame)
        captcha_input_frame.pack(fill=tk.X, pady=10)

        ttk.Label(captcha_input_frame, text="验证码:").pack(side=tk.LEFT)
        self.captcha_var = tk.StringVar()
        self.captcha_entry = ttk.Entry(captcha_input_frame, textvariable=self.captcha_var, width=10)
        self.captcha_entry.pack(side=tk.LEFT, padx=10)
        self.captcha_entry.focus()

        ttk.Button(captcha_input_frame, text="刷新",
                  command=self._fetch_captcha).pack(side=tk.LEFT, padx=5)
        ttk.Button(captcha_input_frame, text="验证图形码",
                  command=self._verify_captcha).pack(side=tk.LEFT)

        self.captcha_msg = ttk.Label(captcha_frame, text="", foreground="blue")
        self.captcha_msg.pack(pady=5)

        sms_frame = ttk.LabelFrame(main_frame, text="短信验证码", padding="10")
        sms_frame.pack(fill=tk.X, pady=10)

        self.sms_var = tk.StringVar()
        sms_input_frame = ttk.Frame(sms_frame)
        sms_input_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sms_input_frame, text="短信码:").pack(side=tk.LEFT)
        self.sms_entry = ttk.Entry(sms_input_frame, textvariable=self.sms_var, width=15)
        self.sms_entry.pack(side=tk.LEFT, padx=10)
        self.sms_entry.bind('<Return>', lambda e: self._submit())

        self.send_sms_btn = ttk.Button(sms_input_frame, text="发送短信",
                                       command=self._send_sms, state=tk.DISABLED)
        self.send_sms_btn.pack(side=tk.LEFT, padx=5)

        self.sms_msg = ttk.Label(sms_frame, text="请先验证图形验证码", foreground="gray")
        self.sms_msg.pack(pady=5)

        self.countdown_label = ttk.Label(sms_frame, text="", foreground="red")
        self.countdown_label.pack()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        self.submit_btn = ttk.Button(btn_frame, text="确认登录",
                                    command=self._submit, width=15)
        self.submit_btn.pack(side=tk.LEFT, padx=10)

        ttk.Button(btn_frame, text="取消",
                  command=self._on_close, width=10).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="请先输入图形验证码，点击【验证图形码】")
        ttk.Label(main_frame, textvariable=self.status_var,
                 foreground="green").pack(pady=10)

    def _verify_captcha(self):
        """验证图形验证码"""
        from lxml import etree

        captcha_code = self.captcha_var.get().strip()

        if not captcha_code:
            self.captcha_msg.config(text="请输入图形验证码", foreground="red")
            self.status_var.set("请先输入图形验证码")
            return

        self.status_var.set("正在验证图形验证码...")
        self.captcha_msg.config(text="验证中...")

        try:
            html_res = self.sess.get(LOGIN_URL, headers=HEADERS)
            html_res.encoding = 'utf-8'
            html = etree.HTML(html_res.text)
            public_key = html.xpath('//*[@type="text/javascript"]/text()')[0].split('setPublicKey("')[1].split('")')[0]

            username_e = rsa_encrypt(self.username, public_key)
            password_e = rsa_encrypt(self.password, public_key)

            data = {
                'password': password_e,
                'loginId': username_e,
                'captcha': captcha_code,
            }
            res = self.sess.post(GET_CONFIG_URL, data=json.dumps(data), headers=HEADERS_JSON)

            if res.status_code == 200:
                result = json.loads(res.text)
                if result.get('code') == '1':
                    self.captcha_msg.config(text="图形验证码正确 ✓", foreground="green")
                    self.captcha_entry.config(state=tk.DISABLED)
                    self.send_sms_btn.config(state=tk.NORMAL)
                    self.status_var.set("图形验证码正确！请点击【发送短信】")
                    self._encrypted_username = username_e
                    self._encrypted_password = password_e
                else:
                    self.captcha_msg.config(text="图形验证码错误，请重试", foreground="red")
                    self.status_var.set("图形验证码错误，请重新输入")
                    self.captcha_entry.select_clear()
                    self.captcha_entry.focus()
            else:
                self.status_var.set(f"验证请求失败 ({res.status_code})")
                self.captcha_msg.config(text=f"请求失败 ({res.status_code})", foreground="red")
        except Exception as e:
            error_msg = str(e)
            if "CERTIFICATE" in error_msg.upper() or "SSL" in error_msg.upper() or "SSLError" in error_msg:
                self.sess.verify = False
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                self.status_var.set("SSL证书问题，已尝试绕过，请重试")
                self.captcha_msg.config(text="SSL错误已处理，请点击【刷新】重新获取验证码", foreground="orange")
            else:
                self.status_var.set(f"验证失败: {error_msg}")
                self.captcha_msg.config(text=f"错误: {error_msg}", foreground="red")

    def _fetch_captcha(self):
        """获取图形验证码"""
        # 首先确保 SSL 验证被禁用（可能在exe环境中需要）
        if not self.sess.verify:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        try:
            captcha_res = self.sess.get(CAPTCHA_URL, timeout=15)
            if captcha_res.status_code == 200:
                from PIL import Image, ImageTk
                from io import BytesIO

                bytes_stream = BytesIO(captcha_res.content)
                img = Image.open(bytes_stream)
                img = img.resize((200, 80), Image.Resampling.LANCZOS)
                self.captcha_photo = ImageTk.PhotoImage(img)
                self.captcha_label.config(image=self.captcha_photo)

                self.captcha_img_data = captcha_res.content
                self.captcha_var.set('')
                self.captcha_entry.config(state=tk.NORMAL)
                self.send_sms_btn.config(state=tk.DISABLED)
                self.status_var.set("请输入图形验证码，点击【验证图形码】")
                self.captcha_msg.config(text="请输入图片中的验证码")
                self.sms_msg.config(text="请先验证图形验证码")
                self.captcha_entry.focus()
            else:
                self.status_var.set(f"获取验证码失败 ({captcha_res.status_code})")
                self.captcha_msg.config(text=f"获取失败 ({captcha_res.status_code})", foreground="red")
        except Exception as e:
            error_msg = str(e)
            # 尝试重新禁用 SSL 验证并重试
            if "CERTIFICATE" in error_msg.upper() or "SSL" in error_msg.upper() or "SSLError" in error_msg:
                self.sess.verify = False
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                try:
                    captcha_res = self.sess.get(CAPTCHA_URL, timeout=15)
                    if captcha_res.status_code == 200:
                        from PIL import Image, ImageTk
                        from io import BytesIO

                        bytes_stream = BytesIO(captcha_res.content)
                        img = Image.open(bytes_stream)
                        img = img.resize((200, 80), Image.Resampling.LANCZOS)
                        self.captcha_photo = ImageTk.PhotoImage(img)
                        self.captcha_label.config(image=self.captcha_photo)

                        self.captcha_img_data = captcha_res.content
                        self.captcha_var.set('')
                        self.captcha_entry.config(state=tk.NORMAL)
                        self.send_sms_btn.config(state=tk.DISABLED)
                        self.status_var.set("请输入图形验证码，点击【验证图形码】")
                        self.captcha_msg.config(text="请输入图片中的验证码")
                        self.sms_msg.config(text="请先验证图形验证码")
                        self.captcha_entry.focus()
                        return
                except Exception:
                    pass
            if "timeout" in error_msg.lower():
                self.status_var.set("连接超时，请检查网络")
                self.captcha_msg.config(text="连接超时，请检查网络或稍后重试", foreground="red")
            else:
                self.status_var.set(f"获取验证码失败: {error_msg}")
                self.captcha_msg.config(text=f"错误: {error_msg}", foreground="red")

    def _send_sms(self):
        """发送短信验证码"""
        if not hasattr(self, '_encrypted_username') or not hasattr(self, '_encrypted_password'):
            self.captcha_msg.config(text="请先验证图形验证码", foreground="red")
            self.status_var.set("请先完成图形验证码验证")
            return

        self.status_var.set("正在发送短信验证码...")
        self.send_sms_btn.config(state=tk.DISABLED)

        try:
            data_sms = {'loginId': self._encrypted_username, 'password': self._encrypted_password}
            res_sms = self.sess.post(SEND_CODE_URL, data=json.dumps(data_sms), headers=HEADERS_JSON)
            result_sms = json.loads(res_sms.text)

            if result_sms.get('msg') == 'success':
                self.sms_msg.config(text="短信验证码已发送，请查收 ✓", foreground="green")
                self.status_var.set("短信已发送，请在下方输入短信验证码后按回车或点击【确认登录】")
                self._start_countdown(60)
                self.sms_entry.focus()
            else:
                self.sms_msg.config(text="短信发送失败，请重试", foreground="red")
                self.status_var.set("短信发送失败")
                self.send_sms_btn.config(state=tk.NORMAL)

        except Exception as e:
            self.sms_msg.config(text=f"发送失败: {e}", foreground="red")
            self.status_var.set(f"短信发送失败: {e}")
            self.send_sms_btn.config(state=tk.NORMAL)

    def _start_countdown(self, seconds):
        """倒计时"""
        if seconds > 0:
            self.countdown_label.config(text=f"请在 {seconds} 秒内输入")
            self.dialog.after(1000, lambda: self._start_countdown(seconds - 1))
        else:
            self.countdown_label.config(text="验证码可能已过期")

    def _submit(self):
        """提交验证"""
        from lxml import etree

        msg_code = self.sms_var.get().strip()

        if not msg_code:
            self.sms_msg.config(text="请输入短信验证码", foreground="red")
            self.status_var.set("请输入短信验证码")
            return

        if not hasattr(self, '_encrypted_username') or not hasattr(self, '_encrypted_password'):
            self.sms_msg.config(text="请先完成图形验证码验证", foreground="red")
            self.status_var.set("请先完成图形验证码验证")
            return

        self.status_var.set("正在验证短信验证码...")
        self.submit_btn.config(state=tk.DISABLED)

        try:
            html_res = self.sess.get(LOGIN_URL, headers=HEADERS)
            html_res.encoding = 'utf-8'
            html = etree.HTML(html_res.text)
            execution = html.xpath('//*[@id="fm1"]/div[4]/input[1]')[0].attrib.get('value')

            login_data = {
                'password': self._encrypted_password,
                'username': self._encrypted_username,
                'msgCode': msg_code,
                'captcha': self.captcha_var.get().strip(),
                'uuid': '',
                'execution': execution,
                '_eventId': 'submit',
                'geolocation': ''
            }

            res_login = self.sess.post(LOGIN_URL, data=login_data, headers=HEADERS)

            # 登录 POST 的状态码不是最终判据；CASTGC 才表示统一认证已完成。
            if self.sess.cookies.get('CASTGC'):
                self.msg_code = msg_code
                self.result = True
                self.status_var.set("登录成功！")
                self.sms_msg.config(text="登录成功 ✓", foreground="green")
                self.dialog.after(500, self.dialog.destroy)
            else:
                self.sms_msg.config(text="短信验证码错误", foreground="red")
                self.status_var.set("短信验证码错误，请重试")
                self.submit_btn.config(state=tk.NORMAL)

        except Exception as e:
            self.status_var.set(f"验证失败: {e}")
            self.sms_msg.config(text=f"错误: {e}", foreground="red")
            self.submit_btn.config(state=tk.NORMAL)

    def _on_close(self):
        """关闭窗口"""
        self.result = False
        self.dialog.destroy()

    def show(self):
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result
