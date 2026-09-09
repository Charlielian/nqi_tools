# -*- coding: utf-8 -*-
"""
Qt6 现代化安全登录对话框 (图形验证码 + 短信验证码)
完全对齐 Tkinter 版本的 LoginDialog 认证安全流程
"""

import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QPixmap, QImage

from utils.config import LOGIN_URL, CAPTCHA_URL, GET_CONFIG_URL, SEND_CODE_URL, HEADERS, HEADERS_JSON
from utils.crypto import rsa_encrypt


class QtLoginDialog(QDialog):
    """Qt6 现代化登录验证安全对话框"""

    def __init__(self, parent=None, username="", password="", session=None):
        super().__init__(parent)
        self.setWindowTitle("统一安全身份认证")
        self.setFixedSize(420, 520)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self.username = username
        self.password = password
        self.sess = session
        self.result = False

        self._encrypted_username = None
        self._encrypted_password = None
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._remaining_seconds = 0

        self._init_ui()
        self._fetch_captcha()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 头部标题
        title_box = QVBoxLayout()
        title_lbl = QLabel("请完成安全双因子验证")
        title_lbl.setObjectName("MainTitle")
        user_lbl = QLabel(f"登录账号: {self.username}")
        user_lbl.setObjectName("HintLabel")
        title_box.addWidget(title_lbl)
        title_box.addWidget(user_lbl)
        main_layout.addLayout(title_box)

        # 1. 图形验证码卡片
        self.card_captcha = QFrame()
        self.card_captcha.setObjectName("CardFrame")
        c_layout = QVBoxLayout(self.card_captcha)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(10)

        c_title = QLabel("第一步：图形验证码")
        c_title.setObjectName("CardTitle")
        c_layout.addWidget(c_title)

        # 验证码图片与刷新
        img_row = QHBoxLayout()
        self.lbl_captcha_img = QLabel()
        self.lbl_captcha_img.setFixedSize(200, 70)
        self.lbl_captcha_img.setStyleSheet("background-color: #F2F3F5; border: 1px solid #E5E6EB; border-radius: 4px;")
        self.lbl_captcha_img.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._fetch_captcha)
        img_row.addWidget(self.lbl_captcha_img)
        img_row.addWidget(self.btn_refresh)
        img_row.addStretch()
        c_layout.addLayout(img_row)

        # 输入与验证按钮
        input_row = QHBoxLayout()
        self.entry_captcha = QLineEdit()
        self.entry_captcha.setPlaceholderText("输入上图验证码")
        self.entry_captcha.setFixedHeight(34)
        self.entry_captcha.returnPressed.connect(self._verify_captcha)

        self.btn_verify_captcha = QPushButton("验证图形码")
        self.btn_verify_captcha.setObjectName("PrimaryButton")
        self.btn_verify_captcha.setFixedHeight(34)
        self.btn_verify_captcha.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_verify_captcha.clicked.connect(self._verify_captcha)

        input_row.addWidget(self.entry_captcha, stretch=2)
        input_row.addWidget(self.btn_verify_captcha, stretch=1)
        c_layout.addLayout(input_row)

        self.lbl_captcha_msg = QLabel("请输入图片中的4位验证码")
        self.lbl_captcha_msg.setObjectName("HintLabel")
        c_layout.addWidget(self.lbl_captcha_msg)

        main_layout.addWidget(self.card_captcha)

        # 2. 短信验证码卡片
        self.card_sms = QFrame()
        self.card_sms.setObjectName("CardFrame")
        s_layout = QVBoxLayout(self.card_sms)
        s_layout.setContentsMargins(14, 12, 14, 12)
        s_layout.setSpacing(10)

        s_title = QLabel("第二步：短信验证码")
        s_title.setObjectName("CardTitle")
        s_layout.addWidget(s_title)

        sms_row = QHBoxLayout()
        self.entry_sms = QLineEdit()
        self.entry_sms.setPlaceholderText("请输入收到的短信验证码")
        self.entry_sms.setFixedHeight(34)
        self.entry_sms.setEnabled(False)
        self.entry_sms.returnPressed.connect(self._submit)

        self.btn_send_sms = QPushButton("📨 发送短信")
        self.btn_send_sms.setFixedHeight(34)
        self.btn_send_sms.setEnabled(False)
        self.btn_send_sms.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_sms.clicked.connect(self._send_sms)

        sms_row.addWidget(self.entry_sms, stretch=2)
        sms_row.addWidget(self.btn_send_sms, stretch=1)
        s_layout.addLayout(sms_row)

        self.lbl_sms_msg = QLabel("请先通过上方的图形验证码")
        self.lbl_sms_msg.setObjectName("HintLabel")
        s_layout.addWidget(self.lbl_sms_msg)

        main_layout.addWidget(self.card_sms)

        # 3. 底部提交确认
        bottom_layout = QHBoxLayout()
        self.btn_submit = QPushButton("确认登录并开始使用")
        self.btn_submit.setObjectName("PrimaryButton")
        self.btn_submit.setFixedHeight(38)
        self.btn_submit.setEnabled(False)
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.clicked.connect(self._submit)

        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedHeight(38)
        btn_cancel.clicked.connect(self.reject)

        bottom_layout.addWidget(btn_cancel, stretch=1)
        bottom_layout.addWidget(self.btn_submit, stretch=2)
        main_layout.addLayout(bottom_layout)

    def _fetch_captcha(self):
        """拉取图形验证码"""
        try:
            res = self.sess.get(CAPTCHA_URL, timeout=15)
            if res.status_code == 200:
                qimg = QImage()
                qimg.loadFromData(res.content)
                pixmap = QPixmap.fromImage(qimg).scaled(200, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_captcha_img.setPixmap(pixmap)

                self.entry_captcha.clear()
                self.entry_captcha.setEnabled(True)
                self.btn_verify_captcha.setEnabled(True)
                self.lbl_captcha_msg.setText("请输入图片中的4位验证码")
                self.lbl_captcha_msg.setStyleSheet("color: #4E5969;")
            else:
                self.lbl_captcha_msg.setText(f"获取验证码失败 ({res.status_code})")
                self.lbl_captcha_msg.setStyleSheet("color: #F53F3F;")
        except Exception as e:
            self.lbl_captcha_msg.setText(f"网络异常: {e}")
            self.lbl_captcha_msg.setStyleSheet("color: #F53F3F;")

    def _verify_captcha(self):
        """验证图形验证码并提取RSA密钥"""
        code = self.entry_captcha.text().strip()
        if not code:
            self.lbl_captcha_msg.setText("请输入图形验证码")
            self.lbl_captcha_msg.setStyleSheet("color: #F53F3F;")
            return

        self.lbl_captcha_msg.setText("正在校验图形码...")
        self.lbl_captcha_msg.setStyleSheet("color: #165DFF;")

        try:
            from lxml import etree
            html_res = self.sess.get(LOGIN_URL, headers=HEADERS)
            html_res.encoding = 'utf-8'
            html = etree.HTML(html_res.text)
            public_key = html.xpath('//*[@type="text/javascript"]/text()')[0].split('setPublicKey("')[1].split('")')[0]

            username_e = rsa_encrypt(self.username, public_key)
            password_e = rsa_encrypt(self.password, public_key)

            data = {
                'password': password_e,
                'loginId': username_e,
                'captcha': code,
            }
            res = self.sess.post(GET_CONFIG_URL, data=json.dumps(data), headers=HEADERS_JSON)

            if res.status_code == 200:
                result = json.loads(res.text)
                if result.get('code') == '1':
                    self.lbl_captcha_msg.setText("✓ 图形验证码正确")
                    self.lbl_captcha_msg.setStyleSheet("color: #00B42A; font-weight: bold;")
                    self.entry_captcha.setEnabled(False)
                    self.btn_verify_captcha.setEnabled(False)
                    self.btn_refresh.setEnabled(False)

                    self._encrypted_username = username_e
                    self._encrypted_password = password_e

                    # 解锁短信部分
                    self.btn_send_sms.setEnabled(True)
                    self.entry_sms.setEnabled(True)
                    self.lbl_sms_msg.setText("请点击【发送短信】接收验证码")
                    self.lbl_sms_msg.setStyleSheet("color: #165DFF;")
                else:
                    self.lbl_captcha_msg.setText("图形验证码错误，请重新输入")
                    self.lbl_captcha_msg.setStyleSheet("color: #F53F3F;")
                    self._fetch_captcha()
            else:
                self.lbl_captcha_msg.setText(f"服务器返回错误 ({res.status_code})")
                self.lbl_captcha_msg.setStyleSheet("color: #F53F3F;")
        except Exception as e:
            self.lbl_captcha_msg.setText(f"校验失败: {e}")
            self.lbl_captcha_msg.setStyleSheet("color: #F53F3F;")

    def _send_sms(self):
        """发送短信验证码"""
        try:
            data = {'loginId': self._encrypted_username, 'password': self._encrypted_password}
            res = self.sess.post(SEND_CODE_URL, data=json.dumps(data), headers=HEADERS_JSON)
            result = json.loads(res.text)
            if result.get('msg') == 'success':
                self.lbl_sms_msg.setText("✓ 短信验证码已发送，请查收")
                self.lbl_sms_msg.setStyleSheet("color: #00B42A;")
                self.btn_submit.setEnabled(True)
                self.entry_sms.setFocus()
                self._start_countdown(60)
            else:
                self.lbl_sms_msg.setText(f"短信发送失败: {result.get('msg', '未知错误')}")
                self.lbl_sms_msg.setStyleSheet("color: #F53F3F;")
        except Exception as e:
            self.lbl_sms_msg.setText(f"发送异常: {e}")
            self.lbl_sms_msg.setStyleSheet("color: #F53F3F;")

    def _start_countdown(self, seconds: int):
        self._remaining_seconds = seconds
        self.btn_send_sms.setEnabled(False)
        self._countdown_timer.start(1000)

    def _on_countdown_tick(self):
        self._remaining_seconds -= 1
        if self._remaining_seconds > 0:
            self.btn_send_sms.setText(f"重新发送({self._remaining_seconds}s)")
        else:
            self._countdown_timer.stop()
            self.btn_send_sms.setText("重新发送")
            self.btn_send_sms.setEnabled(True)

    def _submit(self):
        """提交短信验证码，完成最终登录"""
        sms_code = self.entry_sms.text().strip()
        if not sms_code:
            self.lbl_sms_msg.setText("请输入短信验证码")
            self.lbl_sms_msg.setStyleSheet("color: #F53F3F;")
            return

        self.lbl_sms_msg.setText("正在提交认证中...")
        self.lbl_sms_msg.setStyleSheet("color: #165DFF;")
        self.btn_submit.setEnabled(False)

        try:
            from lxml import etree
            html_res = self.sess.get(LOGIN_URL, headers=HEADERS)
            html_res.encoding = 'utf-8'
            html = etree.HTML(html_res.text)
            execution = html.xpath('//*[@id="fm1"]/div[4]/input[1]')[0].attrib.get('value')

            login_data = {
                'password': self._encrypted_password,
                'username': self._encrypted_username,
                'msgCode': sms_code,
                'captcha': self.entry_captcha.text().strip(),
                'uuid': '',
                'execution': execution,
                '_eventId': 'submit',
                'geolocation': ''
            }

            self.sess.post(LOGIN_URL, data=login_data, headers=HEADERS)

            if self.sess.cookies.get('CASTGC'):
                self.lbl_sms_msg.setText("🎉 认证通过，登录成功！")
                self.lbl_sms_msg.setStyleSheet("color: #00B42A; font-weight: bold;")
                self.result = True
                QTimer.singleShot(600, self.accept)
            else:
                self.lbl_sms_msg.setText("短信验证码不正确或已失效，请重试")
                self.lbl_sms_msg.setStyleSheet("color: #F53F3F;")
                self.btn_submit.setEnabled(True)
        except Exception as e:
            self.lbl_sms_msg.setText(f"登录异常: {e}")
            self.lbl_sms_msg.setStyleSheet("color: #F53F3F;")
            self.btn_submit.setEnabled(True)
