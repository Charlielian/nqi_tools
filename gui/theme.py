# -*- coding: utf-8 -*-
"""
GUI 主题配置模块
集中管理界面色彩、字体和样式常量
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class ColorPalette:
    """色彩调色板"""
    # 主色调
    primary: str = '#165DFF'       # 主色蓝
    primary_dark: str = '#1a6ce8'   # 主色深蓝
    primary_light: str = '#e0e7ff'  # 主色浅色

    # 语义色
    success: str = '#22c55e'       # 成功绿
    warning: str = '#f59e0b'       # 警告橙
    error: str = '#ef4444'         # 错误红
    info: str = '#3b82f6'          # 信息蓝

    # 中性色
    white: str = '#ffffff'
    black: str = '#000000'
    gray_50: str = '#f9fafb'       # 背景灰
    gray_100: str = '#f3f4f6'      # 卡片灰
    gray_200: str = '#e5e7eb'      # 边框灰
    gray_300: str = '#d1d5db'      # 禁用灰
    gray_400: str = '#9ca3af'      # 占位符灰
    gray_500: str = '#6b7280'      # 次要文字
    gray_600: str = '#4b5563'      # 主要文字
    gray_700: str = '#374151'      # 标题文字
    gray_800: str = '#1f2937'      # 深色文字
    gray_900: str = '#111827'      # 最深文字

    # 状态色
    status_ready: str = '#a5b4fc'   # 就绪状态
    status_active: str = '#22c55e' # 激活状态
    status_error: str = '#ef4444'  # 错误状态

    # 日志色
    log_info: str = '#333333'
    log_warning: str = '#FFA500'
    log_error: str = '#FF0000'
    log_success: str = '#00AA00'


@dataclass
class FontConfig:
    """字体配置"""
    family: str = 'Microsoft YaHei UI'
    family_fallback: str = 'Segoe UI, sans-serif'
    family_emoji: str = 'Segoe UI Emoji'

    # 字号
    size_xs: int = 9
    size_sm: int = 10
    size_md: int = 11
    size_lg: int = 12
    size_xl: int = 14
    size_2xl: int = 16
    size_3xl: int = 18

    # 标题字号
    title: int = 18
    subtitle: int = 14
    body: int = 11
    caption: int = 9


@dataclass
class SpacingConfig:
    """间距配置"""
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20
    xxl: int = 24

    # 卡片间距
    card_padding: int = 16
    card_margin: int = 12

    # 组件间距
    component_gap: int = 10
    section_gap: int = 15


@dataclass
class BorderConfig:
    """边框配置"""
    radius_sm: int = 4
    radius_md: int = 6
    radius_lg: int = 8
    radius_xl: int = 12

    width: int = 1
    width_thick: int = 2


@dataclass
class ShadowConfig:
    """阴影配置"""
    sm: str = '0 1px 2px rgba(0, 0, 0, 0.05)'
    md: str = '0 4px 6px rgba(0, 0, 0, 0.1)'
    lg: str = '0 10px 15px rgba(0, 0, 0, 0.1)'


# 全局主题实例
colors = ColorPalette()
fonts = FontConfig()
spacing = SpacingConfig()
borders = BorderConfig()
shadows = ShadowConfig()


# ========== 预定义样式 ==========

# 表头颜色选项
HEADER_COLORS = {
    '蓝色': '#165DFF',
    '绿色': '#22C55E',
    '橙色': '#F59E0B',
    '红色': '#EF4444',
    '紫色': '#8B5CF6',
    '青色': '#06B6D4',
}


class ThemeManager:
    """主题管理器 - 支持主题切换"""

    _current_theme = 'light'

    @classmethod
    def get_colors(cls) -> ColorPalette:
        """获取当前主题色彩"""
        return colors

    @classmethod
    def get_fonts(cls) -> FontConfig:
        """获取字体配置"""
        return fonts

    @classmethod
    def get_spacing(cls) -> SpacingConfig:
        """获取间距配置"""
        return spacing

    @classmethod
    def set_theme(cls, theme: str):
        """设置主题"""
        if theme in ('light', 'dark'):
            cls._current_theme = theme

    @classmethod
    def get_current_theme(cls) -> str:
        """获取当前主题名"""
        return cls._current_theme


def get_color(key: str) -> str:
    """获取颜色值"""
    return getattr(colors, key, '#000000')


def get_font_size(size_name: str) -> int:
    """获取字号"""
    return getattr(fonts, f'size_{size_name}', 11)
