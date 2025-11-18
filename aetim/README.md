# 專案名稱：AI 驅動之自動化威脅情資管理系統 v1.1
> AETIM (Automated E-Threat Intelligence Management) - AI 驅動的自動化威脅情資管理系統
> 專案目標： 建立一個自動化流程，主動收集、分析外部威脅情資，並與內部資產進行關聯性分析，最終產出可行動的(actionable)報告，並即時通知相關人員。
> 1. 蒐集威脅情資
> 2. 威脅分析，比對與內部資產的實際影響
> 3. 產生分析報告
> 4. 通知資安官及相關人員
>
> AI 在此計劃中的關鍵角色
> 自然語言處理 (NLP)： 自動閱讀非結構化的資安新聞、部落格、TWCERT 通報，提取 CVE 編號、TTPs 和受影響的產品。
> 威脅摘要： 自動將複雜的漏洞分析，總結為易於 CISO 和高管理解的「業務風險描述」。
> 模式識別： (進階) 分析大量 IOCs，識別出針對貴公司的潛在攻擊活動 (Campaign)。
>
> **版本**：v1.1  
> **最後更新**：2025年11月6日  
> **初始版本**：2025年10月20日 

## 需求：
1. 階段一：基礎建設與情資定義 (Foundation & T-PIR)
2. 階段二：自動化收集與關聯分析 (Automation & Correlation)
3. 階段三：報告生成與即時通知 (Reporting & Notification)
4. 階段四：持續維運與優化 (Operation & PDCA)
... **詳閱：階段一 1.需求分析** ...

## 系統架構：
1. 總體架構與技術棧 (Python Stack)
    - 執行環境： 一台專用的 Linux VM (或 **Docker 容器**)，安裝 Python 3.10+。
        - 核心函式庫 (Libraries)：
        - requests：用於所有 REST API 呼叫 (NVD, CISA)。
        - feedparser：用於解析 RSS feeds (VMware, MSRC)。
        - sqlite3：(或 SQLAlchemy + psycopg2/pyodbc) 用於儲存情資與資產。
        - pandas：用於高效能的記憶體內 (in-memory) 資產比對。
        - openai：(或 google-generativeai) 用於呼叫 LLM API，執行 AI 摘要任務。
        - APScheduler：(或 Crontab) 用於排程自動執行收集任務。
    - 資料庫設計： 我們將使用 SQLite (或您指定的公司資料庫) 建立三個關鍵表格：
        - T_Assets：您的資產清單 (從 CSV 匯入)。
        - T_Raw_Intel：從外部收集到的原始情資 (用於追蹤與避免重複)。
        - T_Validated_Threats：(本階段的關鍵產出) 已確認影響到內部資產的威脅。

2. 詳細設計：情資收集代理人 (Collection Agent)
這是一個 Python 應用程式，由多個「收集器」模組組成，並由一個主排程器 (scheduler.py) 驅動。
... **詳閱：階段二：2.設計分析** ...

## 安裝與部署

> **重要提示**：本節提供快速安裝指南。如需完整的安裝、部署及移轉手冊（適用於 Ubuntu 24.04 正式環境），請參考：[正式環境安裝部署移轉手冊](../系統需求設計與分析/正式環境安裝部署移轉手冊.md)

### 前置需求
- Docker 和 Docker Compose（參考手冊第 2.1 節）
- 網路連線（用於從情資來源抓取資料）

### 快速安裝步驟

#### 1. 準備環境變數檔案
參考手冊第 3.2 節：在專案目錄 (`aetim/`) 建立 `.env` 檔案，設定 API 金鑰。

#### 2. 確認資產清單檔案
參考手冊第 3.3 節：確保 `資產清單 - Sheet1.csv` 檔案位於 `aetim/` 目錄下，且檔案名稱與 `config.yaml` 中的設定一致。

#### 3. 初始化資料庫
參考手冊第 3.4 節：第一次啟動前，執行 `docker compose run --rm aetim python setup_database.py` 初始化資料庫。

#### 4. 調整系統設定（選填）
參考手冊第 3.5 節：可在 `config.yaml` 中調整排程和通知設定，或透過 Web 界面進行設定。

#### 5. 啟動服務
參考手冊第 3.6 節：執行 `docker compose up -d` 啟動服務。

**訪問 Web 界面：**
啟動後，在瀏覽器中訪問：`http://localhost:5001`（正式環境請使用伺服器 IP 地址）

> **網路連線設定**：如需讓其他使用者從外部連線，或設定生產環境的安全配置（Nginx、SSL、認證等），請參考：[網路連線設定指南](網路連線設定指南.md)

### 服務管理

參考手冊第 5 節：服務啟動與停止、查看日誌、自動啟動設定、更新系統、備份與還原等。

### 驗證安裝

參考手冊第 3.7 節：檢查資料庫、Web 界面和收集器執行狀態。

### 疑難排解

參考手冊第 6 節：Docker 相關問題、資料庫相關問題、網路相關問題、Web 界面相關問題、通知相關問題、時區相關問題等。

### 排程設定說明

#### 調整執行間隔

編輯 `config.yaml` 檔案中的 `scheduler.interval` 區塊：

```yaml
scheduler:
  interval:
    hours: 4        # 小時設定
    minutes: null   # 分鐘設定
```

**設定規則：**
1. 優先使用 `minutes`：如果 `minutes` 有值且 > 0，系統會使用分鐘間隔
2. 否則使用 `hours`：如果 `minutes` 為 `null` 或未設定，系統會使用小時間隔
3. 預設值：如果兩者都未設定，預設為 4 小時

**修改後需重啟服務：**
```bash
docker-compose restart
```

#### 常見設定範例

| 需求 | config.yaml 設定 |
|------|------------------|
| 每 30 分鐘執行 | `minutes: 30, hours: null` |
| 每 1 小時執行 | `minutes: null, hours: 1` |
| 每 6 小時執行 | `minutes: null, hours: 6` |
| 每 15 分鐘執行 | `minutes: 15, hours: null` |

### 階段二：關聯分析引擎

關聯分析引擎會自動比對威脅情資與內部資產，計算風險分數。

**執行方式：**
- 自動執行：每次收集任務完成後自動執行
- 手動執行：`docker-compose exec aetim python correlation_engine.py`

**查看結果：**
```bash
# 查看已驗證的威脅
docker-compose exec aetim sqlite3 /app/aetim.db "
SELECT 
    vt.id, vt.risk_score, vt.status,
    ri.cve_id, ri.title, ri.source,
    a.hostname, a.ip_address
FROM T_Validated_Threats vt
JOIN T_Raw_Intel ri ON vt.intel_id = ri.id
JOIN T_Assets a ON vt.asset_id = a.id
ORDER BY vt.risk_score DESC
LIMIT 10;
"
```

### 階段三：報告生成與通知

系統支援兩種報告模板：

#### 報告模板 A：CISO 威脅情資週報（管理層）
- **觸發**：每週一上午 8:00 自動生成
- **格式**：HTML（可選 PDF）
- **內容**：
  - AI 驅動的執行摘要（150 字內）
  - 關鍵指標（威脅統計、圖表）
  - Top 5 曝險最嚴重的資產
  - 未解決的嚴重威脅清單

**測試週報生成：**
```bash
docker-compose exec aetim python reporting_engine.py
```

**查看生成的報告：**
```bash
# 方式一：在容器內查看（按年月目錄）
docker-compose exec aetim ls -lh /app/reports/2025/202511/

# 方式二：在本機查看（因為有 volume mapping）
ls -lh aetim/reports/2025/202511/

# 方式三：查看最新的報告（當前月份）
docker-compose exec aetim find /app/reports -name "*.html" -type f | sort -r | head -5

# 方式四：查看所有年份和月份
docker-compose exec aetim find /app/reports -type d -name "20*" | sort
```

**報告檔案位置與目錄結構：**
- **容器內路徑**：`/app/reports/`
- **本機路徑**：`aetim/reports/`（因為 Docker volume mapping）
- **目錄結構**：`reports/yyyy/yyyymm/`（按年月自動分類）
  - 例如：`reports/2025/202511/` 表示 2025年11月的報告
  - 例如：`reports/2025/202512/` 表示 2025年12月的報告

**報告檔案命名規則：**
- CISO 週報：`ciso_weekly_YYYYMMDD_HHMMSS.html`
- IT 工單：`it_ticket_YYYYMMDD_HHMMSS.json` 或 `.text`
- **完整路徑範例**：`reports/2025/202511/ciso_weekly_20251103_030124.html`

**開啟報告：**
```bash
# 在本機直接開啟最新的 HTML 報告（當前月份）
open aetim/reports/$(date +%Y)/$(date +%Y%m)/ciso_weekly_*.html

# 或使用瀏覽器開啟指定報告（完整路徑）
# macOS:
open aetim/reports/2025/202511/ciso_weekly_20251103_030124.html

# Linux:
xdg-open aetim/reports/2025/202511/ciso_weekly_20251103_030124.html

# Windows:
start aetim/reports/2025/202511/ciso_weekly_20251103_030124.html

# 查看所有報告目錄
ls -R aetim/reports/
```

#### 報告模板 B：IT 維運工單（技術層）
- **觸發**：即時觸發（風險分數 >= 7.0 時）
- **格式**：文字或 JSON
- **內容**：
  - 受影響資產（主機名稱、IP）
  - 威脅描述（CVE ID、標題）
  - 風險分數與分析
  - 建議修補措施

#### 通知設定

- 在 `config.yaml` 設定通知（包含三種通知類型與兩類收件者群組）：

```yaml
notification:
  enabled: true            # 總開關
  email:
    enabled: true          # 是否啟用 Email 通知
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    smtp_username: "${EMAIL_USERNAME}"
    smtp_password: "${EMAIL_PASSWORD}"  # 建議使用環境變數或加密字串
    from_address: "aetim@yourcompany.com"
    use_tls: true
  # 收件者群組（可在 Web「通知設定」頁面維護）
  recipients:
    ciso: security@yourcompany.com
    it: it@yourcompany.com
  # 通知類型設定
  types:
    critical:              # 嚴重威脅：即時通知
      enabled: true
      recipients: [it, ciso]
      threshold: 9.0
    high_daily:            # 高風險每日摘要
      enabled: true
      recipients: [it]
      threshold: 7.0
      # 每日 HH:MM 發送（亦可於 Web 調整）
      schedule: "09:00"
    weekly_report:         # 週報通知
      enabled: true
      recipients: [ciso]
```

**設定環境變數：**
在 `.env` 檔案中新增：
```bash
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_FROM=aetim@yourcompany.com
```

> **重要：SMTP 密碼管理（符合 ISO 27001:2022）**  
> SMTP 密碼不應以明碼存放在版本控制中。請使用環境變數或 `encrypt_password.py` 生成加密字串後填入 `smtp`。

**通知工作流與自動化**
1. **Critical（嚴重）**：`notification.types.critical.enabled = true` 時，當出現 `risk_score > threshold` 的新威脅，系統即時寄送警報與 IT 工單至 `notification.recipients` 中 `types.critical.recipients` 指定的群組。
2. **High Daily**：`notification.types.high_daily.enabled = true` 時，系統於 `notification.types.high_daily.schedule` 指定時間彙總過去 24 小時內 `risk_score > threshold` 的高風險事件並寄送摘要至 `types.high_daily.recipients`。
3. **Weekly Report**：`notification.types.weekly_report.enabled = true` 且 `reporting.weekly_report.enabled = true` 時，系統依「週報排程」設定自動產生 CISO 週報並寄送至 `types.weekly_report.recipients`。

#### 測試與驗證
```bash
# 產生一份最新 CISO 週報（測試用）
docker-compose exec aetim python reporting_engine.py

# 測試 SMTP（需先於 Web 的「通知設定」填寫 SMTP）
curl -X POST http://localhost:5001/api/smtp/test -H 'Content-Type: application/json' \
  -d '{"smtp_server":"smtp.gmail.com","smtp_port":587,"smtp_username":"...","smtp_password":"...","from_address":"...","to_address":"...","use_tls":true}'

# 測試「週報」寄送（將依 types.weekly_report.recipients 發送）
curl -X POST http://localhost:5001/api/weekly-jobs/test-send -H 'Content-Type: application/json' -d '{}'
```

### 階段四：Web 管理界面

AETIM 系統提供了一個完整的 Web 管理界面，讓使用者可以透過瀏覽器輕鬆管理系統設定、監控任務執行狀態、生成報告和發送通知。

#### 訪問 Web 界面

啟動服務後，在瀏覽器中訪問：
```
http://localhost:5001
```

**注意：** 由於 macOS 的 AirPlay Receiver 可能佔用端口 5000，系統已改用端口 5001。如果您的系統沒有使用端口 5000，可以在 `docker-compose.yml` 中改回 `5000:5000`。

#### Web 界面結構

Web 界面分為三個主要區域：

##### 1. 上半部：專案資訊與時間顯示
- **專案名稱**：顯示 "AETIM - 自動化威脅情資管理系統"
- **即時日期時間**：自動更新，顯示當前系統時間

##### 2. 中間部分：設定與控制區

**2.1 基本排程設定**
- 顯示當前收集任務的執行間隔（小時/分鐘）
- 可透過 Web 界面動態修改排程設定
- 設定會即時保存到 `config.yaml`

**2.2 動態排程設定**
- 支援小時和分鐘兩種時間單位
- 可設定 0-23 小時、0-59 分鐘
- 設定優先順序：分鐘 > 小時（如果設定了分鐘，則以分鐘為準）

**2.3 通知設定（以設定為主）**
- 通知總開關、Email 啟用
- SMTP 設定（伺服器／埠口／帳號／密碼／From／TLS）
- 收件者群組（CISO/IT）
- 通知類型對應收件群組：
  - Critical（嚴重）- 即時寄送並可自動建立 IT 工單
  - High Daily（每日摘要）- 設定每日寄送時間（HH:MM）
  - Weekly Report（週報）- 給管理層收件者
- 測試工具：測試 SMTP、測試週報寄送

**2.4 手動立即觸發按鈕**
- **觸發收集任務**：立即執行所有收集器（CISA KEV、NVD、RSS Feeds）
- **觸發關聯分析**：立即執行關聯分析引擎
- **觸發所有任務**：按順序執行收集任務 → 關聯分析

##### 3. 下半部：處理狀態與報告生成

**3.1 處理狀態顯示**
- **收集任務狀態**：顯示當前執行狀態（idle/running/completed/error）
- **關聯分析狀態**：顯示關聯分析的執行狀態
- **即時日誌**：顯示各任務的執行日誌，包含時間戳記
- **整體狀態**：顯示系統整體運行狀態

**3.2 報告生成功能**
- **報告類型選擇**：
  - CISO 週報（管理層）- HTML 格式
  - IT 工單（技術層）- Text 或 JSON 格式
- **格式選擇**：根據報告類型選擇對應的輸出格式
- **生成結果顯示**：顯示報告生成狀態和檔案路徑
- **報告檔案位置**：`reports/yyyy/yyyymm/` 目錄結構

**3.3 通知處理功能**
- **通知類型選擇**：
  - Critical（嚴重威脅）- 立即通知
  - High Daily（高風險每日摘要）
  - Weekly Report（週報通知）
- **收件人選擇**：可選擇通知的收件人
- **通知結果顯示**：顯示通知發送狀態和結果

#### Web API 端點

Web 界面透過 RESTful API 與後端服務溝通，主要 API 端點如下：

**設定相關：**
- `GET /api/config` - 取得當前設定
- `POST /api/config` - 更新系統設定

**任務控制：**
- `POST /api/trigger/collectors` - 觸發收集任務
- `POST /api/trigger/correlation` - 觸發關聯分析
- `POST /api/trigger/all` - 觸發所有任務（收集 + 關聯分析）

**狀態查詢：**
- `GET /api/status` - 取得任務執行狀態

**報告生成：**
- `POST /api/report/generate` - 生成報告
  - 參數：`type`（ciso_weekly/it_ticket）、`format`（html/text/json）

**通知相關：**
- `GET /api/weekly-jobs?limit=20` - 查詢最近通知/週報事件
- `POST /api/weekly-jobs/test-send` - 以最新週報進行一次性測試寄送（驗證設定）

#### 技術實作細節

**前端技術：**
- HTML5 + CSS3（漸層背景、響應式設計）
- JavaScript（Fetch API、非同步更新）
- 即時狀態更新（每 3 秒自動刷新）

**後端技術：**
- Flask Web 框架
- Flask-CORS（跨域請求支援）
- Threading（背景任務執行）
- 全域狀態管理（task_status 字典）

**檔案結構：**
```
aetim/
├── web_app.py          # Flask 應用程式主檔案
├── templates/
│   └── index.html      # Web 界面 HTML 模板
└── docker-compose.yml  # 包含 aetim-web 服務定義
```

#### 安全考量

1. **環境變數保護**：敏感資訊（API 金鑰、Email 密碼）透過 `.env` 檔案管理
2. **密碼加密**：SMTP 密碼支援環境變數和 AES-256-GCM 加密，符合 ISO 27001:2022 規範
3. **CORS 設定**：已啟用 CORS，但仍應在生產環境中限制允許的來源
4. **開發模式**：當前使用 Flask 開發模式，生產環境應使用 WSGI 伺服器（如 Gunicorn）
5. **錯誤處理**：所有 API 端點都包含適當的錯誤處理機制
6. **密碼保護**：密碼不會返回給前端 API，也不會記錄在日誌中

#### 使用範例

**透過 Web 界面執行收集任務：**
1. 訪問 `http://localhost:5001`
2. 在「手動立即觸發」區域點擊「觸發所有任務」按鈕
3. 在「處理狀態」區域監控任務執行進度
4. 查看即時日誌了解詳細執行過程

**透過 Web 界面生成報告：**
1. 在「報告生成」區域選擇報告類型（如：CISO 週報）
2. 選擇報告格式（HTML）
3. 點擊「生成報告」按鈕
4. 等待報告生成完成後，查看結果和檔案路徑

**透過 Web 界面修改設定：**
1. 在「基本排程設定」區域修改小時或分鐘數值
2. 點擊「儲存設定」按鈕
3. 設定會即時保存到 `config.yaml`，並在下一次排程時生效

#### 透過 Web 界面調整「週報排程」（新功能）
1. 在「週報排程設定」區域，選擇「星期（mon..sun）」、「小時（0-23）」、「分鐘（0-59）」
2. 點擊「更新週報排程」
3. 系統會即時保存到 `config.yaml` 的 `reporting.weekly_report.schedule_struct`，並向排程器發送 SIGUSR2 重新載入設定
4. 成功後可在排程器日誌看到新時間（例如：每週 wed 09:30）

`config.yaml` 片段：
```yaml
reporting:
  weekly_report:
    enabled: true
    schedule_struct:
      day_of_week: mon     # mon,tue,wed,thu,fri,sat,sun
      hour: 8              # 0-23
      minute: 0            # 0-59
      timezone: Asia/Taipei
    # 向後相容：舊欄位仍可保留但不再於 UI 顯示
    schedule: monday 08:00
```

注意：
- 若訊號不可用（特殊部署情境），請改用替代方案（建立 reload 旗標檔並由排程器輪詢）或重新啟動排程器容器。

#### 週報排程監視視窗（新功能）
- 位置：頁面下半部新增「週報排程監視」
- 功能：
  - 即時顯示最近多筆週報事件（時間、階段、狀態、收件者遮罩、訊息）
  - 顯示最近一次執行摘要
  - 提供「測試寄送（使用最新 CISO 週報）」按鈕
- 後端儲存：JSONL 檔案 `logs/weekly_jobs/YYYYMM/YYYYMMDD.jsonl`
- 相關 API：
  - `GET /api/weekly-jobs?limit=20` 取得最近事件（含遮罩收件者）
  - `POST /api/weekly-jobs/test-send` 以最新週報試寄（可選參數 `to` 覆寫收件者）

#### 疑難排解

**問題：無法訪問 Web 界面**
- 確認服務已啟動：`docker-compose ps`
- 檢查端口是否被佔用：`lsof -i :5001`
- 查看服務日誌：`docker-compose logs aetim-web`

**問題：Web 界面顯示錯誤**
- 檢查瀏覽器控制台是否有 JavaScript 錯誤
- 查看後端日誌：`docker-compose logs aetim-web --tail=50`
- 確認資料庫連線正常

**問題：任務執行失敗**
- 查看任務日誌：在 Web 界面的「處理狀態」區域查看詳細日誌
- 檢查環境變數設定：確認 `.env` 檔案中的 API 金鑰已正確設定
- 查看完整日誌：`docker-compose logs aetim-web --tail=100`

## 版本歷史

### v1.1 (2025年11月6日)

**新增功能：**
- Web 管理界面（階段四）：完整的 Web 界面，支援設定管理、任務監控、報告生成和通知發送
- 下次執行時間倒數顯示：即時顯示下次執行時間的倒數計時
- 動態排程設定增強：支援小時和分鐘組合設定，並提供「不使用」選項
- 多收件者 Email 設定：支援分別設定 CISO 和 IT 團隊不同的收件者
- SMTP 設定獨立區塊：獨立的 SMTP 設定區塊，並提供測試功能
- 報告目錄結構優化：報告檔案按年月自動分類儲存
- 系統自動啟動功能：Docker 和容器服務自動啟動，啟動時自動執行初始任務
- 時區統一設定：所有時間戳記統一使用 Asia/Taipei 時區

**問題修正：**
- 修正下次執行時間顯示異常問題
- 修正動態排程設定功能不完整問題
- 修正通知人員設定功能限制問題
- 修正 Email 通知未收到問題
- 修正處理狀態與報告顯示問題
- 修正時區設定不一致問題
- 修正 Email 通知功能未啟用檢查邏輯錯誤
- 修正報告檔案路徑顯示不明顯問題

**詳細資訊：**
- 問題修改清單：參考 [問題修改清單](../系統需求設計與分析/問題修改清單.md)
- 新增需求清單：參考 [新增需求清單](../系統需求設計與分析/新增需求清單.md)

### v1.0 (2025年10月20日)

**初始版本：**
- 階段一：基礎建設與情資定義
- 階段二：自動化收集與關聯分析
- 階段三：報告生成與即時通知

---

## 相關文件

### 安裝與部署
- **正式環境安裝部署移轉手冊**：`系統需求設計與分析/正式環境安裝部署移轉手冊.md`
  - 完整的 Ubuntu 24.04 安裝指南
  - 系統部署步驟
  - 系統移轉流程
  - 服務管理與疑難排解

### 專案文件
- **專案初始化摘要**：`系統需求設計與分析/專案初始化摘要.md`
- **問題修改清單**：`系統需求設計與分析/問題修改清單.md`
- **新增需求清單**：`系統需求設計與分析/新增需求清單.md`
- **階段一需求分析**：`系統需求設計與分析/階段一 1.需求分析.md`
- **階段二設計分析**：`系統需求設計與分析/階段二 2.設計分析.md`
- **階段三報告生成**：`系統需求設計與分析/階段三 3.產生分析報告_Reporting Engine.md`

### 下一步
安裝完成後，請參考：
- 系統需求設計與分析文件（瞭解各階段功能）
- `config.yaml`（調整 PIR 關鍵字、情資來源、排程和通知設定）
- 階段二設計文件（瞭解關聯分析引擎的實作）
- 階段三設計文件（瞭解報告生成與通知的實作）
- 階段四設計文件（Web 管理界面的實作與測試報告）

---

## 其他： 



