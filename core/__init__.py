# -*- coding: utf-8 -*-
"""
core - 核心业务模块

TODO: 全项目约 16,700 行代码几乎无类型注解，函数签名全靠文档字符串推测。
      建议引入 mypy + 类型注解，提升代码可维护性和 IDE 智能提示。
"""

from .auth import LoginManager
from .query import JXCXQuery
from .export import export_to_excel, export_with_format
