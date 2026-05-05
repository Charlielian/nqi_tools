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

from urllib.parse import urlencode

from utils.config import (
    BASE_URL, JXCX_URL, JXCX_COUNT_URL, JXCX_SEARCH_URL, JXCX_TABLE_URL,
    HEADERS, MAX_SINGLE_QUERY
)

logger = logging.getLogger(__name__)


class JXCXQuery:
    """即席查询类"""

    def __init__(self, session):
        self.sess = session
        self.enabled = False
        self._field_config_cache = {}

    def get_field_config(self, table_key, fieldtype, api_type='search'):
        """动态获取表字段配置（从API获取）"""
        cache_key = f"{table_key}_{fieldtype}_{api_type}"
        if cache_key in self._field_config_cache:
            logger.debug("使用缓存的字段配置: %s", cache_key)
            return self._field_config_cache[cache_key]

        logger.debug("动态获取字段配置: table_key=%s, fieldtype=%s, api_type=%s", table_key, fieldtype, api_type)

        try:
            if api_type == 'table':
                data = {'tablename': table_key}
                res = self.sess.post(JXCX_TABLE_URL, data=data, headers=HEADERS, timeout=30)

                if res.status_code == 200:
                    result = json.loads(res.content)
                    configs = result.get('CFG_ADHOC_CONF_TABLE', [])
                    logger.debug("从getSelectTable接口获取到 %d 个字段配置", len(configs))

                    self._field_config_cache[cache_key] = configs
                    return configs
                else:
                    logger.error("获取字段配置失败: %s", res.status_code)
                    return None
            else:
                data = {
                    'key': table_key,
                    'field': 'columnname_cn',
                    'field': 'columnname',
                    'field': 'fieldtype',
                    'field': 'datatype',
                    'field': 'tablename',
                    'field': 'tablename_cn',
                    'field': 'columntype',
                    'field': 'sort'
                }
                res = self.sess.post(JXCX_SEARCH_URL, data=data, headers=HEADERS, timeout=30)

                if res.status_code == 200:
                    result = json.loads(res.content)
                    configs = result.get('CFG_ADHOC_CONF_SEARCH', [])
                    logger.debug("从search接口获取到 %d 个字段配置", len(configs))

                    self._field_config_cache[cache_key] = configs
                    return configs
                else:
                    logger.error("获取字段配置失败: %s", res.status_code)
                    return None
        except Exception as e:
            logger.error("获取字段配置异常: %s", e)
            return None

    def build_payload_from_config(self, table_key, fieldtype, where_conditions, api_type='search',
                                  dimension_override=None, fields_override=None):
        """从动态获取的字段配置构建payload

        Args:
            table_key: API查询关键字
            fieldtype: 字段类型过滤条件
            where_conditions: 查询条件列表
            api_type: API类型，'search'使用adhocquery/search接口，'table'使用adhocquery/getSelectTable接口
            dimension_override: 可选的维度参数覆盖，如果提供则使用此参数而非API返回
            fields_override: 可选的字段列表覆盖，如果提供则使用此字段列表构建payload
        """
        configs = self.get_field_config(table_key, fieldtype, api_type)
        if not configs:
            # 如果动态获取失败，尝试使用 fields_override
            if fields_override:
                return self._build_payload_with_fields(
                    table_key, fieldtype, where_conditions, api_type,
                    dimension_override, fields_override
                )
            return None

        logger.debug("API返回的字段配置数量: %d", len(configs))
        logger.debug("API返回的字段名(前10个): %s", [c.get('columnname', '') for c in configs[:10]])
        logger.debug("API返回的fieldtype(前3个): %s", list(set(c.get('fieldtype', '') for c in configs[:3])))

        sorted_configs = sorted(configs, key=lambda x: x.get('sort', 0))

        first_config = sorted_configs[0]

        # 如果提供了维度覆盖参数，则使用覆盖参数；否则使用API返回的参数
        if dimension_override:
            geographicdimension = dimension_override.get('geographicdimension', '小区')
            timedimension = dimension_override.get('timedimension', '天')
            enodeb_field = dimension_override.get('enodebField', 'enodeb_id')
            cgi_field = dimension_override.get('cgiField', 'cgi')
            time_field = dimension_override.get('timeField', 'starttime')
            cell_field = dimension_override.get('cellField', 'cell')
            city_field = dimension_override.get('cityField', 'city')
        else:
            geographicdimension = first_config.get('geographicdimension', '小区')
            timedimension = first_config.get('timedimension', '天')
            enodeb_field = first_config.get('enodeb_field', 'enodeb_id')
            cgi_field = first_config.get('cgi_field', 'cgi')
            time_field = first_config.get('time_field', 'starttime')
            cell_field = first_config.get('cell_field', 'cell')
            city_field = first_config.get('city_field', 'city')

        logger.debug("使用的维度参数: geographicdimension=%s, timedimension=%s", geographicdimension, timedimension)
        logger.debug("  enodebField=%s, cgiField=%s, timeField=%s, cellField=%s, cityField=%s",
                    enodeb_field, cgi_field, time_field, cell_field, city_field)

        # 如果提供了字段覆盖，则使用覆盖的字段配置
        if fields_override:
            return self._build_payload_with_field_configs(
                table_key, fieldtype, where_conditions, api_type,
                geographicdimension, timedimension, enodeb_field, cgi_field,
                time_field, cell_field, city_field, fields_override
            )

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
        table_name = first_config.get('tablename', '')
        table_name_cn = first_config.get('tablename_cn', '')
        supporteddimension = first_config.get('supporteddimension')
        supportedtimedimension = first_config.get('supportedtimedimension', '')

        result_list = []
        for c in sorted_configs:
            result_list.append({
                'feildtype': c.get('fieldtype', ''),
                'table': c.get('tablename', ''),
                'tableName': c.get('tablename_cn', ''),
                'datatype': c.get('datatype', 'character varying'),
                'columntype': c.get('columntype', 1),
                'feildName': c.get('columnname_cn', ''),
                'feild': c.get('columnname', ''),
                'poly': '无', 'anyWay': '无', 'chart': '无', 'chartpoly': '无'
            })

        result = {
            'result': result_list,
            'tableParams': {
                'supporteddimension': supporteddimension,
                'supportedtimedimension': supportedtimedimension
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
            'where': where_conditions,
            'indexcount': 0
        }

        logger.debug("构建的payload包含 %d 个字段", len(columns))
        return payload

    def _build_payload_with_fields(self, table_key, fieldtype, where_conditions, api_type,
                                   dimension_override, fields_list):
        """使用字段列表构建payload（当API获取失败时使用）"""
        if dimension_override is None:
            dimension_override = {}
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
                'columntype': '1',
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
            'where': where_conditions,
            'indexcount': 0
        }

        logger.debug("使用字段列表构建payload，包含 %d 个字段", len(columns))
        return payload

    def _build_payload_with_field_configs(self, table_key, fieldtype, where_conditions, api_type,
                                          geographicdimension, timedimension, enodeb_field, cgi_field,
                                          time_field, cell_field, city_field, fields_override):
        """使用字段配置列表构建payload"""
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
                'columntype': config.get('columntype', '1'),
                'feildName': config.get('feildName', field),
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
            'where': where_conditions,
            'indexcount': 0
        }

        logger.debug("使用字段配置构建payload，包含 %d 个字段", len(columns))
        return payload

    def enter_jxcx(self, retry_times=3, timeout=60):
        """进入即席查询模块"""
        logger.info("========== 进入即席查询模块 ==========")

        for attempt in range(retry_times):
            if attempt > 0:
                logger.info("重试第 %d 次...", attempt)

            try:
                castgc = self.sess.cookies.get('CASTGC', domain='nqi.gmcc.net')
                if not castgc:
                    castgc = self.sess.cookies.get('CASTGC')

                if not castgc:
                    logger.error("未找到CASTGC cookie")
                    continue

                logger.debug("CASTGC获取成功: %s...", castgc[:20] if len(castgc) >= 20 else castgc)

                url = f'{BASE_URL}/pro-portal/pure/urlAction.action'
                params = {
                    'url': 'pro-adhoc/index',
                    'random': random.random(),
                    '__PID': 'JXCX',
                    'token': castgc
                }

                url_with_params = f"{url}?url={params['url']}&__PID={params['__PID']}&random={params['random']}&token={params['token']}"
                logger.debug("请求URL: %s...", url_with_params[:200] if len(url_with_params) >= 200 else url_with_params)

                start_time = time.time()
                res = self.sess.get(url_with_params, headers=HEADERS, timeout=timeout)
                elapsed_time = time.time() - start_time

                logger.debug("响应状态码: %s, 耗时: %.2f秒", res.status_code, elapsed_time)

                if res.status_code == 200:
                    self.enabled = True
                    logger.info("即席查询模块初始化成功！")
                    return True
                else:
                    logger.error("进入即席查询失败，状态码: %s", res.status_code)
                    continue

            except requests.exceptions.Timeout:
                logger.error("请求超时 (timeout=%ds)", timeout)
                continue
            except requests.exceptions.ConnectionError as e:
                logger.error("网络连接错误: %s", e)
                continue
            except Exception as e:
                logger.error("未知错误: %s", e)
                continue

        logger.error("进入即席查询失败，已尝试 %d 次", retry_times)
        return False

    def get_table_count(self, payload):
        """获取查询结果行数"""
        if not self.enabled:
            self.enter_jxcx()

        key_list = ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                    'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount',
                    'columns', 'order', 'search']
        payload_count = {key: value for key, value in payload.items() if key in key_list}
        payload_encoded = self._encode_payload(payload_count)

        logger.debug("查询总数 URL: %s", JXCX_COUNT_URL)
        logger.debug("查询参数 (前500字符): %s...", payload_encoded[:500] if len(payload_encoded) >= 500 else payload_encoded)

        try:
            res = self.sess.post(JXCX_COUNT_URL, data=payload_encoded, headers=HEADERS, timeout=180)
            logger.debug("响应状态码: %s", res.status_code)

            if res.status_code == 200:
                if not res.content or len(res.content.strip()) == 0:
                    logger.error("响应内容为空，可能是Session过期")
                    self.enabled = False
                    return 0

                try:
                    result = json.loads(res.content)
                except json.JSONDecodeError as e:
                    logger.error("JSON解析失败: %s", e)
                    logger.debug("响应内容 (前500字符): %s...", res.text[:500] if len(res.text) >= 500 else res.text)
                    self.enabled = False
                    return 0

                logger.debug("响应内容: %s", result)

                if 'message' in result and result['message']:
                    msg = str(result['message'])
                    logger.warning("服务器返回消息: %s", msg)
                    if '不存在' in msg:
                        logger.warning("数据不存在，返回0")
                        return 0

                count = result.get('count', result.get('data', {}).get('total', 1000000))
                logger.info("查询到的数据行数: %d", count)
                return count
        except Exception as e:
            logger.error("查询异常: %s", e)
            import traceback
            traceback.print_exc()

        logger.warning("查询超时，返回MAX_SINGLE_QUERY(%d)", MAX_SINGLE_QUERY)
        return MAX_SINGLE_QUERY

    def _encode_payload(self, payload):
        """URL编码payload"""
        result = []
        for key, value in payload.items():
            if isinstance(value, dict):
                encoded_value = json.dumps(value, ensure_ascii=False)
                result.append((key, encoded_value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        encoded_item = json.dumps(item, ensure_ascii=False)
                        result.append((key, encoded_item))
                    else:
                        result.append((key, str(item)))
            else:
                result.append((key, str(value) if value is not None else ''))
        return urlencode(result, safe='', encoding='utf-8')

    def get_table(self, payload, to_df=True):
        """获取表格数据"""
        import pandas as pd

        if not self.enabled:
            logger.debug("JXCX 未启用，尝试进入...")
            if not self.enter_jxcx():
                logger.error("无法进入即席查询模块")
                return pd.DataFrame() if to_df else {'data': []}

        payload_encoded = self._encode_payload(payload)

        try:
            res = self.sess.post(JXCX_URL, data=payload_encoded, headers=HEADERS, timeout=180)

            if res.status_code == 200:
                result = json.loads(res.content)

                if 'data' in result and result['data']:
                    data = result['data']
                    if to_df:
                        df = pd.DataFrame(data)
                        logger.info("获取到 %d 行数据", len(df))
                        return df
                    else:
                        return {'data': data}
                else:
                    logger.warning("返回数据为空")
                    return pd.DataFrame() if to_df else {'data': []}
            else:
                logger.error("请求失败，状态码: %s", res.status_code)
                return pd.DataFrame() if to_df else {'data': []}

        except Exception as e:
            logger.error("获取数据异常: %s", e)
            import traceback
            traceback.print_exc()
            return pd.DataFrame() if to_df else {'data': []}

    def get_4g_voice_table(self, volte_payload, epsfb_payload, to_df=True):
        """获取4G语音小区报表数据（VoLTE+EPSFB联合）"""
        result = self._get_4g_voice_table_internal(volte_payload, epsfb_payload)
        if to_df:
            return result['merged']
        else:
            return {'data': result['merged'].to_dict('records')}

    def _get_4g_voice_table_internal(self, volte_payload, epsfb_payload):
        """获取4G语音小区报表数据（内部方法）"""
        import pandas as pd

        result = {'volte': pd.DataFrame(), 'epsfb': pd.DataFrame(), 'merged': pd.DataFrame()}

        if not self.enabled:
            logger.debug("JXCX 未启用，尝试进入...")
            if not self.enter_jxcx():
                logger.error("无法进入即席查询模块")
                return result

        logger.info("========== 开始获取4G语音小区数据 ==========")

        logger.info("正在获取VoLTE数据...")
        volte_df = self.get_table(volte_payload, to_df=True)
        logger.debug("VoLTE数据: %d 行", len(volte_df))
        logger.debug("VoLTE列名: %s", list(volte_df.columns) if not volte_df.empty else 'N/A')
        result['volte'] = volte_df

        logger.info("正在获取EPSFB数据...")
        epsfb_df = self.get_table(epsfb_payload, to_df=True)
        logger.debug("EPSFB数据: %d 行", len(epsfb_df))
        logger.debug("EPSFB列名: %s", list(epsfb_df.columns) if not epsfb_df.empty else 'N/A')
        result['epsfb'] = epsfb_df

        if volte_df.empty and epsfb_df.empty:
            logger.warning("VoLTE和EPSFB数据均为空")
            return result

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

        logger.debug("VoLTE转换后列名: %s", list(volte_df.columns))
        logger.debug("EPSFB转换后列名: %s", list(epsfb_df.columns))

        merge_keys = []
        for key in ['时间', '小区']:
            if key in volte_df.columns:
                merge_keys.append(key)

        logger.debug("合并键: %s", merge_keys)

        if not merge_keys:
            logger.warning("无法确定合并键，使用简单concat")
            merged_df = pd.concat([volte_df, epsfb_df], ignore_index=True)
            result['merged'] = merged_df
            return result

        common_cols = set(['时间', '小区', '地市', '责任网格', '区县', 'starttime', 'city', 'cgi', 'grid', 'area', 'nrcell_name'])
        volte_cols = [c for c in volte_df.columns if (c.startswith('volte_') or 'VoLTE' in c) and c not in common_cols]
        epsfb_cols = [c for c in epsfb_df.columns if (c.startswith('epsfb_') or 'EPSFB' in c) and c not in common_cols]

        logger.debug("VoLTE特有字段: %s", volte_cols)
        logger.debug("EPSFB特有字段: %s", epsfb_cols)

        volte_merge_cols = [c for c in merge_keys if c in volte_df.columns] + [c for c in volte_cols if c in volte_df.columns]
        if '小区名称' in volte_df.columns:
            volte_merge_cols.append('小区名称')
        volte_for_merge = volte_df[volte_merge_cols].copy()

        epsfb_merge_cols = [c for c in merge_keys if c in epsfb_df.columns] + [c for c in epsfb_cols if c in epsfb_df.columns]
        if '小区名称' in epsfb_df.columns:
            epsfb_merge_cols.append('小区名称')
        epsfb_for_merge = epsfb_df[epsfb_merge_cols].copy()
        if '小区名称' in epsfb_for_merge.columns:
            epsfb_for_merge = epsfb_for_merge.rename(columns={'小区名称': '小区名称_epsfb'})

        if not merge_keys:
            # 当没有合并键时，使用简单的 concat
            merged_df = pd.concat([volte_for_merge.reset_index(drop=True), epsfb_for_merge.reset_index(drop=True)], axis=1)
        else:
            merged_df = pd.merge(volte_for_merge, epsfb_for_merge, on=merge_keys, how='outer')

        if '小区名称_epsfb' in merged_df.columns:
            if '小区名称' not in merged_df.columns:
                merged_df['小区名称'] = merged_df['小区名称_epsfb']
            else:
                merged_df['小区名称'] = merged_df['小区名称'].fillna(merged_df['小区名称_epsfb'])
            merged_df = merged_df.drop(columns=['小区名称_epsfb'])
            logger.debug("小区名称已补充（VoLTE优先，EPSFB备用）")

        merged_df = merged_df.dropna(axis=1, how='all')

        cols = list(merged_df.columns)
        if '小区名称' in cols and '小区' in cols:
            cols.remove('小区名称')
            xiaoqu_idx = cols.index('小区')
            cols.insert(xiaoqu_idx + 1, '小区名称')
            merged_df = merged_df[cols]
            logger.debug("已将小区名称列移到小区列后面")

        logger.info("合并完成，最终数据: %d 行, %d 列", len(merged_df), len(merged_df.columns))
        result['merged'] = merged_df
        return result

    def search(self, table_name, cities, start_date, end_date):
        """统一的表格数据查询方法

        不同表格只需在 TABLE_CONFIGS 中配置即可，无需修改此方法。

        Args:
            table_name: 显示的表格名称（如"5G干扰小区"）
            cities: 地市列表
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）

        Returns:
            DataFrame: 查询结果
        """
        import pandas as pd
        from gui.widgets import TableConfig

        # 1. 获取表格配置
        table_config = TableConfig.get_table_config(table_name)
        if not table_config:
            logger.error("未找到表格配置: %s", table_name)
            return pd.DataFrame()

        logger.info("查询配置: %s", table_name)
        logger.debug("  table_key: %s", table_config.get('table_key'))
        logger.debug("  fieldtype: %s", table_config.get('fieldtype'))
        logger.debug("  api_type: %s", table_config.get('api_type'))

        # 2. 确保进入查询模块
        if not self.enabled:
            logger.debug("JXCX 未启用，尝试进入...")
            if not self.enter_jxcx():
                logger.error("无法进入即席查询模块")
                return pd.DataFrame()

        # 3. 构建查询条件
        conditions = []
        default_conditions = table_config.get('default_conditions', [])
        if default_conditions:
            conditions.extend([dict(c) for c in default_conditions])

        # 非工参表添加日期条件
        is_gongcan = table_config.get('is_gongcan', False)
        if not is_gongcan:
            conditions.append({'field': 'starttime', 'operator': '>=', 'value': start_date})
            conditions.append({'field': 'starttime', 'operator': '<=', 'value': end_date})

        # 添加地市条件
        if cities:
            if isinstance(cities, list):
                city_value = ','.join(cities) if len(cities) > 1 else cities[0]
            else:
                city_value = cities
            conditions.append({'field': 'city', 'operator': 'in', 'value': city_value})

        logger.debug("查询条件: %s", conditions)

        # 4. 构建payload
        payload = self.build_payload_from_config(
            table_config['table_key'],
            table_config['fieldtype'],
            conditions,
            table_config.get('api_type', 'search'),
            dimension_override=table_config.get('dimension'),
            fields_override=table_config.get('fields')
        )

        if not payload:
            logger.error("构建payload失败")
            return pd.DataFrame()

        # 5. 检查是否需要特殊处理（如4G语音小区需要VoLTE+EPSFB合并）
        if table_config.get('is_4g_voice'):
            logger.info("4G语音小区查询，需要VoLTE+EPSFB合并...")
            volte_config = TableConfig.get_table_config('VoLTE小区监控预警')
            epsfb_config = TableConfig.get_table_config('EPSFB小区监控预警')

            if volte_config and epsfb_config:
                # 构建VoLTE和EPSFB的payload
                volte_conditions = [dict(c) for c in volte_config.get('default_conditions', [])]
                if not volte_config.get('is_gongcan'):
                    volte_conditions.append({'field': 'starttime', 'operator': '>=', 'value': start_date})
                    volte_conditions.append({'field': 'starttime', 'operator': '<=', 'value': end_date})
                if cities:
                    volte_conditions.append({'field': 'city', 'operator': 'in', 'value': city_value})

                volte_payload = self.build_payload_from_config(
                    volte_config['table_key'], volte_config['fieldtype'], volte_conditions,
                    volte_config.get('api_type', 'search'),
                    dimension_override=volte_config.get('dimension'),
                    fields_override=volte_config.get('fields')
                )

                epsfb_conditions = [dict(c) for c in epsfb_config.get('default_conditions', [])]
                if not epsfb_config.get('is_gongcan'):
                    epsfb_conditions.append({'field': 'starttime', 'operator': '>=', 'value': start_date})
                    epsfb_conditions.append({'field': 'starttime', 'operator': '<=', 'value': end_date})
                if cities:
                    epsfb_conditions.append({'field': 'city', 'operator': 'in', 'value': city_value})

                epsfb_payload = self.build_payload_from_config(
                    epsfb_config['table_key'], epsfb_config['fieldtype'], epsfb_conditions,
                    epsfb_config.get('api_type', 'search'),
                    dimension_override=epsfb_config.get('dimension'),
                    fields_override=epsfb_config.get('fields')
                )

                result = self._get_4g_voice_table_internal(volte_payload, epsfb_payload)
                return result['merged']
            else:
                logger.error("未找到VoLTE或EPSFB配置")
                return pd.DataFrame()

        # 6. 普通表格查询
        return self.get_table(payload, to_df=True)
