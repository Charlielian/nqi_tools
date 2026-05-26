# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载和管理应用程序配置
"""

import os
import sys
import yaml

# ========== 全局 SSL 配置 ==========
# 企业内部系统可能使用自签名证书，禁用 SSL 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_base_path():
    """获取程序运行的基础路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    current_file = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(current_file))


def get_app_path():
    """获取应用程序所在目录（EXE所在目录）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    current_file = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(current_file))


def get_default_config():
    """获取默认配置"""
    return {
        'auth': {
            'username': 'XXXXX',
            'password': 'XXXX'
        },
        'paths': {
            'output_dir': './data_output',
            'cookie_dir': './cookies',
            'captcha_dir': './captcha_images',
            'log_dir': './logs'
        },
        'server': {
            'base_url': 'https://nqi.gmcc.net:20443'
        }
    }


def create_default_config(config_path):
    """创建默认配置文件

    Args:
        config_path: 配置文件路径
    """
    default_config = get_default_config()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write("# NQI工具配置文件\n")
            f.write("# 请根据实际情况修改以下内容\n\n")
            yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"[INFO] 已创建默认配置文件: {config_path}")
    except Exception as e:
        print(f"警告：创建默认配置文件失败: {e}")


def load_config():
    """从 YAML 文件加载配置

    如果 EXE 同目录下没有 config.yaml，会自动创建一个默认配置文件
    """
    config = get_default_config()

    app_path = get_app_path()
    config_file = os.path.join(app_path, 'config.yaml')

    # 优先使用 EXE 同目录的配置文件
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    config.update(yaml_config)
        except Exception as e:
            print(f"警告：加载配置文件失败 ({config_file}): {e}")
    else:
        # EXE 同目录没有配置文件，尝试读取打包内部的配置
        base_path = get_base_path()
        internal_config_file = os.path.join(base_path, 'config.yaml')

        if os.path.exists(internal_config_file):
            try:
                with open(internal_config_file, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        config.update(yaml_config)
            except Exception as e:
                print(f"警告：加载内部配置文件失败: {e}")

        # 在 EXE 同目录创建默认配置文件（方便用户修改）
        create_default_config(config_file)

    return config


_config = load_config()

DEFAULT_USERNAME = _config['auth']['username']
DEFAULT_PASSWORD = _config['auth']['password']
OUTPUT_DIR = _config['paths']['output_dir']
COOKIE_DIR = _config['paths']['cookie_dir']
CAPTCHA_DIR = _config['paths']['captcha_dir']
LOG_DIR = _config['paths']['log_dir']

BASE_URL = _config['server']['base_url']
LOGIN_URL = f'{BASE_URL}/cas/login?service={BASE_URL}/pro-portal/'
CAPTCHA_URL = f'{BASE_URL}/cas/captcha.jpg'
GET_CONFIG_URL = f'{BASE_URL}/cas/getConfig'
SEND_CODE_URL = f'{BASE_URL}/cas/sendCode1'
JXCX_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getTable'
JXCX_COUNT_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getTableCount'
JXCX_SEARCH_URL = f'{BASE_URL}/pro-adhoc/adhocquery/search'
JXCX_TABLE_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getSelectTable'

# ========== 聚类工单查询API ==========
LTESCHEME_BASE = f'{BASE_URL}/pro-ltemr-cicd/modules/disquery'
GET_GRID_URL = f'{LTESCHEME_BASE}/getgrid'                           # 获取责任网格
GET_PROBLEM_LABEL_URL = f'{LTESCHEME_BASE}/getproblemlabel'           # 获取问题标签（旧接口）
GET_PROBLEM_LABEL_BY_DATA_URL = f'{LTESCHEME_BASE}/getproblemlabelByData'  # 获取问题标签（带日期参数）
QUERY_PROPOSAL_URL = f'{LTESCHEME_BASE}/queryProposal'               # 聚类工单查询主接口

MAX_SINGLE_QUERY = 500000

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Origin': BASE_URL,
    'Referer': f'{BASE_URL}/pro-adhoc/',
    'x-requested-with': 'XMLHttpRequest',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
}

HEADERS_JSON = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
    'Content-Type': 'application/json'
}

EXPIRY_DATE = "2026-09-30"
LICENSE_FILE = "license.dat"

# 配置目录（与app_path相同，用于存放secrets.yaml等配置文件）
CONFIG_DIR = get_app_path()
