# -*- coding: utf-8 -*-
"""
RSA 密钥对生成工具
用于生成授权用的公钥和私钥，并自动注入到主程序

使用方法：
    python generate_rsa_keys.py
    - 生成 private_key.pem（私钥，妥善保管！）
    - 生成 public_key.pem（公钥，内嵌到程序中）
    - 自动更新 universal_extractor_gui.py 中的 RSA_PUBLIC_KEY
"""
import os
import re
from Crypto.PublicKey import RSA

# 密钥文件路径
PRIVATE_KEY_FILE = "private_key.pem"
PUBLIC_KEY_FILE = "public_key.pem"
MAIN_PROGRAM_FILE = "../universal_extractor_gui.py"


def generate_rsa_keypair(key_size=2048):
    """生成 RSA 密钥对"""
    print(f"正在生成 {key_size} 位的 RSA 密钥对...")

    # 生成 RSA 密钥对
    key = RSA.generate(key_size)

    # 导出私钥
    private_key = key.export_key()
    with open(PRIVATE_KEY_FILE, 'wb') as f:
        f.write(private_key)
    print(f"私钥已保存到: {os.path.abspath(PRIVATE_KEY_FILE)}")

    # 导出公钥
    public_key = key.publickey().export_key()
    with open(PUBLIC_KEY_FILE, 'wb') as f:
        f.write(public_key)
    print(f"公钥已保存到: {os.path.abspath(PUBLIC_KEY_FILE)}")

    return private_key, public_key


def inject_public_key_to_main(public_key_pem):
    """将公钥注入到主程序"""
    main_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), MAIN_PROGRAM_FILE)

    if not os.path.exists(main_file):
        print(f"警告：未找到主程序文件 {main_file}")
        return False

    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换 RSA_PUBLIC_KEY 配置
    new_key = public_key_pem.decode('utf-8').strip()

    # 使用正则匹配 RSA_PUBLIC_KEY 整个定义
    pattern = r'# RSA 公钥.*?\nRSA_PUBLIC_KEY = """.*?"""'
    replacement = f'# RSA 公钥（自动生成，请勿修改）\nRSA_PUBLIC_KEY = """{new_key}"""'

    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    if new_content == content:
        print("警告：未找到 RSA_PUBLIC_KEY 配置位置")
        return False

    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"已将公钥注入到: {os.path.abspath(main_file)}")
    return True


def load_public_key_pem():
    """读取公钥 PEM 内容"""
    if os.path.exists(PUBLIC_KEY_FILE):
        with open(PUBLIC_KEY_FILE, 'rb') as f:
            return f.read().decode('utf-8')
    return None


def load_private_key():
    """读取私钥"""
    if os.path.exists(PRIVATE_KEY_FILE):
        with open(PRIVATE_KEY_FILE, 'rb') as f:
            return RSA.import_key(f.read())
    return None


def main():
    """主函数"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)  # 切换到脚本所在目录

    print("=" * 60)
    print("   RSA 密钥对生成工具")
    print("=" * 60)
    print("\n注意：")
    print("  - 私钥 (private_key.pem) 必须妥善保管！")
    print("  - 私钥丢失将无法生成新的授权文件")
    print("  - 公钥将自动注入到主程序")
    print()

    # 检查是否已存在密钥
    if os.path.exists(PRIVATE_KEY_FILE):
        response = input("检测到已存在密钥，是否重新生成？(y/N): ").strip().lower()
        if response != 'y':
            print("已取消。")
            return

    private_key, public_key = generate_rsa_keypair()

    # 自动注入到主程序
    print("\n正在注入公钥到主程序...")
    if inject_public_key_to_main(public_key):
        print("\n注入成功！主程序已配置 RSA 公钥。")
    else:
        print("\n注入失败，请手动复制公钥到主程序。")
        print("\n公钥内容（手动复制到 RSA_PUBLIC_KEY）：")
        print("=" * 60)
        print(public_key.decode('utf-8'))
        print("=" * 60)

    print("\n密钥生成完成！")


if __name__ == '__main__':
    main()
