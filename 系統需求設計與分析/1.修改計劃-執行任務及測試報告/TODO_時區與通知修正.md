# AETIM 時區與通知功能修正 - 任務追蹤清單

**開始日期：** 2025年11月06日  
**狀態：** 🔄 進行中

---

## 📋 任務清單

### 🔔 階段一：通知發送問題修正（優先級：高）

#### 1. 檢查 `notify_weekly_report` 函數
- [ ] **Task 1.1**：檢查 `notify_weekly_report` 函數 (`notification_handler.py`)
  - 檢查函數是否正確讀取 config 中的 SMTP 設定
  - 確認函數正確使用 `to_address` 參數
  - 添加詳細的日誌輸出，追蹤設定值
  - **預估時間**：1 小時

#### 2. 改進設定傳遞
- [ ] **Task 1.2**：改進設定傳遞 (`web_app.py`)
  - 確保傳遞給 `notify_weekly_report` 的 config 包含完整的 SMTP 設定
  - 驗證所有必要的 SMTP 設定都存在
  - 添加驗證邏輯，確保設定完整
  - **預估時間**：1.5 小時

#### 3. 添加除錯日誌
- [ ] **Task 1.3**：添加除錯日誌 (`notification_handler.py`, `web_app.py`)
  - 在 `notify_weekly_report` 函數中添加日誌，輸出使用的 SMTP 設定
  - 在 `send_email` 函數中添加日誌，輸出發送過程
  - 在 `web_app.py` 中添加日誌，輸出傳遞的設定
  - **預估時間**：1 小時

---

### ⏰ 階段二：前端時間顯示問題修正（優先級：高）

#### 4. 修改前端時間顯示
- [ ] **Task 2.1**：修改前端時間顯示 (`templates/index.html`)
  - 在 `toLocaleString` 中添加 `timeZone: 'Asia/Taipei'` 選項
  - 確保所有時間戳記顯示都使用 Asia/Taipei 時區
  - 測試時間顯示是否正確
  - **預估時間**：1 小時

#### 5. 修改時間戳記生成
- [ ] **Task 2.2**：修改時間戳記生成 (`web_app.py`)
  - 確保後端生成的時間戳記使用 Asia/Taipei 時區
  - 使用 `datetime.now(timezone)` 生成時區感知的時間戳記
  - 測試時間戳記是否正確
  - **預估時間**：1.5 小時

---

### 📄 階段三：報告檔名時間問題修正（優先級：中）

#### 6. 使用時區感知的 datetime
- [ ] **Task 3.1**：使用時區感知的 datetime (`reporting_engine.py`)
  - 導入 `pytz` 或使用 `zoneinfo`（Python 3.9+）
  - 使用 `datetime.now(timezone('Asia/Taipei'))` 生成時間戳記
  - 測試時間戳記是否正確
  - **預估時間**：1 小時

#### 7. 修改 `save_report` 函數
- [ ] **Task 3.2**：修改 `save_report` 函數 (`reporting_engine.py`)
  - 在生成檔名時使用 Asia/Taipei 時區
  - 確保所有時間戳記都使用正確的時區
  - 測試報告檔名是否正確
  - **預估時間**：1 小時

---

### 📋 階段四：報告格式問題確認（優先級：低）

#### 8. 確認報告格式問題
- [ ] **Task 4.1**：確認報告格式問題
  - 等待使用者提供更多資訊
  - 確認問題的具體內容
  - 制定修正方案
  - **預估時間**：待定

---

## 📊 進度統計

- **總任務數**：8 項
- **已完成**：0 項
- **進行中**：0 項
- **待開始**：8 項
- **完成率**：0%

### 階段進度
- **階段一**：0/3 (0%)
- **階段二**：0/2 (0%)
- **階段三**：0/2 (0%)
- **階段四**：0/1 (0%)

---

## 🧪 測試清單

### 通知發送測試
- [ ] 測試 SMTP 連線
- [ ] 測試通知發送功能
- [ ] 檢查日誌輸出，確認使用的設定
- [ ] 確認收件者收到 Email

### 時間顯示測試
- [ ] 檢查前端時間顯示是否使用 Asia/Taipei 時區
- [ ] 檢查後端時間戳記是否使用 Asia/Taipei 時區
- [ ] 對比系統時間和顯示時間，確認正確

### 報告檔名測試
- [ ] 生成報告，檢查檔名中的時間戳記
- [ ] 確認時間戳記使用 Asia/Taipei 時區
- [ ] 對比系統時間和檔名時間，確認正確

---

## 📝 技術筆記

### Python 時區處理
```python
# 方法 1：使用 pytz（需要安裝）
import pytz
from datetime import datetime

taipei_tz = pytz.timezone('Asia/Taipei')
now = datetime.now(taipei_tz)

# 方法 2：使用 zoneinfo（Python 3.9+）
from zoneinfo import ZoneInfo
from datetime import datetime

now = datetime.now(ZoneInfo('Asia/Taipei'))
```

### JavaScript 時區處理
```javascript
// 使用 toLocaleString 指定時區
const date = new Date(timestamp);
const dateTimeStr = date.toLocaleString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'Asia/Taipei'  // 明確指定時區
});
```

---

## 🔍 問題排查清單

### 通知發送問題
1. [ ] 檢查 `notify_weekly_report` 函數是否正確讀取 config
2. [ ] 檢查 SMTP 設定是否完整傳遞
3. [ ] 檢查 `to_address` 是否正確設定
4. [ ] 檢查日誌輸出，確認使用的設定值
5. [ ] 檢查 Email 是否進入垃圾郵件匣

### 時間顯示問題
1. [ ] 檢查前端是否指定時區
2. [ ] 檢查後端是否使用時區感知的 datetime
3. [ ] 檢查 Docker 時區設定是否正確
4. [ ] 對比系統時間和顯示時間

### 報告檔名問題
1. [ ] 檢查 `save_report` 函數是否使用時區感知的 datetime
2. [ ] 檢查檔名時間戳記是否正確
3. [ ] 對比系統時間和檔名時間

---

**最後更新：** 2025年11月06日

