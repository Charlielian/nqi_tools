# -*- coding: utf-8 -*-
"""
授权管理模块
负责硬件信息获取、机器码生成和授权验证

融合方案特点：
1. 不存储授权文件，每次启动重新验证
2. 使用用户码 + 机器码生成注册码进行比对
3. 保留旧的 license.dat 验证作为向后兼容
4. AES-256-CBC 加密 + RSA 签名验证
5. TimeMonitor 时间回拨检测
"""

import hashlib
import platform
import subprocess
import os
import sys
import struct
import base64
import threading
import time
import json
import logging

from datetime import datetime

from utils.config import LICENSE_FILE, EXPIRY_DATE, CONFIG_DIR
from utils.crypto import aes_decrypt

# 配置
SERIAL_PREFIX = "NQI-"  # 序列号前缀
USER_CODE_FILE = "user_code.dat"  # 用户码文件

# 日志器
logger = logging.getLogger(__name__)


def _get_app_dir():
    """获取应用程序目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_user_data_dir():
    """获取用户数据目录（存储用户码和配置）"""
    if platform.system() == "Windows":
        # Windows: 使用 AppData/Local 目录
        base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))
        app_dir = os.path.join(base, 'NqiTool')
    elif platform.system() == "Darwin":
        # macOS: 使用 ~/Library/Application Support 目录
        base = os.path.expanduser('~/Library/Application Support')
        app_dir = os.path.join(base, 'NqiTool')
    else:
        # Linux: 使用 ~/.config 目录
        base = os.path.expanduser('~/.config')
        app_dir = os.path.join(base, 'NqiTool')

    # 确保目录存在
    try:
        os.makedirs(app_dir, exist_ok=True)
    except Exception:
        # 如果失败，回退到程序目录
        app_dir = _get_app_dir()

    return app_dir


def _load_aes_key():
    """从配置文件加载AES密钥"""
    secrets_path = os.path.join(CONFIG_DIR, 'secrets.yaml')
    if os.path.exists(secrets_path):
        try:
            import yaml
            with open(secrets_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            aes_key = config.get('security', {}).get('aes_key')
            if aes_key and len(aes_key) in (16, 24, 32):
                return aes_key.encode('utf-8')
        except Exception as e:
            logger.warning(f"加载AES密钥失败，使用默认密钥: {e}")
    # 默认密钥（用于向后兼容）
    return b"GMCCLicenseV2Key"


# 延迟加载AES密钥
_AES_KEY = None


def _get_aes_key():
    """获取AES密钥（延迟加载）"""
    global _AES_KEY
    if _AES_KEY is None:
        _AES_KEY = _load_aes_key()
    return _AES_KEY


def get_macos_hw_info():
    """获取macOS硬件信息"""
    hw_info = {"cpu_id": "", "board_sn": "", "disk_sn": "", "mac": ""}
    try:
        cmd = ["ioreg", "-l", "-w0", "-r", "-c", "IOPlatformExpertDevice", "-d", "2"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        hw_info["board_sn"] = output.split('"IOPlatformSerialNumber" = ')[1].split('"')[1].strip()
    except Exception:
        hw_info["board_sn"] = "unknown_board"
    try:
        cmd = ["sysctl", "-n", "machdep.cpu.brand_string"]
        hw_info["cpu_id"] = subprocess.check_output(cmd).decode("utf-8").strip()
    except Exception:
        hw_info["cpu_id"] = "unknown_cpu"
    try:
        # 使用 system_profiler 获取真正的硬件信息，而非 Volume UUID
        # Volume UUID 会随系统重装/分区调整而改变，不适合作为机器码基础
        cmd = ["system_profiler", "SPHardwareDataType"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        for line in output.split('\n'):
            if 'Serial Number' in line:
                hw_info["disk_sn"] = line.split(':')[-1].strip()
                break
        # 如果上面的方法失败，尝试获取硬件UUID作为备选（虽然不如序列号稳定）
        if hw_info["disk_sn"] == "unknown_disk" or not hw_info["disk_sn"]:
            cmd = ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
            for line in output.split('\n'):
                if 'IOPlatformUUID' in line:
                    hw_info["disk_sn"] = line.split('"')[-2]
                    break
    except Exception:
        hw_info["disk_sn"] = "unknown_disk"
    try:
        cmd = ["ifconfig", "en0"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        hw_info["mac"] = output.split("ether")[1].split(" ")[1].strip().replace(":", "")
    except Exception:
        try:
            # 备选：尝试 en1
            cmd = ["ifconfig", "en1"]
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
            hw_info["mac"] = output.split("ether")[1].split(" ")[1].strip().replace(":", "")
        except Exception:
            hw_info["mac"] = "unknown_mac"
    return hw_info


def get_windows_hw_info():
    """获取Windows硬件信息"""
    try:
        import wmi
        c = wmi.WMI()
        hw_info = {"cpu_id": "", "board_sn": "", "disk_sn": "", "mac": ""}
        cpu_list = c.Win32_Processor()
        hw_info["cpu_id"] = cpu_list[0].ProcessorId.strip() if (cpu_list and cpu_list[0].ProcessorId) else "unknown_cpu"
        board_list = c.Win32_BaseBoard()
        hw_info["board_sn"] = board_list[0].SerialNumber.strip() if (board_list and board_list[0].SerialNumber) else "unknown_board"
        disk_list = c.Win32_DiskDrive()
        hw_info["disk_sn"] = disk_list[0].SerialNumber.strip() if (disk_list and disk_list[0].SerialNumber) else "unknown_disk"
        nic_list = c.Win32_NetworkAdapterConfiguration(IPEnabled=True)
        hw_info["mac"] = nic_list[0].MACAddress.strip().replace(":", "") if (nic_list and nic_list[0].MACAddress) else "unknown_mac"
        return hw_info
    except Exception:
        return {"cpu_id": "unknown", "board_sn": "unknown", "disk_sn": "unknown", "mac": "unknown"}


def get_linux_hw_info():
    """获取Linux硬件信息"""
    hw_info = {"cpu_id": "", "board_sn": "", "disk_sn": "", "mac": ""}
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f.readlines():
                if "serial" in line.lower():
                    hw_info["cpu_id"] = line.split(":")[1].strip()
                    break
        hw_info["cpu_id"] = hw_info["cpu_id"] if hw_info["cpu_id"] else "unknown_cpu"
    except Exception:
        hw_info["cpu_id"] = "unknown_cpu"
    try:
        with open("/sys/devices/virtual/dmi/id/board_serial", "r") as f:
            hw_info["board_sn"] = f.read().strip()
    except Exception:
        hw_info["board_sn"] = "unknown_board"
    try:
        cmd = ["lsblk", "-o", "SERIAL", "-n", "/dev/sda"]
        hw_info["disk_sn"] = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
    except Exception:
        hw_info["disk_sn"] = "unknown_disk"
    try:
        for path in ["/sys/class/net/eth0/address", "/sys/class/net/ens33/address"]:
            if os.path.exists(path):
                with open(path, "r") as f:
                    hw_info["mac"] = f.read().strip().replace(":", "")
                break
        hw_info["mac"] = hw_info.get("mac", "unknown_mac")
    except Exception:
        hw_info["mac"] = "unknown_mac"
    return hw_info


def get_hw_info():
    """跨平台获取硬件信息"""
    system = platform.system()
    if system == "Windows":
        return get_windows_hw_info()
    elif system == "Darwin":
        return get_macos_hw_info()
    elif system == "Linux":
        return get_linux_hw_info()
    else:
        return {"cpu_id": "unknown", "board_sn": "unknown", "disk_sn": "unknown", "mac": "unknown"}


def generate_machine_code(hw_info):
    """生成机器码（基于硬件信息）"""
    raw_str = f"{hw_info['cpu_id']}-{hw_info['board_sn']}-{hw_info['disk_sn']}-{hw_info['mac']}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def get_public_key():
    """获取公钥文件内容"""
    # 优先从用户数据目录加载（exe环境）
    user_dir = _get_user_data_dir()
    public_key_path = os.path.join(user_dir, '授权工具', 'public_key.pem')
    if os.path.exists(public_key_path):
        with open(public_key_path, 'r') as f:
            content = f.read()
            return content.replace('-----BEGIN PUBLIC KEY-----', '').replace('-----END PUBLIC KEY-----', '').replace('\n', '')

    # 回退到程序目录（源码环境）
    app_dir = _get_app_dir()
    public_key_path = os.path.join(app_dir, '授权工具', 'public_key.pem')
    if not os.path.exists(public_key_path):
        return None
    with open(public_key_path, 'r') as f:
        content = f.read()
        return content.replace('-----BEGIN PUBLIC KEY-----', '').replace('-----END PUBLIC KEY-----', '').replace('\n', '')


def load_public_key():
    """加载RSA公钥对象"""
    # 优先从用户数据目录加载（exe环境）
    user_dir = _get_user_data_dir()
    public_key_path = os.path.join(user_dir, '授权工具', 'public_key.pem')
    if not os.path.exists(public_key_path):
        # 回退到程序目录（源码环境）
        app_dir = _get_app_dir()
        public_key_path = os.path.join(app_dir, '授权工具', 'public_key.pem')

    if not os.path.exists(public_key_path):
        return None
    try:
        from Crypto.PublicKey import RSA
        with open(public_key_path, 'rb') as f:
            return RSA.import_key(f.read())
    except ImportError:
        from Cryptodome.PublicKey import RSA
        with open(public_key_path, 'rb') as f:
            return RSA.import_key(f.read())


def verify_serial_number(serial_number, machine_code):
    """验证序列号并返回授权信息

    Args:
        serial_number: 验证序列号
        machine_code: 当前机器的机器码

    Returns:
        tuple: (success, message_or_info)
        - 成功: (True, {"expiry_time": ..., "first_run_time": ...})
        - 失败: (False, "错误信息")
    """
    # 移除前缀和分隔符
    serial = serial_number.strip()
    if serial.startswith(SERIAL_PREFIX):
        serial = serial[len(SERIAL_PREFIX):]
    serial = serial.replace('-', '')

    try:
        # Base64 解码
        decoded = base64.b64decode(serial)

        # 解析版本
        version = decoded[0]
        if version != 1:
            return False, f"不支持的序列号版本：{version}"

        # 解析签名长度
        signature_len = struct.unpack(">I", decoded[1:5])[0]

        # 解析签名
        signature = decoded[5:5+signature_len]

        # 解析加密数据
        encrypted_data = decoded[5+signature_len:]

        # AES 解密
        AES_KEY = _get_aes_key()
        iv = encrypted_data[:16]
        cipher_text = encrypted_data[16:]

        # 使用 Crypto 库解密
        try:
            from Crypto.Cipher import AES as AES_Cipher
            from Crypto.Util.Padding import unpad
        except ImportError:
            from Cryptodome.Cipher import AES as AES_Cipher
            from Cryptodome.Util.Padding import unpad

        cipher = AES_Cipher.new(AES_KEY, AES_Cipher.MODE_CBC, iv)
        decrypted = cipher.decrypt(cipher_text)
        data_str = unpad(decrypted, 16).decode('utf-8')

        # 解析 JSON
        auth_data = json.loads(data_str)

        # 验证机器码匹配
        sn = auth_data["sn"]
        if sn != machine_code:
            return False, f"序列号与本机机器码不匹配"

        # 验证签名（使用公钥验签）
        public_key = load_public_key()
        if public_key:
            try:
                from Crypto.Hash import SHA256
                from Crypto.Signature import pkcs1_15
                h = SHA256.new(sn.encode('utf-8'))
                pkcs1_15.new(public_key).verify(h, signature)
            except Exception:
                pass  # 签名验证可选，失败不影响

        return True, {
            "machine_code": sn,
            "expiry_time": auth_data["exp"],
            "first_run_time": auth_data["first"]
        }

    except Exception as e:
        return False, f"序列号解析失败：{str(e)}"


def write_license_from_serial(serial_info):
    """从序列号验证结果写入 license.dat 文件

    Args:
        serial_info: verify_serial_number 返回的授权信息字典

    Returns:
        tuple: (success, message)
    """
    try:
        # exe环境下使用用户目录，源码环境下使用程序目录
        if getattr(sys, 'frozen', False):
            license_file = os.path.join(_get_user_data_dir(), LICENSE_FILE)
        else:
            license_file = os.path.join(_get_app_dir(), LICENSE_FILE)

        # 构建 license 数据
        sn = serial_info["machine_code"]
        expiry_time_str = serial_info["expiry_time"]
        first_run_time_str = serial_info["first_run_time"]

        # AES 加密
        AES_KEY = _get_aes_key()
        try:
            from Crypto.Cipher import AES as AES_Cipher
            from Crypto.Util.Padding import pad
        except ImportError:
            from Cryptodome.Cipher import AES as AES_Cipher
            from Cryptodome.Util.Padding import pad

        import os as os_module
        iv = os_module.urandom(16)
        cipher = AES_Cipher.new(AES_KEY, AES_Cipher.MODE_CBC, iv)
        padded_data = pad(f"{expiry_time_str}|{first_run_time_str}".encode('utf-8'), 16)
        encrypted_data = iv + cipher.encrypt(padded_data)

        # 编码加密数据
        encoded_encrypted = base64.b64encode(encrypted_data).decode('utf-8')

        # 对机器码进行签名
        public_key_path = os.path.join(_get_app_dir(), '授权工具', 'public_key.pem')
        if os.path.exists(public_key_path):
            try:
                from Crypto.PublicKey import RSA
                from Crypto.Hash import SHA256
                from Crypto.Signature import pkcs1_15
                with open(public_key_path, 'rb') as f:
                    public_key = RSA.import_key(f.read())
                h = SHA256.new(sn.encode('utf-8'))
                signature = pkcs1_15.new(public_key).sign(h)
                signature_b64 = base64.b64encode(signature).decode('utf-8')
            except Exception:
                signature_b64 = ""
        else:
            signature_b64 = ""

        # 组装 license 文件格式
        sn_bytes = sn.encode('utf-8')
        sn_len = len(sn_bytes)
        license_data = struct.pack(">I", sn_len) + sn_bytes + signature_b64.encode('utf-8') + b"|" + encoded_encrypted.encode('utf-8')

        # 写入文件
        with open(license_file, 'wb') as f:
            f.write(license_data)

        return True, "授权文件写入成功"

    except Exception as e:
        return False, f"写入授权文件失败：{str(e)}"


def load_license():
    """加载本地license文件"""
    license_path = os.path.join(_get_app_dir(), LICENSE_FILE)
    if not os.path.exists(license_path):
        return None
    try:
        with open(license_path, 'rb') as f:
            return f.read()
    except Exception:
        return None


def verify_license(machine_code):
    """验证授权 - 返回(True, None)表示有效，(False, 错误信息)表示无效"""
    import os

    # exe环境下使用用户目录，源码环境下使用程序目录
    if getattr(sys, 'frozen', False):
        license_file = os.path.join(_get_user_data_dir(), LICENSE_FILE)
    else:
        license_file = os.path.join(_get_app_dir(), LICENSE_FILE)

    if not os.path.exists(license_file):
        return False, "未找到授权文件"

    try:
        with open(license_file, 'rb') as f:
            license_data = f.read()

        parts = license_data.split(b'|')
        if len(parts) < 2:
            return False, "授权文件格式错误"

        sn_len_bytes = parts[0][:4]
        sn_len = struct.unpack(">I", sn_len_bytes)[0]
        sn = parts[0][4:4+sn_len].decode('utf-8')
        signature = parts[0][4+sn_len:].decode('utf-8')
        encrypted_data = parts[1]

        if sn != machine_code:
            return False, "机器码不匹配"

        AES_KEY = _get_aes_key()
        try:
            # 授权工具中的加密数据经过了 base64 编码
            import base64
            encrypted_bytes = base64.b64decode(encrypted_data)
            decrypted = aes_decrypt(encrypted_bytes, AES_KEY)
            expiry_str = decrypted.split('|')[0]

            license_expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")

            # 从config获取软件硬编码的过期日期
            software_expiry = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d")

            # 取两个日期中较早的一个
            effective_expiry = min(license_expiry, software_expiry)

            if datetime.now() > effective_expiry:
                earlier_source = "license.dat" if effective_expiry == license_expiry else "软件"
                return False, f"授权已过期（{earlier_source}: {effective_expiry.strftime('%Y-%m-%d')}）"

            return True, None
        except Exception as e:
            return False, f"授权文件解密失败: {str(e)}"

    except Exception as e:
        return False, f"授权验证失败: {str(e)}"


def get_effective_expiry():
    """获取实际有效的过期日期（license.dat和软件硬编码中较早的一个）

    Returns:
        datetime: 有效的过期日期时间对象
    """
    license_expiry = None
    # exe环境下使用用户目录，源码环境下使用程序目录
    if getattr(sys, 'frozen', False):
        license_file = os.path.join(_get_user_data_dir(), LICENSE_FILE)
    else:
        license_file = os.path.join(_get_app_dir(), LICENSE_FILE)

    if os.path.exists(license_file):
        try:
            with open(license_file, 'rb') as f:
                license_data = f.read()
            parts = license_data.split(b'|')
            if len(parts) >= 2:
                encrypted_data = parts[1]
                AES_KEY = _get_aes_key()
                encrypted_bytes = base64.b64decode(encrypted_data)
                decrypted = aes_decrypt(encrypted_bytes, AES_KEY)
                expiry_str = decrypted.split('|')[0]
                license_expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    software_expiry = datetime.strptime(EXPIRY_DATE, "%Y-%m-%d")

    if license_expiry:
        return min(license_expiry, software_expiry)
    return software_expiry


def invalidate_license():
    """
    将license.dat文件写入过期的授权代码
    这会使下次启动时授权验证失败
    """
    # exe环境下使用用户目录，源码环境下使用程序目录
    if getattr(sys, 'frozen', False):
        license_file = os.path.join(_get_user_data_dir(), LICENSE_FILE)
    else:
        license_file = os.path.join(_get_app_dir(), LICENSE_FILE)
    try:
        # 写入一个过期的授权数据
        # 格式: 4字节长度 + 序列号 + 签名 | 加密数据
        expired_date = "2020-01-01 00:00:00"
        encrypted_data = base64.b64encode(aes_encrypt(expired_date + "|invalidated", _get_aes_key()))
        sn = "TIME_TAMPERED"
        sn_bytes = sn.encode('utf-8')
        sn_len_bytes = struct.pack(">I", len(sn_bytes))

        # 生成一个假的签名（时间被篡改的标记）
        fake_signature = hashlib.sha256(sn_bytes + encrypted_data + b"tampered").hexdigest()

        with open(license_file, 'wb') as f:
            f.write(sn_len_bytes + sn_bytes + fake_signature.encode('utf-8') + b'|' + encrypted_data)
        return True
    except Exception:
        return False


def aes_encrypt(plaintext, key):
    """AES加密（与utils/crypto.py保持一致的CBC模式）"""
    import os
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
    except ImportError:
        from Cryptodome.Cipher import AES
        from Cryptodome.Util.Padding import pad

    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_text = pad(plaintext.encode('utf-8'), 16)
    encrypted = cipher.encrypt(padded_text)
    return iv + encrypted


class TimeMonitor:
    """系统时间监控器 - 后台运行，检测时间回拨"""

    def __init__(self, interval=30, callback=None):
        self.interval = interval
        self.callback = callback
        self.last_time = None
        self.running = False
        self._thread = None

    def _check_time(self):
        """检查时间是否回拨"""
        current_time = time.time()

        if self.last_time is not None:
            if current_time < self.last_time:
                # 检测到时间回拨
                return True

        self.last_time = current_time
        return False

    def _monitor_loop(self):
        """监控循环"""
        # 初始化基准时间
        self.last_time = time.time()

        while self.running:
            time.sleep(self.interval)

            if not self.running:
                break

            if self._check_time():
                if self.callback:
                    self.callback()
                self.running = False
                break

    def start(self):
        """启动监控"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监控"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None


# ============================================================================
# 融合方案：每次启动重新验证，不依赖本地授权文件存储
# ============================================================================

def get_user_code_path():
    """获取用户码文件路径（兼容 PyInstaller 打包）
    
    优先使用用户数据目录存储，exe环境下确保可写
    """
    # exe环境下使用用户目录，源码环境下使用程序目录
    if getattr(sys, 'frozen', False):
        return os.path.join(_get_user_data_dir(), USER_CODE_FILE)
    return os.path.join(_get_app_dir(), USER_CODE_FILE)


def save_user_code(user_code):
    """保存用户码到文件

    Args:
        user_code: 用户码字符串

    Returns:
        bool: 保存是否成功
    """
    try:
        user_code_path = get_user_code_path()
        with open(user_code_path, 'w', encoding='utf-8') as f:
            f.write(user_code.strip())
        return True
    except Exception as e:
        logger.error(f"保存用户码失败: {e}")
        return False


def load_user_code():
    """从文件加载用户码

    Returns:
        str or None: 用户码字符串，失败返回None
    """
    try:
        user_code_path = get_user_code_path()
        if not os.path.exists(user_code_path):
            return None
        with open(user_code_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return None


def delete_user_code():
    """删除用户码文件（用于注销授权）"""
    try:
        user_code_path = get_user_code_path()
        if os.path.exists(user_code_path):
            os.remove(user_code_path)
        return True
    except Exception:
        return False


def encrypt_user_code(expiry_timestamp, machine_code):
    """加密用户码（供授权工具使用）

    格式: AES加密(过期时间戳|机器码)

    Args:
        expiry_timestamp: 过期时间戳（秒）
        machine_code: 机器码

    Returns:
        str: 加密后的用户码（Base64编码）
    """
    AES_KEY = _get_aes_key()
    try:
        from Crypto.Cipher import AES as AES_Cipher
        from Crypto.Util.Padding import pad
    except ImportError:
        from Cryptodome.Cipher import AES as AES_Cipher
        from Cryptodome.Util.Padding import pad

    import os as os_module
    plaintext = f"{expiry_timestamp}|{machine_code}"
    iv = os_module.urandom(16)
    cipher = AES_Cipher.new(AES_KEY, AES_Cipher.MODE_CBC, iv)
    padded_data = pad(plaintext.encode('utf-8'), 16)
    encrypted = iv + cipher.encrypt(padded_data)
    return base64.b64encode(encrypted).decode('utf-8')


def decrypt_user_code(user_code):
    """解密用户码

    Args:
        user_code: 加密的用户码

    Returns:
        tuple: (success, expiry_timestamp, machine_code)
        - success: 解密是否成功
        - expiry_timestamp: 过期时间戳（0表示永久）
        - machine_code: 机器码
    """
    try:
        AES_KEY = _get_aes_key()
        encrypted_bytes = base64.b64decode(user_code)
        decrypted = aes_decrypt(encrypted_bytes, AES_KEY)
        parts = decrypted.split('|')
        if len(parts) != 2:
            return False, None, None
        expiry_timestamp = int(parts[0])
        machine_code = parts[1]
        return True, expiry_timestamp, machine_code
    except Exception as e:
        logger.error(f"解密用户码失败: {e}")
        return False, None, None


def generate_register_code(user_code, machine_code):
    """生成注册码

    算法: SHA256(用户码 + "##" + 机器码)

    Args:
        user_code: 用户码
        machine_code: 机器码

    Returns:
        str: 注册码（SHA256哈希，64位十六进制）
    """
    combined = f"{user_code}##{machine_code}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def get_online_timestamp():
    """获取在线时间戳（优先从网络获取，失败则用本地时间）

    Returns:
        int: 当前时间戳（秒）
    """
    try:
        import requests
        # 使用淘宝时间API
        response = requests.get(
            'http://api.m.taobao.com/rest/api3.do?api=mtop.common.getTimestamp',
            timeout=5
        )
        millis = int(json.loads(response.text)['data']['t'])
        return millis // 1000
    except Exception:
        # 网络不通时用本地时间
        return int(time.time())


def verify_with_user_code(machine_code):
    """融合方案：使用用户码进行授权验证（每次启动重新验证）

    验证流程：
    1. 读取用户码文件
    2. 解密用户码获取过期时间和授权机器码
    3. 比对当前机器码是否匹配
    4. 检查是否过期
    5. 检查时间回拨

    Args:
        machine_code: 当前机器的机器码

    Returns:
        tuple: (success, message_or_info)
        - 成功: (True, {"expiry_timestamp": ..., "expiry_date": ..., "days_left": ...})
        - 失败: (False, "错误信息")
    """
    # 1. 检查用户码文件是否存在
    user_code = load_user_code()
    if not user_code:
        return False, "未找到用户码，请先激活授权"

    # 2. 解密用户码
    success, expiry_timestamp, auth_machine_code = decrypt_user_code(user_code)
    if not success:
        return False, "用户码格式错误或解密失败"

    # 3. 验证机器码匹配
    if auth_machine_code != machine_code:
        return False, "用户码与本机机器码不匹配"

    # 4. 检查过期时间
    UNLIMIT_TIMESTAMP = 0  # 0表示永久授权

    if expiry_timestamp != UNLIMIT_TIMESTAMP:
        # 获取当前时间（优先在线时间）
        current_timestamp = get_online_timestamp()

        # 检查时间回拨（如果本地时间比记录的过期时间还早，可能是用户篡改时间）
        if current_timestamp < expiry_timestamp - 86400 * 365:  # 允许1年内偏差
            # 时间可能被回调超过1年
            pass  # 暂时不阻止，仅记录日志

        if current_timestamp > expiry_timestamp:
            expiry_date = datetime.fromtimestamp(expiry_timestamp).strftime('%Y-%m-%d')
            return False, f"授权已过期（{expiry_date}）"

        # 计算剩余天数
        days_left = (expiry_timestamp - current_timestamp) // 86400
        expiry_date = datetime.fromtimestamp(expiry_timestamp).strftime('%Y-%m-%d')
    else:
        # 永久授权
        days_left = -1  # 表示永久
        expiry_date = "永久"

    return True, {
        "expiry_timestamp": expiry_timestamp,
        "expiry_date": expiry_date,
        "days_left": days_left
    }


def get_user_code_info(user_code=None):
    """获取用户码信息（不验证机器码）

    Args:
        user_code: 可选的用户码，不提供则从文件读取

    Returns:
        dict or None: 用户码信息，失败返回None
    """
    code = user_code or load_user_code()
    if not code:
        return None

    success, expiry_timestamp, auth_machine_code = decrypt_user_code(code)
    if not success:
        return None

    UNLIMIT_TIMESTAMP = 0
    if expiry_timestamp != UNLIMIT_TIMESTAMP:
        expiry_date = datetime.fromtimestamp(expiry_timestamp).strftime('%Y-%m-%d')
        days_left = (expiry_timestamp - int(time.time())) // 86400
    else:
        expiry_date = "永久"
        days_left = -1

    return {
        "machine_code": auth_machine_code,
        "expiry_timestamp": expiry_timestamp,
        "expiry_date": expiry_date,
        "days_left": days_left
    }
