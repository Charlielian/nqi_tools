# -*- coding: utf-8 -*-
"""
报表字段配置模块 - 从 field_configs.json 动态加载

字段数据已迁移到 gui/field_configs.json，修改配置只需编辑 JSON 文件，无需改代码。
本模块保持向后兼容，所有导入语句（from gui.field_configs import XXX）继续有效。

特性：
- 模块导入时自动加载 JSON 数据
- 提供 reload() 函数支持外部修改 JSON 后的热重载
- 兼容 PyInstaller 打包环境

用法：
    from gui.field_configs import INTERFERENCE_5G_FIELDS  # 自动加载
    from gui.field_configs import reload  # 或手动重载
    reload()  # 外部修改 field_configs.json 后执行
"""

import json
import os
import sys
import logging

logger = logging.getLogger(__name__)

_CONFIG_FILE = 'field_configs.json'


def _find_config_path():
    """查找 field_configs.json 文件路径（兼容 PyInstaller 打包）"""
    # 优先查找 gui 包同目录
    gui_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(gui_dir, _CONFIG_FILE)
    if os.path.exists(path):
        return path

    # PyInstaller 打包环境（_MEIPASS）
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        path = os.path.join(base, 'gui', _CONFIG_FILE)
        if os.path.exists(path):
            return path
        path = os.path.join(base, _CONFIG_FILE)
        if os.path.exists(path):
            return path

    # 尝试程序根目录
    from utils.config import get_base_path
    path = os.path.join(get_base_path(), 'gui', _CONFIG_FILE)
    if os.path.exists(path):
        return path

    return None


def load_field_configs():
    """加载所有字段配置，返回 {变量名: 值} 字典"""
    path = _find_config_path()
    if path is None:
        logger.error("未找到字段配置文件: %s", _CONFIG_FILE)
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def reload():
    """重新加载配置（外部修改 JSON 后可调用），返回模块自身"""
    new_configs = load_field_configs()
    globals().update(new_configs)
    logger.info("字段配置已重新加载，共 %d 个配置项", len(new_configs))
    return globals()


# ====== 模块导入时自动加载 ======
_field_configs = load_field_configs()
if _field_configs:
    globals().update(_field_configs)
    logger.info("字段配置加载完成，共 %d 个配置项", len(_field_configs))
else:
    logger.warning("字段配置为空，请检查 %s 文件", _CONFIG_FILE)