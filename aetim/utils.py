import yaml
import os
import sys
import sqlite3
from sqlite3 import Error
from crypto_utils import get_smtp_password

CONFIG_FILE = 'config.yaml'
APP_DIR_DOCKER = "/app"
APP_DIR_LOCAL = os.path.dirname(__file__)  # 支援本機直接執行（非 Docker）

def load_config():
    """
    載入設定檔並替換環境變數 (從 .env 讀取)
    """
    # 先嘗試 Docker 目錄，若不存在則回退至本機模組目錄
    config_path_docker = os.path.join(APP_DIR_DOCKER, CONFIG_FILE)
    config_path_local = os.path.join(APP_DIR_LOCAL, CONFIG_FILE)
    config_path = config_path_docker if os.path.exists(config_path_docker) else config_path_local
    if not os.path.exists(config_path):
        print(f"錯誤：找不到設定檔（嘗試 {config_path_docker} 與 {config_path_local}）。", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = f.read()
            
        # 替換 ${VAR} 或 $VAR 格式的環境變數
        expanded_config = os.path.expandvars(raw_config)
        config = yaml.safe_load(expanded_config)
        
        # 檢查 API 金鑰 (僅警告)
        # 如果環境變數未設定，os.path.expandvars 會將 ${VAR} 替換為空字串或保持原樣
        # 安全處理 None 值：先取得值，如果不是 None 才調用 strip()
        nvd_key_raw = config['api_keys'].get('nvd')
        nvd_key = str(nvd_key_raw).strip() if nvd_key_raw is not None else ''
        if not nvd_key or nvd_key == '${NVD_API_KEY}' or nvd_key == 'YOUR_NVD_API_KEY_HERE' or nvd_key == 'None':
            print("警告：NVD API 金鑰未設定 (NVD_API_KEY)。NVD 收集器將以低速率運行。")
            
        openai_key_raw = config['api_keys'].get('openai')
        openai_key = str(openai_key_raw).strip() if openai_key_raw is not None else ''
        if not openai_key or openai_key == '${OPENAI_API_KEY}' or openai_key == 'YOUR_OPENAI_API_KEY_HERE' or openai_key == 'None':
            print("警告：OpenAI API 金鑰未設定 (OPENAI_API_KEY)。AI 摘要功能將無法使用。")
        
        # 處理 SMTP 密碼（加密/解密）
        if 'notification' in config and 'email' in config['notification']:
            email_config = config['notification'].get('email', {})
            if 'smtp_password' in email_config:
                # 使用統一的密碼取得函數（支援環境變數、加密字串、明碼）
                config['notification']['email']['smtp_password'] = get_smtp_password(
                    email_config['smtp_password']
                )
            
        return config
    except yaml.YAMLError as e:
        print(f"讀取 config.yaml 失敗：{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"載入設定時發生未知錯誤：{e}", file=sys.stderr)
        sys.exit(1)

def get_db_connection():
    """
    建立並回傳一個 SQLite 資料庫連線
    """
    config = load_config()
    # 先用 Docker 目錄，若不存在則回退本機目錄
    db_file_docker = os.path.join(APP_DIR_DOCKER, config['database']['file'])
    db_file_local = os.path.join(APP_DIR_LOCAL, config['database']['file'])
    db_file = db_file_docker if os.path.exists(db_file_docker) else db_file_local
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row # 讓查詢結果可以像字典一樣用欄位名存取
        print(f"資料庫連線成功：{db_file}")
    except Error as e:
        print(f"資料庫連線失敗：{e}", file=sys.stderr)
        
    return conn
