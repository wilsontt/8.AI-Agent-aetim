import requests
import feedparser
import json
import sqlite3
from datetime import datetime
import pandas as pd
from utils import get_db_connection, load_config
import time 
import sys

# --- 輔助函式：檢查情資是否已存在 ---
def is_intel_exists(db_conn, unique_id):
    """
    檢查情資是否已存在 T_Raw_Intel 中 (依 title 或 cve_id)
    """
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT 1 FROM T_Raw_Intel WHERE title = ? OR cve_id = ?", (unique_id, unique_id))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"檢查情資是否存在時出錯：{e}")
        return True

# --- P0 (緊急) 收集器 ---
def fetch_cisa_kev(db_conn, config, use_backup=False):
    """
    PIR-04, PIR-01: 抓取 CISA 已知遭利用漏洞 (KEV)
    
    Args:
        db_conn: 資料庫連線
        config: 設定檔
        use_backup: 是否使用備用 URL（內部使用，避免遞迴）
    """
    print("--- [Collector] 執行：CISA KEV (P0) ---")
    
    # 備用 URL 清單（多個可能的 endpoint）
    backup_urls = [
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        "https://www.cisa.gov/known-exploited-vulnerabilities-catalog/known-exploited-vulnerabilities.json",
    ]
    
    # 決定使用的 URL
    if use_backup:
        # 如果已經嘗試過主要 URL，使用第一個備用 URL
        url = backup_urls[0]
        print(f"[除錯] 使用備用 URL：{url}")
    else:
        url = config['threat_feeds']['cisa_kev']
        print(f"[除錯] 使用主要 URL：{url}")
    
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'AETIM-Collector/1.0'})
        response.raise_for_status() 
        data = response.json()
        new_vulns_found = 0
        
        # 檢查資料格式是否正確
        if not isinstance(data, dict):
            raise ValueError(f"CISA KEV 資料格式錯誤：預期 dict，得到 {type(data)}")
        
        vulnerabilities = data.get('vulnerabilities', [])
        if not vulnerabilities:
            print("警告：CISA KEV 資料為空，可能 URL 已變更或資料格式有變。")
            print(f"[除錯] 回傳資料結構：{list(data.keys())}")
            return
        
        print(f"[除錯] 找到 {len(vulnerabilities)} 筆漏洞記錄")
        
        for vuln in vulnerabilities:
            cve_id = vuln.get('cveID')
            if not cve_id:
                continue  # 跳過沒有 CVE ID 的記錄
                
            title = f"CISA KEV: {cve_id} - {vuln.get('vulnerabilityName', 'N/A')}"
            
            if not is_intel_exists(db_conn, cve_id):
                raw_data = json.dumps(vuln)
                cursor = db_conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO T_Raw_Intel (source, type, title, url, cve_id, raw_data, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'new')
                    """,
                    ('CISA_KEV', 'CVE', title, vuln.get('knownRansomwareUse', 'N/A'), cve_id, raw_data)
                )
                new_vulns_found += 1
                
        db_conn.commit()
        print(f"--- [Collector] CISA KEV 完成。發現 {new_vulns_found} 筆新情資。 ---")
        if new_vulns_found == 0:
            print("提示：所有漏洞已在資料庫中，或沒有新的漏洞。")
        
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            if not use_backup:
                print(f"錯誤：主要 CISA KEV URL 不存在 (404)。嘗試備用 URL...")
                # 嘗試備用 URL（只嘗試一次）
                try:
                    return fetch_cisa_kev(db_conn, config, use_backup=True)
                except Exception as backup_e:
                    print(f"錯誤：備用 URL 也失敗：{backup_e}")
            else:
                print(f"錯誤：備用 URL 也不存在 (404)")
            print(f"提示：請檢查 CISA KEV Catalog 官方網站確認正確的 JSON feed URL。")
            print(f"可能的 URL：")
            for backup_url in backup_urls:
                print(f"  - {backup_url}")
        else:
            print(f"錯誤：抓取 CISA KEV 失敗 (HTTP {e.response.status_code})：{e}")
    except requests.RequestException as e:
        print(f"錯誤：抓取 CISA KEV 失敗（網路錯誤）：{e}")
        print(f"提示：請檢查網路連線或防火牆設定。")
    except json.JSONDecodeError as e:
        print(f"錯誤：解析 CISA KEV JSON 失敗：{e}")
        print(f"[除錯] 回應內容（前 500 字元）：{response.text[:500]}")
    except Exception as e:
        print(f"錯誤：CISA KEV 收集器發生未預期錯誤：{e}")
        import traceback
        traceback.print_exc()

# --- P1/P2 (高/中) 收集器 ---
def fetch_rss_feeds(db_conn, config):
    """
    PIR-02, PIR-03, PIR-05: 抓取 TWCERT, VMware, MSRC 的 RSS Feeds
    """
    print("--- [Collector] 執行：RSS Feeds (P1/P2) ---")
    feeds = {
        'VMware': config['threat_feeds']['vmware_vmsa'],
        'MSRC': config['threat_feeds']['msrc_rss'],
        'TWCERT_Alert': config['threat_feeds']['twcert_rss'],
        'TWCERT_CC': config['threat_feeds']['twcert_cc_rss'],
    }
    
    new_entries_found = 0
    
    for source_name, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                
                if not is_intel_exists(db_conn, title):
                    raw_data = json.dumps({
                        'summary': entry.get('summary', 'N/A'),
                        'published': entry.get('published', 'N/A')
                    })
                    
                    cursor = db_conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO T_Raw_Intel (source, type, title, url, raw_data, status)
                        VALUES (?, ?, ?, ?, ?, 'new')
                        """,
                        (source_name, 'Advisory', title, link, raw_data)
                    )
                    new_entries_found += 1
                    
        except Exception as e:
            print(f"錯誤：處理 RSS feed '{source_name}' ({url}) 失敗：{e}")

    if new_entries_found > 0:
        db_conn.commit()
    print(f"--- [Collector] RSS Feeds 完成。發現 {new_entries_found} 筆新情資。 ---")


# --- P1 (高) 收集器 ---
def fetch_nvd(db_conn, config):
    """
    PIR-01, PIR-02, PIR-03: 根據 PIR 關鍵字抓取 NVD
    *** (第 3 版重構：修正日期格式與增加防呆) ***
    """
    print("--- [Collector] 執行：NVD (P1) ---")
    base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    api_key = config['api_keys'].get('nvd', '')
    headers = {'apiKey': api_key} if api_key else {}
    
    keywords = [k.lower() for k in config['pir_keywords']]
    new_vulns_found = 0
    
    # --- (修正點) 建立正確的 NVD 日期格式 ---
    # 格式: YYYY-MM-DDTHH:mm:ss.SSSZ
    try:
        end_time = datetime.utcnow()
        start_time = end_time - pd.Timedelta(days=1)
        
        # .isoformat() 產生 '...T...123456'
        # 我們需要切到毫秒 ([:-3]) 並加上 'Z'
        nvd_start_time = start_time.isoformat()[:-3] + 'Z'
        nvd_end_time = end_time.isoformat()[:-3] + 'Z'
    except Exception as e:
        print(f"錯誤：建立 NVD 日期格式失敗：{e}", file=sys.stderr)
        return

    params = {
        'resultsPerPage': 200,
        'pubStartDate': nvd_start_time,
        'pubEndDate': nvd_end_time
    }
    
    try:
        print(f"[NVD Debug] 正在抓取 {nvd_start_time} 至 {nvd_end_time} 的所有 CVEs...")
        response = requests.get(base_url, headers=headers, params=params, timeout=60) 
        
        print(f"[NVD Debug] 抓取完成. 狀態: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        all_vulns = data.get('vulnerabilities', [])
        print(f"[NVD Debug] 獲得 {len(all_vulns)} 筆 CVEs. 準備開始本地端過濾...")
        
        for vuln in all_vulns:
            # --- (防呆點) 確保 cve 是字典 ---
            cve = vuln.get('cve')
            if not isinstance(cve, dict):
                print(f"[NVD Debug] 跳過一筆格式錯誤的 CVE (cve 非 dict)")
                continue

            cve_id = cve.get('id')
            if not cve_id:
                print(f"[NVD Debug] 跳過一筆沒有 CVE ID 的資料")
                continue
                
            cve_data_as_string = json.dumps(cve).lower()
            
            matched_keyword = None
            for keyword in keywords:
                if keyword in cve_data_as_string:
                    matched_keyword = keyword
                    break 
            
            if matched_keyword:
                if not is_intel_exists(db_conn, cve_id):
                    cvss_score = 0.0
                    
                    # --- (防呆點) 確保 metrics 結構正確 ---
                    metrics_data = cve.get('metrics', {}).get('cvssMetricV31', [])
                    if isinstance(metrics_data, list) and len(metrics_data) > 0:
                        cvss_data = metrics_data[0].get('cvssData', {})
                        if isinstance(cvss_data, dict):
                            cvss_score = cvss_data.get('baseScore', 0.0)
                    
                    title = f"NVD: {cve_id} (Keyword: {matched_keyword})"
                    raw_data = json.dumps(cve)
                    
                    cursor = db_conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO T_Raw_Intel (source, type, title, cve_id, cvss_score, raw_data, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'new')
                        """,
                        ('NVD', 'CVE', title, cve_id, cvss_score, raw_data)
                    )
                    new_vulns_found += 1
                    print(f"[NVD Debug] 發現相符 CVE: {cve_id} (關鍵字: {matched_keyword})")
        
        is_key_valid = (api_key and api_key != 'YOUR_NVD_API_KEY_HERE')
        sleep_duration = 6 if is_key_valid else 10 
        print(f"[NVD Debug] NVD 任務完成. 休息 {sleep_duration} 秒...")
        time.sleep(sleep_duration)

    except requests.exceptions.Timeout as e:
        print(f"錯誤 (Timeout)：抓取 NVD API 超時：{e}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"錯誤 (Request)：抓取 NVD API 失敗 (狀態碼 {e.response.status_code if e.response else 'N/A'})：{e}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"錯誤 (JSON)：解析 NVD JSON 失敗：{e}", file=sys.stderr)
            
    if new_vulns_found > 0:
        db_conn.commit()
    print(f"--- [Collector] NVD 完成。發現 {new_vulns_found} 筆新情資。 ---")



# import requests
# import feedparser
# import json
# import sqlite3
# from datetime import datetime  # <--- 新增
# import pandas as pd            # <--- 新增
# from utils import get_db_connection, load_config
# import time # 匯入 time 模組 以便使用 sleep 函式

# # --- 輔助函式：檢查情資是否已存在 ---
# def is_intel_exists(db_conn, unique_id):
#     """
#     檢查情資是否已存在 T_Raw_Intel 中 (依 title 或 cve_id)
#     """
#     try:
#         cursor = db_conn.cursor()
#         # 我們用 title 或 cve_id 作為唯一鍵
#         cursor.execute("SELECT 1 FROM T_Raw_Intel WHERE title = ? OR cve_id = ?", (unique_id, unique_id))
#         return cursor.fetchone() is not None
#     except sqlite3.Error as e:
#         print(f"檢查情資是否存在時出錯：{e}")
#         return True # 發生錯誤時，預設為存在，避免重複寫入

# # --- P0 (緊急) 收集器 ---
# def fetch_cisa_kev(db_conn, config):
#     """
#     PIR-04, PIR-01: 抓取 CISA 已知遭利用漏洞 (KEV)
#     """
#     print("--- [Collector] 執行：CISA KEV (P0) ---")
#     url = config['threat_feeds']['cisa_kev']
#     try:
#         response = requests.get(url, timeout=15)
#         response.raise_for_status() # 如果 http code 不是 200, 拋出例外
        
#         data = response.json()
#         new_vulns_found = 0
        
#         for vuln in data.get('vulnerabilities', []):
#             cve_id = vuln.get('cveID')
#             title = f"CISA KEV: {cve_id} - {vuln.get('vulnerabilityName')}"
            
#             if not is_intel_exists(db_conn, cve_id):
#                 raw_data = json.dumps(vuln)
#                 # 嘗試從 NVD 抓取 CVSS (CISA KEV 不直接提供)
#                 # 這裡我們先簡化，CVSS 在關聯分析階段再抓
                
#                 cursor = db_conn.cursor()
#                 cursor.execute(
#                     """
#                     INSERT INTO T_Raw_Intel (source, type, title, url, cve_id, raw_data, status)
#                     VALUES (?, ?, ?, ?, ?, ?, 'new')
#                     """,
#                     ('CISA_KEV', 'CVE', title, vuln.get('knownRansomwareUse', 'N/A'), cve_id, raw_data)
#                 )
#                 new_vulns_found += 1
                
#         db_conn.commit()
#         print(f"--- [Collector] CISA KEV 完成。發現 {new_vulns_found} 筆新情資。 ---")
        
#     except requests.RequestException as e:
#         print(f"錯誤：抓取 CISA KEV 失敗：{e}")
#     except json.JSONDecodeError as e:
#         print(f"錯誤：解析 CISA KEV JSON 失敗：{e}")

# # --- P1/P2 (高/中) 收集器 ---
# def fetch_rss_feeds(db_conn, config):
#     """
#     PIR-02, PIR-03, PIR-05: 抓取 TWCERT, VMware, MSRC 的 RSS Feeds
#     """
#     print("--- [Collector] 執行：RSS Feeds (P1/P2) ---")
#     feeds = {
#         'VMware': config['threat_feeds']['vmware_vmsa'],
#         'MSRC': config['threat_feeds']['msrc_rss'],
#         'TWCERT_Alert': config['threat_feeds']['twcert_rss'],
#         'TWCERT_CC': config['threat_feeds']['twcert_cc_rss'],
#     }
    
#     new_entries_found = 0
    
#     for source_name, url in feeds.items():
#         try:
#             feed = feedparser.parse(url)
#             for entry in feed.entries:
#                 title = entry.title
#                 link = entry.link
                
#                 if not is_intel_exists(db_conn, title):
#                     raw_data = json.dumps({
#                         'summary': entry.get('summary', 'N/A'),
#                         'published': entry.get('published', 'N/A')
#                     })
                    
#                     cursor = db_conn.cursor()
#                     cursor.execute(
#                         """
#                         INSERT INTO T_Raw_Intel (source, type, title, url, raw_data, status)
#                         VALUES (?, ?, ?, ?, ?, 'new')
#                         """,
#                         (source_name, 'Advisory', title, link, raw_data)
#                     )
#                     new_entries_found += 1
                    
#         except Exception as e:
#             print(f"錯誤：處理 RSS feed '{source_name}' ({url}) 失敗：{e}")

#     if new_entries_found > 0:
#         db_conn.commit()
#     print(f"--- [Collector] RSS Feeds 完成。發現 {new_entries_found} 筆新情資。 ---")


# # --- P1 (高) 收集器 ---
# def fetch_nvd(db_conn, config):
#     """
#     PIR-01, PIR-02, PIR-03: 根據 PIR 關鍵字抓取 NVD
#     *** (全新重構邏輯) ***
#     """
#     print("--- [Collector] 執行：NVD (P1) ---")
#     base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
#     api_key = config['api_keys'].get('nvd', '')
#     headers = {'apiKey': api_key} if api_key else {}
    
#     # 準備本地端過濾用的關鍵字 (全部轉小寫)
#     keywords = config['pir_keywords']
#     new_vulns_found = 0
    
# # 設定 API 參數：抓取過去 24 小時內發布的 CVEs
#     params = {
#         'resultsPerPage': 200, # 一次抓 200 筆 (最大 2000)
#         'pubStartDate': (datetime.utcnow() - pd.Timedelta(days=1)).isoformat().replace('T', ' ')[:-3] + 'Z', # 格式 2025-10-22 17:30:00Z
#         'pubEndDate': datetime.utcnow().isoformat().replace('T', ' ')[:-3] + 'Z'
#     }
    
#     try:
#         print(f"[NVD Debug] 正在抓取過去 24 小時的所有 CVEs...")
#         response = requests.get(base_url, headers=headers, params=params, timeout=60) 
        
#         print(f"[NVD Debug] 抓取完成. 狀態: {response.status_code}")
#         response.raise_for_status()
#         data = response.json()
        
#         all_vulns = data.get('vulnerabilities', [])
#         print(f"[NVD Debug] 獲得 {len(all_vulns)} 筆 CVEs. 準備開始本地端過濾...")
        
#         # 迴圈檢查每一筆 CVE
#         for vuln in all_vulns:
#             cve = vuln.get('cve', {})
#             cve_id = cve.get('id')
            
#             # 將整筆 CVE 資料轉為小寫字串，以便搜尋
#             cve_data_as_string = json.dumps(cve).lower()
            
#             matched_keyword = None
            
#             # 檢查是否包含任何一個我們的關鍵字
#             for keyword in keywords:
#                 if keyword in cve_data_as_string:
#                     matched_keyword = keyword
#                     break # 找到一個就跳出
            
#             # 如果有匹配到，且資料庫不存在，就寫入
#             if matched_keyword:
#                 if not is_intel_exists(db_conn, cve_id):
#                     cvss_score = 0.0
#                     metrics = cve.get('metrics', {}).get('cvssMetricV31', [])
#                     if metrics:
#                         cvss_score = metrics[0].get('cvssData', {}).get('baseScore', 0.0)
                    
#                     title = f"NVD: {cve_id} (Keyword: {matched_keyword})"
#                     raw_data = json.dumps(cve)
                    
#                     cursor = db_conn.cursor()
#                     cursor.execute(
#                         """
#                         INSERT INTO T_Raw_Intel (source, type, title, cve_id, cvss_score, raw_data, status)
#                         VALUES (?, ?, ?, ?, ?, ?, 'new')
#                         """,
#                         ('NVD', 'CVE', title, cve_id, cvss_score, raw_data)
#                     )
#                     new_vulns_found += 1
#                     print(f"[NVD Debug] 發現相符 CVE: {cve_id} (關鍵字: {matched_keyword})")
        
#         # API 速率限制 (無論有無 Key 都休息一下)
#         is_key_valid = (api_key and api_key != 'YOUR_NVD_API_KEY_HERE')
#         sleep_duration = 6 if is_key_valid else 10 # 沒 Key 休息 10 秒
#         print(f"[NVD Debug] NVD 任務完成. 休息 {sleep_duration} 秒...")
#         time.sleep(sleep_duration)

#     except requests.exceptions.Timeout as e:
#         print(f"錯誤 (Timeout)：抓取 NVD API 超時：{e}", file=sys.stderr)
#     except requests.RequestException as e:
#         print(f"錯誤 (Request)：抓取 NVD API 失敗：{e}", file=sys.stderr)
#     except json.JSONDecodeError as e:
#         print(f"錯誤 (JSON)：解析 NVD JSON 失敗：{e}", file=sys.stderr)
            
#     if new_vulns_found > 0:
#         db_conn.commit()
#     print(f"--- [Collector] NVD 完成。發現 {new_vulns_found} 筆新情資。 ---")
