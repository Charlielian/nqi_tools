# -*- coding: utf-8 -*-
"""
日志系统模块
提供同时输出到控制台和日志文件的日志功能
"""

import sys
import logging
import io
import os

from utils.config import LOG_DIR


class TeeLogger:
    """同时输出到控制台和日志文件的日志系统"""
    _instance = None
    _log_file = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.handlers = []

    def add_file_handler(self, filepath):
        """添加文件日志处理器"""
        self._log_file = filepath
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        handler = logging.FileHandler(filepath, encoding='utf-8')
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
        self.handlers.append(handler)

    def write(self, message):
        """同时输出到控制台和日志文件"""
        sys.__stdout__.write(message)
        if self._log_file:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(message)


_original_print = print
_log_file_path = None


def set_log_file(filepath):
    """设置日志文件路径并启用日志记录"""
    global _log_file_path
    _log_file_path = filepath
    TeeLogger.get_instance().add_file_handler(filepath)


def debug_print(*args, **kwargs):
    """增强的print函数，同时输出到控制台和日志文件"""
    import traceback
    stack = traceback.extract_stack()
    caller = stack[-2] if len(stack) >= 2 else None

    output = io.StringIO()
    kwargs['file'] = output
    kwargs['end'] = kwargs.get('end', '\n')
    _original_print(*args, **kwargs)
    message = output.getvalue()
    output.close()

    _print_kwargs = {k: v for k, v in kwargs.items() if k != 'file'}
    _original_print(*args, **_print_kwargs)

    if _log_file_path:
        with open(_log_file_path, 'a', encoding='utf-8') as f:
            f.write(message)


def ensure_dirs():
    """确保必要的目录存在"""
    from utils.config import OUTPUT_DIR, COOKIE_DIR, CAPTCHA_DIR
    for dir_path in [OUTPUT_DIR, COOKIE_DIR, CAPTCHA_DIR, LOG_DIR]:
        os.makedirs(dir_path, exist_ok=True)
