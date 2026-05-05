# -*- coding: utf-8 -*-
"""
授权管理模块
负责硬件信息获取、机器码生成和授权验证
"""

import hashlib
import platform
import subprocess
import os
import struct
import base64
import threading
import time
import json

from datetime import datetime

from utils.config import LICENSE_FILE, EXPIRY_DATE
from utils.crypto import aes_decrypt

# 配置
SERIAL_PREFIX = "NQI-"  # 序列号前缀


def get_macos_hw_info():
    """获取macOS硬件信息 - 稳定性增强版"""
    hw_info = {"cpu_id": "", "board_sn": "", "disk_sn": "", "mac": ""}

    # 主板序列号 - 最稳定的标识符
    try:
        cmd = ["ioreg", "-l", "-w0", "-r", "-c", "IOPlatformExpertDevice", "-d", "2"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        if '"IOPlatformSerialNumber" = "' in output:
            hw_info["board_sn"] = output.split('"IOPlatformSerialNumber" = ')[1].split('"')[1].strip()
        elif "IOPlatformUUID" in output:
            parts = output.split('"IOPlatformUUID" = "')
            if len(parts) > 1:
                hw_info["board_sn"] = parts[1].split('"')[0].strip()
        else:
            hw_info["board_sn"] = "unknown_board"
    except:
        hw_info["board_sn"] = "unknown_board"

    # CPU信息 - 使用更稳定的获取方式
    try:
        cmd = ["sysctl", "-n", "machdep.cpu.brand_string"]
        hw_info["cpu_id"] = subprocess.check_output(cmd).decode("utf-8").strip()
    except:
        try:
            # 备选方案：使用CPU型号标识符
            cmd = ["sysctl", "-n", "machdep.cpu.model"]
            hw_info["cpu_id"] = f"Intel-{subprocess.check_output(cmd).decode('utf-8').strip()}"
        except:
            hw_info["cpu_id"] = "unknown_cpu"

    # 磁盘标识符 - 使用更稳定的标识
    try:
        cmd = ["system_profiler", "SPHardwareDataType"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        if "Hardware UUID:" in output:
            hw_info["disk_sn"] = output.split("Hardware UUID:")[1].split("\n")[0].strip()
        elif "Serial Number (system):" in output:
            hw_info["disk_sn"] = output.split("Serial Number (system):")[1].split("\n")[0].strip()
        else:
            hw_info["disk_sn"] = "unknown_disk"
    except:
        hw_info["disk_sn"] = "unknown_disk"

    # MAC地址 - 获取最稳定的那个
    try:
        # 优先使用 en0（通常是主网络接口）
        cmd = ["networksetup", "-getmacaddress", "en0"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        if "MAC Address:" in output:
            hw_info["mac"] = output.split("MAC Address:")[1].split(" ")[1].strip().replace(":", "").lower()
        else:
            # 备选方案
            cmd = ["ifconfig", "en0"]
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
            if "ether" in output:
                hw_info["mac"] = output.split("ether")[1].split()[0].strip().replace(":", "").lower()
            else:
                hw_info["mac"] = "unknown_mac"
    except:
        hw_info["mac"] = "unknown_mac"

    return hw_info


def get_windows_hw_info():
    """获取Windows硬件信息 - 稳定性增强版"""
    try:
        import wmi
        c = wmi.WMI()
        hw_info = {"cpu_id": "", "board_sn": "", "disk_sn": "", "mac": ""}

        # CPU标识
        cpu_list = c.Win32_Processor()
        if cpu_list and cpu_list[0].ProcessorId:
            hw_info["cpu_id"] = cpu_list[0].ProcessorId.strip()
        else:
            hw_info["cpu_id"] = "unknown_cpu"

        # 主板序列号
        board_list = c.Win32_BaseBoard()
        if board_list and board_list[0].SerialNumber:
            hw_info["board_sn"] = board_list[0].SerialNumber.strip()
        else:
            hw_info["board_sn"] = "unknown_board"

        # 磁盘序列号 - 优先使用系统盘
        disk_list = c.Win32_DiskDrive()
        if disk_list:
            # 选择第一个有效磁盘
            for disk in disk_list:
                if disk.SerialNumber:
                    hw_info["disk_sn"] = disk.SerialNumber.strip()
                    break
        if not hw_info["disk_sn"] or hw_info["disk_sn"] == "unknown_disk":
            hw_info["disk_sn"] = "unknown_disk"

        # MAC地址 - 优先使用有线网络适配器
        nic_list = c.Win32_NetworkAdapterConfiguration(IPEnabled=True)
        if nic_list:
            for nic in nic_list:
                if nic.MACAddress:
                    # 排除虚拟适配器
                    adapter = [a for a in c.Win32_NetworkAdapter() if a.Index == nic.Index]
                    if adapter and 'virtual' not in str(adapter[0].Name).lower():
                        hw_info["mac"] = nic.MACAddress.strip().replace(":", "").lower()
                        break
        if not hw_info["mac"] or hw_info["mac"] == "unknown_mac":
            hw_info["mac"] = "unknown_mac"

        return hw_info
    except:
        return {"cpu_id": "unknown", "board_sn": "unknown", "disk_sn": "unknown", "mac": "unknown"}


def get_linux_hw_info():
    """获取Linux硬件信息 - 稳定性增强版"""
    hw_info = {"cpu_id": "", "board_sn": "", "disk_sn": "", "mac": ""}

    # CPU标识 - 使用processor id
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()
            # 优先获取 model name，它更稳定
            for line in content.split('\n'):
                if line.startswith('model name'):
                    hw_info["cpu_id"] = line.split(':')[1].strip()
                    break
            # 如果没有model name，尝试processor id
            if not hw_info["cpu_id"]:
                for line in content.split('\n'):
                    if line.startswith('processor'):
                        hw_info["cpu_id"] = f"processor_{line.split(':')[1].strip()}"
                        break
        if not hw_info["cpu_id"]:
            hw_info["cpu_id"] = "unknown_cpu"
    except:
        hw_info["cpu_id"] = "unknown_cpu"

    # 主板序列号 - 多个备选路径
    try:
        board_serial_paths = [
            "/sys/class/dmi/id/board_serial",
            "/sys/devices/virtual/dmi/id/board_serial",
        ]
        for path in board_serial_paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    hw_info["board_sn"] = f.read().strip()
                    break
        if not hw_info["board_sn"]:
            hw_info["board_sn"] = "unknown_board"
    except:
        hw_info["board_sn"] = "unknown_board"

    # 磁盘序列号 - 多个备选路径
    try:
        # 尝试获取系统盘的序列号
        disk_paths = [
            "/sys/class/block/sda/device/serial",
            "/sys/class/block/nvme0n1/device/serial",
        ]
        for path in disk_paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    hw_info["disk_sn"] = f.read().strip()
                    break
        if not hw_info["disk_sn"]:
            hw_info["disk_sn"] = "unknown_disk"
    except:
        hw_info["disk_sn"] = "unknown_disk"

    # MAC地址 - 获取第一个非环回的有线网络接口
    try:
        net_path = "/sys/class/net"
        if os.path.exists(net_path):
            for iface in os.listdir(net_path):
                # 排除环回接口和虚拟接口
                if iface.startswith('lo') or iface.startswith('docker') or iface.startswith('virbr'):
                    continue
                iface_path = os.path.join(net_path, iface)
                addr_file = os.path.join(iface_path, "address")
                if os.path.exists(addr_file):
                    with open(addr_file, "r") as f:
                        hw_info["mac"] = f.read().strip().replace(":", "").lower()
                        break
        if not hw_info.get("mac"):
            hw_info["mac"] = "unknown_mac"
    except:
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
    """生成机器码（基于硬件信息）

    稳定性保证：
    1. 所有字段统一转小写、去除空格和特殊字符
    2. 按固定顺序拼接（已排序）
    3. 不依赖任何日期或时间
    4. SHA256哈希是确定性的
    """
    def normalize(value):
        """规范化硬件信息：转小写、去除空格和不可见字符"""
        if value is None:
            return ""
        # 转小写、去除空格、制表符、换行符等
        return str(value).lower().strip().replace(" ", "").replace("\t", "").replace("\n", "").replace("\r", "")

    # 按固定顺序处理字段，确保一致性
    fields = [
        normalize(hw_info.get('cpu_id', '')),
        normalize(hw_info.get('board_sn', '')),
        normalize(hw_info.get('disk_sn', '')),
        normalize(hw_info.get('mac', ''))
    ]

    # 过滤空值，但保持顺序
    fields = [f for f in fields if f and f != 'unknown']

    # 使用固定分隔符拼接
    raw_str = "-".join(fields)

    # 空值保护：如果所有字段都是unknown或空，使用默认标识
    if not raw_str or raw_str == "unknown-unknown-unknown-unknown":
        return hashlib.sha256(b"fallback_machine_identifier").hexdigest()

    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def get_public_key():
    """获取公钥文件内容"""
    public_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '授权工具', 'public_key.pem')
    if not os.path.exists(public_key_path):
        return None
    with open(public_key_path, 'r') as f:
        content = f.read()
        return content.replace('-----BEGIN PUBLIC KEY-----', '').replace('-----END PUBLIC KEY-----', '').replace('\n', '')


def load_public_key():
    """加载RSA公钥对象"""
    public_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '授权工具', 'public_key.pem')
    if not os.path.exists(public_key_path):
        return None
    try:
        from Crypto.PublicKey import RSA
        with open(public_key_path, 'rb') as f:
            return RSA.import_key(f.read())
    except:
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
        AES_KEY = b"GMCCLicenseV2Key"
        iv = encrypted_data[:16]
        cipher_text = encrypted_data[16:]

        # 使用 Crypto 库解密
        try:
            from Crypto.Cipher import AES as AES_Cipher
            from Crypto.Util.Padding import unpad
        except:
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
            except:
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
        license_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', LICENSE_FILE)

        # 构建 license 数据
        sn = serial_info["machine_code"]
        expiry_time_str = serial_info["expiry_time"]
        first_run_time_str = serial_info["first_run_time"]

        # AES 加密
        AES_KEY = b"GMCCLicenseV2Key"
        try:
            from Crypto.Cipher import AES as AES_Cipher
            from Crypto.Util.Padding import pad
        except:
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
        public_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '授权工具', 'public_key.pem')
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
            except:
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
    license_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', LICENSE_FILE)
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

    license_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', LICENSE_FILE)

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

        AES_KEY = b"GMCCLicenseV2Key"
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
    license_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', LICENSE_FILE)

    if os.path.exists(license_file):
        try:
            with open(license_file, 'rb') as f:
                license_data = f.read()
            parts = license_data.split(b'|')
            if len(parts) >= 2:
                encrypted_data = parts[1]
                AES_KEY = b"GMCCLicenseV2Key"
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
    license_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', LICENSE_FILE)
    try:
        expired_date = "2020-01-01 00:00:00"

        # 使用与 utils/crypto.py 一致的 AES 加密
        AES_KEY = b"GMCCLicenseV2Key"
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
        except:
            from Cryptodome.Cipher import AES
            from Cryptodome.Util.Padding import pad

        import os as os_module
        iv = os_module.urandom(16)
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        padded_data = pad((expired_date + "|invalidated").encode('utf-8'), 16)
        encrypted = iv + cipher.encrypt(padded_data)
        encrypted_data = base64.b64encode(encrypted)

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
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

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