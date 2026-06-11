# -*- coding: utf-8 -*-
"""
YAML表格配置加载器
自动扫描table_configs和custom_configs目录，加载所有表格配置
"""

import yaml
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _datatype_to_code(datatype_str, field_name=''):
    """将数据类型字符串转换为浏览器使用的数字代码

    浏览器使用的格式:
    - "2" = bigint/timestamp/integer
    - "1" = character varying/varchar/character
    - "decimal" = 小数类型
    - "boolean" = 布尔类型（保持原样）

    特殊字段处理（保持与HAR一致）:
    - ncgi 和 nrcell_name 必须保持 'character varying'（不是 '1'）
    - starttime/endtime 使用 '1'（时间类型）

    Args:
        datatype_str: 数据类型字符串
        field_name: 字段名称（用于特殊处理）

    Returns:
        转换后的值（可能是数字代码或字符串）
    """
    if not datatype_str:
        return datatype_str

    # 特殊字段：ncgi 和 nrcell_name 必须保持 'character varying'
    if field_name in ('ncgi', 'nrcell_name'):
        return 'character varying'

    datatype_lower = datatype_str.lower()

    # bigint, timestamp, integer 类型使用 "2"
    if datatype_lower in ('bigint', 'timestamp', 'integer', 'int', '2'):
        return '2'

    # character varying, varchar, character 使用 "1"
    if datatype_lower in ('character varying', 'character', 'varchar', 'text', '1'):
        return '1'

    # boolean 类型使用 "1"（与浏览器一致）
    if datatype_lower in ('boolean',):
        return '1'

    # decimal 类型保持原样
    if datatype_lower in ('decimal', 'numeric', 'double', 'float', 'real'):
        return datatype_str

    # 其他类型保持原样
    return datatype_str


class TableConfigLoader:
    """YAML配置加载器 - 自动扫描并加载所有表格配置

    支持双目录加载：
    1. 内置配置目录 (table_configs) - 程序内置，只读
    2. 自定义配置目录 (custom_configs) - 用户自定义，可覆盖内置配置
    """

    def __init__(self, config_dir='table_configs', custom_dir='custom_configs'):
        """
        Args:
            config_dir: 内置YAML配置文件目录，默认 table_configs
            custom_dir: 用户自定义YAML配置文件目录，默认 custom_configs
        """
        self.config_dir = Path(config_dir)
        self.custom_dir = Path(custom_dir) if custom_dir else None
        self._configs = {}
        self._loaded = False

    def load_all(self):
        """扫描所有目录，加载所有YAML文件
        
        加载顺序：
        1. 先加载内置配置 (table_configs)
        2. 再加载自定义配置 (custom_configs)
        
        自定义配置可以覆盖内置配置，实现配置扩展
        """
        self._configs = {}

        # 加载内置配置
        self._load_from_dir(self.config_dir, "内置")

        # 加载自定义配置（优先级更高）
        if self.custom_dir and self.custom_dir.exists():
            custom_count = self._load_from_dir(self.custom_dir, "自定义")
            if custom_count > 0:
                logger.info(f"已从自定义目录加载 {custom_count} 个配置（可覆盖内置配置）")
        elif self.custom_dir:
            # 自定义目录不存在时自动创建
            try:
                self.custom_dir.mkdir(parents=True, exist_ok=True)
                self._create_readme_if_needed()
                logger.info(f"已创建自定义配置目录: {self.custom_dir}")
            except Exception as e:
                logger.warning(f"无法创建自定义配置目录: {e}")

        self._loaded = True
        total = len(self._configs)
        logger.info(f"共加载 {total} 个YAML表格配置")

    def _load_from_dir(self, config_dir, source_type="内置"):
        """从指定目录加载YAML文件
        
        Args:
            config_dir: 配置目录路径
            source_type: 来源类型描述（用于日志）
            
        Returns:
            int: 成功加载的配置数量
        """
        if not config_dir.exists():
            logger.warning(f"{source_type}配置目录 {config_dir} 不存在")
            return 0

        count = 0
        for yaml_file in sorted(config_dir.glob('*.yaml')):
            # 跳过隐藏文件和README文件
            if yaml_file.name.startswith('_'):
                continue
            if yaml_file.stem.lower() == 'readme':
                continue
            
            try:
                config = self._load_yaml(yaml_file)
                if config and 'name' in config:
                    self._normalize_config(config)
                    # 记录配置来源
                    config['_source'] = source_type
                    config['_file'] = str(yaml_file)
                    self._configs[config['name']] = config
                    count += 1
                    logger.info(f"加载{source_type}配置: {config['name']}")
            except Exception as e:
                logger.error(f"加载 {yaml_file} 失败: {e}")

        return count

    def _create_readme_if_needed(self):
        """如果自定义目录为空，创建README文件"""
        readme_path = self.custom_dir / 'README.md'
        if not readme_path.exists() and not any(self.custom_dir.glob('*.yaml')):
            readme_content = """# 自定义表格配置

此目录用于存放用户自定义的表格YAML配置文件。

## 使用方法

1. 在本目录创建新的 `.yaml` 文件
2. 参考下方模板填写配置
3. 重启程序，表格自动出现

## 配置模板

```yaml
# 表格显示名称（必填且唯一）
name: 我的自定义表格

# API配置
table_key: 后端API的table_key
table_name: 数据库表名
fieldtype: 字段类型
api_type: search  # 或 table

# 维度配置
dimension:
  geographicdimension: 小区
  timedimension: 天
  enodebField: enodeb_id
  cgiField: cgi
  timeField: starttime
  cellField: cell
  cityField: city

# 字段列表
fields:
  - feild: starttime
    feildName: 数据时间
    datatype: character varying
    columntype: 1

# 查询条件
conditions:
  where:
    - feild: starttime
      datatype: timestamp
      symbol: '>='
      val: '{start_date} 00:00:00'
      whereCon: and
      query: true
```

## 占位符

在 conditions.where 的 val 字段中可使用：
- `{start_date}` - 开始日期
- `{end_date}` - 结束日期
- `{city}` - 地市

## 注意事项

- 文件名建议使用英文
- name 字段必须唯一
- 字段名必须与API返回的字段名一致
"""
            try:
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(readme_content)
                logger.info(f"已创建 README.md: {readme_path}")
            except Exception as e:
                logger.warning(f"无法创建 README.md: {e}")

    def _load_yaml(self, yaml_file):
        """加载单个YAML文件"""
        with open(yaml_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _normalize_config(self, config):
        """标准化配置：补全字段属性，调整字段顺序，转换数据类型"""
        fieldtype = config.get('fieldtype', config.get('name', ''))
        table = config.get('table_name', '')
        # tableName 应该使用 fieldtype（报表中文名），而不是数据库表名
        tableName = fieldtype

        # 补全fields中的属性，并调整字段顺序以匹配API要求
        normalized_fields = []
        for field in config.get('fields', []):
            if isinstance(field, dict):
                # 转换datatype为API要求的数字代码
                datatype_str = field.get('datatype', 'character varying')
                field_name = field.get('feild', '')
                datatype_code = _datatype_to_code(datatype_str, field_name)

                # 转换columntype为整数
                columntype = field.get('columntype', 1)
                if isinstance(columntype, str):
                    try:
                        columntype = int(columntype)
                    except (ValueError, TypeError):
                        columntype = 1

                # 获取中文名称，如果为空则使用英文字段名作为备选
                feild_name = field.get('feildName', '')
                if not feild_name:
                    feild_name = field.get('feild', '')

                # 按照API要求的顺序构建字段（feildtype, table, tableName, datatype, columntype, feildName, feild）
                normalized_field = {
                    'feildtype': fieldtype,
                    'table': table,
                    'tableName': tableName,
                    'datatype': datatype_code,
                    'columntype': columntype,
                    'feildName': feild_name,
                    'feild': field.get('feild', ''),
                    'poly': '无',
                    'anyWay': '无',
                    'chart': '无',
                    'chartpoly': '无'
                }
                normalized_fields.append(normalized_field)

        # 更新fields列表
        config['fields'] = normalized_fields

    def ensure_loaded(self):
        """确保配置已加载"""
        if not self._loaded:
            self.load_all()

    def get_config(self, name):
        """获取指定表格配置"""
        self.ensure_loaded()
        return self._configs.get(name)

    def get_all_names(self):
        """获取所有已加载的表格名称"""
        self.ensure_loaded()
        return sorted(self._configs.keys())

    def build_payload(self, config, start_date, end_date, city):
        """从配置构建payload（替换占位符）

        Args:
            config: 表格配置字典
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            city: 地市名称

        Returns:
            dict: 构建好的payload
        """
        # 调试日志
        logger.debug(f"[build_payload] 表名: {config.get('name', 'unknown')}")
        logger.debug(f"[build_payload] conditions keys: {config.get('conditions', {}).keys() if config.get('conditions') else 'None'}")
        logger.debug(f"[build_payload] where条件数量: {len(config.get('conditions', {}).get('where', []))}")

        # 基础参数
        result = {
            'draw': 1,
            'start': 0,
            'length': 200,
            'total': 0,
            'indexcount': 0
        }

        # 添加维度配置
        result.update(config.get('dimension', {}))

        # 构建result字段
        table_params = config.get('tableParams', {})
        result['result'] = {
            'result': config.get('fields', []),
            'tableParams': table_params if table_params else {'supporteddimension': None, 'supportedtimedimension': ''},
            'columnname': ''
        }

        # 构建where条件（替换占位符）
        where = []
        conditions = config.get('conditions', {})
        logger.debug(f"[build_payload] conditions内容: {conditions}")
        for cond in conditions.get('where', []):
            if isinstance(cond, dict):
                c = cond.copy()
                # 替换占位符
                for key in ['val', 'feildName']:
                    if key in c and isinstance(c[key], str):
                        c[key] = c[key].replace('{start_date}', start_date)
                        c[key] = c[key].replace('{end_date}', end_date)
                        c[key] = c[key].replace('{city}', city)
                # 确保布尔值正确
                if 'query' in c and isinstance(c['query'], bool):
                    c['query'] = c['query']
                where.append(c)
                logger.debug(f"[build_payload] 添加条件: {c}")
        result['where'] = where
        logger.debug(f"[build_payload] 最终where条件数量: {len(where)}")

        # 添加columns参数（用于DataTables）
        field_names = [f.get('feild', '') for f in config.get('fields', []) if isinstance(f, dict)]
        result['columns'] = self._build_columns_param(field_names)
        result['order'] = [{'column': 0, 'dir': 'desc'}]
        result['search'] = {'value': '', 'regex': False}

        # 添加固定参数
        fixed_params = config.get('conditions', {}).get('fixed_params', {})
        result.update(fixed_params)

        # 处理columns和order的映射
        if 'columns' in config:
            result['columns'] = config['columns']
        if 'order' in config:
            result['order'] = config['order']

        return result

    def _build_columns_param(self, field_list):
        """构建DataTables格式的columns参数"""
        columns = []
        for field in field_list:
            columns.append({
                'data': field,
                'name': '',
                'searchable': True,
                'orderable': True,
                'search': {'value': '', 'regex': False}
            })
        return columns

    def reload(self):
        """重新加载所有配置"""
        self._loaded = False
        self.load_all()


# 全局单例
_yaml_loader = None


def get_yaml_loader():
    """获取全局YAML加载器单例"""
    global _yaml_loader
    if _yaml_loader is None:
        _yaml_loader = TableConfigLoader()
        _yaml_loader.load_all()
    return _yaml_loader


def load_all_configs():
    """便捷函数：加载所有配置并返回"""
    loader = get_yaml_loader()
    return loader._configs


def get_table_config(name):
    """便捷函数：获取指定表格配置"""
    return get_yaml_loader().get_config(name)


def get_all_table_names():
    """便捷函数：获取所有表格名称"""
    return get_yaml_loader().get_all_names()


def build_payload_from_yaml(config, start_date, end_date, city):
    """便捷函数：从配置构建payload"""
    return get_yaml_loader().build_payload(config, start_date, end_date, city)
