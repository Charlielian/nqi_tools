# -*- coding: utf-8 -*-
"""
辅助函数模块
提供验证码处理、Cookie管理等辅助功能
"""

import os
import pickle

from utils.config import COOKIE_DIR, CAPTCHA_DIR, HEADERS
from utils.logger import ensure_dirs


def save_cookie(cookie, username):
    """保存cookie到文件"""
    ensure_dirs()
    filepath = os.path.join(COOKIE_DIR, f'{username}.pkl')
    with open(filepath, 'wb') as f:
        pickle.dump(cookie, f)


def load_cookie(username):
    """从文件加载cookie"""
    filepath = os.path.join(COOKIE_DIR, f'{username}.pkl')
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    return None


def captcha_handle(img_content, attempt=1):
    """验证码处理（OCR识别）"""
    try:
        from PIL import Image, ImageFilter
        import pytesseract
        from io import BytesIO

        bytes_stream = BytesIO(img_content)
        img = Image.open(bytes_stream)
        img_gray = img.convert('L')
        img_black_white = img_gray.point(lambda x: 255 if x > 85 else 0)
        img_qucao = img_black_white.filter(ImageFilter.SMOOTH_MORE)
        img = img_qucao.convert('RGB')

        config = '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        result = pytesseract.image_to_string(img, config=config)[0:4].replace('\n', '')
        return result
    except Exception as e:
        print(f"验证码OCR识别失败: {e}")
        ensure_dirs()
        img_path = os.path.join(CAPTCHA_DIR, f'captcha_{attempt}.jpg')
        with open(img_path, 'wb') as f:
            f.write(img_content)
        return None


def encode_payload(payload):
    """URL编码payload"""
    from urllib.parse import urlencode
    return urlencode(payload, safe='', encoding='utf-8')


def get_timestamp():
    """获取当前时间戳（毫秒）"""
    import time
    return str(int(time.time() * 1000))
