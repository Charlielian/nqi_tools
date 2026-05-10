# -*- coding: utf-8 -*-
"""聚类工单API测试脚本"""

import requests
import json
import urllib3
import logging
import os
from datetime import datetime

urllib3.disable_warnings()

def setup_logging():
    """配置日志输出到文件和控制台"""
    log_dir = './logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'cluster_api_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

BASE_URL = 'https://nqi.gmcc.net:20443'
PRO_LTESCHEME_URL = f'{BASE_URL}/pro-ltemr-cicd/modules/disquery'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Origin': BASE_URL,
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': f'{BASE_URL}/pro-ltemr-cicd/modules/ltescheme/unify/disquery/showgis.jsp?firstQuery=1',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br'
}

def load_cookie(username):
    """从文件加载Cookie"""
    cookie_file = f'./cookies/{username}.json'
    if not os.path.exists(cookie_file):
        logger.error("Cookie文件不存在: %s", cookie_file)
        return None

    with open(cookie_file, 'r', encoding='utf-8') as f:
        cookie_data = json.load(f)

    jar = requests.cookies.RequestsCookieJar()
    if isinstance(cookie_data, list):
        for item in cookie_data:
            jar.set(
                item.get('name'), 
                item.get('value', ''),
                domain=item.get('domain', 'nqi.gmcc.net'), 
                path=item.get('path', '/')
            )
    else:
        for name, value in cookie_data.items():
            if isinstance(value, dict):
                jar.set(name, value.get('value', ''), domain=value.get('domain', ''))
            else:
                jar.set(name, value)
    return jar

def test_api(username='default'):
    """测试聚类工单API"""
    logger.info("=" * 60)
    logger.info(f"开始测试聚类工单API (用户: {username})")
    logger.info("=" * 60)

    sess = requests.Session()
    urllib3.disable_warnings()
    sess.verify = False

    cookie_jar = load_cookie(username)
    if cookie_jar:
        sess.cookies.update(cookie_jar)
        logger.info("[OK] Cookie已加载")
        
        # 列出加载的Cookie
        for cookie in sess.cookies:
            logger.debug("  - %s: %s...", cookie.name, cookie.value[:20] if len(cookie.value) > 20 else cookie.value)
    else:
        logger.error("[FAIL] Cookie加载失败")
        return

    # 检查必要的Cookie
    required_cookies = ['CASTGC', 'JSESSIONID', 'rememberMe']
    for name in required_cookies:
        found = any(c.name == name for c in sess.cookies)
        if found:
            logger.info("[OK] Cookie '%s' 存在", name)
        else:
            logger.warning("[WARN] Cookie '%s' 不存在", name)

    # 测试1: getgrid
    logger.info("\n--- 测试 getgrid ---")
    grid_url = f'{PRO_LTESCHEME_URL}/getgrid'
    data = {'city': '860662'}

    try:
        logger.debug("请求URL: %s", grid_url)
        logger.debug("请求数据: %s", data)

        res = sess.post(grid_url, data=data, headers=HEADERS, timeout=30)
        logger.info("响应状态码: %d", res.status_code)

        if res.status_code == 200 and res.headers.get('content-type', '').startswith('application/json'):
            result = res.json()
            if result.get('code') == 1:
                grids = json.loads(result.get('obj', '[]'))
                logger.info("[OK] 获取到 %d 个网格", len(grids))
                for g in grids[:3]:
                    logger.debug("  - %s", g)
            else:
                logger.warning("[WARN] 返回code不为1: %s", result)
        else:
            logger.warning("[WARN] 响应不是JSON或状态码异常")
            logger.debug("响应内容: %s", res.text[:500])
    except Exception as e:
        logger.exception("[ERROR] 获取网格异常: %s", str(e))

    # 测试2: getproblemlabelByData
    logger.info("\n--- 测试 getproblemlabelByData ---")
    label_url = f'{PRO_LTESCHEME_URL}/getproblemlabelByData'
    data = {
        'typeid': '1',
        'starttime': '2026-05-01',
        'endtime': '2026-05-09'
    }

    try:
        logger.debug("请求URL: %s", label_url)
        logger.debug("请求数据: %s", data)

        res = sess.post(label_url, data=data, headers=HEADERS, timeout=30)
        logger.info("响应状态码: %d", res.status_code)

        if res.status_code == 200 and res.headers.get('content-type', '').startswith('application/json'):
            result = res.json()
            logger.info("[OK] 响应: %s", result)
        else:
            logger.warning("[WARN] 响应不是JSON")
            logger.debug("响应内容: %s", res.text[:500])
    except Exception as e:
        logger.exception("[ERROR] 获取问题标签异常: %s", str(e))

    # 测试3: queryProposal (聚类工单查询)
    logger.info("\n--- 测试 queryProposal ---")
    query_url = f'{PRO_LTESCHEME_URL}/queryProposal'

    post_data = {
        'firstQuery': '',
        'timeType': '问题生成时间',
        'start_date': '2026-05-01',
        'end_date': '2026-05-09',
        'city': '860662',
        'area_grid': '',
        'order_code': '',
        'problemSource': '',
        'question_type': '',
        'problem_status': '',
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
        'isquery': 'ture',
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
        'rows': '100',
        'pagination[pageSize]': '100',
        'pagination[page]': '1',
    }

    try:
        logger.debug("请求URL: %s", query_url)
        res = sess.post(query_url, data=post_data, headers=HEADERS, timeout=60)
        logger.info("响应状态码: %d", res.status_code)

        if res.status_code == 200 and res.headers.get('content-type', '').startswith('application/json'):
            result = res.json()
            message = result.get('message', {})
            if message.get('success'):
                rows = result.get('rows', [])
                pagination = result.get('pagination', {})
                logger.info("[OK] 查询成功")
                logger.info("    返回行数: %d", len(rows))
                if rows:
                    logger.info("    第一条数据: %s", rows[0])
            else:
                logger.warning("[WARN] 查询失败: %s", message)
        else:
            logger.warning("[WARN] 响应不是JSON")
            logger.debug("响应内容: %s", res.text[:500])
    except Exception as e:
        logger.exception("[ERROR] 查询聚类工单异常: %s", str(e))

    logger.info("\n测试完成!")

if __name__ == '__main__':
    import sys
    username = sys.argv[1] if len(sys.argv) > 1 else 'default'
    test_api(username)
