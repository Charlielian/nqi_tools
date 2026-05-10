# -*- coding: utf-8 -*-
"""
数据查询模块
负责即席查询、数据获取和分批处理
"""

import logging
import requests
import json
import random
import time
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed

from urllib.parse import urlencode

from utils.config import (
    BASE_URL, JXCX_URL, JXCX_COUNT_URL, JXCX_SEARCH_URL, JXCX_TABLE_URL,
    HEADERS
)
from utils.constants import (
    TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG, TIMEOUT_EXTRA_LONG,
    RETRY_TIMES, RETRY_DELAY,
    BATCH_THRESHOLD, MAX_SINGLE_QUERY, BATCH_SIZES, BATCH_TIMEOUTS,
    MAX_PARALLEL_QUERIES,
    DEFAULT_DRAW, DEFAULT_START, DEFAULT_LENGTH
)
from utils.logger import get_report_logger
from utils.retry import RetryError

logger = logging.getLogger(__name__)


def get_cookie_value(cookie_jar, name, domain=None):
    """安全获取cookie值，处理多个同名cookie的情况

    Args:
        cookie_jar: requests的CookieJar对象
        name: cookie名称
        domain: 可选的domain过滤

    Returns:
        cookie值，如果不存在则返回None
    """
    try:
        # 先尝试直接获取
        if domain:
            value = cookie_jar.get(name, domain=domain)
            if value:
                return value
        # 尝试不带domain获取
        return cookie_jar.get(name)
    except requests.cookies.CookieConflictError:
        # 存在多个同名cookie，手动遍历获取第一个
        cookies = [c for c in cookie_jar if c.name == name]
        if cookies:
            # 如果指定了domain，优先返回匹配domain的
            if domain:
                for c in cookies:
                    if c.domain == domain or (domain in c.domain):
                        return c.value
            return cookies[0].value
        return None


def convert_where_conditions(conditions):
    """转换where条件格式为API要求的格式

    Args:
        conditions: 新格式条件列表 [{'field': 'xxx', 'operator': '>=', 'value': 'xxx'}]
                   或旧格式条件列表 [{'feild': 'xxx', 'symbol': '>=', 'val': 'xxx'}]

    Returns:
        转换后的条件列表 [{'datatype': 'xxx', 'feild': 'xxx', 'symbol': 'xxx', 'val': 'xxx', 'feildName': '', 'whereCon': 'and', 'query': True}]
    """
    if not conditions:
        return []

    result = []
    for i, cond in enumerate(conditions):
        # 判断是旧格式还是新格式
        if 'feild' in cond and 'symbol' in cond and 'val' in cond:
            # 已经是旧格式，直接使用
            result.append(cond)
        elif 'field' in cond and 'operator' in cond and 'value' in cond:
            # 新格式，需要转换
            where_con = 'and' if i > 0 else 'and'

            # 根据字段名和操作符推断datatype
            field = cond['field']
            operator = cond['operator']
            value = cond['value']

            # 推断数据类型
            datatype = 'character'  # 默认
            if 'time' in field.lower() or 'date' in field.lower():
                datatype = 'timestamp'
                # 时间格式处理 - 与浏览器保持一致，使用空格分隔而非加号
                # 浏览器发送格式: "2026-04-26 00:00:00" 或 "2026-04-26 23:59:59"
                if ' ' not in value and '+' not in value:
                    # 纯日期格式，需要添加时间部分
                    if operator in ('>=', '>'):
                        value = value + ' 00:00:00'
                    elif operator in ('<=', '<', '='):
                        value = value + ' 23:59:59'
                # 结束时间使用 < 而非 <=（与浏览器保持一致）
                if operator == '<=':
                    operator = '<'

            # 推断symbol（保持原样）
            symbol = operator

            result.append({
                'datatype': datatype,
                'feild': field,
                'feildName': '',
                'symbol': symbol,
                'val': value,
                'whereCon': where_con,
                'query': True
            })
        else:
            # 未识别的格式，跳过
            logger.warning("无法识别的条件格式: %s", cond)

    return result


class JXCXQuery:
    """即席查询类"""

    def __init__(self, session):
        self.sess = session
        self.enabled = False
        self._field_config_cache = {}
        self._cancel_flag = False  # 取消查询标志

    def check_session_valid(self):
        """检查Session是否有效，以及JXCX模块是否可访问

        Returns:
            bool: True表示Session有效且JXCX可用，False表示无效或已过期
        """
        import random
        try:
            # 首先检查 CASTGC cookie 是否存在
            castgc = get_cookie_value(self.sess.cookies, 'CASTGC', domain='nqi.gmcc.net')
            if not castgc:
                castgc = get_cookie_value(self.sess.cookies, 'CASTGC')

            if not castgc:
                logger.warning("[Session检测] 未找到CASTGC cookie")
                return False

            logger.info("[Session检测] CASTGC存在，验证JXCX模块可访问性...")

            # 真正检查 JXCX 模块是否可用（而不是只检查主站首页）
            url = f'{BASE_URL}/pro-portal/pure/urlAction.action'
            params = {
                'url': 'pro-adhoc/index',
                'random': random.random(),
                '__PID': 'JXCX',
                'token': castgc
            }
            url_with_params = f"{url}?url={params['url']}&__PID={params['__PID']}&random={params['random']}&token={params['token']}"

            res = self.sess.get(url_with_params, headers=HEADERS, timeout=TIMEOUT_SHORT)

            if res.status_code == 200:
                logger.info("[Session检测] JXCX模块可访问，Session有效")
                return True
            else:
                logger.warning("[Session检测] JXCX模块不可访问，状态码: %d", res.status_code)
                return False
        except Exception as e:
            logger.warning("[Session检测] Session检测失败: %s", str(e)[:100])
            return False

    def cancel_query(self):
        """取消当前正在进行的查询"""
        logger.info("[取消请求] 收到取消查询请求")
        self._cancel_flag = True

    def reset_cancel_flag(self):
        """重置取消查询标志"""
        self._cancel_flag = False
        logger.info("[取消请求] 取消标志已重置")

    def is_cancelled(self):
        """检查是否已取消查询"""
        return self._cancel_flag

    def get_field_config(self, table_key, fieldtype, api_type='search', table_name=None):
        """动态获取表字段配置（从API获取）

        Args:
            table_key: API查询关键字或显示名称
            fieldtype: 字段类型过滤条件
            api_type: API类型，'search'使用adhocquery/search接口，'table'使用adhocquery/getSelectTable接口
            table_name: 数据库表名（用于api_type='table'时）
        """
        cache_key = f"{table_key}_{fieldtype}_{api_type}"
        if cache_key in self._field_config_cache:
            logger.info("使用缓存的字段配置: %s", cache_key)
            return self._field_config_cache[cache_key]

        logger.info("动态获取字段配置: table_key=%s, fieldtype=%s, api_type=%s, table_name=%s",
                    table_key, fieldtype, api_type, table_name)

        try:
            if api_type == 'table':
                # 使用table_name（数据库表名）而不是table_key（显示名称）
                db_table = table_name if table_name else table_key
                data = {'tablename': db_table}
                logger.info("调用getSelectTable接口，使用表名: %s", db_table)
                res = self.sess.post(JXCX_TABLE_URL, data=data, headers=HEADERS, timeout=TIMEOUT_MEDIUM)

                if res.status_code == 200:
                    result = json.loads(res.content)
                    configs = result.get('CFG_ADHOC_CONF_TABLE', [])

                    # 如果返回空配置，尝试其他可能的响应格式
                    if not configs:
                        # 尝试 'row' 字段（某些表可能使用此格式）
                        configs = result.get('row', [])
                        if configs:
                            logger.info("从getSelectTable接口(row字段)获取到 %d 个字段配置", len(configs))
                        else:
                            logger.warning("getSelectTable接口返回空配置，尝试使用search接口")
                            # 递归尝试search接口
                            logger.info("[调试] 从table接口递归调用search接口, table_key=%s", table_key)
                            return self.get_field_config(table_key, fieldtype, 'search', table_name)

                    logger.info("从getSelectTable接口获取到 %d 个字段配置", len(configs))

                    self._field_config_cache[cache_key] = configs
                    return configs
                else:
                    logger.error("获取字段配置失败: %s", res.status_code)
                    return None
            else:
                # search接口需要传递多个field参数
                data = {'key': table_key}
                fields_to_fetch = [
                    'columnname_cn', 'columnname', 'fieldtype', 'datatype',
                    'tablename', 'tablename_cn', 'columntype', 'sort',
                    'geographicdimension', 'timedimension', 'enodeb_field', 'cgi_field',
                    'time_field', 'cell_field', 'city_field',
                    'supporteddimension', 'supportedtimedimension'
                ]
                for field in fields_to_fetch:
                    data['field'] = field

                res = self.sess.post(JXCX_SEARCH_URL, data=data, headers=HEADERS, timeout=TIMEOUT_MEDIUM)

                if res.status_code == 200:
                    result = json.loads(res.content)
                    configs = result.get('CFG_ADHOC_CONF_SEARCH', [])
                    logger.info("从search接口获取到 %d 个字段配置", len(configs))

                    # 如果configs为空，尝试其他可能的响应格式
                    if not configs:
                        # 尝试 'data' 字段
                        configs = result.get('data', [])
                        if configs:
                            logger.info("从search接口(data字段)获取到 %d 个字段配置", len(configs))

                    # 如果仍然为空，尝试使用table接口
                    if not configs:
                        logger.warning("search接口返回空配置，尝试使用table接口")
                        logger.info("[调试] 从search接口递归调用table接口, table_key=%s, table_name=%s", table_key, table_name)
                        return self.get_field_config(table_key, fieldtype, 'table', table_name)

                    self._field_config_cache[cache_key] = configs
                    return configs
                else:
                    logger.error("获取字段配置失败: %s", res.status_code)
                    return None
        except Exception as e:
            logger.error("获取字段配置异常: %s", e)
            import traceback
            traceback.print_exc()
            return None

    def build_payload_from_config(self, table_key, fieldtype, where_conditions, api_type='search',
                                  dimension_override=None, fields_override=None, table_name=None):
        """从动态获取的字段配置构建payload

        Args:
            table_key: API查询关键字
            fieldtype: 字段类型过滤条件
            where_conditions: 查询条件列表
            api_type: API类型，'search'使用adhocquery/search接口，'table'使用adhocquery/getSelectTable接口
            dimension_override: 可选的维度参数覆盖，如果提供则使用此参数而非API返回
            fields_override: 可选的字段列表覆盖，如果提供则使用此字段列表构建payload
            table_name: 数据库表名（用于api_type='table'时）
        """
        # 转换where条件格式（旧格式保持不变，新格式转换后使用）
        converted_conditions = convert_where_conditions(where_conditions)

        # 优先使用 dimension_override 来获取维度参数
        if dimension_override:
            geographicdimension = dimension_override.get('geographicdimension', '小区')
            timedimension = dimension_override.get('timedimension', '天')
            enodeb_field = dimension_override.get('enodebField', 'enodeb_id')
            cgi_field = dimension_override.get('cgiField', 'cgi')
            time_field = dimension_override.get('timeField', 'starttime')
            cell_field = dimension_override.get('cellField', 'cell')
            city_field = dimension_override.get('cityField', 'city')
            supporteddimension = dimension_override.get('supporteddimension', None)
            supportedtimedimension = dimension_override.get('supportedtimedimension', '')
        else:
            geographicdimension = '小区'
            timedimension = '天'
            enodeb_field = 'enodeb_id'
            cgi_field = 'cgi'
            time_field = 'starttime'
            cell_field = 'cell'
            city_field = 'city'
            supporteddimension = None
            supportedtimedimension = ''

        # 如果提供了字段覆盖，直接使用字段覆盖构建payload
        if fields_override:
            logger.info("使用预定义的字段覆盖，共 %d 个字段", len(fields_override))
            return self._build_payload_with_field_configs(
                table_key, fieldtype, converted_conditions, api_type,
                geographicdimension, timedimension, enodeb_field, cgi_field,
                time_field, cell_field, city_field, fields_override,
                supporteddimension, supportedtimedimension
            )

        # 没有字段覆盖，需要从API获取字段配置
        logger.info("【字段配置】开始获取字段配置: table_key=%s, fieldtype=%s, api_type=%s, table_name=%s",
                    table_key, fieldtype, api_type, table_name)
        # 重要：将调试信息也输出到标准logger，以便在界面显示
        logger.info(f"[调试] table_key={table_key}, fieldtype={fieldtype}, api_type={api_type}")
        configs = self.get_field_config(table_key, fieldtype, api_type, table_name=table_name)
        if not configs:
            logger.error("【错误】无法获取字段配置，table_key=%s, fieldtype=%s, api_type=%s", table_key, fieldtype, api_type)
            logger.warning("API返回空配置，尝试备用接口...")
            fallback_api_type = 'search' if api_type == 'table' else 'table'
            logger.info("【备用方案】尝试使用备用API类型: %s", fallback_api_type)
            configs = self.get_field_config(table_key, fieldtype, fallback_api_type, table_name=table_name)
            if not configs:
                logger.error("【错误】备用方案也失败，返回None")
                return None
            logger.info("【备用方案】成功使用 %s 获取到 %d 个字段配置", fallback_api_type, len(configs))
            api_type = fallback_api_type

        logger.info("API返回的字段配置数量: %d", len(configs))
        # 过滤掉非字典类型的配置项，防止API返回异常数据导致崩溃
        valid_configs = [c for c in configs if isinstance(c, dict)]
        if len(valid_configs) != len(configs):
            logger.warning("过滤掉了 %d 个非字典类型的配置项", len(configs) - len(valid_configs))
        configs = valid_configs

        if not configs:
            logger.error("没有有效的字段配置，返回None")
            return None

        logger.info("有效字段配置数量: %d", len(configs))
        logger.info("API返回的字段名(前10个): %s", [c.get('columnname', '') for c in configs[:10]])
        logger.info("API返回的fieldtype(前3个): %s", list(set(c.get('fieldtype', '') for c in configs[:3])))

        sorted_configs = sorted(configs, key=lambda x: x.get('sort', 0) if isinstance(x, dict) else 0)
        first_config = sorted_configs[0]

        # 从API配置获取维度参数（如果有的话）
        geographicdimension = first_config.get('geographicdimension', geographicdimension)
        timedimension = first_config.get('timedimension', timedimension)
        enodeb_field = first_config.get('enodeb_field', first_config.get('enodebField', enodeb_field))
        cgi_field = first_config.get('cgi_field', first_config.get('cgiField', cgi_field))
        time_field = first_config.get('time_field', first_config.get('timeField', time_field))
        cell_field = first_config.get('cell_field', first_config.get('cellField', cell_field))
        city_field = first_config.get('city_field', first_config.get('cityField', city_field))
        supporteddimension = first_config.get('supporteddimension', supporteddimension)
        supportedtimedimension = first_config.get('supportedtimedimension', supportedtimedimension)

        logger.info("使用的维度参数: geographicdimension=%s, timedimension=%s", geographicdimension, timedimension)
        logger.info("  enodebField=%s, cgiField=%s, timeField=%s, cellField=%s, cityField=%s",
                    enodeb_field, cgi_field, time_field, cell_field, city_field)

        # 构建字段列表
        field_list = [c['columnname'] for c in sorted_configs]

        # 构建columns参数
        columns = []
        for field in field_list:
            columns.append({
                'data': field,
                'name': '',
                'searchable': True,
                'orderable': True,
                'search': {'value': '', 'regex': False}
            })

        # 构建result参数
        table_name_from_config = first_config.get('tablename', '')
        table_name_cn = first_config.get('tablename_cn', '')

        result_list = []
        for c in sorted_configs:
            # columntype需要转换为字符串以与浏览器请求格式一致
            columntype = c.get('columntype', 1)
            if isinstance(columntype, int):
                columntype = str(columntype)
            result_list.append({
                'feildtype': c.get('fieldtype', ''),
                'table': c.get('tablename', ''),
                'tableName': c.get('tablename_cn', ''),
                'datatype': c.get('datatype', 'character varying'),
                'columntype': columntype,
                'feildName': c.get('columnname_cn', ''),
                'feild': c.get('columnname', ''),
                'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'
            })

        result = {
            'result': result_list,
            'tableParams': {
                'supporteddimension': supporteddimension if supporteddimension else '',
                'supportedtimedimension': supportedtimedimension if supportedtimedimension else ''
            },
            'columnname': ''
        }

        payload = {
            'draw': 1,
            'start': 0,
            'length': 200,
            'total': 0,
            'geographicdimension': geographicdimension,
            'timedimension': timedimension,
            'enodebField': enodeb_field,
            'cgiField': cgi_field,
            'timeField': time_field,
            'cellField': cell_field,
            'cityField': city_field,
            'columns': columns,
            'order': [{'column': 0, 'dir': 'desc'}],
            'search': {'value': '', 'regex': False},
            'result': result,
            'where': converted_conditions,  # 使用转换后的条件
            'indexcount': 0
        }

        logger.info("构建的payload包含 %d 个字段", len(columns))
        return payload

    def _build_payload_with_fields(self, table_key, fieldtype, where_conditions, api_type,
                                   dimension_override, fields_list):
        """使用字段列表构建payload（当API获取失败时使用）"""
        # 转换where条件格式为API要求的格式
        converted_conditions = convert_where_conditions(where_conditions)

        geographicdimension = dimension_override.get('geographicdimension', '小区')
        timedimension = dimension_override.get('timedimension', '天')
        enodeb_field = dimension_override.get('enodebField', 'enodeb_id')
        cgi_field = dimension_override.get('cgiField', 'cgi')
        time_field = dimension_override.get('timeField', 'starttime')
        cell_field = dimension_override.get('cellField', 'cell')
        city_field = dimension_override.get('cityField', 'city')
        table_name = dimension_override.get('table_name', '')

        # 构建columns
        columns = []
        for field in fields_list:
            columns.append({
                'data': field,
                'name': '',
                'searchable': True,
                'orderable': True,
                'search': {'value': '', 'regex': False}
            })

        # 构建result
        result_list = []
        for field in fields_list:
            result_list.append({
                'feildtype': fieldtype,
                'table': table_name,
                'tableName': '',
                'datatype': 'character varying',
                'columntype': 1,
                'feildName': field,
                'feild': field,
                'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'
            })

        result = {
            'result': result_list,
            'tableParams': {
                'supporteddimension': None,
                'supportedtimedimension': ''
            },
            'columnname': ''
        }

        payload = {
            'draw': 1,
            'start': 0,
            'length': 200,
            'total': 0,
            'geographicdimension': geographicdimension,
            'timedimension': timedimension,
            'enodebField': enodeb_field,
            'cgiField': cgi_field,
            'timeField': time_field,
            'cellField': cell_field,
            'cityField': city_field,
            'columns': columns,
            'order': [{'column': 0, 'dir': 'desc'}],
            'search': {'value': '', 'regex': False},
            'result': result,
            'where': converted_conditions,  # 使用转换后的条件格式
            'indexcount': 0
        }

        logger.info("使用字段列表构建payload，包含 %d 个字段", len(columns))
        return payload

    def _build_payload_with_field_configs(self, table_key, fieldtype, where_conditions, api_type,
                                         geographicdimension, timedimension, enodeb_field, cgi_field,
                                         time_field, cell_field, city_field, fields_override,
                                         supporteddimension=None, supportedtimedimension=''):
        """使用字段配置列表构建payload"""
        # 转换where条件格式为API要求的格式
        converted_conditions = convert_where_conditions(where_conditions)
        
        # 调试日志
        logger.info("[DEBUG] 输入条件数量: %d", len(where_conditions) if where_conditions else 0)
        logger.info("[DEBUG] 转换后条件数量: %d", len(converted_conditions) if converted_conditions else 0)
        if where_conditions:
            logger.info("[DEBUG] 输入条件[0]: %s", where_conditions[0])
        if converted_conditions:
            logger.info("[DEBUG] 转换后条件[0]: %s", converted_conditions[0])

        # fields_override 是一个字典列表，每个字典包含字段配置
        columns = []
        result_list = []
        table_name = ''

        for config in fields_override:
            field = config.get('feild', config.get('columnname', ''))
            if not field:
                continue

            columns.append({
                'data': field,
                'name': '',
                'searchable': True,
                'orderable': True,
                'search': {'value': '', 'regex': False}
            })

            table_name = config.get('table', table_name)
            result_list.append({
                'feildtype': config.get('feildtype', fieldtype),
                'table': config.get('table', table_name),
                'tableName': config.get('tableName', ''),
                'datatype': config.get('datatype', 'character varying'),
                'columntype': config.get('columntype', 1),
                'feildName': config.get('feildName', field),
                'feild': field,
                'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'
            })

        result = {
            'result': result_list,
            'tableParams': {
                'supporteddimension': supporteddimension if supporteddimension else '',
                'supportedtimedimension': supportedtimedimension if supportedtimedimension else ''
            },
            'columnname': ''
        }

        payload = {
            'draw': 1,
            'start': 0,
            'length': 200,
            'total': 0,
            'geographicdimension': geographicdimension,
            'timedimension': timedimension,
            'enodebField': enodeb_field,
            'cgiField': cgi_field,
            'timeField': time_field,
            'cellField': cell_field,
            'cityField': city_field,
            'columns': columns,
            'order': [{'column': 0, 'dir': 'desc'}],
            'search': {'value': '', 'regex': False},
            'result': result,
            'where': converted_conditions,  # 使用转换后的条件格式
            'indexcount': 0
        }

        logger.info("使用字段配置构建payload，包含 %d 个字段", len(columns))
        return payload

    def build_4g_voice_payload(self, volte_fields, epsfb_fields, where_conditions,
                               volte_dimension, epsfb_dimension):
        """构建4G语音小区的VoLTE和EPSFB的payload

        Args:
            volte_fields: VoLTE表的字段配置列表
            epsfb_fields: EPSFB表的字段配置列表
            where_conditions: 查询条件列表
            volte_dimension: VoLTE表的维度参数
            epsfb_dimension: EPSFB表的维度参数

        Returns:
            dict: {'volte': volte_payload, 'epsfb': epsfb_payload}
        """
        volte_payload = self._build_payload_with_field_configs(
            'VoLTE小区监控预警数据表-天',
            'VoLTE小区监控预警数据表-天',
            where_conditions,
            'table',
            volte_dimension.get('geographicdimension', '小区'),
            volte_dimension.get('timedimension', '天'),
            volte_dimension.get('enodebField', 'enodeb_id'),
            volte_dimension.get('cgiField', 'cgi'),
            volte_dimension.get('timeField', 'starttime'),
            volte_dimension.get('cellField', 'cell'),
            volte_dimension.get('cityField', 'city'),
            volte_fields
        )

        epsfb_payload = self._build_payload_with_field_configs(
            'EPSFB小区监控预警数据表-天',
            'EPSFB小区监控预警数据表-天',
            where_conditions,
            'table',
            epsfb_dimension.get('geographicdimension', '小区'),
            epsfb_dimension.get('timedimension', '天'),
            epsfb_dimension.get('enodebField', '---'),  # EPSFB表使用---
            epsfb_dimension.get('cgiField', 'cgi'),
            epsfb_dimension.get('timeField', 'starttime'),
            epsfb_dimension.get('cellField', 'cell'),
            epsfb_dimension.get('cityField', 'city'),
            epsfb_fields
        )

        logger.info("4G语音小区payload构建完成: VoLTE=%d字段, EPSFB=%d字段",
                   len(volte_fields), len(epsfb_fields))
        return {'volte': volte_payload, 'epsfb': epsfb_payload}

    def enter_jxcx(self, retry_times=None, timeout=None):
        """进入即席查询模块

        Args:
            retry_times: 重试次数（默认使用常量）
            timeout: 超时时间（默认使用常量）
        """
        if retry_times is None:
            retry_times = RETRY_TIMES
        if timeout is None:
            timeout = TIMEOUT_LONG

        logger.info("========== 进入即席查询模块 ==========")

        for attempt in range(retry_times):
            if attempt > 0:
                logger.info("重试第 %d 次...", attempt)

            try:
                castgc = get_cookie_value(self.sess.cookies, 'CASTGC', domain='nqi.gmcc.net')
                if not castgc:
                    castgc = get_cookie_value(self.sess.cookies, 'CASTGC')

                if not castgc:
                    logger.error("未找到CASTGC cookie")
                    continue

                logger.info("CASTGC获取成功: %s...", castgc[:20] if len(castgc) >= 20 else castgc)

                url = f'{BASE_URL}/pro-portal/pure/urlAction.action'
                params = {
                    'url': 'pro-adhoc/index',
                    'random': random.random(),
                    '__PID': 'JXCX',
                    'token': castgc
                }

                url_with_params = f"{url}?url={params['url']}&__PID={params['__PID']}&random={params['random']}&token={params['token']}"
                logger.info("请求URL: %s...", url_with_params[:200] if len(url_with_params) >= 200 else url_with_params)

                # 保存当前cookies，以便检测是否有新的cookie
                cookies_before = set((c.name, c.value) for c in self.sess.cookies)

                start_time = time.time()
                # 使用 allow_redirects=True 跟随重定向
                res = self.sess.get(url_with_params, headers=HEADERS, timeout=timeout, allow_redirects=True)
                elapsed_time = time.time() - start_time

                logger.info("响应状态码: %s, 耗时: %.2f秒", res.status_code, elapsed_time)

                # 检查是否有新的有效cookie（JSESSIONID）
                cookies_after = set((c.name, c.value) for c in self.sess.cookies)
                new_cookies = cookies_after - cookies_before
                if new_cookies:
                    new_cookie_names = [name for name, _ in new_cookies]
                    logger.info("检测到新Cookie: %s", new_cookie_names)

                # 检查最终URL是否到达目标页面
                final_url = res.url if hasattr(res, 'url') else ''
                if 'pro-adhoc' in final_url or 'index' in final_url:
                    logger.info("成功到达即席查询页面: %s", final_url[:100])
                    self.enabled = True
                    logger.info("即席查询模块初始化成功！")
                    return True

                # 即使状态码不是200，检查是否包含有效的adhoc内容
                if res.status_code == 200 and ('adhoc' in res.text or 'jxcx' in res.text.lower()):
                    self.enabled = True
                    logger.info("即席查询模块初始化成功！（内容检测）")
                    return True

                # 如果有JSESSIONID更新，也认为成功
                jsessionid = get_cookie_value(self.sess.cookies, 'JSESSIONID')
                if jsessionid:
                    logger.info("检测到JSESSIONID，模块可能已初始化")
                    self.enabled = True
                    return True

                logger.error("进入即席查询失败，状态码: %s, 最终URL: %s", res.status_code, final_url[:100])
                continue

            except requests.exceptions.Timeout:
                logger.error("请求超时 (timeout=%ds)", timeout)
                # 超时后检查是否已经有有效cookie
                jsessionid = get_cookie_value(self.sess.cookies, 'JSESSIONID')
                if jsessionid:
                    logger.info("超时但检测到JSESSIONID，模块可能已初始化")
                    self.enabled = True
                    return True
                continue
            except requests.exceptions.ConnectionError as e:
                logger.error("网络连接错误: %s", e)
                continue
            except Exception as e:
                logger.error("未知错误: %s", e)
                import traceback
                logger.debug(traceback.format_exc())
                continue

        logger.error("进入即席查询失败，已尝试 %d 次", retry_times)
        return False

    def get_table_count(self, payload, retry_times=None, retry_delay=None, report_name=None):
        """获取查询结果行数

        Args:
            payload: 请求参数
            retry_times: 重试次数（默认使用常量）
            retry_delay: 重试间隔（默认使用常量）
            report_name: 报表名称（用于日志标识，传入时使用report_logger）
        """
        # 如果提供了report_name，使用report_logger；否则使用模块级logger
        if report_name:
            log = get_report_logger(report_name)
        else:
            log = logger
            report_name = "QueryModule"

        if retry_times is None:
            retry_times = RETRY_TIMES
        if retry_delay is None:
            retry_delay = RETRY_DELAY

        if not self.enabled:
            self.enter_jxcx()

        # getTableCount请求需要这些参数（与旧版保持一致，包含columns/order/search）
        key_list = ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                    'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount',
                    'columns', 'order', 'search']
        payload_count = {key: value for key, value in payload.items() if key in key_list}
        payload_encoded = self._encode_payload(payload_count)

        # ========== 详细调试日志 ==========
        log.info("")
        log.info("╔══════════════════════════════════════════════════════════════════════════════╗")
        log.info("║ [get_table_count] 获取数据总数 [%s]                                      ║", report_name)
        log.info("╠══════════════════════════════════════════════════════════════════════════════╣")
        log.info("║ 请求URL: %s", JXCX_COUNT_URL)
        log.info("║")
        
        # Session/Cookie状态诊断
        log.info("║ [Session状态诊断]")
        castgc = get_cookie_value(self.sess.cookies, 'CASTGC', domain='nqi.gmcc.net')
        if not castgc:
            castgc = get_cookie_value(self.sess.cookies, 'CASTGC')
        if castgc:
            log.info("║   CASTGC cookie: 存在 (长度=%d)", len(castgc))
        else:
            log.info("║   CASTGC cookie: 不存在!")
        
        jsessionid = get_cookie_value(self.sess.cookies, 'JSESSIONID', domain='nqi.gmcc.net')
        if not jsessionid:
            jsessionid = get_cookie_value(self.sess.cookies, 'JSESSIONID')
        if jsessionid:
            log.info("║   JSESSIONID cookie: 存在")
        else:
            log.info("║   JSESSIONID cookie: 不存在")
        
        # 请求头信息
        log.info("║")
        log.info("║ [请求Headers]")
        for key in ['User-Agent', 'Content-Type', 'Cookie']:
            if key == 'Cookie':
                cookie_str = '; '.join([f"{c.name}={c.value[:20]}..." if len(c.value) > 20 else f"{c.name}={c.value}" 
                                       for c in self.sess.cookies])
                log.info("║   %s: %s", key, cookie_str[:200])
            elif key in HEADERS:
                log.info("║   %s: %s", key, HEADERS[key])
        log.info("║")
        log.info("║ [筛选后的payload参数]")
        for k, v in payload_count.items():
            if k == 'result':
                log.info("║   %s: (JSON, 长度=%d字符)", k, len(json.dumps(v)))
            elif k == 'where':
                log.info("║   %s: %s", k, json.dumps(v)[:200])
            elif k == 'columns':
                log.info("║   %s: (列表, %d项)", k, len(v) if isinstance(v, list) else 0)
            else:
                log.info("║   %s: %s", k, v)
        log.info("║")
        log.info("║ [编码后的请求体] (长度=%d字符)", len(payload_encoded))
        log.info("║ %s", payload_encoded[:300])
        if len(payload_encoded) > 300:
            log.info("║ ... (省略 %d 字符)", len(payload_encoded) - 300)
        log.info("╚══════════════════════════════════════════════════════════════════════════════╝")
        log.info("")

        for attempt in range(retry_times):
            try:
                log.info("[尝试 %d/%d] 发送getTableCount请求...", attempt + 1, retry_times)
                res = self.sess.post(JXCX_COUNT_URL, data=payload_encoded, headers=HEADERS, timeout=TIMEOUT_EXTRA_LONG)
                
                # ========== 详细响应日志 ==========
                log.info("")
                log.info("┌──────────────────────────────────────────────────────────────────────────────┐")
                log.info("│ [get_table_count] 响应信息                                                   │")
                log.info("├──────────────────────────────────────────────────────────────────────────────┤")
                log.info("│ HTTP状态码: %s", res.status_code)
                log.info("│ 响应头 Content-Type: %s", res.headers.get('Content-Type', 'N/A'))
                log.info("│ 响应内容长度: %d 字节", len(res.content))
                log.info("│ 响应内容: %s", res.text[:1000])
                if len(res.text) > 1000:
                    log.info("│           ... (省略 %d 字符)", len(res.text) - 1000)
                log.info("└──────────────────────────────────────────────────────────────────────────────┘")
                log.info("")

                if res.status_code != 200:
                    log.error("│ HTTP状态码异常: %s", res.status_code)
                    log.error("└────────────────────────────────────────────────────────────────────┘")
                    self.enabled = False
                    return 0

                if not res.content or len(res.content.strip()) == 0:
                    log.error("│ 响应内容为空，可能是Session过期")
                    log.error("└────────────────────────────────────────────────────────────────────┘")
                    self.enabled = False
                    # Session过期，尝试重新进入
                    if attempt < retry_times - 1:
                        log.info("尝试重新进入即席查询模块 (%d/%d)...", attempt + 2, retry_times)
                        time.sleep(retry_delay)
                        if self.enter_jxcx():
                            continue
                    return 0

                try:
                    result = json.loads(res.content)
                except json.JSONDecodeError as e:
                    log.error("│ JSON解析失败: %s", e)
                    log.error("│ 响应内容: %s", res.text[:500])
                    log.error("└────────────────────────────────────────────────────────────────────┘")
                    self.enabled = False
                    if attempt < retry_times - 1:
                        log.info("尝试重新进入即席查询模块 (%d/%d)...", attempt + 2, retry_times)
                        time.sleep(retry_delay)
                        if self.enter_jxcx():
                            continue
                    return 0

                # 检查是否有错误消息
                if 'message' in result and result['message']:
                    msg = str(result['message'])
                    log.warning("│ 服务器消息: %s", msg)
                    # 检查常见的错误消息
                    if any(err in msg for err in ['不存在', '失败', '错误', 'error', 'Error', '异常', 'timeout', 'Timeout']):
                        log.warning("│ API返回错误，返回0")
                        log.warning("└────────────────────────────────────────────────────────────────────┘")
                        return 0

                # 检查响应结构中的count字段
                # 注意：count=0 是有效数据，不应该触发错误
                count = self._extract_count_from_response(result)
                if count is not None:
                    log.info("│ ✓ 成功提取count: %s", count)
                    log.info("│ 响应完整内容: %s", str(result)[:500])
                    log.info("└────────────────────────────────────────────────────────────────────┘")
                    return int(count) if count != '' else 0

                # 如果没有找到count字段，记录详细错误
                log.warning("│ ✗ 未能在响应中找到count字段")
                log.warning("│ 响应keys: %s", list(result.keys()) if isinstance(result, dict) else type(result))
                log.warning("│ 响应完整内容: %s", str(result)[:1000])
                log.warning("└────────────────────────────────────────────────────────────────────┘")
                
                if attempt < retry_times - 1:
                    time.sleep(retry_delay)
                    continue

                    return 0
                else:
                    logger.error("请求失败，状态码: %s", res.status_code)
                    if attempt < retry_times - 1:
                        time.sleep(retry_delay)
                        continue
                    return 0

            except requests.exceptions.Timeout:
                logger.error("请求超时 (timeout=180s)")
                if attempt < retry_times - 1:
                    time.sleep(retry_delay)
                    continue
            except requests.exceptions.ConnectionError as e:
                logger.error("网络连接错误: %s", e)
                if attempt < retry_times - 1:
                    time.sleep(retry_delay)
                    continue
            except Exception as e:
                logger.error("查询异常: %s", e)
                import traceback
                traceback.print_exc()
                if attempt < retry_times - 1:
                    time.sleep(retry_delay)
                    continue

        logger.warning("查询失败，已尝试 %d 次，返回MAX_SINGLE_QUERY(%d)", retry_times, MAX_SINGLE_QUERY)
        return MAX_SINGLE_QUERY

    def _extract_count_from_response(self, result):
        """从API响应中提取count字段

        Args:
            result: API响应的JSON对象

        Returns:
            count值或None（如果未找到）
        """
        # 位置1: result['count']
        if 'count' in result:
            return result['count']

        # 位置2: result['data']['count']
        if 'data' in result and isinstance(result['data'], dict):
            if 'count' in result['data']:
                return result['data']['count']

        # 位置3: result['data']['total']
        if 'data' in result and isinstance(result['data'], dict):
            if 'total' in result['data']:
                return result['data']['total']

        # 位置4: result['recordsTotal']
        if 'recordsTotal' in result:
            return result['recordsTotal']

        # 位置5: result['data'] 是数字
        if 'data' in result and isinstance(result['data'], (int, float)):
            return result['data']

        # 位置6: result['result'] 是数字
        if 'result' in result and isinstance(result['result'], (int, float)):
            return result['result']

        # 位置7: result['recordsFiltered'] - DataTables标准格式，旧版使用的字段
        if 'recordsFiltered' in result:
            return result['recordsFiltered']

        return None

    def _encode_payload(self, payload):
        """URL编码payload - 使用DataTables标准格式"""
        from urllib.parse import quote
        out_list = []
        for key in payload:
            # columns, order, search 使用DataTables标准的扁平URL编码格式
            # result, where 使用JSON序列化
            if key == 'columns':
                if isinstance(payload[key], str):
                    out_list.append(quote(key) + '=' + quote(payload[key]))
                    continue
                elif not isinstance(payload[key], list):
                    out_list.append(quote(key) + '=' + quote(str(payload[key])))
                    continue

                # DataTables标准格式: columns[0][data]=field&columns[0][name]=&...
                col_parts = []
                for i, col in enumerate(payload[key]):
                    if isinstance(col, str):
                        col_parts.append(f'columns[{i}]={quote(col)}')
                        continue
                    try:
                        for sub_key, sub_val in col.items():
                            if isinstance(sub_val, dict):
                                for ss_key, ss_val in sub_val.items():
                                    col_parts.append(f'columns[{i}][{sub_key}][{ss_key}]={quote(str(ss_val))}')
                            else:
                                col_parts.append(f'columns[{i}][{sub_key}]={quote(str(sub_val))}')
                    except AttributeError:
                        continue
                out_list.append('&'.join(col_parts))
            elif key == 'order':
                # DataTables标准格式: order[0][column]=0&order[0][dir]=desc
                order_parts = []
                for i, ord_item in enumerate(payload[key]):
                    for sub_key, sub_val in ord_item.items():
                        order_parts.append(f'order[{i}][{sub_key}]={quote(str(sub_val))}')
                out_list.append('&'.join(order_parts))
            elif key == 'search':
                # DataTables标准格式: search[value]=&search[regex]=false
                search_parts = []
                for sub_key, sub_val in payload[key].items():
                    search_parts.append(f'search[{sub_key}]={quote(str(sub_val))}')
                out_list.append('&'.join(search_parts))
            elif key in ['result', 'where']:
                # 使用与浏览器一致的JSON格式
                # ensure_ascii=False: 保持中文原样
                # separators=(',', ':'): 去除空格，与浏览器格式一致
                json_str = json.dumps(payload[key], ensure_ascii=False, separators=(',', ':'))
                out_list.append(quote(key) + '=' + quote(json_str))
            elif isinstance(payload[key], int):
                out_list.append(quote(key) + '=' + str(payload[key]))
            else:
                out_list.append(quote(key) + '=' + quote(str(payload[key]) if payload[key] is not None else ''))
        return '&'.join(out_list)

    def _fetch_data(self, payload, timeout=None, report_name=None):
        """发送请求获取数据（从API获取单页数据）

        Args:
            payload: 请求参数
            timeout: 超时时间（秒）
            report_name: 报表名称（用于日志标识）

        Returns:
            list: 数据列表，失败返回空列表
        """
        # 如果提供了report_name，使用report_logger；否则使用模块级logger
        if report_name:
            log = get_report_logger(report_name)
        else:
            log = logger

        if timeout is None:
            timeout = getattr(self, '_current_batch_timeout', 300)

        # ========== 详细日志记录（用于排查问题） ==========
        logger.info("")
        logger.info("┌──────────────────────────────────────────────────────────────────┐")
        logger.info("│ [_fetch_data] 发送数据请求                                        │")
        logger.info("├──────────────────────────────────────────────────────────────────┤")
        logger.info("│ 请求URL: %s", JXCX_URL)
        logger.info("│ 请求方法: POST")
        logger.info("│ 超时时间: %ds", timeout)

        # 编码payload
        payload_encoded = self._encode_payload(payload)
        logger.info("│ 编码后Payload长度: %d 字符", len(payload_encoded))

        # 显示关键参数
        logger.info("│ [关键参数]")
        for key in ['start', 'length', 'geographicdimension', 'timedimension']:
            if key in payload:
                logger.info("│   %s: %s", key, payload[key])
        logger.info("└──────────────────────────────────────────────────────────────────┘")

        try:
            res = self.sess.post(JXCX_URL, data=payload_encoded, headers=HEADERS, timeout=timeout)

            # ========== 详细响应日志 ==========
            logger.info("")
            logger.info("┌──────────────────────────────────────────────────────────────────┐")
            logger.info("│ [_fetch_data] 响应信息                                           │")
            logger.info("├──────────────────────────────────────────────────────────────────┤")
            logger.info("│ HTTP状态码: %s", res.status_code)
            logger.info("│ 响应头 Content-Type: %s", res.headers.get('Content-Type', 'N/A'))
            logger.info("│ 响应内容长度: %d 字节", len(res.content))

            if res.status_code != 200:
                logger.error("│ 响应内容: %s", res.text[:500])
                logger.error("└──────────────────────────────────────────────────────────────────┘")
                self.enabled = False
                return []

            if not res.content or len(res.content.strip()) == 0:
                logger.error("│ 响应内容为空，可能是Session过期")
                logger.error("└──────────────────────────────────────────────────────────────────┘")
                self.enabled = False
                return []

            try:
                result = json.loads(res.content)
            except json.JSONDecodeError as e:
                logger.error("│ JSON解析失败: %s", e)
                logger.error("│ 响应内容: %s", res.text[:500])
                logger.error("└──────────────────────────────────────────────────────────────────┘")
                self.enabled = False
                return []

            # 打印完整响应内容用于调试
            logger.info("│ 响应keys: %s", list(result.keys()) if isinstance(result, dict) else type(result))
            logger.info("│ 响应内容 (前500字符): %s", str(result)[:500])
            if len(str(result)) > 500:
                logger.info("│                  ... (省略 %d 字符)", len(str(result)) - 500)

            # 检查是否有错误消息
            if 'message' in result and result['message']:
                msg_text = str(result['message'])
                logger.warning("│ 服务器消息: %s", msg_text)
                if '不存在' in msg_text:
                    logger.warning("└──────────────────────────────────────────────────────────────────┘")
                    return []

            # 获取数据列表 - 支持多种响应格式
            data_list = result.get('data') or []
            if not data_list and isinstance(result, dict):
                # 尝试其他可能的数据字段
                for key in ['result', 'records', 'rows', 'dataList']:
                    if key in result and result[key]:
                        data_list = result[key] if isinstance(result[key], list) else []
                        logger.info("│ 使用备用字段 '%s' 获取到 %d 条数据", key, len(data_list))
                        break

            logger.info("│ 返回数据条数: %d", len(data_list))

            if not data_list:
                logger.warning("│ [警告] 数据为空")
                logger.warning("└──────────────────────────────────────────────────────────────────┘")
            else:
                logger.info("│ 第一条数据字段: %s", list(data_list[0].keys())[:10])
                logger.info("└──────────────────────────────────────────────────────────────────┘")

            return data_list

        except requests.exceptions.Timeout:
            log.error("")
            log.error("╔══════════════════════════════════════════════════════════════════╗")
            log.error("║ [ERROR] 请求超时 (timeout=%ds)                                      ║", timeout)
            log.error("╚══════════════════════════════════════════════════════════════════╝")
            return []
        except requests.exceptions.ConnectionError as e:
            log.error("")
            log.error("╔══════════════════════════════════════════════════════════════════╗")
            log.error("║ [ERROR] 连接错误: %s", str(e)[:50])
            log.error("╚══════════════════════════════════════════════════════════════════╝")
            return []
        except Exception as e:
            log.error("")
            log.error("╔══════════════════════════════════════════════════════════════════╗")
            log.error("║ [ERROR] 请求异常: %s", str(e)[:50])
            log.error("╚══════════════════════════════════════════════════════════════════╝")
            import traceback
            traceback.print_exc()
            return []

    # 批次大小和对应超时时间配置（使用常量）
    def _get_batch_sizes(self):
        """获取批次大小列表"""
        return BATCH_SIZES

    def _get_batch_timeouts(self):
        """获取批次超时配置"""
        return BATCH_TIMEOUTS

    def _auto_detect_batch_size(self, payload, test_sizes=None):
        """自动探测最佳批次大小

        从大到小测试，选择能成功返回的最大批次

        Args:
            payload: 查询参数
            test_sizes: 测试的批次大小列表，默认为 BATCH_SIZES

        Returns:
            tuple: (batch_size, timeout)
        """
        import copy
        batch_timeouts = self._get_batch_timeouts()
        if test_sizes is None:
            test_sizes = self._get_batch_sizes()

        logger.info("[批次探测] 开始自动探测最佳批次大小...")

        for size in test_sizes:
            timeout = batch_timeouts.get(size, 60)
            logger.info("[批次探测] 测试批次大小: %d, 超时: %ds", size, timeout)

            try:
                test_payload = copy.deepcopy(payload)
                test_payload['start'] = 0
                test_payload['length'] = size

                # 发送测试请求
                test_data = self._fetch_data(test_payload, timeout=timeout)

                if test_data is not None and len(test_data) > 0:
                    logger.info("[批次探测] ✓ 批次大小 %d 可用，获取到 %d 条数据", size, len(test_data))
                    return size, timeout
                else:
                    logger.warning("[批次探测] ✗ 批次大小 %d 返回空数据", size)
            except Exception as e:
                logger.warning("[批次探测] ✗ 批次大小 %d 失败: %s", size, str(e)[:100])

        # 所有批次都失败，返回最小批次
        logger.warning("[批次探测] 所有批次探测失败，使用默认批次大小 200")
        return 200, self.BATCH_TIMEOUTS[200]

    def _fetch_by_loop(self, payload, total_count, progress_callback=None):
        """一次性获取全部数据（不分页，防止重复/遗漏）

        Args:
            payload: 查询参数
            total_count: 预期总行数
            progress_callback: 进度回调函数 callback(current, total, message)

        Returns:
            list: 数据列表
        """
        import copy

        logger.debug("开始获取数据，预期总量: %d", total_count)

        # 一次性获取所有数据，不分页
        p = copy.deepcopy(payload)
        p['start'] = 0
        p['length'] = total_count

        # 根据数据量设置合理的超时时间
        timeout = max(60, min(600, total_count // 1000 * 3))
        logger.debug("设置超时时间: %d 秒", timeout)

        if progress_callback:
            progress_callback(0, total_count, f"正在获取 {total_count} 条数据...")

        try:
            data_list = self._fetch_data(p, timeout=timeout)

            if data_list:
                logger.info("✓ 获取数据: %d 条", len(data_list))
                if progress_callback:
                    progress_callback(len(data_list), total_count, f"获取完成: {len(data_list)} 条")
            else:
                logger.warning("获取返回空数据")
                if progress_callback:
                    progress_callback(0, total_count, "获取数据为空")
            return data_list if data_list else []

        except Exception as e:
            logger.error("获取数据失败: %s", str(e)[:200])
            if progress_callback:
                progress_callback(0, total_count, f"获取失败: {str(e)[:50]}")
            raise

    def _get_field_mapping(self, payload):
        """获取字段中英文映射

        Args:
            payload: 查询参数

        Returns:
            DataFrame: 包含字段映射的DataFrame，第一行是字段名
        """
        import pandas as pd

        if 'result' not in payload or 'result' not in payload['result']:
            logger.warning("payload中缺少result字段")
            return pd.DataFrame()

        result_list = payload['result']['result']
        result_df = pd.DataFrame(result_list)

        en = list(result_df['feild'])
        zn = list(result_df['feildName'])
        en_zh_dict = dict(zip(en, zn))

        return pd.DataFrame([en_zh_dict])

    def get_table(self, payload, to_df=True, progress_callback=None, report_name="未知报表"):
        """获取表格数据（一次性获取全部数据）

        Args:
            payload: 请求参数
            to_df: 是否转换为DataFrame
            progress_callback: 进度回调函数，签名: callback(current, total, message)
            report_name: 报表名称（用于日志标识）
        """
        import pandas as pd

        # 获取报表专用的日志记录器
        report_logger = get_report_logger(report_name)

        report_logger.info("▶ 开始提取报表: %s", report_name)

        if not self.enabled:
            report_logger.info("JXCX 未启用，尝试进入...")
            if not self.enter_jxcx():
                report_logger.error("无法进入即席查询模块")
                return pd.DataFrame() if to_df else {'data': []}

        # 主动检测 Session 有效性
        if not self.check_session_valid():
            report_logger.warning("Session已过期，尝试重新进入...")
            if not self.enter_jxcx(retry_times=2, timeout=60):
                report_logger.error("重新进入失败，请尝试重新登录")
                return pd.DataFrame() if to_df else {'data': []}

        # ========== 详细调试信息（仅文件） ==========
        import json as json_lib

        # 请求目标详情（DEBUG）
        if 'result' in payload and 'result' in payload['result']:
            table_configs = payload['result']['result']
            table_names = list(set([r.get('table', '') for r in table_configs]))
            field_names = list(set([r.get('feildName', '') for r in table_configs]))
            report_logger.debug("表名: %s", table_names)
            report_logger.debug("字段: %s", field_names)

        geo_dim = payload.get('geographicdimension', 'N/A')
        time_dim = payload.get('timedimension', 'N/A')
        report_logger.debug("地理维度: %s, 时间维度: %s", geo_dim, time_dim)

        # 查询条件（DEBUG）- 添加更详细的日志
        if 'where' in payload and payload['where']:
            report_logger.info("=" * 60)
            report_logger.info("[查询条件详情]")
            for i, cond in enumerate(payload['where']):
                report_logger.info("  条件[%d]: %s %s %s", i, cond.get('feild', ''), cond.get('symbol', ''), cond.get('val', ''))
            report_logger.info("=" * 60)

        # 完整Payload（DEBUG）
        report_logger.debug("请求Payload: %s", json_lib.dumps(payload, ensure_ascii=False, indent=2))

        # ========== 第一步：获取总行数 ==========
        count_payload = payload.copy()
        key_list = ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                    'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount']
        count_payload = {key: value for key, value in count_payload.items() if key in key_list}

        report_logger.debug("获取数据总数...")

        total_count = self.get_table_count(count_payload, report_name=report_name)
        report_logger.info("预期数据行数: %d", total_count)

        if progress_callback:
            progress_callback(0, total_count, f"开始查询，共 {total_count} 行数据")

        if total_count == 0:
            report_logger.warning("数据为空")
            return pd.DataFrame() if to_df else {'data': []}

        # ========== 第二步：获取数据 ==========
        report_logger.info("")
        report_logger.info("┌──────────────────────────────────────────────────────────────────┐")
        report_logger.info("│ Step 2: 获取数据内容                                              │")
        report_logger.info("├──────────────────────────────────────────────────────────────────┤")
        report_logger.info("│ 请求URL: %s", JXCX_URL)
        report_logger.info("│ 请求参数: start=0, length=%d", total_count)
        report_logger.info("│ 预计超时时间: %ds", max(60, min(300, total_count // 1000 * 2)))
        report_logger.info("└──────────────────────────────────────────────────────────────────┘")

        data_list = self._fetch_by_loop(payload, total_count, progress_callback)

        report_logger.info("[结果] 实际获取数据: %d 条", len(data_list))

        if to_df:
            res_df = pd.DataFrame(data_list) if data_list else pd.DataFrame()

            if res_df.empty:
                report_logger.warning("DataFrame为空，未获取到任何数据")
                report_logger.warning("数据为空的常见原因:")
                report_logger.warning("  1. 该日期范围内确实没有数据")
                report_logger.warning("  2. 地市名称与数据库不匹配")
                report_logger.warning("  3. 查询条件(where)字段与数据库表结构不匹配")
                report_logger.warning("  4. 时间字段格式不正确")
                return pd.DataFrame()

            # 应用字段映射（与旧版保持一致）
            en_zh_df = self._get_field_mapping(payload)
            if not en_zh_df.empty:
                res_df = pd.concat([en_zh_df, res_df], ignore_index=True)
                index_first = res_df.index.tolist()[0]
                to_colname = list(res_df.loc[index_first])
                res_df.columns = to_colname
                res_df.drop(index=index_first, inplace=True)
                report_logger.info("[字段映射] 已转换为中文字段名，共 %d 个字段", len(to_colname))

            report_logger.info("✓ 报表完成: %s, 数据: %d行 x %d列", report_name, len(res_df), len(res_df.columns))
            return res_df
        else:
            report_logger.info("✓ 报表完成: %s, 数据: %d条", report_name, len(data_list))
            return {'data': data_list}

    def get_4g_voice_table(self, volte_payload, epsfb_payload, to_df=True):
        """获取4G语音小区报表数据（VoLTE+EPSFB联合）"""
        result = self._get_4g_voice_table_internal(volte_payload, epsfb_payload)
        if to_df:
            return result['merged']
        else:
            return {'data': result['merged'].to_dict('records')}

    def _get_4g_voice_table_internal(self, volte_payload, epsfb_payload):
        """获取4G语音小区报表数据（内部方法）
        
        按时间+CGI唯一值联合VoLTE预警和EPSFB预警表
        """
        import pandas as pd

        result = {'volte': pd.DataFrame(), 'epsfb': pd.DataFrame(), 'merged': pd.DataFrame()}

        report_logger = get_report_logger("4G语音小区")

        # ========== 4G语音报表开始 ==========
        report_logger.info("▶ 开始提取4G语音小区报表（预警报表联合）")

        if not self.enabled:
            report_logger.info("JXCX 未启用，尝试进入...")
            if not self.enter_jxcx():
                report_logger.error("无法进入即席查询模块")
                return result

        # ========== 步骤1：获取VoLTE数据 ==========
        report_logger.info("获取VoLTE预警数据...")

        volte_df = self.get_table(volte_payload, to_df=True, report_name="4G语音-VoLTE预警")
        report_logger.info("[VoLTE预警] 获取数据: %d 行", len(volte_df))

        result['volte'] = volte_df

        # ========== 步骤2：获取EPSFB数据 ==========
        report_logger.info("获取EPSFB预警数据...")

        epsfb_df = self.get_table(epsfb_payload, to_df=True, report_name="4G语音-EPSFB预警")
        report_logger.info("[EPSFB预警] 获取数据: %d 行", len(epsfb_df))

        result['epsfb'] = epsfb_df

        if volte_df.empty and epsfb_df.empty:
            report_logger.warning("VoLTE和EPSFB预警数据均为空")
            return result

        # ========== 步骤3：数据合并（按时间+CGI唯一值） ==========
        report_logger.debug("开始数据合并处理（按时间+CGI唯一值）...")

        # 确定合并键（支持多种字段名）
        time_col = None
        cgi_col = None
        for col in volte_df.columns:
            col_lower = col.lower()
            if col_lower == 'starttime' or col == '时间' or col_lower == 'result_time':
                time_col = col
            if col_lower == 'cgi' or col == '小区' or col_lower == 'cell':
                cgi_col = col

        if time_col is None:
            for col in volte_df.columns:
                if 'time' in col.lower() or '时间' in col:
                    time_col = col
                    break

        report_logger.info("[合并] 检测到的合并键 - 时间字段: %s, 小区字段: %s", time_col, cgi_col)
        report_logger.debug("[合并] VoLTE所有列: %s", list(volte_df.columns))
        report_logger.debug("[合并] EPSFB所有列: %s", list(epsfb_df.columns))

        # 按时间+CGI去重（取唯一值）
        if time_col and cgi_col:
            report_logger.info("[合并] 按 %s + %s 去重", time_col, cgi_col)
            if time_col in volte_df.columns and cgi_col in volte_df.columns:
                volte_df = volte_df.drop_duplicates(subset=[time_col, cgi_col], keep='first')
                report_logger.info("[合并] VoLTE去重后: %d 行", len(volte_df))
            if time_col in epsfb_df.columns and cgi_col in epsfb_df.columns:
                epsfb_df = epsfb_df.drop_duplicates(subset=[time_col, cgi_col], keep='first')
                report_logger.info("[合并] EPSFB去重后: %d 行", len(epsfb_df))

        # 重命名中文字段
        col_name_map = {
            'starttime': '时间', 'city': '地市', 'cgi': '小区', 'grid': '责任网格',
            'area': '区县', 'nrcell_name': '小区名称'
        }

        volte_rename = {}
        for en_col in volte_df.columns:
            if en_col in col_name_map:
                volte_rename[en_col] = col_name_map[en_col]
        volte_df = volte_df.rename(columns=volte_rename)

        epsfb_rename = {}
        for en_col in epsfb_df.columns:
            if en_col in col_name_map:
                epsfb_rename[en_col] = col_name_map[en_col]
        epsfb_df = epsfb_df.rename(columns=epsfb_rename)

        report_logger.debug("[合并] VoLTE转换后列名: %s", list(volte_df.columns))
        report_logger.debug("[合并] EPSFB转换后列名: %s", list(epsfb_df.columns))

        # 确定合并键（使用实际存在的字段）
        merge_keys = []
        if time_col and time_col in volte_df.columns:
            merge_keys.append(time_col)
        if cgi_col and cgi_col in volte_df.columns:
            merge_keys.append(cgi_col)
        
        report_logger.info("[合并] 合并键: %s", merge_keys)

        if not merge_keys:
            report_logger.warning("[合并] 无法确定合并键，使用concat合并")
            merged_df = pd.concat([volte_df, epsfb_df], ignore_index=True)
            result['merged'] = merged_df
        else:
            # 确定VoLTE和EPSFB的特有字段（支持多种前缀格式，排除合并键）
            # 合并键字段不作为特有字段
            merge_key_names = {'时间', '小区', 'starttime', 'cgi', 'result_time', 'cell'}
            
            # 匹配VoLTE字段：volte_, volte_alarm_, volte_alarm_cell_warning. 等
            volte_cols = []
            for c in volte_df.columns:
                if c in merge_key_names:
                    continue
                c_lower = c.lower()
                if (c_lower.startswith('volte') or 'volte' in c_lower or 
                    c_lower.startswith('lte_') or c_lower.startswith('lte_')):
                    if c not in volte_cols:
                        volte_cols.append(c)
            
            # 匹配EPSFB字段：epsfb_, epsfb_cell_warning. 等
            epsfb_cols = []
            for c in epsfb_df.columns:
                if c in merge_key_names:
                    continue
                c_lower = c.lower()
                if (c_lower.startswith('epsfb') or 'epsfb' in c_lower or 
                    c_lower.startswith('lte_')):
                    if c not in epsfb_cols:
                        epsfb_cols.append(c)

            report_logger.info("[合并] VoLTE特有字段 (%d个): %s", len(volte_cols), volte_cols[:10] if len(volte_cols) > 10 else volte_cols)
            report_logger.info("[合并] EPSFB特有字段 (%d个): %s", len(epsfb_cols), epsfb_cols[:10] if len(epsfb_cols) > 10 else epsfb_cols)

            # 构建VoLTE合并数据
            volte_merge_cols = [c for c in merge_keys if c in volte_df.columns] + [c for c in volte_cols if c in volte_df.columns]
            # 添加小区名称字段（支持多种列名）
            for name_col in ['nrcell_name', '小区名称', 'cell_name']:
                if name_col in volte_df.columns and name_col not in volte_merge_cols and name_col not in merge_keys:
                    volte_merge_cols.append(name_col)
                    break
            volte_for_merge = volte_df[volte_merge_cols].copy()

            # 构建EPSFB合并数据
            epsfb_merge_cols = [c for c in merge_keys if c in epsfb_df.columns] + [c for c in epsfb_cols if c in epsfb_df.columns]
            # 添加小区名称字段（支持多种列名）
            for name_col in ['nrcell_name', '小区名称', 'cell_name']:
                if name_col in epsfb_df.columns and name_col not in epsfb_merge_cols and name_col not in merge_keys:
                    epsfb_merge_cols.append(name_col)
                    break
            epsfb_for_merge = epsfb_df[epsfb_merge_cols].copy()

            # 补充小区名称（支持nrcell_name和小区名称两种列名）
            epsfb_name_col = None
            volte_name_col = None
            
            for col in epsfb_for_merge.columns:
                if col in merge_keys:
                    continue
                if col == 'nrcell_name' or col == '小区名称' or col == 'cell_name':
                    epsfb_name_col = col
                    break
            
            for col in volte_for_merge.columns:
                if col in merge_keys:
                    continue
                if col == 'nrcell_name' or col == '小区名称' or col == 'cell_name':
                    volte_name_col = col
                    break
            
            # 重命名EPSFB的小区名称列避免冲突
            if epsfb_name_col:
                epsfb_for_merge = epsfb_for_merge.rename(columns={epsfb_name_col: 'nrcell_name_epsfb'})

            if not merge_keys:
                merged_df = pd.concat([volte_for_merge, epsfb_for_merge], axis=1)
            else:
                # 使用外连接合并（union all效果）
                merged_df = pd.merge(volte_for_merge, epsfb_for_merge, on=merge_keys, how='outer')

            # 补充小区名称（VoLTE优先，EPSFB备用）
            if 'nrcell_name_epsfb' in merged_df.columns:
                if 'nrcell_name' not in merged_df.columns:
                    merged_df['nrcell_name'] = merged_df['nrcell_name_epsfb']
                else:
                    merged_df['nrcell_name'] = merged_df['nrcell_name'].fillna(merged_df['nrcell_name_epsfb'])
                merged_df = merged_df.drop(columns=['nrcell_name_epsfb'])
                report_logger.debug("[合并] 小区名称已补充（VoLTE优先，EPSFB备用）")

            # 删除全为空的列
            merged_df = merged_df.dropna(axis=1, how='all')

            # 清理重复的列（如city_x/city_y, nrcell_name_x/nrcell_name_y）
            # 先收集所有带后缀的列
            cols_to_drop = []
            cols_to_merge = {}
            for col in merged_df.columns:
                if col.endswith('_x'):
                    base_col = col[:-2]
                    y_col = base_col + '_y'
                    if y_col in merged_df.columns:
                        # 合并_x和_y列，优先使用_x的值
                        merged_df[base_col] = merged_df[col].fillna(merged_df[y_col])
                        cols_to_drop.extend([col, y_col])
            
            # 处理nrcell_name和nrcell_name_epsfb的合并
            if 'nrcell_name_epsfb' in merged_df.columns:
                if 'nrcell_name' not in merged_df.columns:
                    merged_df['nrcell_name'] = merged_df['nrcell_name_epsfb']
                else:
                    merged_df['nrcell_name'] = merged_df['nrcell_name'].fillna(merged_df['nrcell_name_epsfb'])
                merged_df = merged_df.drop(columns=['nrcell_name_epsfb'])
                report_logger.debug("[合并] 小区名称已补充（VoLTE优先，EPSFB备用）")

            if cols_to_drop:
                merged_df = merged_df.drop(columns=cols_to_drop)
                report_logger.debug("[合并] 已清理重复列: %s", set(cols_to_drop))

            # 调整列顺序
            cols = list(merged_df.columns)
            if 'nrcell_name' in cols and 'cgi' in cols:
                cols.remove('nrcell_name')
                cgi_idx = cols.index('cgi')
                cols.insert(cgi_idx + 1, 'nrcell_name')
                merged_df = merged_df[cols]
                report_logger.debug("[合并] 已将小区名称列移到小区列后面")

        result['merged'] = merged_df

        # ========== 4G语音报表完成 ==========
        report_logger.info("✓ 4G语音小区报表完成: VoLTE=%d行, EPSFB=%d行, 合并=%d行",
                          len(volte_df), len(epsfb_df), len(merged_df))

        return result

    # ========== 并行查询支持 ==========

    def query_tables_parallel(self, table_configs, max_workers=None, progress_callback=None):
        """并行查询多个报表

        Args:
            table_configs: 表配置列表，每个元素为 (table_name, payload) 元组
            max_workers: 最大并行数（默认使用常量）
            progress_callback: 进度回调函数 callback(completed, total, table_name, status)

        Returns:
            dict: {table_name: DataFrame} 查询结果字典
        """
        if max_workers is None:
            max_workers = MAX_PARALLEL_QUERIES
        import pandas as pd

        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════════════╗")
        logger.info("║                     并行查询模式                                  ║")
        logger.info("╠══════════════════════════════════════════════════════════════════╣")
        logger.info("║ 报表数量: %d", len(table_configs))
        logger.info("║ 最大并行数: %d", max_workers)
        logger.info("╚══════════════════════════════════════════════════════════════════╝")

        results = {}
        completed = 0
        total = len(table_configs)

        def query_single_table(table_name, payload):
            """查询单个表（用于线程池）"""
            try:
                report_logger = get_report_logger(table_name)
                report_logger.info("[并行查询] 开始查询: %s", table_name)
                df = self.get_table(payload, to_df=True, report_name=table_name)
                report_logger.info("[并行查询] ✓ 完成查询: %s, 获取 %d 行", table_name, len(df))
                logger.info("[并行查询] ✓ 完成查询: %s, 获取 %d 行", table_name, len(df))
                return table_name, df
            except Exception as e:
                logger.error("[并行查询] ✗ 查询失败: %s, 错误: %s", table_name, str(e)[:100])
                return table_name, pd.DataFrame()

        # 使用线程池并行查询
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(query_single_table, name, payload): name
                for name, payload in table_configs
            }

            # 等待完成
            for future in as_completed(futures):
                table_name = futures[future]
                completed += 1
                try:
                    name, df = future.result()
                    results[name] = df
                    logger.info("[并行进度] %d/%d 完成: %s", completed, total, name)

                    # 更新进度
                    if progress_callback:
                        status = "成功" if not df.empty else "空数据"
                        progress_callback(completed, total, name, status)

                except Exception as e:
                    logger.error("[并行查询] ✗ 处理结果失败: %s, 错误: %s", table_name, str(e)[:100])
                    results[table_name] = pd.DataFrame()
                    if progress_callback:
                        progress_callback(completed, total, table_name, "失败")

        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════════════╗")
        logger.info("║                     并行查询完成                                  ║")
        logger.info("╠══════════════════════════════════════════════════════════════════╣")
        for name, df in results.items():
            status = "成功" if not df.empty else "失败/空"
            logger.info("║ %s: %d 行 [%s]", name.ljust(20), len(df), status)
        logger.info("╚══════════════════════════════════════════════════════════════════╝")

        return results


class ClusterOrderQuery:
    """聚类工单查询类"""

    def __init__(self, session):
        self.sess = session
        from utils.config import (
            BASE_URL, GET_GRID_URL, GET_PROBLEM_LABEL_URL, QUERY_PROPOSAL_URL
        )
        self.base_url = BASE_URL
        self.grid_url = GET_GRID_URL
        self.label_url = GET_PROBLEM_LABEL_URL
        self.query_url = QUERY_PROPOSAL_URL
        self._initialized = False

        # 聚类工单API专用headers（参考浏览器请求）
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Origin': 'https://nqi.gmcc.net:20443',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://nqi.gmcc.net:20443/pro-ltemr-cicd/modules/ltescheme/unify/disquery/showgis.jsp?firstQuery=1',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        }

    def _ensure_session(self):
        """确保聚类工单Session已初始化

        访问 pro-ltemr-cicd/portal 页面以获取该模块专属的Session
        这个Session对于后续的聚类工单API调用是必需的
        """
        if self._initialized:
            return True

        try:
            # 访问聚类工单页面以获取Session
            # 这个请求会返回一个302重定向到CAS，并设置新的JSESSIONID
            portal_url = f"{self.base_url}/pro-ltemr-cicd/portal?menuname=jlwtd&address=/modules/ltescheme/unify/disquery/showgis.jsp"
            logger.info("[聚类工单] 初始化Session，访问: %s", portal_url)

            # 使用 allow_redirects=True 跟随重定向
            res = self.sess.get(portal_url, headers=self.headers, timeout=30, allow_redirects=True)

            # 检查是否成功获取到Session
            jsessionid = get_cookie_value(self.sess.cookies, 'JSESSIONID', domain='nqi.gmcc.net')
            if not jsessionid:
                jsessionid = get_cookie_value(self.sess.cookies, 'JSESSIONID')

            if jsessionid:
                logger.info("[聚类工单] Session初始化成功，JSESSIONID: %s...", jsessionid[:16])
                self._initialized = True
                return True
            else:
                logger.warning("[聚类工单] Session初始化失败，未获取到JSESSIONID")
                return False

        except Exception as e:
            logger.error("[聚类工单] Session初始化异常: %s", str(e))
            return False

    def get_grids(self, city_code):
        """获取责任网格列表

        Args:
            city_code: 地市编码（如 860662）

        Returns:
            list: 网格列表 [{'id': '责任网格-阳江阳西县', 'text': '责任网格-阳江阳西县'}, ...]
        """
        # 确保Session已初始化
        if not self._ensure_session():
            logger.warning("[聚类工单] Session未初始化，无法获取网格")
            return []

        try:
            data = {'city': city_code}
            res = self.sess.post(self.grid_url, data=data, headers=self.headers, timeout=30)

            if res.status_code == 200:
                result = json.loads(res.content)
                if result.get('code') == 1:
                    grids = json.loads(result.get('obj', '[]'))
                    logger.info("[聚类工单] 获取到 %d 个责任网格", len(grids))
                    return grids
                else:
                    logger.warning("[聚类工单] 获取网格失败: %s", result.get('msg', '未知错误'))
            else:
                logger.warning("[聚类工单] 获取网格HTTP错误: %d", res.status_code)
        except Exception as e:
            logger.error("[聚类工单] 获取网格异常: %s", str(e))

        return []

    def get_problem_labels(self, start_date, end_date, typeid=1):
        """获取问题标签列表

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            typeid: 问题类型ID（默认1）

        Returns:
            list: 问题标签列表 [{'id': 'xxx', 'text': 'xxx'}, ...]
        """
        # 确保Session已初始化
        if not self._ensure_session():
            logger.warning("[聚类工单] Session未初始化，无法获取问题标签")
            return []

        try:
            # 浏览器实际只发送typeid参数
            data = {
                'typeid': typeid
            }
            res = self.sess.post(self.label_url, data=data, headers=self.headers, timeout=30)

            if res.status_code == 200:
                result = json.loads(res.content)
                if isinstance(result, list):
                    logger.info("[聚类工单] 获取到 %d 个问题标签", len(result))
                    return result
                else:
                    logger.warning("[聚类工单] 问题标签返回格式异常: %s", result)
            else:
                logger.warning("[聚类工单] 获取问题标签HTTP错误: %d", res.status_code)
        except Exception as e:
            logger.error("[聚类工单] 获取问题标签异常: %s", str(e))

        return []

    def query_orders(self, params, progress_callback=None):
        """查询聚类工单

        Args:
            params: 查询参数字典
                - timeType: 时间类型（问题生成时间/派发时间/确认时间）
                - start_date: 开始日期 (YYYY-MM-DD)
                - end_date: 结束日期 (YYYY-MM-DD)
                - city: 地市编码（如 860662）
                - area_grid: 责任网格（可选，多个用逗号分隔）
                - detailed_type: 详细问题类型列表（可选）
                - problem_status: 工单状态（可选）
                - page: 页码（默认1）
                - rows: 每页行数（默认100）
            progress_callback: 进度回调函数 callback(current, total, message)

        Returns:
            dict: {
                'rows': 数据行列表,
                'total': 总行数,
                'page': 当前页,
                'total_pages': 总页数,
                'columns': 列定义
            }
        """
        # 确保Session已初始化
        if not self._ensure_session():
            logger.warning("[聚类工单] Session未初始化，无法查询")
            if progress_callback:
                progress_callback(0, 0, "Session初始化失败")
            return {'rows': [], 'total': 0, 'page': 1, 'total_pages': 0, 'columns': []}

        try:
            # 构建请求数据
            # firstQuery: 首次查询时设为1，后续查询设为空
            is_first_query = params.get('first_query', True)
            post_data = {
                'firstQuery': '1' if is_first_query else '',
                'timeType': params.get('timeType', '问题生成时间'),
                'start_date': params.get('start_date', ''),
                'end_date': params.get('end_date', ''),
                'city': params.get('city', ''),
                'area_grid': params.get('area_grid', ''),
                'order_code': '',
                'problemSource': '',
                'question_type': '',
                'problem_status': params.get('problem_status', ''),
                'cover_scene': '',
                'special_label': '',
                'value_label': '',
                'vcfirst_submitter': '',
                'vcdetail_submitter': '',
                'vcevaluator': '',
                'vcdetail_cause': '',
                'vcdetail_measures': '',
                'handover': '',
                'intevaluate_type': '',
                'search_uuid': '',
                'alllikequery': '',
                'vcimport': '',
                'vcdatatype': '',
                'intproposal_company': '',
                'isquery': 'true',
                'ordercheck': '',
                'ischeck': '',
                'isDuplicateRemoval': 'false',
                'intisprovince': '',
                'vccellviplevel': '',
                'query_type': 'null',
                'query_detail_type': '',
                'intisupscale': '',
                'vcupscale_code': '',
                'vcbilling_plbtype': '',
                'vcnetwork_type': '',
                'intorderanaly_record': '',
                'vcdataroot': '',
                'iscs': '',
                'intis_warranty': '',
                'vcorder_type': '',
                'isspecial': 'false',
                'rows': params.get('rows', 100),
                'pagination[pageSize]': params.get('rows', 100),
                'pagination[page]': params.get('page', 1),
            }

            # 添加详细问题类型（使用浏览器实际格式: detailed_type[]）
            detailed_types = params.get('detailed_type', [])
            if detailed_types:
                # 使用 detailed_type[] 格式，与浏览器请求一致
                for dt in detailed_types:
                    post_data['detailed_type[]'] = dt

            if progress_callback:
                progress_callback(0, 0, "正在查询聚类工单...")

            # 发送请求
            res = self.sess.post(self.query_url, data=post_data, headers=self.headers, timeout=60)

            if res.status_code == 200:
                result = json.loads(res.content)

                # 解析响应
                message = result.get('message', {})
                if message.get('success'):
                    rows = result.get('rows', [])
                    pagination = result.get('pagination', {})
                    columns = result.get('columns', [])

                    total = pagination.get('totalCount', 0)
                    total_pages = pagination.get('totalPage', 1)
                    current_page = pagination.get('currentPage', 1)

                    if progress_callback:
                        progress_callback(len(rows), total, f"获取到 {len(rows)} 条数据，共 {total} 条")

                    logger.info("[聚类工单] 查询成功: %d/%d 条", len(rows), total)

                    return {
                        'rows': rows,
                        'total': total,
                        'page': current_page,
                        'total_pages': total_pages,
                        'columns': columns
                    }
                else:
                    error_msg = message.get('message', '未知错误')
                    logger.error("[聚类工单] 查询失败: %s", error_msg)
                    if progress_callback:
                        progress_callback(0, 0, f"查询失败: {error_msg}")
            else:
                logger.error("[聚类工单] HTTP错误: %d", res.status_code)
                if progress_callback:
                    progress_callback(0, 0, f"HTTP错误: {res.status_code}")

        except Exception as e:
            logger.error("[聚类工单] 查询异常: %s", str(e))
            if progress_callback:
                progress_callback(0, 0, f"异常: {str(e)[:50]}")

        return {'rows': [], 'total': 0, 'page': 1, 'total_pages': 0, 'columns': []}

    def query_all_orders(self, params, progress_callback=None):
        """查询所有聚类工单（自动翻页获取全部）

        Args:
            params: 查询参数字典（同query_orders）
            progress_callback: 进度回调函数

        Returns:
            list: 所有数据行
        """
        all_rows = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            params['page'] = page
            result = self.query_orders(params, progress_callback)

            if result['rows']:
                all_rows.extend(result['rows'])
                total_pages = result['total_pages']

                if progress_callback:
                    progress_callback(
                        len(all_rows), result['total'],
                        f"第 {page}/{total_pages} 页，已获取 {len(all_rows)} 条"
                    )

                page += 1
            else:
                break

        logger.info("[聚类工单] 共获取 %d 条数据", len(all_rows))
        return all_rows
