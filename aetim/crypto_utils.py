#!/usr/bin/env python3
"""
AETIM 密碼加密工具模組
功能：提供 AES-256-GCM 加密/解密功能，符合 ISO 27001:2022 規範
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import os
import base64
import sys

def get_encryption_key():
    """
    取得加密密鑰（優先順序：環境變數 > 密鑰檔案）
    
    Returns:
        bytes: 32 bytes 加密密鑰，如果未設定則返回 None
    """
    # 優先從環境變數讀取
    key = os.environ.get('AETIM_ENCRYPTION_KEY')
    if key:
        # 如果是 base64 編碼，解碼；否則直接使用
        try:
            decoded_key = base64.b64decode(key)
            if len(decoded_key) >= 32:
                return decoded_key[:32]
            else:
                # 如果長度不足，補零到 32 bytes
                return decoded_key.ljust(32, b'\0')
        except:
            # 如果不是 base64，直接使用字串（補零到 32 bytes）
            key_bytes = key.encode('utf-8')
            return key_bytes[:32].ljust(32, b'\0')
    
    # 從密鑰檔案讀取
    key_file = os.path.join('/app', '.aetim_key')
    if os.path.exists(key_file):
        try:
            with open(key_file, 'rb') as f:
                key_data = f.read()
                if len(key_data) >= 32:
                    return key_data[:32]
                else:
                    return key_data.ljust(32, b'\0')
        except Exception as e:
            print(f"警告：無法讀取密鑰檔案 {key_file}：{e}", file=sys.stderr)
            return None
    
    return None

def encrypt_password(password: str) -> str:
    """
    加密密碼
    
    Args:
        password: 明碼密碼
        
    Returns:
        加密字串格式：ENCRYPTED:<ciphertext>:<nonce>:<tag>
        
    Raises:
        ValueError: 如果加密密鑰未設定
    """
    key = get_encryption_key()
    if not key:
        raise ValueError("加密密鑰未設定（請設定 AETIM_ENCRYPTION_KEY 環境變數或建立 .aetim_key 檔案）")
    
    if len(key) < 32:
        raise ValueError("加密密鑰長度不足（需要至少 32 bytes）")
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96 bits nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, password.encode('utf-8'), None)
    
    # 分離密文和認證標籤（GCM 模式）
    tag = ciphertext[-16:]
    ciphertext_only = ciphertext[:-16]
    
    # Base64 編碼
    ciphertext_b64 = base64.b64encode(ciphertext_only).decode('utf-8')
    nonce_b64 = base64.b64encode(nonce).decode('utf-8')
    tag_b64 = base64.b64encode(tag).decode('utf-8')
    
    return f"ENCRYPTED:{ciphertext_b64}:{nonce_b64}:{tag_b64}"

def decrypt_password(encrypted_str: str) -> str:
    """
    解密密碼
    
    Args:
        encrypted_str: 加密字串（格式：ENCRYPTED:...）
        
    Returns:
        明碼密碼
        
    Raises:
        ValueError: 如果解密失敗或格式錯誤
    """
    if not encrypted_str or not isinstance(encrypted_str, str):
        return encrypted_str  # 不是字串，直接返回
    
    if not encrypted_str.startswith('ENCRYPTED:'):
        return encrypted_str  # 不是加密字串，直接返回
    
    try:
        parts = encrypted_str.split(':')
        if len(parts) != 4:
            raise ValueError("加密字串格式錯誤：應為 ENCRYPTED:<ciphertext>:<nonce>:<tag>")
        
        _, ciphertext_b64, nonce_b64, tag_b64 = parts
        
        # Base64 解碼
        ciphertext_only = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)
        tag = base64.b64decode(tag_b64)
        
        # 合併密文和認證標籤
        ciphertext = ciphertext_only + tag
        
        # 解密
        key = get_encryption_key()
        if not key:
            raise ValueError("加密密鑰未設定（請設定 AETIM_ENCRYPTION_KEY 環境變數或建立 .aetim_key 檔案）")
        
        if len(key) < 32:
            raise ValueError("加密密鑰長度不足（需要至少 32 bytes）")
        
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext.decode('utf-8')
    except Exception as e:
        raise ValueError(f"解密失敗：{str(e)}")

def get_smtp_password(config_value):
    """
    取得 SMTP 密碼（支援環境變數、加密字串、明碼）
    
    優先順序：
    1. 環境變數 EMAIL_PASSWORD
    2. 加密字串（ENCRYPTED:...）
    3. 環境變數引用（${EMAIL_PASSWORD}）
    4. 明碼（發出警告）
    
    Args:
        config_value: config.yaml 中的密碼值
        
    Returns:
        str: 明碼密碼
    """
    # 優先檢查環境變數
    env_password = os.environ.get('EMAIL_PASSWORD')
    if env_password:
        return env_password
    
    # 檢查是否為加密字串
    if isinstance(config_value, str) and config_value.startswith('ENCRYPTED:'):
        try:
            return decrypt_password(config_value)
        except Exception as e:
            print(f"警告：解密 SMTP 密碼失敗：{e}", file=sys.stderr)
            print("警告：將嘗試使用原始值，但可能無法正常運作", file=sys.stderr)
            return config_value
    
    # 檢查是否為環境變數引用
    if isinstance(config_value, str) and config_value.startswith('${'):
        expanded = os.path.expandvars(config_value)
        if expanded != config_value:
            return expanded
    
    # 明碼（發出警告）
    if isinstance(config_value, str) and config_value and not config_value.startswith('${'):
        # 檢查是否為預設值或範例值
        if config_value not in ['your_password', 'YOUR_PASSWORD', '']:
            print("警告：config.yaml 中使用明碼 SMTP 密碼，建議改用環境變數或加密字串", file=sys.stderr)
            print("警告：明碼密碼不符合 ISO 27001:2022 規範，請參考密碼加密遷移指南", file=sys.stderr)
    
    return config_value

