# AETIM - AI 驅動之自動化威脅情資管理系統

[![Version](https://img.shields.io/badge/version-v1.2-blue.svg)](https://github.com/your-repo/aetim)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

> **AETIM (Automated E-Threat Intelligence Management)** 是一個自動化威脅情資管理系統，專為滿足 ISO 27001:2022 A.5.7 (威脅情資) 控制項而設計。

## 📋 目錄

- [專案概述](#專案概述)
- [核心功能](#核心功能)
- [系統架構](#系統架構)
- [快速開始](#快速開始)
- [配置說明](#配置說明)
- [使用指南](#使用指南)
- [Web 管理界面](#web-管理界面)
- [API 文檔](#api-文檔)
- [版本歷史](#版本歷史)
- [相關文件](#相關文件)

---

## 專案概述

AETIM 是一個 AI 驅動的自動化威脅情資管理系統，旨在建立一個完整的自動化流程，主動收集、分析外部威脅情資，並與內部資產進行關聯性分析，最終產出可行動的報告，並即時通知相關人員。

### 專案目標

1. **自動化收集**：從多個公開與官方來源自動收集威脅情資
2. **智能分析**：比對威脅與內部資產，計算風險分數
3. **報告生成**：生成不同受眾的報告（管理層與技術層）
4. **即時通知**：根據風險等級發送差異化通知

### AI 在此計劃中的關鍵角色

- **自然語言處理 (NLP)**：自動閱讀非結構化的資安新聞、部落格、TWCERT 通報，提取 CVE 編號、TTPs 和受影響的產品
- **威脅摘要**：自動將複雜的漏洞分析，總結為易於 CISO 和高管理解的「業務風險描述」
- **模式識別**：(進階) 分析大量 IOCs，識別出針對貴公司的潛在攻擊活動 (Campaign)

---

## 核心功能

### 🔍 階段一：基礎建設與情資定義

- ✅ 內部資產清冊管理（CSV 匯入）
- ✅ 優先情資需求 (PIR) 定義
- ✅ 多來源威脅情資訂閱（CISA KEV、NVD、VMware VMSA、MSRC、TWCERT）

### 🤖 階段二：自動化收集與關聯分析

- ✅ 自動化情資收集（排程執行）
- ✅ 關聯分析引擎（比對威脅與資產）
- ✅ 風險分數計算（CVSS + 加權因子）
- ✅ 資料庫儲存與追蹤

### 📊 階段三：報告生成與即時通知

- ✅ **CISO 週報**：管理層週報（HTML 格式，含 AI 摘要）
- ✅ **IT 工單**：技術層工單（TEXT/JSON 格式）
- ✅ **通知機制**：三種通知類型（嚴重威脅、高風險每日摘要、週報）
- ✅ **報告目錄結構**：按年月自動分類（`reports/yyyy/yyyymm/`）

### 🌐 階段四：Web 管理界面

- ✅ 完整的 Web 管理界面
- ✅ 即時狀態監控
- ✅ 動態排程設定
- ✅ 週報排程可視化設定（v1.2 新增）
- ✅ 週報排程監視功能（v1.2 新增）
- ✅ 通知設定結構化（v1.2 新增）

---

## 系統架構

### 技術棧

- **執行環境**：Docker + Docker Compose
- **程式語言**：Python 3.10+
- **資料庫**：SQLite 3
- **Web 框架**：Flask
- **排程器**：APScheduler
- **資料處理**：Pandas
- **AI 整合**：OpenAI GPT-4

### 系統架構圖

```
┌─────────────────────────────────────────────────────────┐
│                    AETIM 系統架構                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐   │
│  │  Scheduler   │───▶│  Collectors  │───▶│   DB     │   │
│  │  (排程器)     │    │  (收集器)     │    │ (資料庫)  │   │
│  └──────────────┘    └──────────────┘    └──────────┘   │
│         │                    │                 │        │
│         │                    ▼                 │        │
│         │            ┌──────────────┐          │        │
│         │            │  Correlation │          │        │
│         │            │   Engine     │          │        │
│         │            │ (關聯引擎)    │          │        │
│         │            └──────────────┘          │        │
│         │                    │                 │        │
│         ▼                    ▼                 ▼        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐   │
│  │  Reporting   │    │ Notification │    │ Reports  │   │
│  │   Engine     │    │   Handler    │    │ (報告)    │   │
│  └──────────────┘    └──────────────┘    └──────────┘   │
│         │                    │                           │
│         └────────────────────┴───────────────────────   │
│                          │                               │
│                    ┌──────────────┐                      │
│                    │  Web App     │                      │
│                    │  (管理界面)   │                      │
│                    └──────────────┘                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 資料庫設計

- **T_Assets**：內部資產清冊
- **T_Raw_Intel**：原始威脅情資
- **T_Validated_Threats**：已驗證的威脅（關聯分析結果）

---

## 快速開始

### 前置需求

- Docker 和 Docker Compose
- 網路連線（用於從情資來源抓取資料）
- （選填）API 金鑰：NVD API Key、OpenAI API Key

### 安裝步驟

#### 1. 準備環境變數檔案

在專案目錄 (`aetim/`) 建立 `.env` 檔案：

```bash
# NVD API 金鑰（選填）
NVD_API_KEY=your_nvd_api_key_here

# OpenAI API 金鑰（選填，用於 AI 摘要）
OPENAI_API_KEY=your_openai_api_key_here

# Email 設定（選填）
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=default@company.com
```

#### 2. 確認資產清單檔案

確保 `資產清單 - Sheet1.csv` 檔案位於 `aetim/` 目錄下，且檔案名稱與 `config.yaml` 中的設定一致。

#### 3. 初始化資料庫

第一次啟動前，執行：

```bash
cd aetim
docker compose run --rm aetim python setup_database.py
```

#### 4. 啟動服務

```bash
docker compose up -d
```

#### 5. 訪問 Web 界面

啟動後，在瀏覽器中訪問：

```
http://localhost:5001
```

> **注意**：由於 macOS 的 AirPlay Receiver 可能佔用端口 5000，系統已改用端口 5001。如果您的系統沒有使用端口 5000，可以在 `docker-compose.yml` 中改回 `5000:5000`。

### 驗證安裝

```bash
# 檢查服務狀態
docker compose ps

# 查看服務日誌
docker compose logs -f aetim
docker compose logs -f aetim-web

# 檢查資料庫
docker compose exec aetim sqlite3 /app/aetim.db "SELECT COUNT(*) FROM T_Assets;"
```

---

## 配置說明

### 設定檔結構

主要設定檔為 `aetim/config.yaml`，包含以下區塊：

#### 1. 資料庫與資產設定

```yaml
database:
  file: aetim.db

assets:
  csv_file: 資產清單 - Sheet1.csv
```

#### 2. API 金鑰設定

```yaml
api_keys:
  nvd: ${NVD_API_KEY}        # 從環境變數讀取
  openai: ${OPENAI_API_KEY}   # 從環境變數讀取
```

#### 3. 威脅情資來源

```yaml
threat_feeds:
  cisa_kev: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
  vmware_vmsa: https://www.vmware.com/security/advisories.xml
  msrc: https://api.msrc.microsoft.com/cvrf/v2.0/updates
  msrc_rss: https://msrc.microsoft.com/update-guide/rss
  twcert_rss: https://www.twcert.org.tw/tw/rss-1-1.xml
  twcert_cc_rss: https://www.twcert.org.tw/tw/rss-1-2.xml
```

#### 4. PIR 關鍵字

```yaml
pir_keywords:
  - VMware ESXi 7.0
  - Windows Server 2016
  - Microsoft SQL Server 2017
```

#### 5. 排程器設定

```yaml
scheduler:
  interval:
    hours: 4        # 小時設定（可設為 null）
    minutes: null   # 分鐘設定（優先使用，可設為 null）
```

**設定規則**：
- 優先使用 `minutes`：如果 `minutes` 有值且 > 0，系統會使用分鐘間隔
- 否則使用 `hours`：如果 `minutes` 為 `null` 或未設定，系統會使用小時間隔
- 預設值：如果兩者都未設定，預設為 4 小時

#### 6. 報告設定

```yaml
reporting:
  weekly_report:
    enabled: true
    schedule: "monday 08:00"  # 舊格式（保留向後相容）
    schedule_struct:          # 新格式（v1.2 新增，優先使用）
      day_of_week: mon         # mon,tue,wed,thu,fri,sat,sun
      hour: 8                  # 0-23
      minute: 0                # 0-59
      timezone: Asia/Taipei
  output_dir: ./reports
  templates:
    ciso_weekly:
      enabled: true
      format: [html, pdf]
      include_ai_summary: true
    it_ticket:
      enabled: true
      format: [text, json]
```

#### 7. 通知設定（v1.2 新結構）

```yaml
notification:
  enabled: true            # 總開關
  email:
    enabled: true          # Email 通知開關
    smtp_server: smtp.gmail.com
    smtp_port: 587
    smtp_username: ${EMAIL_USERNAME}
    smtp_password: ${EMAIL_PASSWORD}  # 支援環境變數或加密字串
    from_address: ${EMAIL_FROM}
    to_address: ${EMAIL_TO}            # 預設收件者（保留向後相容）
    use_tls: true
    # 以下欄位保留向後相容
    ciso_email: ciso@yourcompany.com
    it_email: it@yourcompany.com
  # 收件者群組（v1.2 新增，統一管理）
  recipients:
    ciso: ciso@yourcompany.com
    it: it@yourcompany.com
  # 通知類型設定（v1.2 新增，每種類型可獨立設定）
  types:
    critical:              # 嚴重威脅通知
      enabled: true
      recipients: [it, ciso]
      threshold: 9.0
    high_daily:            # 高風險每日摘要
      enabled: true
      recipients: [it]
      threshold: 7.0
      schedule: "09:00"    # 每日發送時間（HH:MM）
    weekly_report:         # 週報通知
      enabled: true
      recipients: [ciso]   # 可設定為 [ciso], [it], 或 [ciso, it]
  # 以下欄位保留向後相容
  thresholds:
    critical: 9.0
    high: 7.0
    medium: 4.0
  channels:
    email: true
```

### SMTP 密碼管理

SMTP 密碼支援三種設定方式（優先順序由高到低）：

1. **環境變數**（推薦，最安全）：
   ```yaml
   smtp_password: ${EMAIL_PASSWORD}
   ```

2. **加密字串**（符合 ISO 27001:2022）：
   ```bash
   python encrypt_password.py
   # 輸入密碼後，會產生加密字串
   ```
   ```yaml
   smtp_password: ENCRYPTED:xxxxx:yyyyy:zzzzz
   ```

3. **明碼**（不推薦，僅用於測試環境）：
   ```yaml
   smtp_password: your_password_here
   ```

---

## 使用指南

### 排程設定

#### 調整執行間隔

**方式一：透過 Web 界面**
1. 訪問 `http://localhost:5001`
2. 在「排程設定」區域修改小時或分鐘數值
3. 點擊「儲存設定」
4. 設定會即時保存到 `config.yaml`，並在下一次排程時生效

**方式二：直接編輯 `config.yaml`**
```yaml
scheduler:
  interval:
    hours: 4
    minutes: null
```
修改後需重啟服務：
```bash
docker compose restart
```

#### 常見設定範例

| 需求           | config.yaml 設定           |
| -------------- | -------------------------- |
| 每 30 分鐘執行 | `minutes: 30, hours: null` |
| 每 1 小時執行  | `minutes: null, hours: 1`  |
| 每 6 小時執行  | `minutes: null, hours: 6`  |
| 每 15 分鐘執行 | `minutes: 15, hours: null` |

### 週報排程設定（v1.2 新增）

#### 透過 Web 界面設定

1. 訪問 `http://localhost:5001`
2. 在「週報排程設定（CISO 週報）」區域：
   - 選擇「星期」（mon, tue, wed, thu, fri, sat, sun）
   - 選擇「小時」（0-23）
   - 選擇「分鐘」（0-59）
3. 點擊「更新週報排程」
4. 系統會即時保存到 `config.yaml` 並向排程器發送 SIGUSR2 訊號重新載入設定
5. 成功後可在排程器日誌看到新時間設定

#### 直接編輯 `config.yaml`

```yaml
reporting:
  weekly_report:
    enabled: true
    schedule_struct:
      day_of_week: mon
      hour: 8
      minute: 0
      timezone: Asia/Taipei
```

修改後，在容器內觸發重排程：
```bash
docker compose exec aetim kill -USR2 $(cat /app/scheduler.pid)
```

### 報告生成

#### CISO 週報

- **觸發方式**：
  - 自動：每週排程時間自動生成
  - 手動：透過 Web 界面「報告生成」功能
- **格式**：HTML（可選 PDF）
- **內容**：
  - AI 驅動的執行摘要（150 字內）
  - 關鍵指標（威脅統計、圖表）
  - Top 5 曝險最嚴重的資產
  - 未解決的嚴重威脅清單

#### IT 工單

- **觸發方式**：
  1. **即時觸發**：當發現嚴重威脅（風險分數 ≥ 9.0）時立即生成並發送
  2. **週報彙總**：每週排程時，如果收件者包含 IT，會彙總過去 7 天的高風險威脅（風險分數 ≥ 7.0）生成彙總報告
- **格式**：TEXT 或 JSON
- **內容**：
  - 受影響資產資訊
  - 威脅描述（CVE ID、標題）
  - 風險分數與分析
  - 建議修補措施

#### 查看生成的報告

```bash
# 查看報告目錄結構
ls -R aetim/reports/

# 查看最新報告（當前月份）
ls -lh aetim/reports/$(date +%Y)/$(date +%Y%m)/

# 開啟最新的 HTML 報告（macOS）
open aetim/reports/$(date +%Y)/$(date +%Y%m)/ciso_weekly_*.html
```

**報告檔案位置與命名規則**：
- **目錄結構**：`reports/yyyy/yyyymm/`（按年月自動分類）
- **CISO 週報**：`ciso_weekly_YYYYMMDD_HHMMSS.html`
- **IT 工單**：`it_ticket_YYYYMMDD_HHMMSS.json` 或 `.text`
- **完整路徑範例**：`reports/2025/202511/ciso_weekly_20251116_080000.html`

### 通知設定

#### 通知類型

系統支援三種通知類型，每種類型可獨立設定：

1. **Critical（嚴重威脅）**
   - 觸發：即時（風險分數 ≥ threshold）
   - 收件者：可設定為 `[it, ciso]`
   - 內容：IT 工單 + 緊急警報

2. **High Daily（高風險每日摘要）**
   - 觸發：每日排程（預設：09:00）
   - 收件者：可設定為 `[it]`
   - 內容：過去 24 小時的高風險威脅清單

3. **Weekly Report（週報通知）**
   - 觸發：週報排程時間
   - 收件者：可設定為 `[ciso]`, `[it]`, 或 `[ciso, it]`
   - 內容：
     - CISO 收件者：CISO 週報（HTML）
     - IT 收件者：IT 工單彙總報告（JSON）

#### 透過 Web 界面設定

1. 訪問 `http://localhost:5001`
2. 在「週報排程通知設定」區域：
   - 設定通知總開關
   - 設定 CISO Email 和 IT Email
   - 設定 SMTP 相關資訊
   - 設定每種通知類型的啟用狀態和收件者群組
3. 點擊「儲存設定」

### 週報排程監視（v1.2 新增）

- **位置**：Web 界面下半部「週報排程監視」區域
- **功能**：
  - 即時顯示最近多筆週報事件（時間、階段、狀態、收件者、訊息）
  - 顯示最近一次執行摘要
  - 提供「測試寄送」按鈕（使用最新 CISO 週報）
- **事件記錄**：JSONL 檔案 `logs/weekly_jobs/YYYYMM/YYYYMMDD.jsonl`

---

## Web 管理界面

### 訪問方式

啟動服務後，在瀏覽器中訪問：
```
http://localhost:5001
```

### 主要功能區域

#### 1. 上半部：專案資訊與時間顯示
- 專案名稱：AETIM - 自動化威脅情資管理系統
- 即時日期時間：自動更新，顯示當前系統時間

#### 2. 中間部分：設定與控制區

**2.1 排程設定**
- 顯示當前收集任務的執行間隔
- 可透過 Web 界面動態修改排程設定

**2.2 週報排程設定（CISO 週報）**
- 可設定週報生成時間（星期、小時、分鐘）
- 支援動態重排程（無需重啟服務）

**2.3 週報排程通知設定**
- 通知總開關、Email 啟用
- SMTP 設定（伺服器、埠口、帳號、密碼、From、TLS）
- 收件者群組（CISO/IT）
- 通知類型設定（Critical、High Daily、Weekly Report）
- 測試工具：測試 SMTP、測試週報寄送

**2.4 手動立即觸發按鈕**
- **觸發收集任務**：立即執行所有收集器
- **觸發關聯分析**：立即執行關聯分析引擎
- **觸發所有任務**：按順序執行收集任務 → 關聯分析

#### 3. 下半部：處理狀態與報告生成

**3.1 處理狀態顯示**
- 收集任務狀態（idle/running/completed/error）
- 關聯分析狀態
- 即時日誌（包含時間戳記）
- 整體狀態

**3.2 報告生成功能**
- 報告類型選擇（CISO 週報、IT 工單）
- 格式選擇（HTML、TEXT、JSON）
- 生成結果顯示（狀態和檔案路徑）

**3.3 週報排程監視**
- 最近週報事件列表
- 執行狀態（成功、失敗、跳過）
- 測試寄送功能

---

## API 文檔

### 設定相關

#### GET /api/config
取得當前系統設定

**回應範例**：
```json
{
  "scheduler": {
    "interval": {
      "hours": 4,
      "minutes": null
    }
  },
  "reporting": {
    "weekly_report": {
      "enabled": true,
      "schedule_struct": {
        "day_of_week": "mon",
        "hour": 8,
        "minute": 0,
        "timezone": "Asia/Taipei"
      }
    }
  },
  "notification": {
    "enabled": true,
    "email": { ... },
    "recipients": { ... },
    "types": { ... }
  }
}
```

#### POST /api/config
更新系統設定

**請求範例**：
```json
{
  "scheduler": {
    "interval": {
      "hours": 4,
      "minutes": null
    }
  },
  "reporting": {
    "weekly_report": {
      "schedule_struct": {
        "day_of_week": "wed",
        "hour": 9,
        "minute": 30
      }
    }
  }
}
```

### 任務控制

#### POST /api/trigger/collectors
觸發收集任務

#### POST /api/trigger/correlation
觸發關聯分析

#### POST /api/trigger/all
觸發所有任務（收集 + 關聯分析）

### 狀態查詢

#### GET /api/status
取得任務執行狀態

**回應範例**：
```json
{
  "collectors": {
    "status": "completed",
    "last_run": "2025-11-16T08:00:00+08:00"
  },
  "correlation": {
    "status": "idle",
    "last_run": null
  }
}
```

### 報告生成

#### POST /api/report/generate
生成報告

**請求參數**：
- `type`：報告類型（`ciso_weekly` 或 `it_ticket`）
- `format`：格式（`html`、`text`、`json`）

**請求範例**：
```json
{
  "type": "ciso_weekly",
  "format": "html"
}
```

### 通知相關

#### GET /api/weekly-jobs
查詢最近週報事件

**查詢參數**：
- `limit`：返回筆數（預設：20）

**回應範例**：
```json
[
  {
    "id": "20251116_080000_001",
    "triggered_at": "2025-11-16T08:00:00+08:00",
    "phase": "done",
    "status": "success",
    "message": "週報生成並已寄出（2 封）",
    "recipients": ["ciso@company.com", "it@company.com"],
    "report_filepath": "reports/2025/202511/ciso_weekly_20251116_080000.html; reports/2025/202511/it_ticket_20251116_080000.json"
  }
]
```

#### POST /api/weekly-jobs/test-send
測試寄送週報

**請求範例**：
```json
{
  "to": "test@company.com"  // 可選，覆寫收件者
}
```

### SMTP 測試

#### POST /api/smtp/test
測試 SMTP 連線

**請求範例**：
```json
{
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_username": "your_email@gmail.com",
  "smtp_password": "your_password",
  "from_address": "your_email@gmail.com",
  "to_address": "test@company.com",
  "use_tls": true
}
```

---

## 版本歷史

### v1.2 (2025年11月16日)

**新增功能**：
- ✅ 週報排程可視化設定：透過 Web 界面調整週報生成時間（星期、小時、分鐘）
- ✅ 週報排程監視功能：即時顯示週報執行記錄和狀態
- ✅ 通知設定結構化：支援每種通知類型獨立設定啟用狀態和收件者群組
- ✅ 週報報告生成邏輯增強：根據收件者類型決定生成哪些報告（CISO 週報、IT 工單彙總）
- ✅ IT 工單週報彙總：週報排程時可同時生成 IT 工單彙總報告

**改進**：
- ✅ 動態重排程：支援 SIGUSR2 訊號觸發重排程，無需重啟服務
- ✅ 向後相容性：保留舊的設定格式，確保平滑升級

**文件更新**：
- ✅ 更新技術規格文件（v1.2）
- ✅ 更新報告生成規格說明
- ✅ 新增規格相關調整記錄

### v1.1 (2025年11月6日)

**新增功能**：
- ✅ Web 管理界面（階段四）：完整的 Web 界面，支援設定管理、任務監控、報告生成和通知發送
- ✅ 下次執行時間倒數顯示：即時顯示下次執行時間的倒數計時
- ✅ 動態排程設定增強：支援小時和分鐘組合設定
- ✅ 多收件者 Email 設定：支援分別設定 CISO 和 IT 團隊不同的收件者
- ✅ SMTP 設定獨立區塊：獨立的 SMTP 設定區塊，並提供測試功能
- ✅ 報告目錄結構優化：報告檔案按年月自動分類儲存
- ✅ 系統自動啟動功能：Docker 和容器服