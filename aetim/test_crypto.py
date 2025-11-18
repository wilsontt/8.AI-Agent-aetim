#!/usr/bin/env python3
"""
AETIM SMTP 密碼加密功能測試腳本
測試項目：
1. 加密/解密函數測試
2. 密鑰載入測試
3. 錯誤處理測試
4. 環境變數測試
5. 加密字串測試
6. 向後相容性測試
"""

import sys
import os
import base64
import secrets

# 添加當前目錄到路徑
sys.path.insert(0, os.path.dirname(__file__))

def test_encryption_decryption():
    """測試加密/解密函數"""
    print("=" * 60)
    print("測試 1：加密/解密函數")
    print("=" * 60)
    
    try:
        from crypto_utils import encrypt_password, decrypt_password, get_encryption_key
        
        # 產生測試密鑰
        test_key = secrets.token_bytes(32)
        key_b64 = base64.b64encode(test_key).decode('utf-8')
        os.environ['AETIM_ENCRYPTION_KEY'] = key_b64
        
        # 測試密碼
        test_password = "TestPassword123!@#"
        
        # 加密
        encrypted = encrypt_password(test_password)
        print(f"✓ 加密成功")
        print(f"  原始密碼：{test_password}")
        print(f"  加密字串：{encrypted[:50]}...")
        
        # 驗證格式
        if not encrypted.startswith('ENCRYPTED:'):
            print("✗ 錯誤：加密字串格式不正確")
            return False
        
        parts = encrypted.split(':')
        if len(parts) != 4:
            print("✗ 錯誤：加密字串格式不正確（應有 4 個部分）")
            return False
        
        print(f"✓ 加密字串格式正確")
        
        # 解密
        decrypted = decrypt_password(encrypted)
        print(f"✓ 解密成功")
        print(f"  解密後密碼：{decrypted}")
        
        # 驗證
        if decrypted != test_password:
            print(f"✗ 錯誤：解密後的密碼不匹配")
            print(f"  預期：{test_password}")
            print(f"  實際：{decrypted}")
            return False
        
        print(f"✓ 密碼匹配正確")
        
        # 清理
        del os.environ['AETIM_ENCRYPTION_KEY']
        
        print("✓ 測試 1 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 測試 1 失敗：{e}")
        import traceback
        traceback.print_exc()
        return False

def test_key_loading():
    """測試密鑰載入"""
    print("=" * 60)
    print("測試 2：密鑰載入")
    print("=" * 60)
    
    try:
        from crypto_utils import get_encryption_key
        
        # 測試環境變數方式
        test_key = secrets.token_bytes(32)
        key_b64 = base64.b64encode(test_key).decode('utf-8')
        os.environ['AETIM_ENCRYPTION_KEY'] = key_b64
        
        loaded_key = get_encryption_key()
        if loaded_key is None:
            print("✗ 錯誤：無法從環境變數載入密鑰")
            return False
        
        if len(loaded_key) != 32:
            print(f"✗ 錯誤：密鑰長度不正確（預期 32，實際 {len(loaded_key)}）")
            return False
        
        print("✓ 環境變數密鑰載入成功")
        
        # 清理
        del os.environ['AETIM_ENCRYPTION_KEY']
        
        print("✓ 測試 2 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 測試 2 失敗：{e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling():
    """測試錯誤處理"""
    print("=" * 60)
    print("測試 3：錯誤處理")
    print("=" * 60)
    
    try:
        from crypto_utils import encrypt_password, decrypt_password, get_encryption_key
        
        # 測試 3.1：無密鑰時加密
        if 'AETIM_ENCRYPTION_KEY' in os.environ:
            del os.environ['AETIM_ENCRYPTION_KEY']
        
        # 刪除密鑰檔案（如果存在）
        key_file = os.path.join('/app', '.aetim_key')
        if os.path.exists(key_file):
            os.remove(key_file)
        
        try:
            encrypt_password("test")
            print("✗ 錯誤：應該在無密鑰時拋出異常")
            return False
        except ValueError as e:
            if "加密密鑰未設定" in str(e):
                print("✓ 無密鑰時正確拋出異常")
            else:
                print(f"✗ 錯誤：異常訊息不正確：{e}")
                return False
        
        # 測試 3.2：錯誤格式的加密字串
        try:
            decrypt_password("INVALID_FORMAT")
            print("✗ 錯誤：應該在格式錯誤時拋出異常或返回原值")
            # 實際上應該返回原值（不是加密字串）
            result = decrypt_password("INVALID_FORMAT")
            if result == "INVALID_FORMAT":
                print("✓ 非加密字串正確返回原值")
            else:
                print(f"✗ 錯誤：非加密字串處理不正確")
                return False
        except Exception as e:
            print(f"✗ 錯誤：不應該拋出異常：{e}")
            return False
        
        # 測試 3.3：格式錯誤的加密字串
        try:
            decrypt_password("ENCRYPTED:invalid")
            print("✗ 錯誤：應該在格式錯誤時拋出異常")
            return False
        except ValueError as e:
            if "格式錯誤" in str(e) or "解密失敗" in str(e):
                print("✓ 格式錯誤時正確拋出異常")
            else:
                print(f"✗ 錯誤：異常訊息不正確：{e}")
                return False
        
        print("✓ 測試 3 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 測試 3 失敗：{e}")
        import traceback
        traceback.print_exc()
        return False

def test_get_smtp_password():
    """測試 get_smtp_password 函數"""
    print("=" * 60)
    print("測試 4：get_smtp_password 函數")
    print("=" * 60)
    
    try:
        from crypto_utils import get_smtp_password, encrypt_password, decrypt_password
        
        # 設定測試密鑰
        test_key = secrets.token_bytes(32)
        key_b64 = base64.b64encode(test_key).decode('utf-8')
        os.environ['AETIM_ENCRYPTION_KEY'] = key_b64
        
        # 測試 4.1：環境變數優先
        os.environ['EMAIL_PASSWORD'] = 'env_password_123'
        result = get_smtp_password('config_password')
        if result != 'env_password_123':
            print(f"✗ 錯誤：環境變數優先級不正確（預期 env_password_123，實際 {result}）")
            return False
        print("✓ 環境變數優先級正確")
        del os.environ['EMAIL_PASSWORD']
        
        # 測試 4.2：加密字串
        encrypted = encrypt_password('encrypted_password_123')
        result = get_smtp_password(encrypted)
        if result != 'encrypted_password_123':
            print(f"✗ 錯誤：加密字串解密失敗（預期 encrypted_password_123，實際 {result}）")
            return False
        print("✓ 加密字串解密正確")
        
        # 測試 4.3：環境變數引用
        os.environ['EMAIL_PASSWORD'] = 'ref_password_123'
        result = get_smtp_password('${EMAIL_PASSWORD}')
        if result != 'ref_password_123':
            print(f"✗ 錯誤：環境變數引用不正確（預期 ref_password_123，實際 {result}）")
            return False
        print("✓ 環境變數引用正確")
        del os.environ['EMAIL_PASSWORD']
        
        # 測試 4.4：明碼（應該發出警告但返回原值）
        result = get_smtp_password('plain_password_123')
        if result != 'plain_password_123':
            print(f"✗ 錯誤：明碼處理不正確（預期 plain_password_123，實際 {result}）")
            return False
        print("✓ 明碼處理正確（應有警告訊息）")
        
        # 清理
        del os.environ['AETIM_ENCRYPTION_KEY']
        
        print("✓ 測試 4 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 測試 4 失敗：{e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """執行所有測試"""
    print("\n" + "=" * 60)
    print("AETIM SMTP 密碼加密功能 - 單元測試")
    print("=" * 60 + "\n")
    
    results = []
    
    # 執行測試
    results.append(("加密/解密函數", test_encryption_decryption()))
    results.append(("密鑰載入", test_key_loading()))
    results.append(("錯誤處理", test_error_handling()))
    results.append(("get_smtp_password", test_get_smtp_password()))
    
    # 輸出結果
    print("=" * 60)
    print("測試結果摘要")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ 通過" if result else "✗ 失敗"
        print(f"{test_name:30s} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"總計：{len(results)} 個測試")
    print(f"通過：{passed} 個")
    print(f"失敗：{failed} 個")
    print("=" * 60)
    
    return failed == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

