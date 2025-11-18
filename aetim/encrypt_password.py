#!/usr/bin/env python3
"""
AETIM 密碼加密工具
功能：命令列工具，用於加密和解密 SMTP 密碼

用法：
    加密：python encrypt_password.py <password>
    解密：python encrypt_password.py --decrypt <encrypted_string>
    產生密鑰：python encrypt_password.py --generate-key
"""

import sys
import os
import base64
from crypto_utils import encrypt_password, decrypt_password, get_encryption_key

def generate_key():
    """產生新的加密密鑰"""
    import secrets
    key = secrets.token_bytes(32)
    key_b64 = base64.b64encode(key).decode('utf-8')
    
    print("=" * 60)
    print("新的加密密鑰已產生")
    print("=" * 60)
    print("\n方法1：使用環境變數（推薦）")
    print("在 .env 檔案或系統環境變數中設定：")
    print(f"export AETIM_ENCRYPTION_KEY={key_b64}")
    print("\n方法2：使用密鑰檔案")
    print("將以下內容儲存到 .aetim_key 檔案（權限設為 600）：")
    print(key_b64)
    print("\n注意：請妥善保管此密鑰，遺失將無法解密已加密的密碼")
    print("=" * 60)

def main():
    if len(sys.argv) < 2:
        print("AETIM 密碼加密工具")
        print("=" * 60)
        print("\n用法：")
        print("  加密密碼：")
        print("    python encrypt_password.py <password>")
        print("\n  解密密碼（測試用）：")
        print("    python encrypt_password.py --decrypt <encrypted_string>")
        print("\n  產生新的加密密鑰：")
        print("    python encrypt_password.py --generate-key")
        print("\n範例：")
        print("  python encrypt_password.py 'MyPassword123!'")
        print("  python encrypt_password.py --decrypt ENCRYPTED:xxxxx:yyyyy:zzzzz")
        print("  python encrypt_password.py --generate-key")
        print("\n注意：")
        print("  - 加密前請先設定 AETIM_ENCRYPTION_KEY 環境變數或建立 .aetim_key 檔案")
        print("  - 加密後的密碼字串可設定到 config.yaml 的 smtp_password 欄位")
        print("=" * 60)
        sys.exit(1)
    
    if sys.argv[1] == '--generate-key':
        generate_key()
        sys.exit(0)
    
    if sys.argv[1] == '--decrypt':
        if len(sys.argv) < 3:
            print("錯誤：請提供要解密的字串")
            print("用法：python encrypt_password.py --decrypt <encrypted_string>")
            sys.exit(1)
        
        encrypted_str = sys.argv[2]
        try:
            password = decrypt_password(encrypted_str)
            print("=" * 60)
            print("解密成功")
            print("=" * 60)
            print(f"解密後的密碼：{password}")
            print("=" * 60)
        except Exception as e:
            print(f"錯誤：解密失敗：{e}")
            print("\n可能的原因：")
            print("  1. 加密字串格式錯誤")
            print("  2. 加密密鑰未設定或不正確")
            print("  3. 加密字串已損壞")
            sys.exit(1)
    else:
        password = sys.argv[1]
        
        # 檢查密鑰是否設定
        key = get_encryption_key()
        if not key:
            print("錯誤：加密密鑰未設定")
            print("\n請先設定加密密鑰：")
            print("  方法1：設定環境變數")
            print("    export AETIM_ENCRYPTION_KEY=$(openssl rand -base64 32)")
            print("\n  方法2：建立密鑰檔案")
            print("    openssl rand -base64 32 > .aetim_key")
            print("    chmod 600 .aetim_key")
            print("\n或執行以下命令產生密鑰：")
            print("    python encrypt_password.py --generate-key")
            sys.exit(1)
        
        try:
            encrypted = encrypt_password(password)
            print("=" * 60)
            print("加密成功")
            print("=" * 60)
            print(f"加密字串：\n{encrypted}")
            print("\n請將此字串設定到 config.yaml 的 smtp_password 欄位：")
            print(f"  smtp_password: {encrypted}")
            print("\n範例 config.yaml：")
            print("  notification:")
            print("    email:")
            print(f"      smtp_password: {encrypted}")
            print("=" * 60)
        except Exception as e:
            print(f"錯誤：加密失敗：{e}")
            sys.exit(1)

if __name__ == '__main__':
    main()

