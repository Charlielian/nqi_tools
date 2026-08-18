# -*- coding: utf-8 -*-
"""
NQI 数据提取问题定界分析脚本
逐阶段诊断已配置报表的提取问题，定位具体失败环节

使用方法:
    python test_api.py

功能特性:
1. 6阶段诊断架构: 环境(S0) → 认证(S1) → 入口(S2) → Payload(S3) → Count(S4) → Data(S5)
2. 问题定界分类: 自动识别 AUTH_FAILED / JXCX_ENTRY_FAILED / PAYLOAD_BUILD_FAILED / COUNT_API_FAILED / DATA_API_FAILED / FIELD_MAPPING_FAILED / SUCCESS
3. 全流程请求/响应详细日志 (DEBUG 级别写入文件)
4. 控制台实时输出阶段进度与失败原因
5. 结构化诊断报告 (JSON) + 失败报表 debug_payload.json
6. 根因分析 + 修复建议
"""

import os
import sys
import json
import logging
import traceback
import threading
import time
import copy
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 问题定界分类 ==========
class DiagnoseCode:
    SUCCESS                  = "SUCCESS"
    ENV_FAILED               = "ENV_FAILED"
    AUTH_FAILED              = "AUTH_FAILED"
    JXCX_ENTRY_FAILED        = "JXCX_ENTRY_FAILED"
    PAYLOAD_BUILD_FAILED     = "PAYLOAD_BUILD_FAILED"
    COUNT_API_FAILED         = "COUNT_API_FAILED"
    DATA_API_FAILED          = "DATA_API_FAILED"
    FIELD_MAPPING_FAILED     = "FIELD_MAPPING_FAILED"


# ========== 配置日志 ==========
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'test_api')
os.makedirs(log_dir, exist_ok=True)
_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f'test_api_{_run_id}.log')
diag_json_file = os.path.join(log_dir, f'test_api_{_run_id}_diagnostic.json')


class ThreadSafeFormatter(logging.Formatter):
    def format(self, record):
        record.thread_tag = f"[{record.threadName[:8]}]"
        return super().format(record)


_formatter_file = ThreadSafeFormatter('%(asctime)s %(thread_tag)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
_formatter_console = ThreadSafeFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

_file_handler = logging.FileHandler(log_file, encoding='utf-8')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(_formatter_file)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_formatter_console)

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])
logger = logging.getLogger('test_api')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ========== 诊断辅助 ==========

def _box_log(log, lines, char='─', title=None):
    """输出一个 ASCII box 日志块"""
    width = 72
    top = f"╔{'═' * (width - 2)}╗"
    bot = f"╚{'═' * (width - 2)}╝"
    mid = f"╟{'─' * (width - 2)}╢"
    if title:
        log.info(top)
        title_str = f"║ {title} {'═' * (width - 4 - len(title))}║"
        log.info(title_str)
        log.info(mid)
    else:
        log.info(top)
    for line in lines:
        log.info(f"║ {line:<{width - 4}} ║")
    log.info(bot)


def _trunc(s, n=60):
    """截断字符串"""
    s = str(s)
    return s[:n] + ('...' if len(s) > n else '')


def _diag_summary(result):
    """从诊断结果生成一行简报"""
    code = result.get('diag_code', '?')
    name = result.get('name', '?')
    steps = result.get('steps', {})
    count = steps.get('S4_count')
    rows = steps.get('S5_rows')
    err = result.get('error', '')
    return f"{code} | {name} | count={count} rows={rows} | {_trunc(err, 50)}"


# ========== 配置读取 ==========

def get_table_configs():
    try:
        from gui.widgets import TableConfig
        configs = {}
        for name, config in TableConfig.TABLE_CONFIGS.items():
            payload_func = config.get('payload_func')
            if payload_func:
                configs[name] = {
                    'payload_func': payload_func,
                    'config': config,
                    'table_name': config.get('table_name', 'N/A'),
                    'fieldtype': config.get('fieldtype', 'N/A'),
                }
        logger.info(f"从 TableConfig 读取到 {len(configs)} 个报表配置")
        return configs
    except Exception as e:
        logger.error(f"读取 TableConfig 失败: {e}")
        logger.debug(traceback.format_exc())
        return {}


def get_category_mapping():
    try:
        from gui.main_window import NqiToolGUI
        if hasattr(NqiToolGUI, 'CATEGORIES'):
            return NqiToolGUI.CATEGORIES
    except Exception:
        pass
    return {
        '干扰': ['5G干扰小区', '5G_干扰报表_自忙时', '4G干扰小区'],
        '容量': ['5G小区容量报表', '5G小区容量-周报表', '重要场景-天'],
        '工参': ['5G小区工参报表', '4G小区工参报表'],
        'MR覆盖': ['5GMR覆盖-小区天', '4GMR覆盖-小区天'],
        '语音报表': ['4G语音-VoLTE', '4G语音-EPSFB', '5G语音小区'],
        '语音预警': ['VoLTE小区监控预警', 'EPSFB小区监控预警', 'VONR小区监控预警'],
        '小区性能': ['5G小区性能KPI报表', '4G小区性能KPI报表'],
        '全程完好率': ['4G全程完好率报表', '5G全程完好率报表'],
    }


# ========== CLI 界面 ==========

def print_banner():
    print()
    print("=" * 60)
    print("       NQI 数据提取问题定界分析工具")
    print("       Phased Diagnosis - S0:Env S1:Auth S2:JXCX S3:Payload S4:Count S5:Data")
    print("=" * 60)


def print_table_menu(table_configs, category_mapping):
    print("\n  可测试报表列表：\n")
    index_map = {}
    idx = 0

    for category, table_names in category_mapping.items():
        available = [t for t in table_names if t in table_configs]
        if not available:
            continue
        print(f"  【{category}】")
        for table_name in available:
            idx += 1
            index_map[idx] = (table_name, table_configs[table_name]['payload_func'])
            print(f"    {idx:>2}. {table_name}")
        print()

    categorized = set()
    for tables in category_mapping.values():
        categorized.update(tables)
    uncategorized = sorted(set(table_configs.keys()) - categorized)
    if uncategorized:
        print("  【其他】")
        for table_name in uncategorized:
            idx += 1
            index_map[idx] = (table_name, table_configs[table_name]['payload_func'])
            print(f"    {idx:>2}. {table_name}")
        print()

    return index_map


def get_user_selection(index_map):
    while True:
        try:
            choice = input("  请输入报表编号 (多选用逗号分隔, 0=全部, q=退出): ").strip()
            if choice.lower() == 'q':
                return None
            if choice == '0':
                return list(index_map.values())
            indices = [int(x.strip()) for x in choice.split(',')]
            selected = [index_map[i] for i in indices if i in index_map]
            invalid = [i for i in indices if i not in index_map]
            if invalid:
                print(f"  ⚠ 无效编号: {invalid}")
            if selected:
                return selected
            print("  ⚠ 请输入有效编号")
        except ValueError:
            print("  ⚠ 输入格式错误")
        except KeyboardInterrupt:
            print("\n  已取消")
            return None


def get_test_params():
    print("\n  --- 测试参数 ---")
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    start = input(f"  开始日期 [{yesterday}]: ").strip() or yesterday
    end = input(f"  结束日期 [{yesterday}]: ").strip() or start
    city = input("  地市 [阳江]: ").strip() or '阳江'
    limit = input("  查询条数 [5]: ").strip() or '5'
    try:
        limit = int(limit)
    except ValueError:
        limit = 5

    max_workers = input("  并发线程数 [3]: ").strip() or '3'
    try:
        max_workers = int(max_workers)
        max_workers = max(1, min(max_workers, 10))
    except ValueError:
        max_workers = 3

    return start, end, city, limit, max_workers


def get_credentials():
    username = password = None
    try:
        from utils.config import DEFAULT_USERNAME, DEFAULT_PASSWORD
        username, password = DEFAULT_USERNAME, DEFAULT_PASSWORD
    except Exception:
        pass
    if not username or username == 'XXXXX' or not password:
        print("\n  ⚠ 未检测到配置凭证，请手动输入")
        username = input("  用户名: ").strip()
        password = input("  密码: ").strip()
    return username, password


# ========== 诊断函数（文件级详细日志 + 控制台摘要） ==========

def diagnose_env():
    """S0: 环境检查"""
    steps = {}
    log = logger

    # 模块导入
    try:
        from core.auth import LoginManager
        from core.query import JXCXQuery, get_cookie_value
        from gui.widgets import TableConfig
        from utils.config import BASE_URL, JXCX_URL, JXCX_COUNT_URL, HEADERS
        steps['S0_import'] = True
        log.info("[S0] ✓ 模块导入成功")
    except ImportError as e:
        steps['S0_import'] = False
        steps['S0_error'] = f"ImportError: {e}"
        log.error("[S0] ✗ 模块导入失败: %s", e)
        return None, steps

    # 报表配置读取
    try:
        from gui.widgets import TableConfig
        table_count = len(TableConfig.TABLE_CONFIGS)
        steps['S0_table_configs'] = table_count
        log.info("[S0] ✓ 报表配置: %d 个", table_count)
    except Exception as e:
        steps['S0_table_configs'] = 0
        steps['S0_error'] = str(e)
        log.warning("[S0] ⚠ 读取报表配置失败: %s", e)

    return True, steps


def diagnose_login(username, password):
    """S1: 登录认证诊断"""
    log = logger
    steps = {}

    log.info("")
    log.info(f"{'─' * 72}")
    log.info("[S1] ▶ 开始登录诊断")
    log.info(f"{'─' * 72}")

    try:
        from core.auth import LoginManager
        from core.query import get_cookie_value

        login_mgr = LoginManager(username, password)
        session = login_mgr.login(try_times=1)

        if not session:
            steps['S1_session'] = None
            steps['diag_code'] = DiagnoseCode.AUTH_FAILED
            steps['error'] = "登录返回 None"
            log.error("[S1] ✗ 登录失败: 返回 None")
            return None, steps

        # Cookie 诊断
        castgc = get_cookie_value(session.cookies, 'CASTGC', domain='nqi.gmcc.net')
        if not castgc:
            castgc = get_cookie_value(session.cookies, 'CASTGC')
        jsessionid = get_cookie_value(session.cookies, 'JSESSIONID', domain='nqi.gmcc.net')
        if not jsessionid:
            jsessionid = get_cookie_value(session.cookies, 'JSESSIONID')

        cookie_info = []
        if castgc:
            cookie_info.append(f"CASTGC={castgc[:20]}...(len={len(castgc)})")
        if jsessionid:
            cookie_info.append(f"JSESSIONID={jsessionid[:20]}...")
        steps['S1_session'] = True
        steps['S1_castgc'] = castgc
        steps['S1_jsessionid'] = jsessionid
        steps['diag_code'] = DiagnoseCode.SUCCESS

        log.info("[S1] ✓ 登录成功 | Cookies: %s", ' | '.join(cookie_info))
        return session, steps

    except Exception as e:
        steps['S1_session'] = None
        steps['diag_code'] = DiagnoseCode.AUTH_FAILED
        steps['error'] = str(e)
        log.error("[S1] ✗ 登录异常: %s", e)
        log.debug(traceback.format_exc())
        return None, steps


def diagnose_enter_jxcx(query):
    """S2: 进入即席查询模块诊断"""
    log = logger
    steps = {}

    log.info("")
    log.info(f"{'─' * 72}")
    log.info("[S2] ▶ 开始进入即席查询模块诊断")
    log.info(f"{'─' * 72}")

    try:
        from core.query import get_cookie_value

        jsessionid_before = get_cookie_value(query.sess.cookies, 'JSESSIONID')

        result = query.enter_jxcx()

        jsessionid_after = get_cookie_value(query.sess.cookies, 'JSESSIONID')

        if result:
            steps['S2_result'] = True
            steps['S2_jsessionid_before'] = jsessionid_before
            steps['S2_jsessionid_after'] = jsessionid_after
            steps['diag_code'] = DiagnoseCode.SUCCESS
            log.info("[S2] ✓ 进入即席查询成功 | JSESSIONID %s→%s",
                     '有' if jsessionid_before else '无',
                     '已更新' if (jsessionid_after != jsessionid_before) else '未变')
            return True, steps
        else:
            steps['S2_result'] = False
            steps['S2_jsessionid_before'] = jsessionid_before
            steps['S2_jsessionid_after'] = jsessionid_after
            steps['diag_code'] = DiagnoseCode.JXCX_ENTRY_FAILED
            steps['error'] = "enter_jxcx() 返回 False"
            log.error("[S2] ✗ 进入即席查询失败: 返回 False")
            return False, steps

    except Exception as e:
        steps['S2_result'] = False
        steps['diag_code'] = DiagnoseCode.JXCX_ENTRY_FAILED
        steps['error'] = str(e)
        log.error("[S2] ✗ 进入即席查询异常: %s", e)
        log.debug(traceback.format_exc())
        return False, steps


def diagnose_build_payload(query, table_name, payload_func, start_date, end_date, city):
    """S3: Payload 构建诊断（完整打印字段配置获取过程）"""
    log = logger
    steps = {}

    func_name = payload_func.__name__

    log.info("")
    log.info(f"{'─' * 72}")
    log.info(f"[S3] ▶ Payload 构建诊断: {table_name}")
    log.info(f"{'─' * 72}")

    try:
        if 'gongcan' in func_name:
            payload = payload_func()
            steps['S3_is_gongcan'] = True
            log.info("[S3] 工参报表，跳过动态字段配置获取")
        else:
            payload = payload_func(start_date, end_date, city)
            steps['S3_is_gongcan'] = False

        if payload is None:
            steps['diag_code'] = DiagnoseCode.PAYLOAD_BUILD_FAILED
            steps['error'] = "payload_func() 返回 None"
            log.error("[S3] ✗ Payload 构建失败: 返回 None")
            return None, steps

        # 诊断 Payload 关键参数
        geo_dim = payload.get('geographicdimension', 'N/A')
        time_dim = payload.get('timedimension', 'N/A')
        where = payload.get('where', [])
        result = payload.get('result', {})
        result_list = result.get('result', []) if isinstance(result, dict) else []
        columns = payload.get('columns', [])
        enodeb_field = payload.get('enodebField', 'N/A')
        cgi_field = payload.get('cgiField', 'N/A')
        time_field = payload.get('timeField', 'N/A')
        cell_field = payload.get('cellField', 'N/A')
        city_field = payload.get('cityField', 'N/A')

        # 详细 box 日志
        _box_log(log, [
            f"报表名: {table_name}",
            f"函数名: {func_name}",
            f"地理维度: {geo_dim}",
            f"时间维度: {time_dim}",
            f"字段数(result): {len(result_list)}",
            f"字段数(columns): {len(columns)}",
            f"条件数(where): {len(where)}",
        ], title=f"[S3] Payload 概览")
        _box_log(log, [
            f"enodebField: {enodeb_field}",
            f"cgiField: {cgi_field}",
            f"timeField: {time_field}",
            f"cellField: {cell_field}",
            f"cityField: {city_field}",
        ], title=f"[S3] 维度参数")

        # 打印 where 条件
        if where:
            cond_lines = []
            for i, cond in enumerate(where):
                feild = cond.get('feild', '')
                symbol = cond.get('symbol', '')
                val = cond.get('val', '')
                datatype = cond.get('datatype', '')
                cond_lines.append(f"  [{i}] {feild} {symbol} {datatype} {repr(_trunc(val, 30))}")
            if cond_lines:
                _box_log(log, cond_lines, title="[S3] Where 条件")

        # 打印 result 字段（前 20 个 + 总数）
        if result_list:
            field_names = [r.get('feild', '') for r in result_list[:20]]
            shown = f"[{', '.join(field_names)}]"
            if len(result_list) > 20:
                shown += f" ... (+{len(result_list) - 20} 个)"
            _box_log(log, [shown], title=f"[S3] 字段列表 (共 {len(result_list)} 个)")

        steps['S3_result_field_count'] = len(result_list)
        steps['S3_columns_count'] = len(columns)
        steps['S3_where_count'] = len(where)
        steps['S3_geo_dimension'] = geo_dim
        steps['S3_time_dimension'] = time_dim
        steps['S3_diag_code'] = DiagnoseCode.SUCCESS
        steps['diag_code'] = DiagnoseCode.SUCCESS

        log.info("[S3] ✓ Payload 构建成功 | 字段数=%d | 条件=%d | 维度=%s/%s",
                 len(result_list), len(where), geo_dim, time_dim)

        return payload, steps

    except Exception as e:
        steps['diag_code'] = DiagnoseCode.PAYLOAD_BUILD_FAILED
        steps['error'] = str(e)
        log.error("[S3] ✗ Payload 构建异常: %s", e)
        log.debug(traceback.format_exc())
        return None, steps


def diagnose_count(query, payload, table_name):
    """S4: Count 查询诊断（打印完整请求/响应）"""
    from utils.config import JXCX_COUNT_URL, HEADERS
    from utils.helpers import encode_datatables_payload
    log = logger
    steps = {}

    log.info("")
    log.info(f"{'─' * 72}")
    log.info(f"[S4] ▶ Count 查询诊断: {table_name}")
    log.info(f"{'─' * 72}")

    try:
        from core.query import get_cookie_value
        from utils.config import JXCX_COUNT_URL

        # --- 请求前诊断 ---
        castgc = get_cookie_value(query.sess.cookies, 'CASTGC', domain='nqi.gmcc.net')
        if not castgc:
            castgc = get_cookie_value(query.sess.cookies, 'CASTGC')
        jsessionid = get_cookie_value(query.sess.cookies, 'JSESSIONID')

        cookie_str = '; '.join([
            f"{c.name}={c.value[:20]}..." if len(c.value) > 20 else f"{c.name}={c.value}"
            for c in query.sess.cookies
        ])

        _box_log(log, [
            f"CASTGC: {'存在 (len=' + str(len(castgc)) + ')' if castgc else '不存在!'}",
            f"JSESSIONID: {'存在' if jsessionid else '不存在'}",
        ], title="[S4] Cookie 状态")

        _box_log(log, [
            f"User-Agent: {HEADERS.get('User-Agent', 'N/A')[:60]}",
            f"Content-Type: {HEADERS.get('Content-Type', 'N/A')}",
            f"Cookie: {cookie_str[:120]}",
        ], title="[S4] 请求 Headers")

        # 构建 count payload
        key_list = ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                    'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount',
                    'columns', 'order', 'search']
        payload_count = {k: v for k, v in payload.items() if k in key_list}

        geo = payload_count.get('geographicdimension', '')
        time_dim = payload_count.get('timedimension', '')
        where_c = payload_count.get('where', [])

        _box_log(log, [
            f"URL: {JXCX_COUNT_URL}",
            f"geographicdimension: {geo}",
            f"timedimension: {time_dim}",
            f"where 条目数: {len(where_c)}",
        ], title="[S4] Count 请求参数")

        # 编码
        encoded = encode_datatables_payload(payload_count)
        _box_log(log, [
            f"编码后长度: {len(encoded)} 字符",
            f"前 300 字符: {encoded[:300]}",
        ], title="[S4] 编码后请求体")

        # --- 发送请求 ---
        t0 = time.time()
        res = query.sess.post(JXCX_COUNT_URL, data=encoded, headers=HEADERS, timeout=300)
        elapsed = time.time() - t0

        # --- 响应诊断 ---
        _box_log(log, [
            f"HTTP 状态码: {res.status_code}",
            f"Content-Type: {res.headers.get('Content-Type', 'N/A')}",
            f"响应长度: {len(res.content)} 字节",
            f"耗时: {elapsed:.2f}秒",
        ], title="[S4] 响应状态")

        if res.status_code != 200:
            steps['S4_http_code'] = res.status_code
            steps['diag_code'] = DiagnoseCode.COUNT_API_FAILED
            steps['error'] = f"HTTP {res.status_code}"
            log.error("[S4] ✗ HTTP 状态码异常: %s", res.status_code)
            log.error("[S4] 响应: %s", res.text[:500])
            return 0, steps

        if not res.content or len(res.content.strip()) == 0:
            steps['diag_code'] = DiagnoseCode.COUNT_API_FAILED
            steps['error'] = "响应内容为空"
            log.error("[S4] ✗ 响应内容为空")
            return 0, steps

        # JSON 解析
        try:
            result_data = json.loads(res.content)
        except json.JSONDecodeError as e:
            steps['diag_code'] = DiagnoseCode.COUNT_API_FAILED
            steps['error'] = f"JSON解析失败: {e}"
            log.error("[S4] ✗ JSON解析失败: %s", e)
            log.error("[S4] 响应: %s", res.text[:500])
            return 0, steps

        # 打印完整响应 keys
        resp_keys = list(result_data.keys()) if isinstance(result_data, dict) else type(result_data).__name__
        log.info("[S4] 响应 keys: %s", resp_keys)
        log.info("[S4] 响应内容(前800字符): %s", str(result_data)[:800])

        # 检查错误消息
        if 'message' in result_data and result_data['message']:
            msg = str(result_data['message'])
            log.warning("[S4] 服务器消息: %s", msg)
            if any(err in msg for err in ['不存在', '失败', '错误', 'error', 'Error', '异常', 'timeout', 'Timeout']):
                steps['diag_code'] = DiagnoseCode.COUNT_API_FAILED
                steps['error'] = f"服务器错误: {msg}"
                log.error("[S4] ✗ 服务器返回错误消息: %s", msg)
                return 0, steps

        # 提取 count
        count = query._extract_count_from_response(result_data)

        # 备用：直接从响应中取 count 字段（兜底）
        if count is None:
            if 'count' in result_data:
                count = result_data['count']

        if count is not None:
            steps['S4_count'] = int(count) if count != '' else 0
            steps['diag_code'] = DiagnoseCode.SUCCESS
            log.info("[S4] ✓ Count 查询成功 | count=%s", count)
            return int(count) if count != '' else 0, steps
        else:
            steps['diag_code'] = DiagnoseCode.COUNT_API_FAILED
            steps['error'] = f"响应中未找到count字段, keys={resp_keys}"
            log.error("[S4] ✗ 未能从响应中提取count | keys=%s", resp_keys)
            log.error("[S4] 完整响应: %s", str(result_data)[:1000])
            return 0, steps

    except Exception as e:
        steps['diag_code'] = DiagnoseCode.COUNT_API_FAILED
        steps['error'] = str(e)
        log.error("[S4] ✗ Count 查询异常: %s", e)
        log.debug(traceback.format_exc())
        return 0, steps


def diagnose_data(query, payload, table_name, limit, count):
    """S5: Data 查询诊断（打印完整请求/响应）"""
    from utils.config import JXCX_URL, HEADERS
    from utils.helpers import encode_datatables_payload
    log = logger
    steps = {}

    log.info("")
    log.info(f"{'─' * 72}")
    log.info(f"[S5] ▶ Data 查询诊断: {table_name}")
    log.info(f"{'─' * 72}")

    try:
        from utils.config import JXCX_URL

        # 构造 data payload
        data_payload = copy.deepcopy(payload)
        data_payload['draw'] = 1
        data_payload['start'] = 0
        data_payload['length'] = min(limit, 200)
        data_payload['total'] = 0
        if 'columns' not in data_payload:
            data_payload['columns'] = []
        if 'order' not in data_payload:
            data_payload['order'] = [{'column': 0, 'dir': 'desc'}]
        if 'search' not in data_payload:
            data_payload['search'] = {'value': '', 'regex': False}
        if 'indexcount' in data_payload:
            data_payload['indexcount'] = 2

        # 打印 data payload 概览
        _box_log(log, [
            f"URL: {JXCX_URL}",
            f"start: {data_payload.get('start')}",
            f"length: {data_payload.get('length')}",
            f"draw: {data_payload.get('draw')}",
            f"预期总数(count): {count}",
            f"geographicdimension: {data_payload.get('geographicdimension', 'N/A')}",
            f"timedimension: {data_payload.get('timedimension', 'N/A')}",
        ], title="[S5] Data 请求参数")

        # 编码
        encoded = encode_datatables_payload(data_payload)
        log.info("[S5] 编码后 payload 长度: %d 字符", len(encoded))

        # --- 发送请求 ---
        timeout = max(60, min(300, 30 + (count // 1000) * 60)) if count > 0 else 120
        t0 = time.time()

        res = query.sess.post(JXCX_URL, data=encoded, headers=HEADERS, timeout=timeout)
        elapsed = time.time() - t0

        # --- 响应诊断 ---
        _box_log(log, [
            f"HTTP 状态码: {res.status_code}",
            f"Content-Type: {res.headers.get('Content-Type', 'N/A')}",
            f"响应长度: {len(res.content)} 字节",
            f"耗时: {elapsed:.2f}秒 (超时={timeout}s)",
        ], title="[S5] 响应状态")

        if res.status_code != 200:
            steps['S5_http_code'] = res.status_code
            steps['diag_code'] = DiagnoseCode.DATA_API_FAILED
            steps['error'] = f"HTTP {res.status_code}"
            log.error("[S5] ✗ HTTP 状态码异常: %s", res.status_code)
            return None, steps

        if not res.content or len(res.content.strip()) == 0:
            steps['diag_code'] = DiagnoseCode.DATA_API_FAILED
            steps['error'] = "响应内容为空"
            log.error("[S5] ✗ 响应内容为空")
            return None, steps

        # JSON 解析
        try:
            result_data = json.loads(res.content)
        except json.JSONDecodeError as e:
            steps['diag_code'] = DiagnoseCode.DATA_API_FAILED
            steps['error'] = f"JSON解析失败: {e}"
            log.error("[S5] ✗ JSON解析失败: %s", e)
            log.error("[S5] 响应: %s", res.text[:500])
            return None, steps

        resp_keys = list(result_data.keys()) if isinstance(result_data, dict) else type(result_data).__name__
        log.info("[S5] 响应 keys: %s", resp_keys)
        log.info("[S5] 响应内容(前800字符): %s", str(result_data)[:800])

        # 检查错误消息
        if 'message' in result_data and result_data['message']:
            msg = str(result_data['message'])
            log.warning("[S5] 服务器消息: %s", msg)
            if '不存在' in msg:
                steps['diag_code'] = DiagnoseCode.DATA_API_FAILED
                steps['error'] = f"服务器错误: {msg}"
                log.error("[S5] ✗ 服务器返回错误: %s", msg)
                return None, steps

        # 提取数据列表
        data_list = result_data.get('data') or []
        if not data_list and isinstance(result_data, dict):
            for key in ['result', 'records', 'rows', 'dataList']:
                if key in result_data and result_data[key]:
                    data_list = result_data[key] if isinstance(result_data[key], list) else []
                    log.info("[S5] 从字段 '%s' 获取到 %d 条数据", key, len(data_list))
                    break

        log.info("[S5] 返回数据条数: %d", len(data_list))

        # 检测 count/Data 不一致（关键诊断点）
        records_filtered = result_data.get('recordsFiltered', 0)
        records_total = result_data.get('recordsTotal', 0)
        steps['S5_recordsFiltered'] = records_filtered
        steps['S5_recordsTotal'] = records_total

        if not data_list and (records_filtered > 0 or records_total > 0):
            # 重要：不一致！服务器说有数，但返回空数据
            steps['S5_rows'] = 0
            steps['S5_inconsistent'] = True
            steps['diag_code'] = DiagnoseCode.DATA_API_FAILED
            steps['error'] = (f"数据不一致: Count/Data冲突 "
                              f"| count={count} recordsFiltered={records_filtered} recordsTotal={records_total} "
                              f"| data=[](空)")
            log.error("")
            log.error("╔══════════════════════════════════════════════════════════════════════════════╗")
            log.error("║ [S5] ★★★ 数据不一致警告 ★★★                                   ║")
            log.error("╠══════════════════════════════════════════════════════════════════════════════╣")
            log.error("║ Count接口报告数据量: %s", count)
            log.error("║ Data接口 recordsFiltered: %s", records_filtered)
            log.error("║ Data接口 recordsTotal: %s", records_total)
            log.error("║ Data接口实际返回 data: [] (空)                                       ║")
            log.error("╠══════════════════════════════════════════════════════════════════════════════╣")
            log.error("║ 可能原因:                                                            ║")
            log.error("║   1. 日期范围问题: 周粒度报表需7天以上，单日查询无数据              ║")
            log.error("║   2. Count缓存: Count和Data接口数据源不一致                        ║")
            log.error("║   3. 权限/地市问题: 部分数据需要更高权限                           ║")
            log.error("╚══════════════════════════════════════════════════════════════════════════════╝")
            return [], steps

        if not data_list:
            steps['S5_rows'] = 0
            steps['S5_inconsistent'] = False
            steps['diag_code'] = DiagnoseCode.DATA_API_FAILED
            steps['error'] = "API 返回数据为空（可能日期范围内无数据）"
            log.warning("[S5] ⚠ 返回数据为空")
            return [], steps

        # 字段映射诊断
        first_row_keys = list(data_list[0].keys())[:10]
        steps['S5_rows'] = len(data_list)
        steps['S5_sample_keys'] = first_row_keys
        steps['diag_code'] = DiagnoseCode.SUCCESS

        # 尝试中文字段映射
        en_zh_df = query._get_field_mapping(payload)
        if not en_zh_df.empty:
            log.info("[S5] ✓ 字段映射存在，共 %d 个中文字段", len(en_zh_df.columns))
            steps['S5_field_mapping'] = True
            steps['S5_field_mapping_count'] = len(en_zh_df.columns)
        else:
            log.warning("[S5] ⚠ 字段映射为空（返回英文字段名）")
            steps['S5_field_mapping'] = False

        sample_fields = ', '.join(f"{k}={str(v)[:20]}" for k, v in list(data_list[0].items())[:5])
        log.info("[S5] ✓ Data 查询成功 | 返回 %d 条 | 样本: %s", len(data_list), sample_fields)

        return data_list, steps

    except Exception as e:
        steps['diag_code'] = DiagnoseCode.DATA_API_FAILED
        steps['error'] = str(e)
        log.error("[S5] ✗ Data 查询异常: %s", e)
        log.debug(traceback.format_exc())
        return None, steps


# ========== 根因分析与修复建议 ==========

def analyze_root_cause(table_name, steps):
    """根据诊断阶段结果推断根因并给出修复建议"""
    code = steps.get('diag_code', '?')
    err = steps.get('error', '')

    suggestions = []
    root_cause = ""

    if code == DiagnoseCode.PAYLOAD_BUILD_FAILED:
        root_cause = "字段配置 API (adhocquery/search 或 adhocquery/getSelectTable) 返回空配置"
        suggestions = [
            f"1. 确认报表 '{table_name}' 在大数据平台中确实存在且已发布",
            "2. 尝试手动在浏览器中打开该报表，记录正确的报表关键字（table_key）",
            "3. 检查 fieldtype 参数是否与数据库中的 fieldtype 匹配",
            f"4. 当前错误: {err}",
        ]
    elif code == DiagnoseCode.COUNT_API_FAILED:
        if 'JSON' in err:
            root_cause = "Count API 返回了非 JSON 格式的响应，可能是服务器内部错误"
            suggestions = [
                "1. 检查请求中的 result/where 参数格式是否正确",
                "2. 尝试缩短日期范围（单日查询）",
                "3. 确认 city 参数（地市名称）与数据库中的 city 字段值一致",
                f"4. 当前错误: {err}",
            ]
        elif '空' in err or 'empty' in err.lower():
            root_cause = "Count API 响应为空，可能是 Session 过期"
            suggestions = [
                "1. Session 可能已过期，尝试重新登录",
                "2. 检查 CASTGC / JSESSIONID cookie 是否仍然有效",
                "3. 确认 JXCX 模块是否已成功进入",
                f"4. 当前错误: {err}",
            ]
        else:
            root_cause = f"Count API 调用失败，HTTP 响应异常或服务器报错"
            suggestions = [
                "1. 检查网络连接是否稳定",
                "2. 尝试重新进入 JXCX 模块",
                "3. 减少查询的日期范围",
                f"4. 当前错误: {err}",
            ]
    elif code == DiagnoseCode.DATA_API_FAILED:
        if '不一致' in err or 'inconsistent' in err.lower() or 'Count/Data' in err or '冲突' in err:
            root_cause = "Count接口与Data接口数据不一致！服务器知道有数据但返回空（周粒度单日查询最常见）"
            suggestions = [
                "1. 【最可能】日期范围不足：周粒度报表需至少7天，当前仅1天，请将结束日期延长到开始日期+7天",
                "2. 确认该报表确实是周粒度，不是天粒度",
                "3. 尝试将日期范围设为整周（如 2026-05-01 ~ 2026-05-07）",
                f"4. 当前错误: {err}",
            ]
        elif '超' in err or 'timeout' in err.lower() or 'Timeout' in err:
            root_cause = "Data API 请求超时，可能数据量过大"
            suggestions = [
                "1. 减少查询日期范围或地市范围",
                "2. 在 GUI 中先测试小批量数据提取",
                "3. 检查服务器负载情况",
                f"4. 当前错误: {err}",
            ]
        elif 'JSON' in err:
            root_cause = "Data API 返回了非 JSON 格式响应"
            suggestions = [
                "1. Payload 参数可能不完整，检查 result 字段配置",
                "2. 尝试在浏览器中手动导出该报表对比请求参数",
                f"3. 当前错误: {err}",
            ]
        else:
            root_cause = f"Data API 返回空数据（日期范围内确实无数据，或请求参数不匹配）"
            suggestions = [
                "1. 确认日期范围内该地市确实有数据",
                "2. 检查 city 字段名称是否与数据库一致（如 '阳江' vs 'Yangjiang'）",
                "3. 对于周粒度报表，确认日期范围至少包含7天",
                f"4. 当前错误: {err}",
            ]
    elif code == DiagnoseCode.FIELD_MAPPING_FAILED:
        root_cause = "中文字段映射失败，返回数据没有字段名或结构异常"
        suggestions = [
            "1. 报表 API 返回的数据结构与预期不一致",
            "2. 尝试在 GUI 中手动导出查看实际返回字段",
            "3. 检查 result 参数中的 feildName 字段是否正确",
        ]
    elif code == DiagnoseCode.AUTH_FAILED:
        root_cause = "登录失败，无法获取有效的认证 Cookie"
        suggestions = [
            "1. 检查用户名/密码是否正确",
            "2. 确认手机号可以收到短信验证码",
            "3. 检查网络能否访问大数据平台登录页面",
        ]
    elif code == DiagnoseCode.JXCX_ENTRY_FAILED:
        root_cause = "无法进入即席查询模块（JXCX），Session 状态异常"
        suggestions = [
            "1. 尝试重新登录",
            "2. 清除浏览器缓存后重新登录",
            "3. 确认账号有访问 JXCX 模块的权限",
        ]
    elif code == DiagnoseCode.SUCCESS:
        root_cause = "全流程成功，无问题"
        suggestions = ["报表提取功能正常，无需修复。"]

    return root_cause, suggestions


# ========== 单报表测试（6阶段诊断） ==========

_progress_lock = threading.Lock()
_output_lock = threading.Lock()
_progress = {'completed': 0, 'total': 0}


def test_single_table(table_name, payload_func, start_date, end_date, city, limit,
                     query_class, session):
    """对单个报表执行6阶段诊断"""
    thread_name = threading.current_thread().name

    log = logger

    log.info("")
    log.info(f"{'═' * 72}")
    log.info(f"▶ 开始诊断: {table_name} ({thread_name})")
    log.info(f"{'═' * 72}")

    result = {
        'name': table_name,
        'diag_code': '?',
        'error': None,
        'time_cost': 0,
        'steps': {},
    }

    t0 = time.time()
    query = query_class(session)

    # --- S3: Payload 构建 ---
    payload, s3_steps = diagnose_build_payload(
        query, table_name, payload_func, start_date, end_date, city
    )
    result['steps']['S3'] = s3_steps

    if payload is None:
        diag_code = s3_steps.get('diag_code', DiagnoseCode.PAYLOAD_BUILD_FAILED)
        result['diag_code'] = diag_code
        result['error'] = s3_steps.get('error', 'Payload 构建失败')
        root_cause, suggestions = analyze_root_cause(table_name, s3_steps)
        result['root_cause'] = root_cause
        result['suggestions'] = suggestions
        result['time_cost'] = round(time.time() - t0, 2)
        _update_progress(result, table_name)
        return result

    # --- S4: Count 查询 ---
    count, s4_steps = diagnose_count(query, payload, table_name)
    result['steps']['S4'] = s4_steps
    result['steps']['S4_count'] = count

    if s4_steps.get('diag_code') != DiagnoseCode.SUCCESS:
        diag_code = s4_steps.get('diag_code', DiagnoseCode.COUNT_API_FAILED)
        result['diag_code'] = diag_code
        result['error'] = s4_steps.get('error', 'Count 查询失败')
        root_cause, suggestions = analyze_root_cause(table_name, s4_steps)
        result['root_cause'] = root_cause
        result['suggestions'] = suggestions
        result['time_cost'] = round(time.time() - t0, 2)
        _update_progress(result, table_name)
        return result

    # --- S5: Data 查询 ---
    data_list, s5_steps = diagnose_data(query, payload, table_name, limit, count)
    result['steps']['S5'] = s5_steps
    result['steps']['S5_rows'] = s5_steps.get('S5_rows', 0)

    if s5_steps.get('diag_code') != DiagnoseCode.SUCCESS:
        diag_code = s5_steps.get('diag_code', DiagnoseCode.DATA_API_FAILED)
        result['diag_code'] = diag_code
        result['error'] = s5_steps.get('error', 'Data 查询失败')
        root_cause, suggestions = analyze_root_cause(table_name, s5_steps)
        result['root_cause'] = root_cause
        result['suggestions'] = suggestions
        result['time_cost'] = round(time.time() - t0, 2)
        _update_progress(result, table_name)
        return result

    # 全流程成功
    result['diag_code'] = DiagnoseCode.SUCCESS
    result['error'] = None
    result['root_cause'] = "全流程成功"
    result['suggestions'] = ["报表提取功能正常。"]
    result['time_cost'] = round(time.time() - t0, 2)
    _update_progress(result, table_name)
    return result


def _update_progress(result, table_name):
    with _progress_lock:
        _progress['completed'] += 1
        done = _progress['completed']
        total = _progress['total']
        code = result['diag_code']
        status = "✓" if code == DiagnoseCode.SUCCESS else "✗"
        t = result['time_cost']
        with _output_lock:
            print(f"\r  进度: {done}/{total} | {status} {table_name} ({t:.1f}s)    ", end='', flush=True)


# ========== 并行执行 ==========

def run_parallel_tests(selected_tables, start_date, end_date, city, limit,
                       max_workers, query_class, session):
    total = len(selected_tables)
    _progress['completed'] = 0
    _progress['total'] = total

    logger.info(f"\n{'=' * 72}")
    logger.info(f"  开始并发诊断 | 报表: {total} 个 | 线程: {max_workers} 个")
    logger.info(f"{'=' * 72}")

    results = []

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='Diag') as executor:
        futures = {
            executor.submit(
                test_single_table,
                name, func, start_date, end_date, city, limit,
                query_class, session
            ): name
            for name, func in selected_tables
        }

        for future in as_completed(futures):
            table_name = futures[future]
            try:
                r = future.result()
                results.append(r)
            except Exception as e:
                logger.error("线程执行异常: %s - %s", table_name, e)
                results.append({
                    'name': table_name,
                    'diag_code': '?',
                    'error': str(e),
                    'time_cost': 0,
                    'steps': {},
                    'root_cause': "线程执行异常",
                    'suggestions': ["检查脚本日志获取详细信息"],
                })

    print()
    return results


# ========== 诊断报告输出 ==========

def generate_diagnostic_report(results, log_file):
    """生成结构化 JSON 诊断报告"""
    summary = {
        'run_id': _run_id,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total': len(results),
        'passed': sum(1 for r in results if r['diag_code'] == DiagnoseCode.SUCCESS),
        'failed': sum(1 for r in results if r['diag_code'] != DiagnoseCode.SUCCESS),
        'by_diag_code': {},
        'failed_tables': [],
        'all_results': [],
    }

    for r in results:
        code = r['diag_code']
        summary['by_diag_code'][code] = summary['by_diag_code'].get(code, 0) + 1
        if code != DiagnoseCode.SUCCESS:
            summary['failed_tables'].append({
                'name': r['name'],
                'diag_code': code,
                'error': r.get('error', ''),
                'root_cause': r.get('root_cause', ''),
                'suggestions': r.get('suggestions', []),
                'time_cost': r['time_cost'],
            })
        # 存储所有结果（截断大字段）
        short_r = dict(r)
        if 'steps' in short_r:
            short_r['steps'] = {k: _trunc(str(v), 200) for k, v in short_r['steps'].items()}
        summary['all_results'].append(short_r)

    with open(diag_json_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════════════════╗")
    logger.info("║                    诊断报告已生成                                      ║")
    logger.info("╠══════════════════════════════════════════════════════════════════════╣")
    logger.info("║ JSON报告: %s", diag_json_file)
    logger.info("║ 详细日志: %s", log_file)
    logger.info("╚══════════════════════════════════════════════════════════════════════╝")

    return summary


def print_summary_report(results):
    """打印控制台总结报告"""
    total = len(results)
    passed = sum(1 for r in results if r['diag_code'] == DiagnoseCode.SUCCESS)
    failed = sum(1 for r in results if r['diag_code'] != DiagnoseCode.SUCCESS)

    print(f"\n{'═' * 72}")
    print(f"                    诊断总结报告")
    print(f"{'═' * 72}")
    print(f"  总计: {total} 个报表 | ✓ 通过: {passed} | ✗ 失败: {failed}")
    print(f"{'─' * 72}")

    # 按问题类型分组
    by_code = {}
    for r in results:
        code = r['diag_code']
        by_code.setdefault(code, []).append(r)

    # 先打印失败的
    for code, items in by_code.items():
        if code == DiagnoseCode.SUCCESS:
            continue
        print(f"\n  【{code}】 ({len(items)} 个)")
        print(f"  {'─' * 60}")
        for r in items:
            name = r['name']
            err = _trunc(r.get('error', ''), 40)
            root = _trunc(r.get('root_cause', ''), 50)
            print(f"    ✗ {name}")
            print(f"      错误: {err}")
            print(f"      根因: {root}")
            if r.get('suggestions'):
                for s in r['suggestions'][:3]:
                    print(f"      {s}")

    # 打印成功的
    if DiagnoseCode.SUCCESS in by_code:
        print(f"\n  【SUCCESS】 ({len(by_code[DiagnoseCode.SUCCESS])} 个)")
        print(f"  {'─' * 60}")
        for r in by_code[DiagnoseCode.SUCCESS]:
            count = r['steps'].get('S4_count', 0)
            rows = r['steps'].get('S5_rows', 0)
            print(f"    ✓ {r['name']} | count={count} rows={rows}")

    print(f"\n{'─' * 72}")
    print(f"  诊断报告: {diag_json_file}")
    print(f"  详细日志: {log_file}")
    print(f"{'═' * 72}")


# ========== 主函数 ==========

def main():
    print_banner()

    logger.info("=" * 60)
    logger.info("NQI 数据提取问题定界分析工具启动")
    logger.info("=" * 60)

    # S0: 环境检查
    env_ok, env_steps = diagnose_env()
    if not env_ok:
        logger.error("环境检查失败，退出")
        sys.exit(1)

    # 读取报表配置
    table_configs = get_table_configs()
    if not table_configs:
        logger.error("无法读取报表配置，退出")
        sys.exit(1)
    category_mapping = get_category_mapping()

    # S1: 登录
    username, password = get_credentials()
    if not username:
        logger.error("未提供用户名，退出")
        sys.exit(1)

    session, login_steps = diagnose_login(username, password)
    if not session:
        logger.error("登录失败，退出")
        sys.exit(1)

    # 选择报表
    index_map = print_table_menu(table_configs, category_mapping)
    selected = get_user_selection(index_map)
    if not selected:
        print("\n  再见！")
        sys.exit(0)

    # 获取测试参数
    start_date, end_date, city, limit, max_workers = get_test_params()

    logger.info(f"测试参数: {start_date} ~ {end_date} | 地市: {city} | 条数: {limit} | 并发: {max_workers}")
    logger.info(f"选中报表: {len(selected)} 个")

    # S2: 进入即席查询（共享一次，不在每个报表中重复做）
    from core.query import JXCXQuery
    query = JXCXQuery(session)
    enter_ok, enter_steps = diagnose_enter_jxcx(query)

    if not enter_ok:
        logger.warning("⚠ 进入即席查询失败，报表诊断中将自动重试")
        # 不退出，继续让各报表在 test_single_table 中各自尝试 enter_jxcx

    # 合并环境/登录/入口的共同 steps 到每个报表结果中
    shared_env_steps = env_steps
    shared_login_steps = login_steps
    shared_enter_steps = enter_steps

    # 并发诊断
    t_start = time.time()
    results = run_parallel_tests(
        selected, start_date, end_date, city, limit, max_workers,
        JXCXQuery, session
    )
    t_total = round(time.time() - t_start, 2)

    # 将共同阶段注入到每个结果
    for r in results:
        r['steps']['S0'] = shared_env_steps
        r['steps']['S1'] = shared_login_steps
        r['steps']['S2'] = shared_enter_steps

    # 生成 JSON 报告
    summary = generate_diagnostic_report(results, log_file)

    # 打印控制台总结
    print_summary_report(results)

    logger.info(f"总耗时: {t_total}s (并发 {max_workers} 线程)")


if __name__ == '__main__':
    main()
