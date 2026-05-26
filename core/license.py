# -*- coding: utf-8 -*-
"""
授权管理模块
仅基于 EXPIRY_DATE 进行过期验证，不使用任何外部授权文件
"""

import threading
import time
import logging

logger = logging.getLogger(__name__)


class TimeMonitor:
    """系统时间监控器 - 后台运行，检测时间回拨"""

    def __init__(self, interval=30, callback=None):
        self.interval = interval
        self.callback = callback
        self.last_time = None
        self.running = False
        self._thread = None

    def _check_time(self):
        """检查时间是否回拨"""
        current_time = time.time()
        if self.last_time is not None:
            if current_time < self.last_time:
                return True
        self.last_time = current_time
        return False

    def _monitor_loop(self):
        """监控循环"""
        self.last_time = time.time()
        while self.running:
            time.sleep(self.interval)
            if not self.running:
                break
            if self._check_time():
                if self.callback:
                    self.callback()
                self.running = False
                break

    def start(self):
        """启动监控"""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监控"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
