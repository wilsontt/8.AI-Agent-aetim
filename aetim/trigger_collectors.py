#!/usr/bin/env python3
"""
AETIM 立即觸發收集任務腳本
用途：手動觸發所有收集器立即執行一次

使用方式：
1. 在 Docker 容器內執行：
   docker-compose exec aetim python trigger_collectors.py

2. 使用信號觸發（如果排程器正在運行）：
   docker-compose exec aetim kill -SIGUSR1 1

3. 在本地環境執行：
   python trigger_collectors.py
"""

import sys
import os
from datetime import datetime
from utils import get_db_connection, load_config
import collectors

def main():
    """立即執行所有收集器任務"""
    print("=" * 60)
    print(f"[{datetime.now()}] --- AETIM 立即觸發收集任務 ---")
    print("=" * 60)
    
    db_conn = None
    try:
        # 載入設定
        config = load_config()
        
        # 建立資料庫連線
        db_conn = get_db_connection()
        
        if db_conn is None:
            print("錯誤：無法獲取資料庫連線，無法執行收集任務。", file=sys.stderr)
            sys.exit(1)
        
        print("\n開始執行所有收集器...\n")
        
        # 依照 PIR 優先級執行
        # P0 (CISA KEV) - 緊急
        collectors.fetch_cisa_kev(db_conn, config)
        
        # P1 (NVD) - 高
        collectors.fetch_nvd(db_conn, config)
        
        # P1/P2 (RSS Feeds) - 高/中
        collectors.fetch_rss_feeds(db_conn, config)
        
        # --- 關聯分析引擎 ---
        print("\n--- [立即觸發] 呼叫關聯分析引擎 (Correlation Engine) ---")
        import correlation_engine
        correlation_engine.run_correlation_analysis(db_conn, config)
        
        print("\n" + "=" * 60)
        print(f"[{datetime.now()}] --- 立即觸發任務執行完畢 ---")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n使用者中斷執行。", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n錯誤：執行收集任務時發生異常：{e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()
            print("資料庫連線已關閉。")

if __name__ == "__main__":
    main()
