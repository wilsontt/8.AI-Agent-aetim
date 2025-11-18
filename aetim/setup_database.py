import sqlite3
import pandas as pd
import yaml
import os
import sys
import re
# --- 步驟 1: 匯入 (取代舊的 load_config) ---
from utils import load_config, get_db_connection

# --- 資料庫結構 (Schema) ---
# 使用英文欄位名稱，保持資料庫最佳實踐

SCHEMA_T_ASSETS = """
CREATE TABLE IF NOT EXISTS T_Assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT,
    ip_address TEXT,
    hostname TEXT,
    os_version TEXT,
    applications TEXT,
    owner TEXT,
    data_sensitivity TEXT,
    is_public TEXT,
    business_criticality TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_T_RAW_INTEL = """
CREATE TABLE IF NOT EXISTS T_Raw_Intel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,                   -- e.g., 'CISA_KEV', 'NVD', 'TWCERT'
    type TEXT NOT NULL,                     -- e.g., 'CVE', 'IOC', 'Advisory'
    title TEXT,
    url TEXT,
    cve_id TEXT,                            -- e.g., 'CVE-2025-XXXX'
    cvss_score REAL,
    raw_data TEXT,                          -- 儲存原始 JSON 或 XML
    status TEXT DEFAULT 'new',              -- 'new', 'processed', 'error'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_T_VALIDATED_THREATS = """
CREATE TABLE IF NOT EXISTS T_Validated_Threats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intel_id INTEGER,
    asset_id INTEGER,
    risk_score REAL,
    status TEXT DEFAULT 'new',     -- 'new', 'acknowledged', 'remediated'
    notes TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (intel_id) REFERENCES T_Raw_Intel (id),
    FOREIGN KEY (asset_id) REFERENCES T_Assets (id)
);
"""

# --- CSV 欄位對應 (關鍵) ---
# 將您 CSV 中的中文欄位對應到資料庫的英文欄位
# (注意：我已處理您 CSV 檔頭中的換行符號)
COLUMN_MAPPING = {
    'ITEM': 'item_id',
    'IP': 'ip_address',
    '主機名稱': 'hostname',
    '作業系統\n(含版本)': 'os_version',
    '運行的應用程式\n(含版本)': 'applications',
    '負責人': 'owner',
    '資料敏感度': 'data_sensitivity',
    '是否對外\n(Public-facing)': 'is_public',
    '業務關鍵性': 'business_criticality'
}

# --- 步驟 2: 刪除 load_config() ---
# (舊的 def load_config(): ... 函式已**完全刪除**)
# def load_config():
#     """
#     載入設定檔並替換環境變數 (從 .env 讀取)
#     """
#     config_path = 'config.yaml'
#     if not os.path.exists(config_path):
#         print(f"錯誤：找不到 {config_path} 設定檔。", file=sys.stderr)
#         sys.exit(1)
        
#     try:
#         # 1. 讀取原始 config 內容
#         with open(config_path, 'r', encoding='utf-8') as f:
#             raw_config = f.read()
            
#         # 2. 使用 OS 模組替換 ${VAR} 或 $VAR 格式的環境變數
#         expanded_config = os.path.expandvars(raw_config)
        
#         # 3. 解析替換後的 YAML
#         config = yaml.safe_load(expanded_config)
        
#         # 4. 檢查 API 金鑰是否已設定
#         if config['api_keys']['nvd'] == 'YOUR_NVD_API_KEY_HERE' or not config['api_keys']['nvd']:
#             print("警告：NVD API 金鑰未設定 (NVD_API_KEY)。")
#             print("     建議至 https://nvd.nist.gov/developers/request-an-api-key 申請並填入 .env 檔案。")
            
#         if config['api_keys']['openai'] == 'YOUR_OPENAI_API_KEY_HERE' or not config['api_keys']['openai']:
#             print("警告：OpenAI API 金鑰未設定 (OPENAI_API_KEY)。AI 摘要功能將無法使用。")
            
#         return config
#     except yaml.YAMLError as e:
#         print(f"讀取 config.yaml 失敗：{e}", file=sys.stderr)
#         sys.exit(1)
#     except Exception as e:
#         print(f"載入設定時發生未知錯誤：{e}", file=sys.stderr)
#         sys.exit(1)

# --- 步驟 3: 修改 create_database ---
# def create_database(db_file):
def create_database(): # 移除了 db_file 參數
    """建立資料庫與所有資料表"""
    # 確保資料庫檔案是建立在 /app 目錄下 (即我們的專案目錄)
    # db_path = os.path.join("/app", db_file)
    
    conn = None
    try:
        # conn = sqlite3.connect(db_path)
        # --- 變更點 ---
        conn = get_db_connection() # 使用 utils 函式
        # --- 變更點 ---

        if conn is None:
            print("錯誤：無法建立資料庫連線。", file=sys.stderr)
            return False
        
        cursor = conn.cursor()
        
        # 執行 Schema
        cursor.execute(SCHEMA_T_ASSETS)
        cursor.execute(SCHEMA_T_RAW_INTEL)
        cursor.execute(SCHEMA_T_VALIDATED_THREATS)
        
        # 清空 T_Assets 以便重新匯入
        cursor.execute("DELETE FROM T_Assets")
        print(f"清除舊資產資料... (if_exists='replace')")
        
        conn.commit()
        # print(f"成功建立/初始化資料庫結構於：{db_path}")
        print(f"成功建立/初始化資料庫結構。")
        return True
    except sqlite3.Error as e:
        print(f"資料庫建立失敗：{e}", file=sys.stderr)
        return False
    finally:
        if conn:
            conn.close()

# --- 步驟 4: 修改 import_assets ---
# def import_assets(db_file, csv_file):
def import_assets(csv_file): # 移除了 db_file 參數
    """將資產清單 CSV 匯入 T_Assets 資料表"""
    # 確保路徑正確（Docker 容器內使用 /app 目錄）
    csv_path = os.path.join("/app", csv_file)

    if not os.path.exists(csv_path):
        print(f"錯誤：找不到資產清單檔案：{csv_path}", file=sys.stderr)
        print("請確認 '資產清單 - Sheet1.csv' 已放置於專案資料夾。", file=sys.stderr)
        return

    conn = None
    try:
        # 1. 讀取 CSV（使用絕對路徑）
        # 注意：CSV 檔案中可能有包含換行符號的欄位名稱
        df = pd.read_csv(csv_path, encoding='utf-8')
        
        # 1.1 顯示實際讀取到的欄位名稱（用於除錯）
        print(f"[除錯] CSV 檔案實際欄位名稱：{list(df.columns)}")
        
        # 1.2 標準化欄位名稱：移除多餘的空白和換行符號，統一處理
        # 建立一個實際欄位名稱到預期欄位名稱的映射
        actual_column_mapping = {}
        
        # 標準化 COLUMN_MAPPING 的鍵（原始欄位名稱）
        normalized_mapping_keys = {}
        for orig_key, new_key in COLUMN_MAPPING.items():
            # 標準化：移除換行符號和空白，轉換為統一格式
            normalized_orig = orig_key.replace('\n', ' ').replace('\r', ' ').strip()
            normalized_mapping_keys[normalized_orig] = new_key
        
        # 比對實際 CSV 欄位與預期欄位
        for actual_col in df.columns:
            # 標準化實際欄位名稱
            normalized_actual = actual_col.replace('\n', ' ').replace('\r', ' ').strip()
            
            # 尋找匹配的預期欄位
            if normalized_actual in normalized_mapping_keys:
                actual_column_mapping[actual_col] = normalized_mapping_keys[normalized_actual]
            else:
                # 如果找不到完全匹配，嘗試模糊匹配（移除括號內容）
                simplified_actual = re.sub(r'\([^)]*\)', '', normalized_actual).strip()
                for norm_key, new_key in normalized_mapping_keys.items():
                    simplified_key = re.sub(r'\([^)]*\)', '', norm_key).strip()
                    if simplified_actual == simplified_key or simplified_actual in simplified_key or simplified_key in simplified_actual:
                        actual_column_mapping[actual_col] = new_key
                        print(f"[除錯] 模糊匹配：'{actual_col}' -> '{new_key}'")
                        break
        
        print(f"[除錯] 欄位對應映射：{actual_column_mapping}")
        
        # 2. 移除空白或無效的 ITEM 行 (您 CSV 的最後一行是範例)
        # 先找到 ITEM 對應的實際欄位名稱
        item_column = None
        for col in df.columns:
            if col.strip().upper() == 'ITEM' or 'ITEM' in col:
                item_column = col
                break
        
        if item_column:
            df = df.dropna(subset=[item_column])
        else:
            print("警告：找不到 ITEM 欄位，跳過空白行過濾步驟。")
        
        # 3. 套用欄位對應（使用實際欄位名稱映射）
        df_renamed = df.rename(columns=actual_column_mapping)
        
        # 4. 只保留我們需要的欄位（對應後的欄位名稱）
        final_columns = list(COLUMN_MAPPING.values())
        # 檢查哪些欄位實際存在
        print(f"[除錯] 對應後的 DataFrame 欄位：{list(df_renamed.columns)}")
        print(f"[除錯] 預期的欄位名稱：{final_columns}")
        
        available_columns = [col for col in final_columns if col in df_renamed.columns]
        missing_columns = [col for col in final_columns if col not in df_renamed.columns]
        
        if missing_columns:
            print(f"錯誤：以下欄位在 CSV 中找不到或無法對應：{missing_columns}", file=sys.stderr)
            print(f"可用的欄位：{list(df_renamed.columns)}", file=sys.stderr)
            print(f"實際 CSV 欄位：{list(df.columns)}", file=sys.stderr)
            print(f"欄位對應映射：{actual_column_mapping}", file=sys.stderr)
            raise ValueError(f"無法找到必要的欄位：{missing_columns}。請檢查 CSV 檔案格式或 COLUMN_MAPPING 設定。")
        
        if not available_columns:
            raise ValueError("沒有任何欄位可以匯入！請檢查 CSV 檔案格式。")
        
        df_final = df_renamed[available_columns]
        print(f"[除錯] 最終匯入的欄位：{list(df_final.columns)}")
        print(f"[除錯] 準備匯入 {len(df_final)} 筆資料")
        
        # 5. 連線資料庫並匯入
        # --- 變更點 ---
        # conn = sqlite3.connect(db_file)
        conn = get_db_connection() # 使用 utils 函式
        # --- 變更點 ---

        if conn is None:
            print("錯誤：無法獲取資料庫連線，無法匯入資產。", file=sys.stderr)
            return  
        
        # # 使用 'replace' 策略：每次執行都清空並重新匯入，確保資產清單永遠是最新
        # df_final.to_sql('T_Assets', conn, if_exists='replace', index=False, index_label='id')
        
        # 使用 'append' 策略，因為 create_database 已清空表格
        df_final.to_sql('T_Assets', conn, if_exists='append', index=False)
        
        # conn.close()
        conn.commit()
        
        # 查詢驗證
        count = pd.read_sql_query("SELECT COUNT(*) FROM T_Assets", conn).iloc[0,0]
        # conn.close()
        
        print(f"成功從 {csv_file} 匯入 {count} 筆資產至 T_Assets 資料表。")

        # print(f"成功從 {csv_file} 匯入 {len(df_final)} 筆資產至 T_Assets 資料表。")

    except pd.errors.ParserError as e:
        print(f"讀取 CSV 失敗：{e}", file=sys.stderr)
    except Exception as e:
        print(f"匯入資產時發生錯誤：{e}", file=sys.stderr)
    finally:
        if conn:
            conn.close()


# --- 步驟 5: 修改主執行程式 ---
# --- 主執行程式 ---
if __name__ == "__main__":
    print(f"--- 啟動 AETIM 系統基礎建設 (在 Docker 內) ---")
    
    # 載入設定
    config = load_config()
    # db_path = config['database']['file']  # <-- 不再需要
    csv_path = config['assets']['csv_file']
    
    # 步驟 1: 建立資料庫結構
    # --- 變更點 ---
    # if create_database(db_path):
    if create_database(): # <-- 移除 db_path
        import_assets(csv_path) # <-- 移除 db_path
    # --- 變更點 ---
        # # 步驟 2: 匯入資產
        # import_assets(db_path, csv_path)
        
    print("--- 基礎建設完成 ---")
