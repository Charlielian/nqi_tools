# -*- coding: utf-8 -*-
"""
调试脚本：直接测试 getTable API 并打印原始响应
用于诊断 getTableCount 有数据但 getTable 返回空的问题
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.auth import LoginManager
from core.query import JXCXQuery, get_cookie_value
from utils.config import BASE_URL, JXCX_URL, JXCX_COUNT_URL, HEADERS

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'debug')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'debug_gettable_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('debug')


def test_get_table(username, password, report_name="5G小区容量-周"):
    """测试 getTable API"""
    
    logger.info("=" * 70)
    logger.info("开始调试 getTable API")
    logger.info("=" * 70)
    
    # 1. 登录
    logger.info("[步骤1] 登录...")
    login_mgr = LoginManager(username, password)
    session = login_mgr.login()
    if not session:
        logger.error("登录失败!")
        return
    
    logger.info("✓ 登录成功")
    
    # 2. 进入 JXCX 模块
    logger.info("[步骤2] 进入即席查询模块...")
    query = JXCXQuery(session)
    if not query.enter_jxcx():
        logger.error("进入JXCX模块失败!")
        return
    
    logger.info("✓ 进入JXCX模块成功")
    
    # 3. 构建测试 payload
    logger.info("[步骤3] 构建测试 payload...")
    from gui.payload_templates import get_5g_capacity_week_payload
    
    payload = get_5g_capacity_week_payload(
        start_date='2026-05-01',
        end_date='2026-05-25', 
        city='阳江'
    )
    
    logger.info("Payload 构建完成")
    logger.info("  表名: appdbv3.a_adhoc_capacity_nr_nrcell_w")
    logger.info("  条件: starttime >= 2026-05-01, starttime < 2026-05-25, city in 阳江")
    logger.info("  indexcount: %s", payload.get('indexcount'))
    
    # 4. 先测试 getTableCount
    logger.info("")
    logger.info("[步骤4] 测试 getTableCount API...")
    
    # 构建 count payload
    count_payload = payload.copy()
    key_list = ['geographicdimension', 'timedimension', 'enodebField', 'cgiField',
                'timeField', 'cellField', 'cityField', 'result', 'where', 'indexcount']
    count_payload = {key: value for key, value in count_payload.items() if key in key_list}
    
    # 编码
    from urllib.parse import quote
    encoded_data = []
    for key in count_payload:
        if key == 'result':
            json_str = json.dumps(count_payload[key], ensure_ascii=False, separators=(',', ':'))
            encoded_data.append(quote(key) + '=' + quote(json_str, safe='/:= '))
        elif key == 'where':
            json_str = json.dumps(count_payload[key], ensure_ascii=False, separators=(',', ':'))
            encoded_data.append(quote(key) + '=' + quote(json_str, safe='/:= '))
        else:
            encoded_data.append(quote(key) + '=' + quote(str(count_payload[key])))
    encoded_count = '&'.join(encoded_data)
    
    logger.info("发送 getTableCount 请求...")
    res_count = session.post(JXCX_COUNT_URL, data=encoded_count, headers=HEADERS, timeout=60)
    
    logger.info("getTableCount 响应:")
    logger.info("  HTTP状态码: %s", res_count.status_code)
    logger.info("  响应内容: %s", res_count.text[:500])
    
    try:
        count_data = json.loads(res_count.text)
        total_count = count_data.get('count', 0)
        logger.info("  解析后 count: %s", total_count)
    except:
        total_count = 0
        logger.error("getTableCount JSON解析失败")
    
    if total_count == 0:
        logger.warning("数据总数为0，无需测试 getTable")
        return
    
    # 5. 测试 getTable API（核心调试）
    logger.info("")
    logger.info("[步骤5] 测试 getTable API (核心调试)...")
    logger.info("  预期数据量: %d", total_count)
    
    # ========== 方案1：使用 JXCXQuery 的 _encode_payload 方法 ==========
    logger.info("")
    logger.info("【调试方案1】使用 _encode_payload 方法（含columns/order/search）...")
    
    # 使用 JXCXQuery 的 _encode_payload 方法进行编码
    # 这样方括号不会被编码，空字符串参数也会被过滤
    encoded_data_str = query._encode_payload(payload)
    
    logger.info("  参数列表: %s", list(payload.keys()))
    logger.info("  encoded_data 长度: %d 字符", len(encoded_data_str))
    
    try:
        res_data = session.post(JXCX_URL, data=encoded_data_str, headers=HEADERS, timeout=120)
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("getTable 原始响应:")
        logger.info("=" * 70)
        logger.info("HTTP状态码: %s", res_data.status_code)
        logger.info("Content-Type: %s", res_data.headers.get('Content-Type', 'N/A'))
        logger.info("响应长度: %d 字节", len(res_data.text))
        logger.info("")
        logger.info("响应内容 (前5000字符):")
        logger.info("-" * 70)
        
        # 打印原始响应
        text = res_data.text
        for i in range(0, min(len(text), 5000), 100):
            logger.info("  %s", text[i:i+100])
        
        if len(text) > 5000:
            logger.info("  ... (省略 %d 字符)", len(text) - 5000)
        
        logger.info("-" * 70)
        logger.info("")
        
        # 尝试解析 JSON
        logger.info("尝试解析 JSON...")
        try:
            parsed = json.loads(text)
            logger.info("JSON 解析成功!")
            logger.info("响应 keys: %s", list(parsed.keys()) if isinstance(parsed, dict) else type(parsed))
            
            # 检查各种可能的数据字段
            logger.info("")
            logger.info("数据字段检查:")
            
            checks = [
                ('data', lambda x: x.get('data')),
                ('result', lambda x: x.get('result')),
                ('records', lambda x: x.get('records')),
                ('rows', lambda x: x.get('rows')),
                ('data.result', lambda x: x.get('data', {}).get('result') if isinstance(x.get('data'), dict) else None),
                ('data.data', lambda x: x.get('data', {}).get('data') if isinstance(x.get('data'), dict) else None),
                ('data.records', lambda x: x.get('data', {}).get('records') if isinstance(x.get('data'), dict) else None),
            ]
            
            for name, getter in checks:
                val = getter(parsed)
                if val is not None:
                    if isinstance(val, list):
                        logger.info("  ✓ %s: list, 长度=%d", name, len(val))
                    else:
                        logger.info("  ? %s: %s", name, type(val))
                else:
                    logger.info("  ✗ %s: 不存在或为空", name)
            
            # 打印找到的数据
            data_list = parsed.get('data')
            if data_list is None:
                data_list = parsed.get('result')
            if data_list is None and isinstance(parsed.get('data'), dict):
                data_list = parsed['data'].get('data') or parsed['data'].get('records') or parsed['data'].get('result')
            
            if isinstance(data_list, list) and len(data_list) > 0:
                logger.info("")
                logger.info("找到数据! 共 %d 条", len(data_list))
                logger.info("第一条数据: %s", json.dumps(data_list[0], ensure_ascii=False)[:500])
            else:
                logger.info("")
                logger.info("未找到数据数组!")
                
        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败: %s", e)
            logger.error("响应不是有效的 JSON 格式")
            
    except requests.exceptions.Timeout:
        logger.error("请求超时!")
    except requests.exceptions.ConnectionError as e:
        logger.error("连接错误: %s", e)
    except Exception as e:
        logger.error("请求异常: %s", e)
        import traceback
        logger.error(traceback.format_exc())
    
    # ========== 方案2：使用 _encode_payload 但包含分页参数 ==========
    logger.info("")
    logger.info("【调试方案2】使用 _encode_payload + 分页参数...")
    
    # 复制payload并添加分页参数
    payload2 = payload.copy()
    payload2['start'] = 0
    payload2['length'] = 10
    payload2['draw'] = 1
    payload2['total'] = 0
    
    encoded_data_str2 = query._encode_payload(payload2)
    
    logger.info("  参数列表: %s", list(payload2.keys()))
    logger.info("  encoded_data 长度: %d 字符", len(encoded_data_str2))
    logger.info("")
    
    try:
        res_data2 = session.post(JXCX_URL, data=encoded_data_str2, headers=HEADERS, timeout=120)
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("方案2 getTable 原始响应:")
        logger.info("=" * 70)
        logger.info("HTTP状态码: %s", res_data2.status_code)
        logger.info("响应长度: %d 字节", len(res_data2.text))
        logger.info("响应内容: %s", res_data2.text[:500])
        
        try:
            parsed2 = json.loads(res_data2.text)
            data2 = parsed2.get('data')
            if data2 and len(data2) > 0:
                logger.info("✓✓✓ 方案2成功! 获取数据: %d 条", len(data2))
            else:
                logger.info("✗ 方案2 data 字段为空, dbTime=%s", parsed2.get('dbTime'))
        except json.JSONDecodeError as e:
            logger.error("方案2 JSON解析失败: %s", e)
            
    except Exception as e:
        logger.error("方案2 请求异常: %s", e)
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("调试完成! 日志文件: %s", log_file)
    logger.info("=" * 70)


if __name__ == '__main__':
    import getpass
    
    print("=" * 50)
    print("  NQI getTable API 调试工具")
    print("=" * 50)
    print()
    
    # 获取凭据
    try:
        from utils.config import DEFAULT_USERNAME, DEFAULT_PASSWORD
        username = DEFAULT_USERNAME
        password = DEFAULT_PASSWORD
        if username == 'XXXXX' or not password:
            raise ValueError()
        print(f"使用配置文件中的凭据")
    except:
        username = input("用户名: ").strip()
        password = getpass.getpass("密码: ").strip()
    
    if not username or not password:
        print("用户名和密码不能为空")
        sys.exit(1)
    
    # 运行测试
    test_get_table(username, password)
