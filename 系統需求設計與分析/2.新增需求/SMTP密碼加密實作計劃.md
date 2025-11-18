# SMTP 密碼加密實作計劃

## 文件資訊

**專案名稱**：AI 驅動之自動化威脅情資管理系統 (AETIM)  
**文件版本**：v1.0  
**建立日期**：2025年11月7日  
**目標**：將 config.yaml 中的 SMTP 密碼從明碼改為加密處理，符合 ISO 27001:2022 規範

---

## 1. 需求分析

### 1.1 當前問題

- **問題**：`config.yaml` 中的 `smtp_password` 以明碼儲存
- **風險**：違反 ISO 27001:2022 的密碼管理規範（A.5.10）
- **影響範圍**：
  - `config.yaml`：明碼密碼
  - `web_app.py`：從 config 讀取並傳遞密碼
  - `notification_handler.py`：使用密碼發送 Email
  - `templates/index.html`：前端顯示和更新密碼

### 1.2 ISO 27001:2022 相關控制項

- **A.5.10 密碼管理**：密碼應以加密形式儲存
- **A.8.2 資訊分類**：敏感資訊（密碼）應適當保護
- **A.8.3 媒體處理**：設定檔中的敏感資訊應加密
- **A.9.4 存取控制**：限制對密碼的存取

### 1.3 目標

1. ✅ 密碼不以明碼形式儲存在 `config.yaml`
2. ✅ 支援環境變數方式（最佳實踐）
3. ✅ 支援加密字串方式（向後相容）
4. ✅ 提供加密/解密工具腳本
5. ✅ 確保向後相容性（現有系統可正常運作）
6. ✅ 符合 ISO 27001:2022 規範

---

## 2. 方案設計

### 2.1 方案選擇：混合方案（推薦）

**方案 A：環境變數方案（優先）**
- ✅ 符合 12-Factor App 原則
- ✅ 最安全（密碼不寫入檔案）
- ✅ 易於管理（透過 .env 或系統環境變數）
- ✅ 符合 ISO 27001:2022 最佳實踐

**方案 B：AES 加密方案（備選）**
- ✅ 支援加密字串儲存在 config.yaml
- ✅ 使用 AES-256-GCM 加密（符合 ISO 27001）
- ✅ 需要主密鑰（儲存在環境變數或密鑰檔案）
- ✅ 提供加密/解密工具

**混合方案優勢：**
- 優先使用環境變數（最安全）
- 支援加密字串（向後相容）
- 自動偵測並選擇合適方式

### 2.2 技術架構

```
┌─────────────────────────────────────────┐
│         config.yaml                     │
│  smtp_password: ${EMAIL_PASSWORD}       │  ← 優先：環境變數
│  或                                     │
│  smtp_password: ENCRYPTED:xxxxx         │  ← 備選：加密字串
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│      utils.py (load_config)             │
│  - 載入 config.yaml                      │
│  - 檢查環境變數                           │
│  - 解密加密字串（如需要）                  │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  notification_handler.py / web_app.py   │
│  - 使用解密後的密碼                        │
│  - 密碼不記錄在日誌中                      │
└─────────────────────────────────────────┘
```

### 2.3 加密方案細節

**加密演算法：** AES-256-GCM（Galois/Counter Mode）
- ✅ 對稱加密，效能佳
- ✅ 提供認證標籤（防篡改）
- ✅ 符合 ISO 27001:2022 要求

**密鑰管理：**
- 主密鑰儲存在環境變數：`AETIM_ENCRYPTION_KEY`
- 或儲存在密鑰檔案：`.aetim_key`（權限 600）
- 密鑰長度：32 bytes (256 bits)

**加密字串格式：**
```
ENCRYPTED:<base64_encoded_ciphertext>:<base64_encoded_nonce>:<base64_encoded_tag>
```

---

## 3. 實作計劃

### 3.1 階段一：建立加密工具模組

**任務 1.1：建立 `crypto_utils.py` 模組**
- [X] 實作 AES-256-GCM 加密函數
- [X] 實作 AES-256-GCM 解密函數
- [X] 實作密鑰載入函數（環境變數或檔案）
- [X] 實作密碼加密/解密包裝函數
- [X] 加入錯誤處理和日誌記錄

**任務 1.2：建立加密工具腳本 `encrypt_password.py`**
- [X] 命令列工具：加密密碼
- [X] 命令列工具：解密密碼（測試用）
- [X] 支援從環境變數讀取密鑰
- [X] 支援從檔案讀取密鑰
- [X] 輸出加密字串格式

**任務 1.3：更新 `requirements.txt`**
- [X] 新增 `cryptography` 套件依賴

### 3.2 階段二：更新設定檔載入邏輯

**任務 2.1：更新 `utils.py`**
- [X] 修改 `load_config()` 函數
- [X] 實作密碼解密邏輯
- [X] 支援環境變數優先
- [X] 支援加密字串解密
- [X] 加入警告訊息（如果使用明碼）

**任務 2.2：更新密碼取得函數**
- [X] 建立 `get_smtp_password()` 輔助函數
- [X] 統一密碼取得邏輯
- [X] 確保密碼不記錄在日誌中

### 3.3 階段三：更新使用密碼的模組

**任務 3.1：更新 `notification_handler.py`**
- [ ] 使用新的密碼取得函數
- [ ] 確保密碼不記錄在日誌中
- [ ] 移除所有密碼的 print 語句

**任務 3.2：更新 `web_app.py`**
- [X] 更新 SMTP 測試端點
- [X] 更新設定更新端點
- [X] 確保密碼不返回給前端
- [X] 確保密碼不記錄在日誌中

**任務 3.3：更新 `templates/index.html`**
- [X] 密碼欄位不顯示實際值（顯示 `***` 或留空）
- [X] 更新密碼更新邏輯
- [X] 加入加密提示訊息

### 3.4 階段四：文件與遷移

**任務 4.1：更新 `config.yaml` 範例**
- [X] 移除明碼密碼範例
- [X] 加入環境變數範例
- [X] 加入加密字串範例
- [X] 加入使用說明註解

**任務 4.2：建立遷移指南**
- [X] 建立 `密碼加密遷移指南.md`
- [X] 說明如何從明碼遷移到環境變數
- [X] 說明如何從明碼遷移到加密字串
- [X] 提供遷移腳本（可選）

**任務 4.3：更新文件**
- [X] 更新 `README.md`：加入密碼管理說明
- [X] 更新 `正式環境安裝部署移轉手冊.md`：加入密碼設定章節
- [X] 更新 `規格_spec.md`：加入密碼加密規格

### 3.5 階段五：測試與驗證

**任務 5.1：單元測試**
- [X] 測試加密/解密函數
- [X] 測試密鑰載入
- [X] 測試錯誤處理

**任務 5.2：整合測試**
- [X] 測試環境變數方式
- [X] 測試加密字串方式
- [X] 測試向後相容性（明碼警告）
- [X] 測試 Email 發送功能

**任務 5.3：安全測試**
- [X] 確認密碼不記錄在日誌中
- [X] 確認密碼不返回給前端
- [X] 確認密鑰檔案權限正確

---

## 4. 實作細節

### 4.1 加密工具模組 (`crypto_utils.py`)

```python
"""
AETIM 密碼加密工具模組
功能：提供 AES-256-GCM 加密/解密功能
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import os
import base64
import sys

def get_encryption_key():
    """
    取得加密密鑰（優先順序：環境變數 > 密鑰檔案）
    """
    # 優先從環境變數讀取
    key = os.environ.get('AETIM_ENCRYPTION_KEY')
    if key:
        # 如果是 base64 編碼，解碼；否則直接使用
        try:
            return base64.b64decode(key)
        except:
            return key.encode('utf-8')[:32].ljust(32, b'\0')
    
    # 從密鑰檔案讀取
    key_file = os.path.join('/app', '.aetim_key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()[:32].ljust(32, b'\0')
    
    return None

def encrypt_password(password: str) -> str:
    """
    加密密碼
    
    Args:
        password: 明碼密碼
        
    Returns:
        加密字串格式：ENCRYPTED:<ciphertext>:<nonce>:<tag>
    """
    key = get_encryption_key()
    if not key:
        raise ValueError("加密密鑰未設定（請設定 AETIM_ENCRYPTION_KEY 環境變數或建立 .aetim_key 檔案）")
    
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
    """
    if not encrypted_str.startswith('ENCRYPTED:'):
        return encrypted_str  # 不是加密字串，直接返回
    
    try:
        parts = encrypted_str.split(':')
        if len(parts) != 4:
            raise ValueError("加密字串格式錯誤")
        
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
            raise ValueError("加密密鑰未設定")
        
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext.decode('utf-8')
    except Exception as e:
        raise ValueError(f"解密失敗：{str(e)}")

def get_smtp_password(config_value):
    """
    取得 SMTP 密碼（支援環境變數、加密字串、明碼）
    
    Args:
        config_value: config.yaml 中的密碼值
        
    Returns:
        明碼密碼
    """
    # 優先檢查環境變數
    env_password = os.environ.get('EMAIL_PASSWORD')
    if env_password:
        return env_password
    
    # 檢查是否為加密字串
    if isinstance(config_value, str) and config_value.startswith('ENCRYPTED:'):
        return decrypt_password(config_value)
    
    # 檢查是否為環境變數引用
    if isinstance(config_value, str) and config_value.startswith('${'):
        expanded = os.path.expandvars(config_value)
        if expanded != config_value:
            return expanded
    
    # 明碼（發出警告）
    if isinstance(config_value, str) and config_value and not config_value.startswith('${'):
        print("警告：config.yaml 中使用明碼密碼，建議改用環境變數或加密字串", file=sys.stderr)
    
    return config_value
```

### 4.2 更新 `utils.py`

```python
from crypto_utils import get_smtp_password

def load_config():
    """
    載入設定檔並處理加密密碼
    """
    # ... 現有代碼 ...
    
    # 處理 SMTP 密碼
    if 'notification' in config and 'email' in config['notification']:
        email_config = config['notification']['email']
        if 'smtp_password' in email_config:
            # 使用統一的密碼取得函數
            config['notification']['email']['smtp_password'] = get_smtp_password(
                email_config['smtp_password']
            )
    
    return config
```

### 4.3 加密工具腳本 (`encrypt_password.py`)

```python
#!/usr/bin/env python3
"""
AETIM 密碼加密工具
用法：
    python encrypt_password.py <password>
    python encrypt_password.py --decrypt <encrypted_string>
"""

import sys
from crypto_utils import encrypt_password, decrypt_password

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法：")
        print("  加密：python encrypt_password.py <password>")
        print("  解密：python encrypt_password.py --decrypt <encrypted_string>")
        sys.exit(1)
    
    if sys.argv[1] == '--decrypt':
        if len(sys.argv) < 3:
            print("錯誤：請提供要解密的字串")
            sys.exit(1)
        try:
            password = decrypt_password(sys.argv[2])
            print(f"解密後的密碼：{password}")
        except Exception as e:
            print(f"解密失敗：{e}")
            sys.exit(1)
    else:
        password = sys.argv[1]
        try:
            encrypted = encrypt_password(password)
            print(f"加密字串：{encrypted}")
            print("\n請將此字串設定到 config.yaml 的 smtp_password 欄位")
        except Exception as e:
            print(f"加密失敗：{e}")
            sys.exit(1)
```

---

## 5. 遷移步驟

### 5.1 從明碼遷移到環境變數（推薦）

1. **設定環境變數**
   ```bash
   # 在 .env 檔案中新增
   EMAIL_PASSWORD=your_actual_password
   ```

2. **更新 config.yaml**
   ```yaml
   notification:
     email:
       smtp_password: ${EMAIL_PASSWORD}
   ```

3. **重新啟動服務**
   ```bash
   docker-compose restart
   ```

### 5.2 從明碼遷移到加密字串

1. **產生加密密鑰**
   ```bash
   # 方法1：使用環境變數
   export AETIM_ENCRYPTION_KEY=$(openssl rand -base64 32)
   
   # 方法2：建立密鑰檔案
   openssl rand -base64 32 > .aetim_key
   chmod 600 .aetim_key
   ```

2. **加密密碼**
   ```bash
   python encrypt_password.py "your_actual_password"
   # 輸出：ENCRYPTED:xxxxx:yyyyy:zzzzz
   ```

3. **更新 config.yaml**
   ```yaml
   notification:
     email:
       smtp_password: ENCRYPTED:xxxxx:yyyyy:zzzzz
   ```

4. **重新啟動服務**
   ```bash
   docker-compose restart
   ```

---

## 6. 測試計劃

### 6.1 單元測試

- [ ] 測試加密函數
- [ ] 測試解密函數
- [ ] 測試密鑰載入（環境變數）
- [ ] 測試密鑰載入（檔案）
- [ ] 測試錯誤處理

### 6.2 整合測試

- [ ] 測試環境變數方式（Email 發送）
- [ ] 測試加密字串方式（Email 發送）
- [ ] 測試向後相容性（明碼警告）
- [ ] 測試 Web 界面 SMTP 測試功能

### 6.3 安全測試

- [ ] 確認密碼不記錄在日誌中
- [ ] 確認密碼不返回給前端 API
- [ ] 確認密鑰檔案權限（600）
- [ ] 確認加密字串無法直接解密（無密鑰）

---

## 7. 風險評估與緩解

### 7.1 風險

| 風險 | 影響 | 機率 | 緩解措施 |
|------|------|------|----------|
| 密鑰遺失 | 高 | 低 | 備份密鑰，使用環境變數優先 |
| 密鑰洩露 | 高 | 低 | 限制密鑰檔案權限，使用環境變數 |
| 向後相容性問題 | 中 | 中 | 保留明碼支援（警告），逐步遷移 |
| 效能影響 | 低 | 低 | AES-GCM 效能佳，影響可忽略 |

### 7.2 緩解措施

1. **密鑰管理**
   - 優先使用環境變數（不寫入檔案）
   - 密鑰檔案權限設為 600
   - 定期輪換密鑰（可選）

2. **向後相容**
   - 保留明碼支援（發出警告）
   - 提供遷移指南
   - 逐步遷移現有系統

3. **監控與日誌**
   - 記錄加密/解密錯誤
   - 不記錄密碼內容
   - 監控異常存取

---

## 8. 時程規劃

| 階段 | 任務 | 預估時間 | 負責人 |
|------|------|----------|--------|
| 階段一 | 建立加密工具模組 | 2-3 小時 | 開發團隊 |
| 階段二 | 更新設定檔載入邏輯 | 1-2 小時 | 開發團隊 |
| 階段三 | 更新使用密碼的模組 | 2-3 小時 | 開發團隊 |
| 階段四 | 文件與遷移 | 1-2 小時 | 開發團隊 |
| 階段五 | 測試與驗證 | 2-3 小時 | 開發團隊 |
| **總計** | | **8-13 小時** | |

---

## 9. 驗收標準

- [ ] ✅ config.yaml 中不再有明碼密碼
- [ ] ✅ 支援環境變數方式（優先）
- [ ] ✅ 支援加密字串方式（備選）
- [ ] ✅ 提供加密/解密工具腳本
- [ ] ✅ Email 發送功能正常運作
- [ ] ✅ Web 界面 SMTP 測試功能正常
- [ ] ✅ 密碼不記錄在日誌中
- [ ] ✅ 密碼不返回給前端
- [ ] ✅ 符合 ISO 27001:2022 規範
- [ ] ✅ 文件完整更新

---

**文件版本**：v1.0  
**建立日期**：2025年11月7日  
**維護者**：開發團隊

