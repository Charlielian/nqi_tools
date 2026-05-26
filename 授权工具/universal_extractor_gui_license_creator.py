# -*- coding: utf-8 -*-
"""
免审批导出工具 - 授权文件生成器

融合方案：生成用户码（不再生成 license.dat）
用户码格式: Base64(AES加密(过期时间戳|机器码))
"""

import os
import sys
import base64
from datetime import datetime

# 加密依赖
try:
    from Crypto.Cipher import AES as AES_Cipher
    from Crypto.Util.Padding import pad
except ModuleNotFoundError:
    from Cryptodome.Cipher import AES as AES_Cipher
    from Cryptodome.Util.Padding import pad

# 配置
LICENSE_AES_KEY = b"GMCCLicenseV2Key"  # 必须与主程序一致


def validate_machine_code(machine_code):
    """验证机器码格式"""
    machine_code = machine_code.strip()
    if len(machine_code) != 64:
        return False, f"机器码长度应为64位，当前为{len(machine_code)}位"
    try:
        int(machine_code, 16)
        return True, None
    except ValueError:
        return False, "机器码包含非法字符"


def aes_encrypt(plaintext, key):
    """AES加密"""
    import os
    iv = os.urandom(16)
    cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
    padded_data = pad(plaintext.encode("utf-8"), 16)
    encrypted_data = cipher.encrypt(padded_data)
    return iv + encrypted_data


def create_user_code(machine_code, expiry_date):
    """生成用户码

    用户码格式: Base64(AES加密(过期时间戳|机器码))
    """
    # 验证机器码
    valid, error = validate_machine_code(machine_code)
    if not valid:
        return False, error

    # 计算过期时间戳
    expiry_datetime = expiry_date.replace(hour=23, minute=59, second=59)
    expiry_timestamp = int(expiry_datetime.timestamp())

    # 构建明文数据
    plaintext = f"{expiry_timestamp}|{machine_code}"

    # AES 加密
    encrypted_data = aes_encrypt(plaintext, LICENSE_AES_KEY)

    # Base64 编码
    user_code = base64.b64encode(encrypted_data).decode('utf-8')

    return True, user_code


def main():
    """主函数"""
    if sys.version_info < (3, 6):
        print("要求Python 3.6及以上版本")
        sys.exit(1)

    print("=" * 60)
    print("   授权文件生成器（融合方案）")
    print("=" * 60)

    print("\n使用说明：")
    print("  1. 用户运行程序，获取机器码")
    print("  2. 用户将机器码发给管理员")
    print("  3. 管理员运行本脚本，输入机器码和授权截止日期")
    print("  4. 管理员将生成的用户码发给用户")
    print("  5. 用户在程序中输入用户码即可完成授权")
    print("\n" + "=" * 60)

    # 获取机器码
    while True:
        machine_code = input("\n请输入用户的机器码：").strip()
        if machine_code:
            valid, error = validate_machine_code(machine_code)
            if valid:
                break
            print(f"错误：{error}")
        else:
            print("错误：机器码不能为空")

    # 获取授权截止日期
    while True:
        expiry_str = input("\n请输入授权截止日期（格式：YYYY-MM-DD，例如：2026-12-31）：").strip()
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                if expiry_date < datetime.now():
                    print("警告：截止日期早于今天，授权将立即过期！")
                break
            except ValueError:
                print("错误：日期格式不正确，请使用 YYYY-MM-DD 格式")
        else:
            print("错误：截止日期不能为空")

    print("\n" + "=" * 60)

    # 生成用户码
    success, result = create_user_code(machine_code, expiry_date)
    if success:
        print("用户码已生成：")
        print()
        print(f"  {result}")
        print()
        print(f"机器码：{machine_code}")
        print(f"过期时间：{expiry_date.strftime('%Y-%m-%d 23:59:59')}")
        print()
        print("请将此用户码发送给用户，用户在程序中输入即可完成授权。")
    else:
        print(f"生成失败：{result}")
        sys.exit(1)


if __name__ == '__main__':
    main()
