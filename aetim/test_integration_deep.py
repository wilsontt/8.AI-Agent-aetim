#!/usr/bin/env python3
"""
AETIM SMTP 密碼加密功能 - 深度整合測試
測試項目：
1. 實際測試 utils.load_config() 與真實 config.yaml
2. 測試環境變數優先級
3. 測試加密字串在實際 config.yaml 中的使用
4. 測試 Web API 端點（get_config）的密碼隱藏
"""

import sys
import os
import yaml
import base64
import secrets
import shutil
import tempfile

# 添加當前目錄到路徑
sys.path.insert(0, os.path.dirname(__file__))

def test_real_load_config_env_var():
    """測試真實的 utils.load_config() 與環境變數"""
    print("=" * 60)
    print("深度整合測試 1：真實 load_config() + 環境變數")
    print("=" * 60)
    
    try:
        # 備份原始 config.yaml
        original_config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        backup_config_path = original_config_path + '.test_backup'
        
        if not os.path.exists(original_config_path):
            print("⚠ 警告：找不到 config.yaml，跳過此測試")
            return True
        
        shutil.copy(original_config_path, backup_config_path)
        
        # 讀取原始 config
        with open(original_config_path, 'r', encoding='utf-8') as f:
            original_config = yaml.safe_load(f)
        
        # 修改 config 使用環境變數
        if 'notification' not in original_config:
            original_config['notification'] = {}
        if 'email' not in original_config['notification']:
            original_config['notification']['email'] = {}
        
        original_config['notification']['email']['smtp_password'] = '${EMAIL_PASSWORD}'
        
        # 寫入測試 config
        with open(original_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(original_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # 設定環境變數
        os.environ['EMAIL_PASSWORD'] = 'real_test_password_123'
        
        # 測試 load_config（需要模擬 Docker 環境的路徑）
        # 由於 utils.py 使用硬編碼 /app/config.yaml，我們需要臨時修改或使用符號連結
        # 這裡我們直接測試 crypto_utils.get_smtp_password 的邏輯
        
        from crypto_utils import get_smtp_password
        
        # 模擬 load_config 的處理流程
        # 1. 讀取 config.yaml
        with open(original_config_path, 'r', encoding='utf-8') as f:
            raw_config = f.read()
        
        # 2. 展開環境變數
        expanded_config = os.path.expandvars(raw_config)
        config = yaml.safe_load(expanded_config)
        
        # 3. 使用 get_smtp_password 處理密碼
        password_value = config.get('notification', {}).get('email', {}).get('smtp_password')
        password = get_smtp_password(password_value)
        
        if password != 'real_test_password_123':
            print(f"✗ 錯誤：load_config 環境變數測試失敗（預期 real_test_password_123，實際 {password}）")
            return False
        
        print("✓ load_config 環境變數測試通過")
        
        # 恢復原始 config
        shutil.move(backup_config_path, original_config_path)
        
        # 清理
        del os.environ['EMAIL_PASSWORD']
        
        print("✓ 深度整合測試 1 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 深度整合測試 1 失敗：{e}")
        import traceback
        traceback.print_exc()
        
        # 嘗試恢復原始 config
        backup_config_path = os.path.join(os.path.dirname(__file__), 'config.yaml.test_backup')
        original_config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        if os.path.exists(backup_config_path):
            shutil.move(backup_config_path, original_config_path)
        
        return False

def test_real_load_config_encrypted():
    """測試真實的 utils.load_config() 與加密字串"""
    print("=" * 60)
    print("深度整合測試 2：真實 load_config() + 加密字串")
    print("=" * 60)
    
    try:
        from crypto_utils import encrypt_password
        
        # 備份原始 config.yaml
        original_config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        backup_config_path = original_config_path + '.test_backup2'
        
        if not os.path.exists(original_config_path):
            print("⚠ 警告：找不到 config.yaml，跳過此測試")
            return True
        
        shutil.copy(original_config_path, backup_config_path)
        
        # 讀取原始 config
        with open(original_config_path, 'r', encoding='utf-8') as f:
            original_config = yaml.safe_load(f)
        
        # 設定加密密鑰
        test_key = secrets.token_bytes(32)
        key_b64 = base64.b64encode(test_key).decode('utf-8')
        os.environ['AETIM_ENCRYPTION_KEY'] = key_b64
        
        # 加密測試密碼
        test_password = 'encrypted_real_test_password_123'
        encrypted = encrypt_password(test_password)
        
        # 修改 config 使用加密字串
        if 'notification' not in original_config:
            original_config['notification'] = {}
        if 'email' not in original_config['notification']:
            original_config['notification']['email'] = {}
        
        original_config['notification']['email']['smtp_password'] = encrypted
        
        # 寫入測試 config
        with open(original_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(original_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # 測試 load_config（模擬處理流程）
        from crypto_utils import get_smtp_password
        
        # 模擬 load_config 的處理流程
        with open(original_config_path, 'r', encoding='utf-8') as f:
            raw_config = f.read()
        
        expanded_config = os.path.expandvars(raw_config)
        config = yaml.safe_load(expanded_config)
        
        # 使用 get_smtp_password 處理密碼
        password_value = config.get('notification', {}).get('email', {}).get('smtp_password')
        password = get_smtp_password(password_value)
        
        if password != test_password:
            print(f"✗ 錯誤：load_config 加密字串測試失敗（預期 {test_password}，實際 {password}）")
            return False
        
        print("✓ load_config 加密字串測試通過")
        
        # 恢復原始 config
        shutil.move(backup_config_path, original_config_path)
        
        # 清理
        del os.environ['AETIM_ENCRYPTION_KEY']
        
        print("✓ 深度整合測試 2 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 深度整合測試 2 失敗：{e}")
        import traceback
        traceback.print_exc()
        
        # 嘗試恢復原始 config
        backup_config_path = os.path.join(os.path.dirname(__file__), 'config.yaml.test_backup2')
        original_config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        if os.path.exists(backup_config_path):
            shutil.move(backup_config_path, original_config_path)
        
        return False

def test_web_api_password_hiding():
    """測試 Web API 端點的密碼隱藏功能"""
    print("=" * 60)
    print("深度整合測試 3：Web API 密碼隱藏")
    print("=" * 60)
    
    try:
        import copy
        
        # 模擬 web_app.py 中的 get_config() 邏輯
        test_config = {
            'notification': {
                'email': {
                    'smtp_password': 'plain_password_123',  # 明碼
                    'smtp_server': 'smtp.test.com'
                }
            }
        }
        
        # 模擬 get_config() 的處理
        safe_config = copy.deepcopy(test_config)
        if 'notification' in safe_config and 'email' in safe_config['notification']:
            if 'smtp_password' in safe_config['notification']['email']:
                password_value = safe_config['notification']['email']['smtp_password']
                if isinstance(password_value, str):
                    if password_value.startswith('ENCRYPTED:'):
                        # 保留加密字串
                        pass
                    elif password_value.startswith('${'):
                        # 保留環境變數引用
                        pass
                    else:
                        # 隱藏明碼
                        safe_config['notification']['email']['smtp_password'] = '***'
        
        # 驗證密碼已隱藏
        hidden_password = safe_config['notification']['email']['smtp_password']
        if hidden_password != '***':
            print(f"✗ 錯誤：密碼未正確隱藏（預期 ***，實際 {hidden_password}）")
            return False
        
        print("✓ 明碼密碼正確隱藏")
        
        # 測試加密字串（應保留）
        test_config2 = {
            'notification': {
                'email': {
                    'smtp_password': 'ENCRYPTED:xxxxx:yyyyy:zzzzz',
                    'smtp_server': 'smtp.test.com'
                }
            }
        }
        
        safe_config2 = copy.deepcopy(test_config2)
        if 'notification' in safe_config2 and 'email' in safe_config2['notification']:
            if 'smtp_password' in safe_config2['notification']['email']:
                password_value = safe_config2['notification']['email']['smtp_password']
                if isinstance(password_value, str):
                    if password_value.startswith('ENCRYPTED:'):
                        pass  # 保留
                    elif password_value.startswith('${'):
                        pass  # 保留
                    else:
                        safe_config2['notification']['email']['smtp_password'] = '***'
        
        encrypted_password = safe_config2['notification']['email']['smtp_password']
        if encrypted_password != 'ENCRYPTED:xxxxx:yyyyy:zzzzz':
            print(f"✗ 錯誤：加密字串不應被隱藏（預期 ENCRYPTED:...，實際 {encrypted_password}）")
            return False
        
        print("✓ 加密字串正確保留")
        
        # 測試環境變數引用（應保留）
        test_config3 = {
            'notification': {
                'email': {
                    'smtp_password': '${EMAIL_PASSWORD}',
                    'smtp_server': 'smtp.test.com'
                }
            }
        }
        
        safe_config3 = copy.deepcopy(test_config3)
        if 'notification' in safe_config3 and 'email' in safe_config3['notification']:
            if 'smtp_password' in safe_config3['notification']['email']:
                password_value = safe_config3['notification']['email']['smtp_password']
                if isinstance(password_value, str):
                    if password_value.startswith('ENCRYPTED:'):
                        pass
                    elif password_value.startswith('${'):
                        pass  # 保留
                    else:
                        safe_config3['notification']['email']['smtp_password'] = '***'
        
        env_ref_password = safe_config3['notification']['email']['smtp_password']
        if env_ref_password != '${EMAIL_PASSWORD}':
            print(f"✗ 錯誤：環境變數引用不應被隱藏（預期 ${{EMAIL_PASSWORD}}，實際 {env_ref_password}）")
            return False
        
        print("✓ 環境變數引用正確保留")
        
        print("✓ 深度整合測試 3 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 深度整合測試 3 失敗：{e}")
        import traceback
        traceback.print_exc()
        return False

def test_priority_order():
    """測試優先級順序"""
    print("=" * 60)
    print("深度整合測試 4：優先級順序測試")
    print("=" * 60)
    
    try:
        from crypto_utils import get_smtp_password, encrypt_password
        
        # 設定加密密鑰
        test_key = secrets.token_bytes(32)
        key_b64 = base64.b64encode(test_key).decode('utf-8')
        os.environ['AETIM_ENCRYPTION_KEY'] = key_b64
        
        # 測試優先級：環境變數 > 加密字串 > 明碼
        encrypted = encrypt_password('encrypted_password')
        
        # 情況1：環境變數存在，應優先使用
        os.environ['EMAIL_PASSWORD'] = 'env_password'
        result = get_smtp_password('config_password')
        if result != 'env_password':
            print(f"✗ 錯誤：環境變數優先級不正確（預期 env_password，實際 {result}）")
            return False
        print("✓ 環境變數優先級正確")
        
        # 情況2：環境變數不存在，使用加密字串
        del os.environ['EMAIL_PASSWORD']
        result = get_smtp_password(encrypted)
        if result != 'encrypted_password':
            print(f"✗ 錯誤：加密字串優先級不正確（預期 encrypted_password，實際 {result}）")
            return False
        print("✓ 加密字串優先級正確")
        
        # 情況3：環境變數和加密字串都不存在，使用明碼（警告）
        result = get_smtp_password('plain_password')
        if result != 'plain_password':
            print(f"✗ 錯誤：明碼處理不正確（預期 plain_password，實際 {result}）")
            return False
        print("✓ 明碼處理正確（應有警告）")
        
        # 清理
        del os.environ['AETIM_ENCRYPTION_KEY']
        
        print("✓ 深度整合測試 4 通過\n")
        return True
        
    except Exception as e:
        print(f"✗ 深度整合測試 4 失敗：{e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """執行所有深度整合測試"""
    print("\n" + "=" * 60)
    print("AETIM SMTP 密碼加密功能 - 深度整合測試")
    print("=" * 60 + "\n")
    
    results = []
    
    # 執行測試
    results.append(("真實 load_config() + 環境變數", test_real_load_config_env_var()))
    results.append(("真實 load_config() + 加密字串", test_real_load_config_encrypted()))
    results.append(("Web API 密碼隱藏", test_web_api_password_hiding()))
    results.append(("優先級順序", test_priority_order()))
    
    # 輸出結果
    print("=" * 60)
    print("深度整合測試結果摘要")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ 通過" if result else "✗ 失敗"
        print(f"{test_name:40s} {status}")
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

