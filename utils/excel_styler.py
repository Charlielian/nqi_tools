# -*- coding: utf-8 -*-
"""
Excel样式管理器
提供统一的Excel样式定义和格式化功能
"""

from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class ExcelStyler:
    """Excel样式管理器"""

    # 预定义的样式配置
    STYLES = {
        'header_blue': {
            'color': '165DFF',
            'font_size': 11,
            'font_color': 'FFFFFF',
            'bold': True
        },
        'header_green': {
            'color': '22C55E',
            'font_size': 11,
            'font_color': 'FFFFFF',
            'bold': True
        },
        'header_orange': {
            'color': 'F59E0B',
            'font_size': 11,
            'font_color': 'FFFFFF',
            'bold': True
        },
        'header_red': {
            'color': 'EF4444',
            'font_size': 11,
            'font_color': 'FFFFFF',
            'bold': True
        },
    }

    # 边框样式
    THIN_BORDER = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # 居中对齐
    CENTER_ALIGNMENT = Alignment(horizontal='center', vertical='center')
    WRAP_ALIGNMENT = Alignment(horizontal='center', vertical='center', wrap_text=True)

    @classmethod
    def get_header_style(cls, style_name='header_blue'):
        """获取表头样式

        Args:
            style_name: 样式名称

        Returns:
            tuple: (fill, font, alignment, border)
        """
        style = cls.STYLES.get(style_name, cls.STYLES['header_blue'])

        fill = PatternFill(
            start_color=style['color'],
            end_color=style['color'],
            fill_type='solid'
        )

        font = Font(
            bold=style['bold'],
            color=style['font_color'],
            size=style['font_size']
        )

        return fill, font, cls.WRAP_ALIGNMENT, cls.THIN_BORDER

    @classmethod
    def apply_header_style(cls, cell, style_name='header_blue'):
        """为单元格应用表头样式

        Args:
            cell: openpyxl Cell对象
            style_name: 样式名称
        """
        fill, font, alignment, border = cls.get_header_style(style_name)
        cell.fill = fill
        cell.font = font
        cell.alignment = alignment
        cell.border = border

    @classmethod
    def apply_cell_style(cls, cell, alignment_type='center'):
        """为单元格应用通用样式

        Args:
            cell: openpyxl Cell对象
            alignment_type: 对齐类型 ('center', 'left', 'right')
        """
        alignment_map = {
            'center': cls.CENTER_ALIGNMENT,
            'left': Alignment(horizontal='left', vertical='center'),
            'right': Alignment(horizontal='right', vertical='center')
        }
        cell.alignment = alignment_map.get(alignment_type, cls.CENTER_ALIGNMENT)
        cell.border = cls.THIN_BORDER

    @classmethod
    def auto_adjust_column_width(cls, worksheet, max_width=50, min_width=8):
        """自动调整列宽

        Args:
            worksheet: openpyxl Worksheet对象
            max_width: 最大列宽
            min_width: 最小列宽
        """
        for column in worksheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)

            for cell in column:
                try:
                    if cell.value:
                        cell_length = len(str(cell.value))
                        if cell_length > max_length:
                            max_length = cell_length
                except (AttributeError, TypeError):
                    pass

            adjusted_width = min(max(max_length + 2, min_width), max_width)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    @classmethod
    def format_worksheet(cls, worksheet, header_style='header_blue',
                         auto_width=True, max_col_width=50):
        """格式化工作表

        Args:
            worksheet: openpyxl Worksheet对象
            header_style: 表头样式名称
            auto_width: 是否自动调整列宽
            max_col_width: 最大列宽
        """
        if worksheet.max_row < 1:
            return

        # 格式化表头
        header_fill, header_font, header_align, header_border = cls.get_header_style(header_style)
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = header_border

        # 格式化数据行
        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
            for cell in row:
                cell.alignment = cls.CENTER_ALIGNMENT
                cell.border = cls.THIN_BORDER

        # 自动调整列宽
        if auto_width:
            cls.auto_adjust_column_width(worksheet, max_width=max_col_width)
