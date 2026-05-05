# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载和管理应用程序配置
"""

import os
import sys
import yaml


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


def load_config():
    """从 YAML 文件加载配置"""
    config = {
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

    app_path = get_app_path()
    config_file = os.path.join(app_path, 'config.yaml')

    if not os.path.exists(config_file):
        base_path = get_base_path()
        config_file = os.path.join(base_path, 'config.yaml')

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    config.update(yaml_config)
        except Exception as e:
            print(f"警告：加载配置文件失败 ({config_file}): {e}")
    else:
        print(f"[INFO] 未找到配置文件 ({config_file})，使用默认配置")

    return config


_config = load_config()

DEFAULT_USERNAME = _config['auth']['username']
DEFAULT_PASSWORD = _config['auth']['password']
OUTPUT_DIR = _config['paths']['output_dir']
COOKIE_DIR = _config['paths']['cookie_dir']
CAPTCHA_DIR = _config['paths']['captcha_dir']
LOG_DIR = _config['paths']['log_dir']

BASE_URL = _config['server']['base_url']
HOST_HEADER = BASE_URL.replace('https://', '')
LOGIN_URL = f'{BASE_URL}/cas/login?service={BASE_URL}/pro-portal/'
CAPTCHA_URL = f'{BASE_URL}/cas/captcha.jpg'
GET_CONFIG_URL = f'{BASE_URL}/cas/getConfig'
SEND_CODE_URL = f'{BASE_URL}/cas/sendCode1'
JXCX_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getTable'
JXCX_COUNT_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getTableCount'
JXCX_SEARCH_URL = f'{BASE_URL}/pro-adhoc/adhocquery/search'
JXCX_TABLE_URL = f'{BASE_URL}/pro-adhoc/adhocquery/getSelectTable'

MAX_SINGLE_QUERY = 500000

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
}

HEADERS_JSON = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
    'Content-Type': 'application/json'
}

EXPIRY_DATE = "2026-06-30"
LICENSE_FILE = "license.dat"
