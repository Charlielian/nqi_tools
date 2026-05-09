# -*- coding: utf-8 -*-
"""
NQI 数据提取统一测试脚本（多线程版）
通过 CLI 交互界面选择要测试的报表，多线程并发测试并输出详细日志

使用方法:
    python test_api.py

优化特性:
1. 多线程并发测试，大幅提升效率
2. 自动从项目配置读取可用报表列表
3. 线程安全的日志记录（避免输出交错）
4. 实时进度显示
5. 详细的错误追踪和调试信息
"""

import os
import sys
import json
import logging
import traceback
import threading
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'test_api')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'test_api_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# 线程安全的日志格式
class ThreadSafeFormatter(logging.Formatter):
    """线程安全的日志格式化器，在每条日志前加线程名"""
    def format(self, record):
        record.thread_tag = f"[{record.threadName[:8]}]"
        return super().format(record)

formatter = ThreadSafeFormatter('%(asctime)s %(thread_tag)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

# 文件 handler：记录所有 DEBUG 信息
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# 控制台 handler：只显示 INFO 以上，简洁格式
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(ThreadSafeFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
logger = logging.getLogger('test_api')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ========== 配置读取 ==========

def get_table_configs():
    """从项目配置自动读取报表列表"""
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
    """获取报表分类映射"""
    try:
        from gui.main_window import NqiToolGUI
        if hasattr(NqiToolGUI, 'CATEGORIES'):
            return NqiToolGUI.CATEGORIES
    except Exception:
        pass
    return {
        '干扰': ['5G干扰小区', '4G干扰小区'],
        '容量': ['5G小区容量报表', '重要场景-天'],
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
    print("=" * 56)
    print("       NQI 数据提取 API 测试工具 (多线程版)")
    print("=" * 56)


def print_table_menu(table_configs, category_mapping):
    """打印报表选择菜单，返回 {编号: (报表名, payload_func)}"""
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

    # 未分类报表
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
    """获取用户选择，返回 [(报表名, payload_func)] 或 None"""
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
    """获取测试参数"""
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

    # 并发数
    max_workers = input("  并发线程数 [3]: ").strip() or '3'
    try:
        max_workers = int(max_workers)
        max_workers = max(1, min(max_workers, 10))  # 限制 1-10
    except ValueError:
        max_workers = 3

    return start, end, city, limit, max_workers


def get_credentials():
    """获取登录凭证"""
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


# ========== 测试执行（线程安全） ==========

# 用于线程安全的进度计数器和输出锁
_progress_lock = threading.Lock()
_output_lock = threading.Lock()
_progress = {'completed': 0, 'total': 0}


def do_login(username, password):
    """执行登录"""
    logger.info("[步骤1] 登录认证")
    try:
        from core.auth import LoginManager
        from core.query import get_cookie_value

        login_mgr = LoginManager(username, password)
        session = login_mgr.login()

        if not session:
            logger.error("  ✗ 登录失败: 返回 None")
            return None

        logger.info(f"  ✓ 登录成功 | Cookies: {len(session.cookies)}")
        for name in ['JSESSIONID', 'CASTGC', 'CAS_TGC']:
            val = get_cookie_value(session.cookies, name)
            if val:
                logger.info(f"    {name}: {val[:25]}...")

        return session
    except Exception as e:
        logger.error(f"  ✗ 登录异常: {e}")
        logger.debug(traceback.format_exc())
        return None


def do_enter_jxcx(query):
    """进入即席查询模块"""
    logger.info("[步骤2] 进入即席查询模块")
    try:
        result = query.enter_jxcx()
        if result:
            logger.info("  ✓ 进入成功")
            return True
        else:
            logger.error("  ✗ 进入失败：enter_jxcx() 返回 False")
            return False
    except Exception as e:
        logger.error(f"  ✗ 进入失败: {e}")
        logger.debug(traceback.format_exc())
        return False


def test_single_table(table_name, payload_func, start_date, end_date, city, limit, query_class, session):
    """测试单个报表（线程内执行）

    每个线程创建独立的 JXCXQuery 实例，避免共享状态竞争。
    """
    thread_name = threading.current_thread().name

    # 每个线程创建独立的 Query 实例（共享 session，但 query 对象独立）
    query = query_class(session)

    logger.info(f"{'─'*50}")
    logger.info(f"▶ 开始测试: {table_name} ({thread_name})")

    result = {
        'name': table_name,
        'success': False,
        'count': 0,
        'data_rows': 0,
        'error': None,
        'time_cost': 0,
    }

    t0 = time.time()

    try:
        # 1. 构建 Payload
        func_name = payload_func.__name__
        if 'gongcan' in func_name:
            payload = payload_func()
        else:
            payload = payload_func(start_date, end_date, city)

        logger.info(f"[{table_name}] Payload 构建成功 | where: {len(payload.get('where', []))} 条件")

        # 2. 查询总数
        try:
            count = query.get_table_count(payload, report_name=table_name)
            result['count'] = count
            logger.info(f"[{table_name}] 数据总数: {count}")
        except Exception as e:
            logger.error(f"[{table_name}] 查询总数失败: {e}")
            result['error'] = str(e)

        # 3. 查询数据样本
        try:
            payload['length'] = limit
            data = query.get_table(payload, to_df=False, report_name=table_name)

            if data is not None:
                result['data_rows'] = len(data)
                if len(data) > 0:
                    sample = data[0]
                    fields = list(sample.items())[:6]
                    logger.info(f"[{table_name}] 返回 {len(data)} 条 | 样本: {', '.join(f'{k}={str(v)[:20]}' for k, v in fields)}")
                else:
                    logger.warning(f"[{table_name}] 返回数据为空")
            else:
                logger.error(f"[{table_name}] 返回 None")
        except Exception as e:
            logger.error(f"[{table_name}] 查询数据失败: {e}")
            result['error'] = str(e)

        result['success'] = True

    except Exception as e:
        logger.error(f"[{table_name}] 测试异常: {e}")
        logger.debug(traceback.format_exc())
        result['error'] = str(e)

    result['time_cost'] = round(time.time() - t0, 2)

    # 更新进度（使用输出锁避免交错）
    with _progress_lock:
        _progress['completed'] += 1
        done = _progress['completed']
        total = _progress['total']
        status = "✓" if result['success'] else "✗"
        with _output_lock:
            print(f"\r  进度: {done}/{total} | {status} {table_name} ({result['time_cost']}s)    ", end='', flush=True)

    return result


def run_parallel_tests(selected_tables, start_date, end_date, city, limit, max_workers, query_class, session):
    """多线程并发执行测试

    Args:
        selected_tables: [(报表名, payload_func), ...]
        max_workers: 最大并发线程数
        query_class: JXCXQuery 类
        session: 已认证的 session

    Returns:
        [result_dict, ...] 测试结果列表
    """
    total = len(selected_tables)
    _progress['completed'] = 0
    _progress['total'] = total

    logger.info(f"\n{'='*56}")
    logger.info(f"  开始并发测试 | 报表: {total} 个 | 线程: {max_workers} 个")
    logger.info(f"{'='*56}")

    results = []

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='Test') as executor:
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
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"线程执行异常: {table_name} - {e}")
                results.append({
                    'name': table_name,
                    'success': False,
                    'count': 0,
                    'data_rows': 0,
                    'error': str(e),
                    'time_cost': 0,
                })

    print()  # 换行（进度条后面）
    return results


# ========== 主函数 ==========

def main():
    print_banner()

    # 导入检查
    logger.info("检查项目模块...")
    try:
        from core.auth import LoginManager
        from core.query import JXCXQuery, get_cookie_value
        from gui.widgets import TableConfig
        from utils.config import BASE_URL, JXCX_URL, JXCX_COUNT_URL, HEADERS
        logger.info("  ✓ 所有模块导入成功")
    except ImportError as e:
        logger.error(f"  ✗ 模块导入失败: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)

    # 读取报表配置
    table_configs = get_table_configs()
    if not table_configs:
        logger.error("无法读取报表配置，退出")
        sys.exit(1)
    category_mapping = get_category_mapping()

    # 登录
    username, password = get_credentials()
    if not username:
        logger.error("未提供用户名，退出")
        sys.exit(1)

    session = do_login(username, password)
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

    # 创建查询实例 & 进入即席查询
    query = JXCXQuery(session)
    if not do_enter_jxcx(query):
        logger.error("无法进入即席查询模块，退出")
        sys.exit(1)

    # 多线程并发测试
    t_start = time.time()
    results = run_parallel_tests(selected, start_date, end_date, city, limit, max_workers, JXCXQuery, session)
    t_total = round(time.time() - t_start, 2)

    # 打印总结
    print(f"\n{'='*56}")
    print(f"  测试总结")
    print(f"{'='*56}")

    # 按成功状态分组，再按耗时排序
    results.sort(key=lambda r: (not r['success'], -r['time_cost']))

    passed = sum(1 for r in results if r['success'])
    failed = sum(1 for r in results if not r['success'])
    total_time = t_total

    # 动态计算列宽
    name_width = max(22, max(len(r['name']) for r in results) + 2) if results else 22
    status_width = 6
    count_width = 6
    time_width = 6

    print(f"  {'状态':^{status_width}} | {'报表名':<{name_width}} | {'数据量':^{count_width}} | {'耗时':^{time_width}}")
    print(f"  {'─'*status_width}─┼─{'─'*name_width}─┼─{'─'*count_width}─┼─{'─'*time_width}")
    for r in results:
        status = "✓ 通过" if r['success'] else "✗ 失败"
        count = r['count'] if r['count'] > 0 else r['data_rows']
        print(f"  {status:^{status_width}} | {r['name']:<{name_width}} | {count:^{count_width}} | {r['time_cost']:^{time_width-1}}s")

    print(f"\n  通过: {passed} | 失败: {failed} | 总计: {len(results)}")
    print(f"  总耗时: {total_time}s (并发 {max_workers} 线程)")
    print(f"  日志文件: {log_file}")
    print(f"{'='*56}")


if __name__ == '__main__':
    main()
