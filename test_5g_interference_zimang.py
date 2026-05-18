# -*- coding: utf-8 -*-
"""
诊断脚本：调试"5G干扰报表_自忙时"报表的提取问题
详细分析payload构建、API响应等关键环节

使用方法：
    python test_5g_interference_zimang.py
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
LOG_FILE = os.path.join(LOG_DIR, f'test_5g_zimang_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# 默认用户名
DEFAULT_USERNAME = 'default'

# Headers（与浏览器HAR抓包一致）
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Origin': BASE_URL,
    'Referer': f'{BASE_URL}/pro-adhoc/adhocquery?datesub=2026-05-17%20~%202026-05-17&datecategory=1&hours=&minutes=&enodeb_id=&cgi=&city=%E9%98%B3%E6%B1%9F&grid=&dimension=0&type=modelcreate&value=undefined&searchtype=&table=undefined&eci=',
    'x-requested-with': 'XMLHttpRequest',
    'sec-ch-ua': '"Chromium";v="147", "Not.A/Brand";v="8"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'priority': 'u=1, i',
}


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


def load_cookie(username):
    """从文件加载Cookie"""
    # 尝试不同的文件名模式
    possible_files = [
        os.path.join(COOKIE_DIR, f'{username}_cookies.json'),
        os.path.join(COOKIE_DIR, f'{username}.json'),
        os.path.join(COOKIE_DIR, 'default.json'),
        os.path.join(COOKIE_DIR, 'nqi_cookies.json'),
    ]
    
    for cookie_file in possible_files:
        if os.path.exists(cookie_file):
            log(f"找到Cookie文件: {cookie_file}", "DEBUG")
            break
    else:
        log(f"未找到Cookie文件, 尝试的文件: {possible_files}", "ERROR")
        return None

    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        jar = requests.cookies.RequestsCookieJar()
        
        # 支持两种格式: 列表格式和字典格式
        if isinstance(data, list):
            # 列表格式: [{"name": "...", "value": "...", ...}, ...]
            for cookie in data:
                jar.set(cookie['name'], cookie['value'], 
                       domain=cookie.get('domain', 'nqi.gmcc.net'),
                       path=cookie.get('path', '/'))
        elif isinstance(data, dict):
            # 字典格式: {"cookie_name": "value", ...}
            jar.update(data)
        
        return jar
    except Exception as e:
        log(f"加载Cookie失败: {e}", "ERROR")
        traceback.print_exc()
        return None


def print_cookie_details(cookie_jar, title):
    """打印Cookie详情"""
    log(f"--- {title} ---")
    if cookie_jar:
        for cookie in cookie_jar:
            log(f"  {cookie.name} = {cookie.value[:30]}... (domain={cookie.domain})")
    else:
        log("  (空)")


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


def build_payload_from_field_configs():
    """从field_configs构建payload（模拟正式代码）"""
    from gui.field_configs import INTERFERENCE_5G_ZIMANG_FIELDS, INTERFERENCE_5G_ZIMANG_DIMENSION
    
    # HAR中：无columntype的字段不包含columntype字段
    no_columntype_fields = {'starttime', 'endtime', 'city', 'area', 'grid'}
    
    result_list = []
    for field in INTERFERENCE_5G_ZIMANG_FIELDS:
        feild = field.get('feild', '')
        feildName = field.get('feildName', feild)
        datatype = field.get('datatype', 'character varying')
        columntype = field.get('columntype', '1')
        
        item = {
            'feildtype': '5G_干扰报表_自忙时',
            'table': 'appdbv3.a_interfere_nrcell_zb4',
            'tableName': '5G_干扰报表_自忙时',
            'datatype': datatype,
            'feildName': feildName,
            'feild': feild,
            'poly': '无',
            'anyWay': '无',
            'chart': '无',
            'chartpoly': '无'
        }
        # HAR中：这些字段不包含columntype
        if feild not in no_columntype_fields:
            item['columntype'] = columntype
        
        result_list.append(item)
    
    # 使用维度参数
    dim = INTERFERENCE_5G_ZIMANG_DIMENSION
    
    payload = {
        'draw': 1,
        'start': 0,
        'length': 200,
        'total': 0,
        'geographicdimension': dim.get('geographicdimension', '小区'),
        'timedimension': dim.get('timedimension', '天、周'),
        'enodebField': dim.get('enodebField', 'gnodeb_id'),
        'cgiField': dim.get('cgiField', 'cgi'),
        'timeField': dim.get('timeField', 'starttime'),
        'cellField': dim.get('cellField', 'nrcell'),
        'cityField': dim.get('cityField', 'city'),
        'columns': [],  # 空columns
        'order': [{'column': 0, 'dir': 'desc'}],
        'search': {'value': '', 'regex': False},
        'result': {
            'result': result_list,
            'tableParams': {'supporteddimension': None, 'supportedtimedimension': '1'},
            'columnname': ''
        },
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': '2026-05-17 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': '2026-05-17 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': '阳江', 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }
    
    return payload


def build_har_like_payload():
    """完全按照HAR抓包的格式构建payload"""
    from gui.field_configs import INTERFERENCE_5G_ZIMANG_FIELDS
    
    # HAR中的字段顺序
    har_field_names = ['starttime', 'endtime', 'city', 'area', 'grid', 'ncgi', 'nrcell_name', 
                      'freq', 'phy_ulmeannl_prb', 'd1_phy_ulmeannl_prb',
                      'phy_ulmeannl_prb0', 'phy_ulmeannl_prb1', 'phy_ulmeannl_prb10', 
                      'phy_ulmeannl_prb100', 'phy_ulmeannl_prb101']
    
    # HAR中的datatype映射
    har_datatype_map = {
        'starttime': '1',
        'endtime': '1',
        'city': '1',
        'area': '1',
        'grid': '1',
    }
    
    result_list = []
    for field_name in har_field_names:
        # 查找字段配置
        field_config = None
        for f in INTERFERENCE_5G_ZIMANG_FIELDS:
            if f.get('feild') == field_name:
                field_config = f
                break
        
        if not field_config:
            log(f"字段 {field_name} 在配置中未找到", "WARN")
            continue
            
        datatype = har_datatype_map.get(field_name, 'character varying')
        feildName = field_config.get('feildName', field_name)
        
        item = {
            'feildtype': '5G_干扰报表_自忙时',
            'table': 'appdbv3.a_interfere_nrcell_zb4',
            'tableName': '5G_干扰报表_自忙时',
            'datatype': datatype,
            'feildName': feildName,
            'feild': field_name,
            'poly': '无',
            'anyWay': '无',
            'chart': '无',
            'chartpoly': '无'
        }
        
        # HAR中只有ncgi, nrcell_name, freq, phy_ulmeannl_prb等有columntype
        if field_name not in ['starttime', 'endtime', 'city', 'area', 'grid']:
            item['columntype'] = '1'
        
        result_list.append(item)
    
    payload = {
        # HAR中getTable请求有 start 和 length 参数
        'start': 0,
        'length': 100,  # 请求返回多少条数据
        'total': 0,
        'draw': 1,
        'geographicdimension': '小区',
        'timedimension': '天、周',
        'enodebField': 'gnodeb_id',
        'cgiField': 'cgi',
        'timeField': 'starttime',
        'cellField': 'nrcell',
        'cityField': 'city',
        'result': {
            'result': result_list,
            'tableParams': {'supporteddimension': None, 'supportedtimedimension': '1'},
            'columnname': ''
        },
        'where': [
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '>=', 'val': '2026-05-17 00:00:00', 'whereCon': 'and', 'query': True},
            {'datatype': 'timestamp', 'feild': 'starttime', 'feildName': '', 'symbol': '<', 'val': '2026-05-17 23:59:59', 'whereCon': 'and', 'query': True},
            {'datatype': 'character', 'feild': 'city', 'feildName': '', 'symbol': 'in', 'val': '阳江', 'whereCon': 'and', 'query': True}
        ],
        'indexcount': 0
    }
    
    return payload


class JxcxSimulator:
    """即席查询模拟器"""
    
    def __init__(self, session):
        self.session = session
        self.enabled = False
    
    def enter_jxcx(self):
        """进入即席查询模块"""
        try:
            # 获取CASTGC token
            castgc = None
            for cookie in self.session.cookies:
                if cookie.name == 'CASTGC':
                    castgc = cookie.value
                    break
            
            if not castgc:
                log("未找到CASTGC cookie", "ERROR")
                return False
            
            log(f"CASTGC token: {castgc[:30]}...", "DEBUG")
            
            # 访问JXCX入口
            url = f'{BASE_URL}/pro-portal/pure/urlAction.action'
            params = {
                'url': 'pro-adhoc/index',
                'random': random.random(),
                '__PID': 'JXCX',
                'token': castgc
            }
            url_with_params = f"{url}?url={params['url']}&__PID={params['__PID']}&random={params['random']}&token={params['token']}"
            
            log(f"访问JXCX入口...", "INFO")
            res = self.session.get(url_with_params, headers=HEADERS, timeout=60, allow_redirects=True)
            
            log(f"响应状态码: {res.status_code}", "INFO")
            log(f"最终URL: {res.url[:100]}...", "DEBUG")
            
            # 检查是否有JSESSIONID
            jsessionid = None
            for cookie in self.session.cookies:
                if cookie.name == 'JSESSIONID':
                    jsessionid = cookie.value
                    break
            
            if jsessionid:
                log(f"获取到JSESSIONID: {jsessionid[:20]}...", "SUCCESS")
                self.enabled = True
                return True
            
            log("未获取到JSESSIONID", "WARN")
            return False
            
        except Exception as e:
            log(f"进入JXCX失败: {e}", "ERROR")
            traceback.print_exc()
            return False
    
    def get_table_count(self, payload, report_name="测试报表"):
        """获取数据总数"""
        log_section(f"获取数据总数: {report_name}")
        
        # 检查Cookie状态
        log(f"Cookie状态检查:", "DEBUG")
        has_castgc = False
        has_jsessionid = False
        for cookie in self.session.cookies:
            if cookie.name == 'CASTGC':
                has_castgc = True
                log(f"  CASTGC: {cookie.value[:30]}...", "DEBUG")
            if cookie.name == 'JSESSIONID':
                has_jsessionid = True
                log(f"  JSESSIONID: {cookie.value[:20]}...", "DEBUG")
        
        if not has_castgc:
            log("警告: 未找到CASTGC Cookie", "WARN")
        if not has_jsessionid:
            log("警告: 未找到JSESSIONID Cookie", "WARN")
        
        # 只保留count需要的参数
        count_payload = {key: value for key, value in payload.items() 
                        if key in ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                                   'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount']}
        
        # 打印payload详情
        log(f"维度参数:", "DEBUG")
        for k in ['geographicdimension', 'timedimension', 'cellField', 'cityField']:
            if k in count_payload:
                log(f"  {k} = {count_payload[k]}", "DEBUG")
        
        # 打印where条件
        if 'where' in count_payload:
            log(f"查询条件:", "DEBUG")
            for cond in count_payload['where']:
                log(f"  {cond.get('feild')} {cond.get('symbol')} {cond.get('val')}", "DEBUG")
        
        # 打印result字段
        if 'result' in count_payload and 'result' in count_payload['result']:
            result_list = count_payload['result']['result']
            log(f"result字段数量: {len(result_list)}", "INFO")
            log(f"前5个字段:", "DEBUG")
            for r in result_list[:5]:
                log(f"  - {r.get('feild')} | datatype={r.get('datatype')} | columntype={r.get('columntype', 'N/A')}", "DEBUG")
        
        # 编码payload
        encoded = encode_payload(count_payload)
        log(f"编码后长度: {len(encoded)} 字符", "DEBUG")
        log(f"编码后内容(前500字符): {encoded[:500]}", "DEBUG")
        
        try:
            log(f"发送请求到 {JXCX_COUNT_URL}...", "INFO")
            res = self.session.post(JXCX_COUNT_URL, data=encoded, headers=HEADERS, timeout=120)
            
            log(f"响应状态码: {res.status_code}", "INFO")
            log(f"响应Content-Type: {res.headers.get('Content-Type', 'N/A')}", "DEBUG")
            log(f"响应内容(原始): {res.text[:1000]}", "DEBUG")
            
            if res.status_code == 200:
                # 检查是否为空响应
                if not res.text or not res.text.strip():
                    log("响应内容为空!", "ERROR")
                    return 0
                
                try:
                    result = json.loads(res.text)
                    log(f"响应JSON: {result}", "DEBUG")
                    log(f"响应类型: {type(result)}", "DEBUG")
                    log(f"响应keys: {list(result.keys()) if isinstance(result, dict) else 'N/A (不是字典)'}", "INFO")
                    
                    # 检查是否返回空数组
                    if isinstance(result, list) and len(result) == 0:
                        log("响应为空数组 [] - Session可能已过期或请求被拒绝", "ERROR")
                        log("建议: 1. 检查Cookie是否有效  2. 尝试重新登录获取新Cookie", "ERROR")
                        return 0
                    
                    # 尝试提取count
                    count = result.get('count')
                    if count is not None:
                        log(f"数据总数: {count}", "SUCCESS")
                        return count
                    
                    # 尝试其他格式
                    count = result.get('data', {}).get('count')
                    if count is not None:
                        log(f"数据总数(data.count): {count}", "SUCCESS")
                        return count
                    
                    log(f"响应中未找到count字段", "WARN")
                    log(f"响应keys: {list(result.keys())}", "WARN")
                    return 0
                except json.JSONDecodeError as e:
                    log(f"JSON解析失败: {e}", "ERROR")
                    return 0
            else:
                log(f"HTTP错误: {res.status_code}", "ERROR")
                log(f"响应内容: {res.text[:500]}", "ERROR")
                return 0
                
        except Exception as e:
            log(f"请求失败: {e}", "ERROR")
            traceback.print_exc()
            return 0
    
    def fetch_data(self, payload, total_count=100, report_name="测试报表"):
        """获取实际数据"""
        log_section(f"获取数据内容: {report_name}")
        
        # 构建payload，包含start和length参数（与正式代码的_fetch_by_loop一致）
        data_payload = {key: value for key, value in payload.items() 
                       if key in ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                                  'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount',
                                  'start', 'length', 'draw', 'total', 'columns', 'order', 'search']}
        
        # 添加start和length参数（与_fetch_by_loop一致）
        data_payload['start'] = 0
        data_payload['length'] = min(total_count, 50000)  # 限制最大50000条
        
        log(f"请求参数:", "DEBUG")
        for k in ['start', 'length', 'draw']:
            if k in data_payload:
                log(f"  {k} = {data_payload[k]}", "DEBUG")
        
        encoded = encode_payload(data_payload)
        log(f"编码后长度: {len(encoded)} 字符", "DEBUG")
        
        try:
            log(f"发送请求到 {JXCX_URL}...", "INFO")
            log(f"预计获取: {data_payload['length']} 条数据", "INFO")
            res = self.session.post(JXCX_URL, data=encoded, headers=HEADERS, timeout=120)
            
            log(f"响应状态码: {res.status_code}", "INFO")
            log(f"响应内容长度: {len(res.content)} 字节", "INFO")
            log(f"响应内容(前1000字符): {res.text[:1000]}", "DEBUG")
            
            if res.status_code == 200:
                try:
                    result = json.loads(res.text)
                    log(f"响应JSON keys: {list(result.keys())}", "DEBUG")
                    
                    # 尝试提取数据
                    data = result.get('data') or result.get('result') or result.get('records')
                    if data and isinstance(data, list):
                        log(f"获取到 {len(data)} 条数据", "SUCCESS")
                        return data
                    
                    log(f"响应中未找到数据数组", "WARN")
                    return []
                    
                except json.JSONDecodeError as e:
                    log(f"JSON解析失败: {e}", "ERROR")
                    return []
            else:
                log(f"HTTP错误: {res.status_code}", "ERROR")
                return []
                
        except Exception as e:
            log(f"请求失败: {e}", "ERROR")
            traceback.print_exc()
            return []


def main():
    """主函数"""
    tee = TeeOutput(LOG_FILE)
    original_stdout = sys.stdout
    sys.stdout = tee

    try:
        log_section("5G干扰报表_自忙时 - 完整流程诊断")
        log(f"测试时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        log(f"Python版本: {sys.version}", "INFO")
        log(f"工作目录: {os.getcwd()}", "INFO")
        log(f"日志文件: {LOG_FILE}", "INFO")

        # 步骤1: 加载Cookie
        log_section("Step 1: 加载Cookie")
        cookie_jar = load_cookie(DEFAULT_USERNAME)
        if cookie_jar is None:
            log("无法加载Cookie文件", "ERROR")
            return
        print_cookie_details(cookie_jar, "加载的Cookie")

        # 步骤2: 创建Session
        session = requests.Session()
        session.verify = False
        session.cookies = cookie_jar

        # 步骤3: 创建模拟器
        jxcx = JxcxSimulator(session)

        # 步骤4: 进入JXCX
        if not jxcx.enter_jxcx():
            log_section("[FATAL] 进入即席查询模块失败")
            return

        # 步骤5: 测试方式1 - 从field_configs构建的payload
        log_section("测试方式1: 使用field_configs构建的payload")
        payload1 = build_payload_from_field_configs()
        log(f"字段数量: {len(payload1['result']['result'])}", "INFO")
        log(f"是否包含columns: {'columns' in payload1}", "DEBUG")
        log(f"columns长度: {len(payload1.get('columns', []))}", "DEBUG")
        count1 = jxcx.get_table_count(payload1, "field_configs方式")
        
        if count1 > 0:
            data1 = jxcx.fetch_data(payload1, count1, "field_configs方式")
            if data1:
                log(f"方式1成功获取 {len(data1)} 条数据", "SUCCESS")
        
        # 步骤6: 测试方式2 - 完全按照HAR格式
        log_section("测试方式2: 完全按照HAR格式")
        payload2 = build_har_like_payload()
        log(f"字段数量: {len(payload2['result']['result'])}", "INFO")
        log(f"是否包含columns: {'columns' in payload2}", "DEBUG")
        log(f"是否包含draw: {'draw' in payload2}", "DEBUG")
        count2 = jxcx.get_table_count(payload2, "HAR格式")
        
        if count2 > 0:
            data2 = jxcx.fetch_data(payload2, count2, "HAR格式")
            if data2:
                log(f"方式2成功获取 {len(data2)} 条数据", "SUCCESS")
        
        # 步骤7: 对比结果
        log_section("测试结果对比")
        log(f"方式1 (field_configs): count={count1}", "INFO")
        log(f"方式2 (HAR格式): count={count2}", "INFO")
        
        if count1 == 0 and count2 == 0:
            log("两种方式都无法获取数据，可能原因:", "ERROR")
            log("  1. 日期范围内确实没有数据", "ERROR")
            log("  2. 地市名称不匹配 (应为'阳江')", "ERROR")
            log("  3. 字段配置不正确", "ERROR")
            log("  4. Session已过期", "ERROR")
            log("  5. API接口有变化", "ERROR")
        
        log_section("诊断完成")
        log(f"日志已保存到: {LOG_FILE}", "INFO")
        log("请将日志文件复制回给开发者分析。", "INFO")

    finally:
        sys.stdout = original_stdout
        tee.close()
        print(f"\n[日志已保存到] {LOG_FILE}")


if __name__ == '__main__':
    main()
