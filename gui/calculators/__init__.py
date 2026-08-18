# -*- coding: utf-8 -*-
"""
计算列模块
从 main_window.py 提取的 DataFrame 计算逻辑，与 GUI 解耦。
所有函数均为纯函数：df in -> df out，可通过可选的 log 回调输出日志。
"""

from gui.calculators.voice_calc import add_4g_voice_calc_columns
from gui.calculators.wanchenglv_calc import (
    add_4g_wanchenglv_calc_columns,
    add_5g_wanchenglv_calc_columns,
)

__all__ = [
    'add_4g_voice_calc_columns',
    'add_4g_wanchenglv_calc_columns',
    'add_5g_wanchenglv_calc_columns',
]
