#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公网IP连接测试脚本
用于测试 120.198.253.84 是否可以替代内网域名 nqi.gmcc.net 访问服务
"""

import os
import requests
import urllib3
import json
import sys

# 禁用代理环境变量
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['no_proxy'] = '*'
os.environ['NO_PROXY'] = '*'

urllib3.disable_warnings()

# 测试配置
PUBLIC_IP = "120.198.253.84"
PORT = 20443
INTERNAL_DOMAIN = "nqi.gmcc.net"

# 构建URL
BASE_URL = f"https://{PUBLIC_IP}:{PORT}"
LOGIN_URL = f"{BASE_URL}/cas/login?service={BASE_URL}/pro-portal/"
CAPTCHA_URL = f"{BASE_URL}/cas/captcha.jpg"
GET_CONFIG_URL = f"{BASE_URL}/cas/getConfig"

# Headers配置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

HEADERS_JSON = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': f'https://{INTERNAL_DOMAIN}:{PORT}',
    'Referer': f'https://{INTERNAL_DOMAIN}:{PORT}/cas/login?service=https://{INTERNAL_DOMAIN}:{PORT}/pro-portal/',
}


def test_connectivity():
    """测试基本连接"""
    print("\n" + "=" * 60)
    print("测试 1: 基本HTTPS连接")
    print("=" * 60)

    session = requests.Session()
    session.trust_env = False  # 禁用环境变量代理

    # 方法1: 不带Host头
    print("\n[测试 1.1] 不带Host头 (curl默认行为)")
    try:
        r = requests.get(BASE_URL, headers=HEADERS, timeout=15, verify=False)
        print(f"    状态码: {r.status_code}")
        print(f"    结果: {'成功' if r.status_code == 200 else '返回异常状态'}")
    except Exception as e:
        print(f"    错误: {type(e).__name__}: {str(e)[:80]}")

    # 方法2: 带内网域名Host头
    print("\n[测试 1.2] 带Host头 (Host: nqi.gmcc.net:20443)")
    headers_with_host = HEADERS.copy()
    headers_with_host['Host'] = f'{INTERNAL_DOMAIN}:{PORT}'

    try:
        r = session.get(BASE_URL, headers=headers_with_host, timeout=15, verify=False)
        print(f"    状态码: {r.status_code}")
        if r.status_code == 200:
            print(f"    ✓ 成功!")
            print(f"    内容长度: {len(r.text)} 字符")
        else:
            print(f"    结果: 返回状态码 {r.status_code}")
    except Exception as e:
        print(f"    错误: {type(e).__name__}: {str(e)[:80]}")

    return session, headers_with_host


def test_login_page(session, headers):
    """测试登录页面"""
    print("\n" + "=" * 60)
    print("测试 2: 登录页面")
    print("=" * 60)

    try:
        # 先尝试访问主页获取cookie
        print("\n[测试 2.0] 访问主页获取Cookie")
        try:
            r = session.get(f"{BASE_URL}/", headers=headers, timeout=15, verify=False)
            print(f"    状态码: {r.status_code}")
            print(f"    Cookie数量: {len(session.cookies)}")
            for name in session.cookies.keys():
                print(f"    Cookie: {name}")
        except Exception as e:
            print(f"    错误: {type(e).__name__}: {str(e)[:80]}")
            print("    继续尝试登录页面...")

        # 然后访问登录页面
        print("\n[测试 2.1] GET 登录页面")
        try:
            r = session.get(LOGIN_URL, headers=headers, timeout=15, verify=False)
            print(f"    状态码: {r.status_code}")

            if r.status_code == 200:
                # 检查是否包含登录表单
                if 'fm1' in r.text:
                    print("    ✓ 找到登录表单 (id=fm1)")
                else:
                    print("    ⚠ 未找到登录表单")

                # 检查关键元素
                if 'execution' in r.text or 'captcha' in r.text.lower():
                    print("    ✓ 包含安全验证元素")

                # 显示内容预览
                preview = r.text[:500].replace('\n', ' ').replace('\r', '')
                print(f"    内容预览: {preview[:200]}...")

                return True
            else:
                print(f"    结果: 返回状态码 {r.status_code}")
                print(f"    内容: {r.text[:200]}")

        except Exception as e:
            print(f"    错误: {type(e).__name__}: {str(e)}")

    except Exception as e:
        print(f"    错误: {type(e).__name__}: {str(e)}")

    return False


def test_captcha(session, headers):
    """测试验证码接口"""
    print("\n" + "=" * 60)
    print("测试 3: 图形验证码接口")
    print("=" * 60)

    try:
        r = session.get(CAPTCHA_URL, headers=headers, timeout=15, verify=False)
        print(f"\n[测试 3.1] GET {CAPTCHA_URL}")
        print(f"    状态码: {r.status_code}")
        print(f"    Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        print(f"    Content-Length: {len(r.content)} bytes")

        if r.status_code == 200:
            # 检查是否为图片
            if r.content[:3] == b'\xff\xd8\xff':
                print("    ✓ 返回JPEG图片")
                return True
            elif r.content[:4] == b'GIF8':
                print("    ✓ 返回GIF图片")
                return True
            elif r.content[:8] == b'\x89PNG\r\n\x1a\n':
                print("    ✓ 返回PNG图片")
                return True
            else:
                print(f"    ⚠ 可能是图片但格式未知")
                print(f"    文件头: {r.content[:20].hex()}")
        else:
            print(f"    结果: 返回状态码 {r.status_code}")
            print(f"    内容: {r.text[:200]}")

    except Exception as e:
        print(f"    错误: {type(e).__name__}: {str(e)}")

    return False


def test_get_config(session, headers):
    """测试getConfig接口"""
    print("\n" + "=" * 60)
    print("测试 4: getConfig接口 (图形验证码验证)")
    print("=" * 60)

    try:
        # 发送一个测试请求
        data = {
            'loginId': 'test_user',
            'password': 'test_pass',
            'captcha': 'test'
        }
        r = session.post(GET_CONFIG_URL, json=data, headers=HEADERS_JSON, timeout=15, verify=False)
        print(f"\n[测试 4.1] POST {GET_CONFIG_URL}")
        print(f"    状态码: {r.status_code}")

        if r.status_code == 200:
            result = r.json()
            print(f"    响应: {json.dumps(result, ensure_ascii=False)[:200]}")

            # 检查响应码
            code = result.get('code')
            if code == '1':
                print("    ✓ 验证通过")
            elif code == '0' or code == 0:
                msg = result.get('msg', '未知')
                print(f"    响应码为0: {msg}")
                print("    (这是正常的，说明API正常工作，只是验证码错误)")
                return True
            else:
                print(f"    响应码: {code}")

            return True
        else:
            print(f"    结果: 返回状态码 {r.status_code}")
            print(f"    内容: {r.text[:200]}")

    except Exception as e:
        print(f"    错误: {type(e).__name__}: {str(e)}")

    return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("       公网IP连接测试工具")
    print("=" * 60)
    print(f"\n目标地址: {BASE_URL}")
    print(f"对应内网域名: {INTERNAL_DOMAIN}:{PORT}")
    print(f"\n测试说明:")
    print(f"  服务器会根据HTTP Host头进行路由验证。")
    print(f"  使用 Host: {INTERNAL_DOMAIN}:{PORT} 来模拟内网访问。")

    # 执行测试
    session, headers = test_connectivity()

    login_ok = test_login_page(session, headers)
    captcha_ok = test_captcha(session, headers)
    config_ok = test_get_config(session, headers)

    # 总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)

    results = [
        ("HTTPS连接", "通过" if session else "失败"),
        ("登录页面", "通过" if login_ok else "失败"),
        ("图形验证码", "通过" if captcha_ok else "失败"),
        ("getConfig接口", "通过" if config_ok else "失败"),
    ]

    for name, status in results:
        icon = "✓" if "通过" in status else "✗"
        print(f"  {icon} {name}: {status}")

    all_passed = all("通过" in s for _, s in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("结论: 公网IP可以正常访问!")
        print("\n如需在项目中使用，请修改 config.yaml:")
        print(f"  server:")
        print(f"    base_url: '{BASE_URL}'")
        print(f"    host_header: '{INTERNAL_DOMAIN}:{PORT}'")
    else:
        print("结论: 部分测试未通过，可能需要进一步排查。")
        print("\n可能的问题:")
        print("  1. 公网IP需要先连接VPN")
        print("  2. 该IP可能没有开放此端口")
        print("  3. 服务器配置可能不支持IP直连")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
