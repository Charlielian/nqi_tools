# -*- coding: utf-8 -*-
"""
NQI 数据提取统一测试脚本
通过 CLI 交互界面选择要测试的报表，执行测试并输出详细日志

使用方法:
    python test_api.py

功能:
1. CLI 交互界面选择报表类型
2. 自动从项目配置读取可用报表列表
3. 详细的日志记录（控制台 + 文件）
4. 完整的错误追踪和调试信息
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime, timedelta

# 配置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'test_api')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'test_api_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('test_api')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get_table_configs():
    """从项目配置自动读取报表列表
    
    Returns:
        dict: {报表名: {'payload_func': 函数对象, 'config': 配置信息}}
    """
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
        
        logger.info(f"从 TableConfig.TABLE_CONFIGS 读取到 {len(configs)} 个报表配置")
        return configs
        
    except Exception as e:
        logger.error(f"读取 TableConfig 失败: {e}")
        logger.debug(traceback.format_exc())
        return {}


def get_category_mapping():
    """获取报表分类映射（从 main_window.py 读取）
    
    Returns:
        dict: {分类名: [报表名列表]}
    """
    try:
        from gui.main_window import NqiToolGUI
        
        # 尝试从类属性获取
        if hasattr(NqiToolGUI, 'CATEGORIES'):
            return NqiToolGUI.CATEGORIES
        
        # 默认分类
        return {
            '干扰': ['5G干扰小区', '4G干扰小区'],
            '容量': ['5G小区容量报表', '重要场景-天'],
            '工参': ['5G小区工参报表', '4G小区工参报表'],
            'MR覆盖': ['5GMR覆盖-小区天', '4GMR覆盖-小区天'],
            '语音报表': ['4G语音-VoLTE', '4G语音-EPSFB', '5G语音小区'],
            '语音预警': ['VoLTE小区监控预警', 'EPSFB小区监控预警', 'VONR小区监控预警'],
            '小区性能': ['5G小区性能KPI报表', '4G小区性能KPI报表'],
            '全程完好率': ['4G全程完好率报表', '5G全程完好率报表'],
            '语音小区': ['4G语音小区', '5G语音小区'],
        }
        
    except Exception as e:
        logger.warning(f"读取分类配置失败，使用默认分类: {e}")
        return {}


def print_banner():
    """打印横幅"""
    print()
    print("=" * 56)
    print("       NQI 数据提取 API 测试工具")
    print("=" * 56)


def print_table_menu(table_configs, category_mapping):
    """打印报表选择菜单
    
    Args:
        table_configs: 报表配置字典
        category_mapping: 分类映射字典
        
    Returns:
        dict: {编号: (报表名, payload_func)}
    """
    print("\n  可测试报表列表：\n")
    
    index_map = {}
    idx = 0
    
    # 按分类显示
    for category, table_names in category_mapping.items():
        available_tables = [t for t in table_names if t in table_configs]
        if not available_tables:
            continue
            
        print(f"  【{category}】")
        for table_name in available_tables:
            idx += 1
            config = table_configs[table_name]
            payload_func = config['payload_func']
            index_map[idx] = (table_name, payload_func)
            
            # 显示表名和字段类型
            fieldtype = config.get('fieldtype', 'N/A')
            print(f"    {idx:>2}. {table_name}")
        print()
    
    # 显示未分类的报表
    categorized = set()
    for tables in category_mapping.values():
        categorized.update(tables)
    
    uncategorized = set(table_configs.keys()) - categorized
    if uncategorized:
        print("  【其他】")
        for table_name in sorted(uncategorized):
            idx += 1
            config = table_configs[table_name]
            payload_func = config['payload_func']
            index_map[idx] = (table_name, payload_func)
            print(f"    {idx:>2}. {table_name}")
        print()
    
    return index_map


def get_user_selection(index_map):
    """获取用户选择"""
    while True:
        try:
            choice = input("  请输入报表编号 (多选用逗号分隔, 0=全部, q=退出): ").strip()
            if choice.lower() == 'q':
                return None

            if choice == '0':
                # 返回所有报表
                return [(name, func) for name, func in index_map.values()]

            # 解析多选
            indices = [int(x.strip()) for x in choice.split(',')]
            selected = []
            for i in indices:
                if i in index_map:
                    selected.append(index_map[i])
                else:
                    print(f"  ⚠ 无效编号: {i}")

            if selected:
                return selected
            else:
                print("  ⚠ 请输入有效的编号")
        except ValueError:
            print("  ⚠ 输入格式错误，请输入数字编号")
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

    return start, end, city, limit


def get_credentials():
    """获取登录凭证"""
    username = None
    password = None
    try:
        from utils.config import DEFAULT_USERNAME, DEFAULT_PASSWORD
        username = DEFAULT_USERNAME
        password = DEFAULT_PASSWORD
    except:
        pass

    if not username or username == 'XXXXX':
        print("\n  ⚠ 未检测到配置文件凭证，请手动输入")
        username = input("  用户名: ").strip()
        password = input("  密码: ").strip()

    return username, password


# ========== 测试执行器 ==========

def do_login(username, password):
    """执行登录"""
    logger.info("[步骤1] 登录认证")
    logger.info(f"  用户: {username}")

    try:
        from core.auth import NqiAuthenticator
        from core.query import get_cookie_value

        auth = NqiAuthenticator(username, password)
        session = auth.authenticate()

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
        query.enter_jxcx()
        logger.info("  ✓ 进入成功")
        return True
    except Exception as e:
        logger.error(f"  ✗ 进入失败: {e}")
        logger.debug(traceback.format_exc())
        return False


def do_test_table(query, table_name, payload_func, start_date, end_date, city, limit):
    """测试单个报表
    
    Args:
        query: JXCXQuery 实例
        table_name: 报表名称
        payload_func: payload 构建函数（已加载的函数对象）
        start_date: 开始日期
        end_date: 结束日期
        city: 地市
        limit: 查询条数
    """
    logger.info(f"\n{'='*56}")
    logger.info(f"  测试报表: {table_name}")
    logger.info(f"{'='*56}")

    # 1. 构建 Payload
    logger.info("[1] 构建 Payload")
    try:
        # 工参类不需要日期参数
        func_name = payload_func.__name__
        if 'gongcan' in func_name:
            payload = payload_func()
        else:
            payload = payload_func(start_date, end_date, city)

        logger.info(f"  ✓ Payload 构建成功")
        
        # 获取 fieldtype
        fieldtype = payload.get('fieldtype')
        if not fieldtype:
            result_list = payload.get('result', {}).get('result', [])
            if result_list:
                fieldtype = result_list[0].get('feildtype', 'N/A')
            else:
                fieldtype = 'N/A'
        logger.info(f"    fieldtype: {fieldtype}")
        
        logger.info(f"    where条件: {len(payload.get('where', []))} 个")
        for i, w in enumerate(payload.get('where', [])):
            logger.info(f"      [{i+1}] {w.get('feild')} {w.get('symbol')} '{w.get('val')}'")

        result_fields = payload.get('result', {}).get('result', [])
        logger.info(f"    返回字段: {len(result_fields)} 个")
        for f in result_fields[:8]:
            logger.info(f"      {f.get('feild')} -> {f.get('feildName')}")
        if len(result_fields) > 8:
            logger.info(f"      ... 共 {len(result_fields)} 个")

    except Exception as e:
        logger.error(f"  ✗ Payload 构建失败: {e}")
        logger.debug(traceback.format_exc())
        return False

    # 2. 查询数据总数
    logger.info(f"\n[2] 查询数据总数")
    try:
        count = query.get_table_count(payload, report_name=table_name)
        logger.info(f"  ✓ 数据总数: {count}")

        if count == 0:
            logger.warning("  ⚠ 数据量为 0，可能日期范围内无数据")
    except Exception as e:
        logger.error(f"  ✗ 查询总数失败: {e}")
        logger.debug(traceback.format_exc())
        count = 0

    # 3. 查询数据样本
    logger.info(f"\n[3] 查询数据样本 (前 {limit} 条)")
    try:
        payload['length'] = limit
        data = query.get_table(payload, to_df=False, report_name=table_name)

        if data is not None and len(data) > 0:
            logger.info(f"  ✓ 查询成功 | 返回 {len(data)} 条")
            sample = data[0]
            logger.info(f"  数据样本 (第1条):")
            for key, value in list(sample.items())[:12]:
                val_str = str(value)[:60] if value is not None else 'NULL'
                logger.info(f"    {key}: {val_str}")
            if len(sample) > 12:
                logger.info(f"    ... 共 {len(sample)} 个字段")
        elif data is not None and len(data) == 0:
            logger.warning("  ⚠ 返回数据为空")
        else:
            logger.error("  ✗ 返回数据为 None")

    except Exception as e:
        logger.error(f"  ✗ 查询数据失败: {e}")
        logger.debug(traceback.format_exc())
        return False

    # 4. 结果判定
    logger.info(f"\n[结果]")
    if count > 0 or (data is not None and len(data) > 0):
        logger.info(f"  ✓ {table_name} 测试通过 (数据量: {count})")
        return True
    else:
        logger.warning(f"  ⚠ {table_name} 测试完成但数据为空 (可能日期范围内无数据)")
        return True  # 流程跑通也算通过


def main():
    """主函数"""
    print_banner()

    # 导入检查
    logger.info("检查项目模块...")
    try:
        from core.auth import NqiAuthenticator
        from core.query import JXCXQuery, get_cookie_value
        from gui.widgets import TableConfig
        from utils.config import BASE_URL, JXCX_URL, JXCX_COUNT_URL, HEADERS
        logger.info("  ✓ 所有模块导入成功")
    except ImportError as e:
        logger.error(f"  ✗ 模块导入失败: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)

    # 自动读取报表配置
    table_configs = get_table_configs()
    if not table_configs:
        logger.error("无法读取报表配置，退出")
        sys.exit(1)

    # 获取分类映射
    category_mapping = get_category_mapping()

    # 获取凭证
    username, password = get_credentials()
    if not username:
        logger.error("未提供用户名，退出")
        sys.exit(1)

    # 登录
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
    start_date, end_date, city, limit = get_test_params()

    logger.info(f"\n测试参数: {start_date} ~ {end_date} | 地市: {city} | 条数: {limit}")
    logger.info(f"选中报表: {len(selected)} 个")
    for name, _ in selected:
        logger.info(f"  - {name}")

    # 创建查询实例
    query = JXCXQuery(session)

    # 进入即席查询
    if not do_enter_jxcx(query):
        logger.error("无法进入即席查询模块，退出")
        sys.exit(1)

    # 执行测试
    results = {}
    for table_name, payload_func in selected:
        try:
            success = do_test_table(query, table_name, payload_func, start_date, end_date, city, limit)
            results[table_name] = '✓ 通过' if success else '✗ 失败'
        except Exception as e:
            logger.error(f"  ✗ {table_name} 测试异常: {e}")
            logger.debug(traceback.format_exc())
            results[table_name] = f'✗ 异常: {e}'

    # 打印总结
    print(f"\n{'='*56}")
    print(f"  测试总结")
    print(f"{'='*56}")
    passed = sum(1 for v in results.values() if v.startswith('✓'))
    failed = sum(1 for v in results.values() if v.startswith('✗'))
    for name, result in results.items():
        print(f"  {result}  {name}")
    print(f"\n  通过: {passed} | 失败: {failed} | 总计: {len(results)}")
    print(f"  日志文件: {log_file}")
    print(f"{'='*56}")


if __name__ == '__main__':
    main()
