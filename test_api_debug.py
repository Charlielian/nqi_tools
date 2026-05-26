# -*- coding: utf-8 -*-
"""
诊断脚本：模拟正式代码提取"45G流量与热点评估物理站"报表的完整流程
在离线机器上运行此脚本，将输出复制回给开发者分析

使用方法：
    python test_api_debug.py
"""
import json
import os
import sys
import requests
import http.cookiejar
import traceback
import urllib3
import datetime
import random
import time
from urllib.parse import quote

urllib3.disable_warnings()

# 配置
BASE_URL = 'https://nqi.gmcc.net:20443'
JXCX_COUNT_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getTableCount'
JXCX_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getTable'

# 目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, 'logs')
COOKIE_DIR = os.path.join(SCRIPT_DIR, 'cookies')
LOG_FILE = os.path.join(LOG_DIR, f'test_api_debug_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# 默认用户名
DEFAULT_USERNAME = 'lianchunliang'

# Headers（与正式代码一致）
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Origin': BASE_URL,
    'Referer': f'{BASE_URL}/pro-adhoc/',
}

# 日志级别
LOG_LEVEL_DEBUG = True


class TeeOutput:
    """同时输出到控制台和文件"""
    def __init__(self, filename):
        self.terminal = sys.stdout
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.file = open(filename, 'w', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.file.write(message)

    def flush(self):
        self.terminal.flush()
        self.file.flush()

    def close(self):
        self.file.close()


def log(msg, level="INFO"):
    """打印日志"""
    timestamp = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
    prefix = {
        "INFO": "[INFO]",
        "DEBUG": "[DEBUG]",
        "ERROR": "[ERROR]",
        "WARN": "[WARN]",
        "SUCCESS": "[OK]",
    }.get(level, "[INFO]")
    print(f"{timestamp} {prefix} {msg}")


def log_section(title):
    """打印分节标题"""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


class HttpCookieEncoder:
    """Cookie序列化编码器 - 与正式代码完全一致"""
    @staticmethod
    def decode(json_str, cookie_jar=None):
        """从JSON字符串解码为CookieJar"""
        from requests.cookies import RequestsCookieJar
        if cookie_jar is None:
            cookie_jar = RequestsCookieJar()

        try:
            cookies_data = json.loads(json_str)
            for cookie_dict in cookies_data:
                cookie = http.cookiejar.Cookie(
                    version=0,
                    name=cookie_dict.get('name', ''),
                    value=cookie_dict.get('value', ''),
                    port=None,
                    port_specified=False,
                    domain=cookie_dict.get('domain', ''),
                    domain_specified=bool(cookie_dict.get('domain')),
                    domain_initial_dot=False,
                    path=cookie_dict.get('path', '/'),
                    path_specified=bool(cookie_dict.get('path')),
                    secure=cookie_dict.get('secure', False),
                    expires=cookie_dict.get('expires'),
                    discard=True,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False
                )
                cookie_jar.set_cookie(cookie)
            return cookie_jar
        except Exception as e:
            log(f"Cookie解码失败: {e}", "ERROR")
            return cookie_jar


def load_cookie(username):
    """从文件加载cookie（与正式代码一致）"""
    from requests.cookies import RequestsCookieJar

    # 先尝试新格式 JSON (username.json)
    json_filepath = os.path.join(COOKIE_DIR, f'{username}.json')
    if os.path.exists(json_filepath):
        try:
            with open(json_filepath, 'r', encoding='utf-8') as f:
                json_str = f.read()
            log(f"从 {username}.json 加载Cookie", "INFO")
            return HttpCookieEncoder.decode(json_str)
        except Exception as e:
            log(f"加载{username}.json失败: {e}", "WARN")

    # 兼容旧格式 nqi_cookies.json
    old_filepath = os.path.join(COOKIE_DIR, 'nqi_cookies.json')
    if os.path.exists(old_filepath):
        try:
            with open(old_filepath, 'r', encoding='utf-8') as f:
                json_str = f.read()
            log(f"从 nqi_cookies.json 加载Cookie", "INFO")
            return HttpCookieEncoder.decode(json_str)
        except Exception as e:
            log(f"加载nqi_cookies.json失败: {e}", "WARN")

    return None


def print_cookie_details(cookie_jar, title="Cookie详情"):
    """打印Cookie详情"""
    log(f"{title}: {len(cookie_jar)} 个Cookie", "DEBUG")
    for i, cookie in enumerate(cookie_jar):
        domain_info = f", domain={cookie.domain}" if cookie.domain else ""
        log(f"  [{i}] {cookie.name}={cookie.value[:40]}...{domain_info}", "DEBUG")


def encode_payload(payload):
    """URL编码payload - 与正式代码一致"""
    out_list = []
    for key in payload:
        if key == 'columns':
            if isinstance(payload[key], str):
                out_list.append(quote(key) + '=' + quote(payload[key]))
                continue
            elif not isinstance(payload[key], list):
                out_list.append(quote(key) + '=' + quote(str(payload[key])))
                continue
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
            order_parts = []
            for i, ord_item in enumerate(payload[key]):
                for sub_key, sub_val in ord_item.items():
                    order_parts.append(f'order[{i}][{sub_key}]={quote(str(sub_val))}')
            out_list.append('&'.join(order_parts))
        elif key == 'search':
            search_parts = []
            for sub_key, sub_val in payload[key].items():
                search_parts.append(f'search[{sub_key}]={quote(str(sub_val))}')
            out_list.append('&'.join(search_parts))
        elif key in ['result', 'where']:
            json_str = json.dumps(payload[key], ensure_ascii=False, separators=(',', ':'))
            out_list.append(quote(key) + '=' + quote(json_str))
        elif isinstance(payload[key], int):
            out_list.append(quote(key) + '=' + str(payload[key]))
        else:
            out_list.append(quote(key) + '=' + quote(str(payload[key]) if payload[key] is not None else ''))
    return '&'.join(out_list)


class JxcxSimulator:
    """模拟正式代码的JxcxQuery类"""

    def __init__(self, session):
        self.sess = session
        self.enabled = False

    def enter_jxcx(self, retry_times=3, timeout=60):
        """进入即席查询模块 - 与正式代码一致"""
        log_section("Step 1: 进入即席查询模块 (enter_jxcx)")

        for attempt in range(retry_times):
            if attempt > 0:
                log(f"重试第 {attempt + 1} 次...", "WARN")

            # 获取CASTGC token
            castgc = self.sess.cookies.get('CASTGC', domain='nqi.gmcc.net')
            if not castgc:
                castgc = self.sess.cookies.get('CASTGC')

            if not castgc:
                log("未找到CASTGC cookie", "ERROR")
                return False

            log(f"CASTGC获取成功: {castgc[:30]}...", "DEBUG")

            # 构建请求URL
            url = f'{BASE_URL}/pro-portal/pure/urlAction.action'
            params = {
                'url': 'pro-adhoc/index',
                'random': random.random(),
                '__PID': 'JXCX',
                'token': castgc
            }
            url_with_params = f"{url}?url={params['url']}&__PID={params['__PID']}&random={params['random']}&token={params['token']}"

            log(f"请求URL: {url_with_params[:150]}...", "DEBUG")

            try:
                start_time = time.time()
                res = self.sess.get(url_with_params, headers=HEADERS, timeout=timeout)
                elapsed_time = time.time() - start_time

                log(f"响应状态码: {res.status_code}, 耗时: {elapsed_time:.2f}秒", "INFO")
                log(f"响应头 Content-Type: {res.headers.get('Content-Type', 'N/A')}", "DEBUG")
                log(f"响应长度: {len(res.content)} 字节", "DEBUG")

                if res.status_code == 200:
                    self.enabled = True
                    log("即席查询模块初始化成功!", "SUCCESS")
                    print_cookie_details(self.sess.cookies, "Session Cookie")
                    return True
                else:
                    log(f"进入即席查询失败，状态码: {res.status_code}", "ERROR")

            except requests.exceptions.Timeout:
                log(f"请求超时 (timeout={timeout}s)", "ERROR")
            except requests.exceptions.ConnectionError as e:
                log(f"网络连接错误: {e}", "ERROR")
            except Exception as e:
                log(f"请求异常: {e}", "ERROR")
                traceback.print_exc()

        log("进入即席查询模块失败", "ERROR")
        return False

    def get_table_count(self, payload, report_name="未知报表"):
        """获取数据总数 - 与正式代码一致"""
        log_section(f"Step 2: 获取数据总数 (get_table_count) - {report_name}")

        if not self.enabled:
            log("JXCX未启用，尝试进入...", "WARN")
            if not self.enter_jxcx():
                log("无法进入即席查询模块", "ERROR")
                return 0

        # getTableCount请求需要的参数
        key_list = ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                    'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount',
                    'columns', 'order', 'search']
        payload_count = {key: value for key, value in payload.items() if key in key_list}
        payload_encoded = encode_payload(payload_count)

        # 诊断Session状态
        log("[Session状态诊断]", "INFO")
        castgc = self.sess.cookies.get('CASTGC', domain='nqi.gmcc.net')
        if not castgc:
            castgc = self.sess.cookies.get('CASTGC')
        log(f"  CASTGC cookie: {'存在' if castgc else '不存在!'}", "INFO" if castgc else "ERROR")

        # 处理多个JSESSIONID的情况
        jsessionids = [c for c in self.sess.cookies if c.name == 'JSESSIONID']
        if jsessionids:
            # 使用第一个有效的JSESSIONID
            jsessionid = jsessionids[0].value
            log(f"  JSESSIONID cookie: 存在 (共{len(jsessionids)}个，使用第1个)", "INFO")
        else:
            jsessionid = None
            log(f"  JSESSIONID cookie: 不存在!", "ERROR")

        # 打印请求头
        log("[请求Headers]", "DEBUG")
        for key in ['User-Agent', 'Content-Type']:
            if key in HEADERS:
                log(f"  {key}: {HEADERS[key]}", "DEBUG")

        # 打印Cookie
        cookie_str = '; '.join([f"{c.name}={c.value[:20]}..." if len(c.value) > 20 else f"{c.name}={c.value}"
                               for c in self.sess.cookies])
        log(f"  Cookie: {cookie_str[:200]}", "DEBUG")

        # 打印payload参数
        log("[筛选后的payload参数]", "DEBUG")
        for k, v in payload_count.items():
            if k == 'result':
                log(f"  {k}: (JSON, 长度={len(json.dumps(v))}字符)", "DEBUG")
            elif k == 'where':
                log(f"  {k}: {json.dumps(v)[:200]}", "DEBUG")
            elif k == 'columns':
                log(f"  {k}: (列表, {len(v) if isinstance(v, list) else 0}项)", "DEBUG")
            else:
                log(f"  {k}: {v}", "DEBUG")

        log(f"[编码后的请求体] (长度={len(payload_encoded)}字符)", "DEBUG")
        log(f"  {payload_encoded[:300]}...", "DEBUG")

        # 发送请求
        log("[发送getTableCount请求... (最多等待180秒)]", "INFO")

        # 诊断：打印所有Cookie
        log("[诊断] 所有Cookie详情:", "DEBUG")
        for cookie in self.sess.cookies:
            log(f"  {cookie.name} = {cookie.value[:40]}... (domain={cookie.domain})", "DEBUG")

        import sys as sys_module
        sys_module.stdout.flush()  # 确保日志输出

        try:
            start_time = time.time()
            res = self.sess.post(JXCX_COUNT_URL, data=payload_encoded, headers=HEADERS, timeout=180)  # 使用180秒超时
            elapsed_time = time.time() - start_time

            log(f"HTTP状态码: {res.status_code}, 耗时: {elapsed_time:.2f}秒", "INFO")
            log(f"响应头 Content-Type: {res.headers.get('Content-Type', 'N/A')}", "DEBUG")
            log(f"响应长度: {len(res.content)} 字节", "DEBUG")

            if res.status_code != 200:
                log(f"HTTP状态码异常: {res.status_code}", "ERROR")
                self.enabled = False
                return 0

            if not res.content or len(res.content.strip()) == 0:
                log("响应内容为空，可能是Session过期", "ERROR")
                self.enabled = False
                return 0

            # 检查Content-Type
            content_type = res.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                log(f"响应不是JSON格式! Content-Type: {content_type}", "ERROR")
                log(f"响应内容前500字符: {res.text[:500]}", "ERROR")
                self.enabled = False
                return 0

            try:
                result = json.loads(res.content)
                log(f"JSON解析成功, keys: {list(result.keys())}", "DEBUG")

                if 'count' in result:
                    count = result['count']
                    log(f"数据总数: {count}", "SUCCESS")
                    return count
                else:
                    log(f"响应中没有count字段: {result}", "WARN")
                    return 0

            except json.JSONDecodeError as e:
                log(f"JSON解析失败: {e}", "ERROR")
                log(f"响应内容前500字符: {res.text[:500]}", "ERROR")
                self.enabled = False
                return 0

        except requests.exceptions.Timeout:
            log("请求超时! 服务器在180秒内没有响应", "ERROR")
            log("可能原因：1) 服务器负载高 2) 查询数据量大 3) 网络问题 4) Session无效", "WARN")
            log("建议：请尝试重新登录获取新的Cookie", "INFO")
            self.enabled = False
            return 0
        except requests.exceptions.ConnectionError as e:
            log(f"网络连接错误: {e}", "ERROR")
            self.enabled = False
            return 0
        except Exception as e:
            log(f"请求异常: {e}", "ERROR")
            traceback.print_exc()
            self.enabled = False
            return 0

    def fetch_data(self, payload, timeout=300):
        """获取实际数据 - 与正式代码一致"""
        log_section("Step 3: 获取实际数据 (_fetch_data)")

        if not self.enabled:
            log("JXCX未启用", "ERROR")
            return []

        # 编码payload
        payload_encoded = encode_payload(payload)

        log(f"请求URL: {JXCX_URL}", "INFO")
        log(f"编码后Payload长度: {len(payload_encoded)} 字符", "DEBUG")

        # 显示关键参数
        log("[关键参数]", "DEBUG")
        for key in ['start', 'length', 'geographicdimension', 'timedimension']:
            if key in payload:
                log(f"  {key}: {payload[key]}", "DEBUG")

        try:
            start_time = time.time()
            res = self.sess.post(JXCX_URL, data=payload_encoded, headers=HEADERS, timeout=timeout)
            elapsed_time = time.time() - start_time

            log(f"HTTP状态码: {res.status_code}, 耗时: {elapsed_time:.2f}秒", "INFO")
            log(f"响应头 Content-Type: {res.headers.get('Content-Type', 'N/A')}", "DEBUG")
            log(f"响应长度: {len(res.content)} 字节", "DEBUG")

            if res.status_code != 200:
                log(f"HTTP状态码异常: {res.status_code}", "ERROR")
                self.enabled = False
                return []

            if not res.content or len(res.content.strip()) == 0:
                log("响应内容为空，可能是Session过期", "ERROR")
                self.enabled = False
                return []

            # 检查Content-Type
            content_type = res.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                log(f"响应不是JSON格式! Content-Type: {content_type}", "ERROR")
                log(f"响应内容前500字符: {res.text[:500]}", "ERROR")
                self.enabled = False
                return []

            try:
                result = json.loads(res.content)
                log(f"JSON解析成功, keys: {list(result.keys())}", "DEBUG")

                # 获取数据列表
                data_list = result.get('data') or []
                if not data_list and isinstance(result, dict):
                    for key in ['result', 'records', 'rows', 'dataList']:
                        if key in result and result[key]:
                            data_list = result[key] if isinstance(result[key], list) else []
                            log(f"使用备用字段 '{key}' 获取到 {len(data_list)} 条数据", "DEBUG")
                            break

                log(f"返回数据条数: {len(data_list)}", "SUCCESS")

                if not data_list:
                    log("数据为空", "WARN")

                return data_list

            except json.JSONDecodeError as e:
                log(f"JSON解析失败: {e}", "ERROR")
                log(f"响应内容前500字符: {res.text[:500]}", "ERROR")
                self.enabled = False
                return []

        except Exception as e:
            log(f"请求异常: {e}", "ERROR")
            traceback.print_exc()
            self.enabled = False
            return []


def build_payload():
    """构建45G流量与热点评估物理站级报表的payload
    
    注意：根据HAR文件分析，前3个字段(starttime, endtime, city)的datatype应为"1"，
    而非"character varying"。supportedtimedimension应为"1"而非空字符串。
    """
    # 字段列表（与正式代码一致）
    fields = [
        ('starttime', '开始时间'), ('endtime', '结束时间'), ('city', '地市'),
        ('station_name', '物理站名称'), ('station_id', '物理站ID'), ('cover_type', '覆盖类型'),
        ('gnodeb_count', '5G逻辑站数量'), ('enodeb_count', '4G逻辑站数量'),
        ('nr_cell_count', '5G小区数量'), ('lte_cell_count', '4G小区数量'),
        ('lte_e_site_list', 'E频站点名列表'), ('lte_d_site_list', 'D频站点名列表'),
        ('lte_f_site_list', 'F频站点名列表'), ('lte_fdd1800_site_list', 'FDD1800站点名列表'),
        ('lte_fdd900_site_list', 'FDD900站点名列表'), ('lte_reverse_site_list', '反向4G站点名列表'),
        ('other_lte_site_list', '其它4G站点列表'), ('nr_2600_site_list', '2.6G站点名列表'),
        ('nr_700_site_list', '700M站点名列表'), ('nr_4900_site_list', '4.9G站点名列表'),
        ('other_nr_site_list', '其它5G站点列表'),
        ('flow_bh_lte_upoctudl', '流量忙时4G流量'), ('flow_bh_nr_upoctudl', '流量忙时5G流量'),
        ('flow_bh_total_upoctudl', '流量忙时45G总流量'), ('flow_bh_nr_upoctudl_rate', '流量忙时5G流量占比'),
        ('flow_bh_lte_connmean', '流量忙时4G RRC连接平均数'), ('flow_bh_lte_connmax', '流量忙时4G RRC连接最大数'),
        ('flow_bh_nr_connmean', '流量忙时5G RRC连接平均数'), ('flow_bh_nr_connmax', '流量忙时5G RRC连接最大数'),
        ('flow_bh_lte_use_rate', '流量忙时4G利用率'), ('lte_hot_level', '流量忙时4G热点等级'),
        ('lte_upoctudl', '4G日流量'), ('nr_upoctudl', '5G日流量'),
        ('total_upoctudl', '45G日总流量'), ('nr_upoctudl_rate', '5G日流量占比'),
    ]

    result_list = []
    for i, (field, name) in enumerate(fields):
        # 前3个字段(starttime, endtime, city)的datatype应为"1"，与浏览器请求一致
        if i < 3:
            datatype = '1'
        else:
            datatype = 'character varying'
        result_list.append({
            'feildtype': '45G流量与热点评估物理站级',
            'table': 'appdbv3.a_cap_ltenr_station',
            'tableName': '45G流量与热点评估物理站级',
            'datatype': datatype,
            'columntype': '1',
            'feildName': name,
            'feild': field,
            'poly': '无',
            'anyWay': '无',
            'chart': '无',
            'chartpoly': '无'
        })

    payload = {
        'draw': 1, 'start': 0, 'length': 200, 'total': 0,
        'geographicdimension': '小区',
        'timedimension': '天、周',
        'enodebField': 'gnodeb_id',
        'cgiField': 'cgi',
        'timeField': 'starttime',
        'cellField': 'cell',
        'cityField': 'city',
        'columns': [
            {'data': f, 'name': '', 'searchable': True, 'orderable': True, 'search': {'value': '', 'regex': False}}
            for f, _ in fields
        ],
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {
            'result': result_list,
            'tableParams': {'supporteddimension': None, 'supportedtimedimension': '1'},  # 修复: 改为"1"
            'columnname': ''
        },
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': '2026-05-07 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': '2026-05-07 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': '阳江', 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }

    return payload


def main():
    """主函数"""
    # 重定向输出到控制台和日志文件
    tee = TeeOutput(LOG_FILE)
    original_stdout = sys.stdout
    sys.stdout = tee

    try:
        log_section("45G流量与热点评估物理站级 - 完整流程诊断")
        log(f"测试时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        log(f"Python版本: {sys.version}", "INFO")
        log(f"工作目录: {os.getcwd()}", "INFO")
        log(f"日志文件: {LOG_FILE}", "INFO")

        # 步骤0: 加载Cookie
        log_section("Step 0: 加载Cookie")
        log(f"Cookie目录: {COOKIE_DIR}", "INFO")
        log(f"用户名: {DEFAULT_USERNAME}", "INFO")

        cookie_jar = load_cookie(DEFAULT_USERNAME)
        if cookie_jar is None:
            log("无法加载Cookie文件", "ERROR")
            return

        print_cookie_details(cookie_jar, "加载的Cookie")

        # 步骤1: 创建Session
        log_section("Step 1: 创建Session并加载Cookie")
        session = requests.Session()
        session.verify = False
        session.cookies = cookie_jar

        print_cookie_details(session.cookies, "Session Cookie (加载后)")

        # 步骤2: 创建模拟器并执行查询
        jxcx = JxcxSimulator(session)

        # Step 1: 进入即席查询模块
        if not jxcx.enter_jxcx():
            log_section("[FATAL] 进入即席查询模块失败")
            log("无法继续执行", "ERROR")
            return

        # Step 2: 构建payload
        log_section("Step 2: 构建查询Payload")
        payload = build_payload()
        log(f"报表名称: 45G流量与热点评估物理站级", "INFO")
        log(f"查询条件: 时间=2026-05-07, 地市=阳江", "INFO")
        log(f"字段数量: {len(payload['columns'])}", "INFO")

        # Step 3: 获取数据总数
        total_count = jxcx.get_table_count(payload, report_name="45G流量与热点评估物理站级")

        if total_count == 0:
            log("数据总数为0，跳过数据获取步骤", "WARN")
            return

        # Step 4: 获取实际数据
        log_section("Step 4: 获取实际数据")
        # 修改payload为获取数据模式
        payload['start'] = 0
        payload['length'] = min(total_count, 10)  # 只获取前10条用于测试
        data = jxcx.fetch_data(payload)

        if data:
            log(f"成功获取 {len(data)} 条数据", "SUCCESS")
            log("第一条数据示例:", "DEBUG")
            if isinstance(data, list) and len(data) > 0:
                log(f"  {json.dumps(data[0], ensure_ascii=False)[:500]}", "DEBUG")
        else:
            log("未能获取到数据", "WARN")

        log_section("测试完成")
        log(f"日志已保存到: {LOG_FILE}", "INFO")
        log("请将日志文件复制回给开发者分析。", "INFO")

    finally:
        sys.stdout = original_stdout
        tee.close()
        print(f"\n[日志已保存到] {LOG_FILE}")


if __name__ == '__main__':
    main()
