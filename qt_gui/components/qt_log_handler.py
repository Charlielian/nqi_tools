# -*- coding: utf-8 -*-
"""
Qt 专用 Logging Handler 模块
将 Python 标准 logging 体系（core/query、core/workers、core/auth、utils 等所有子模块）
的日志自动捕获并无缝重定向到 Qt6 界面中的 LogViewer，实现全量日志实时同步。
"""

import logging
from PyQt6.QtCore import QObject, pyqtSignal


class QtLogBridge(QObject):
    """跨线程发射日志到 Qt 界面"""
    log_emitted = pyqtSignal(str, str)


class QtLoggingHandler(logging.Handler):
    """桥接 Python logging 与 QtLogViewer 的日志处理器"""

    def __init__(self, bridge: QtLogBridge):
        super().__init__()
        self.bridge = bridge
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            if not msg or not msg.strip():
                return
            level_name = record.levelname.upper()
            if level_name == 'CRITICAL':
                level_name = 'ERROR'
            self.bridge.log_emitted.emit(msg, level_name)
        except Exception:
            self.handleError(record)
