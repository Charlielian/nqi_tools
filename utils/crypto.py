# -*- coding: utf-8 -*-
"""
加密工具模块
提供RSA加密、AES加密等加密功能
"""

import base64

try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.Cipher import AES as AES_Cipher
    from Crypto.Util.Padding import pad, unpad
except ModuleNotFoundError:
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Cipher import PKCS1_v1_5
    from Cryptodome.Cipher import AES as AES_Cipher
    from Cryptodome.Util.Padding import pad, unpad


def rsa_encrypt(data, public_key):
    """RSA加密"""
    public_key = '-----BEGIN PUBLIC KEY-----\n' + public_key + '\n-----END PUBLIC KEY-----'
    rsa_key = RSA.importKey(public_key)
    cipher = PKCS1_v1_5.new(rsa_key)
    encrypted_data = base64.b64encode(cipher.encrypt(data.encode(encoding="utf-8")))
    return encrypted_data.decode('utf-8')


def aes_encrypt(plain_text, key):
    """AES加密"""
    import os
    iv = os.urandom(16)
    cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
    padded_data = pad(plain_text.encode("utf-8"), 16)
    encrypted_data = cipher.encrypt(padded_data)
    return iv + encrypted_data


def aes_decrypt(encrypted_data, key):
    """AES解密"""
    iv = encrypted_data[:16]
    cipher = AES_Cipher.new(key, AES_Cipher.MODE_CBC, iv)
    decrypted_data = cipher.decrypt(encrypted_data[16:])
    return unpad(decrypted_data, 16).decode('utf-8')


def rsa_sign(data, private_key):
    """RSA签名"""
    from Crypto.Hash import SHA256
    from Crypto.Signature import pkcs1_15
    h = SHA256.new(data.encode("utf-8"))
    signature = pkcs1_15.new(private_key).sign(h)
    return base64.b64encode(signature).decode('utf-8')


def rsa_verify(data, signature, public_key):
    """RSA验签"""
    from Crypto.Hash import SHA256
    from Crypto.Signature import pkcs1_15
    try:
        public_key = '-----BEGIN PUBLIC KEY-----\n' + public_key + '\n-----END PUBLIC KEY-----'
        rsa_key = RSA.importKey(public_key)
        h = SHA256.new(data.encode("utf-8"))
        pkcs1_15.new(rsa_key).verify(h, base64.b64decode(signature))
        return True
    except Exception:
        return False
