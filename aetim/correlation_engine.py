#!/usr/bin/env python3
"""
AETIM 關聯與風險評分引擎 (Correlation & Scoring Engine)
功能：比對原始情資與內部資產，並計算風險分數

邏輯流程：
1. 載入資產清單（從 T_Assets）
2. 提取新情資（從 T_Raw_Intel，status='new'）
3. 迭代比對（CVE 比對、IOC 比對）
4. 風險評分計算（CVSS + 情境加權）
5. 寫入 T_Validated_Threats 資料表
"""

import sys
import json
import sqlite3
import pandas as pd
import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from utils import get_db_connection, load_config


def extract_product_name_from_intel(intel_data: Dict) -> List[str]:
    """
    從情資資料中提取產品名稱（用於比對）
    
    Args:
        intel_data: 情資資料字典（包含 raw_data 和其他欄位）
    
    Returns:
        產品名稱列表
    """
    product_names = []
    
    # 嘗試從不同來源提取產品名稱
    # 1. 從 raw_data JSON 中提取
    if intel_data.get('raw_data'):
        try:
            raw_data = json.loads(intel_data['raw_data'])
            
            # CISA KEV 格式
            if 'vulnerabilityName' in raw_data:
                product_names.append(raw_data['vulnerabilityName'])
            if 'product' in raw_data:
                product_names.append(raw_data['product'])
            if 'vendorProject' in raw_data:
                product_names.append(raw_data['vendorProject'])
            
            # NVD 格式
            if 'cve' in raw_data:
                cve_data = raw_data['cve']
                # 從 configurations 中提取
                if 'configurations' in cve_data:
                    for config in cve_data['configurations']:
                        if 'nodes' in config:
                            for node in config['nodes']:
                                if 'cpeMatch' in node:
                                    for cpe in node['cpeMatch']:
                                        if 'criteria' in cpe:
                                            # CPE 格式：cpe:2.3:a:microsoft:sql_server:2017:*:*:*:*:*:*:*
                                            # 提取產品名稱
                                            cpe_parts = cpe['criteria'].split(':')
                                            if len(cpe_parts) >= 4:
                                                vendor = cpe_parts[3]
                                                product = cpe_parts[4]
                                                if product and product != '*':
                                                    product_names.append(f"{vendor} {product}")
                                                if vendor and vendor != '*':
                                                    product_names.append(vendor)
                
                # 從 descriptions 中提取關鍵字
                if 'descriptions' in cve_data:
                    for desc in cve_data['descriptions']:
                        if desc.get('lang') == 'en':
                            text = desc.get('value', '').lower()
                            # 搜尋常見產品名稱
                            keywords = ['windows server', 'sql server', 'vmware', 'esxi', 
                                       'microsoft', 'delphi', 'eep']
                            for keyword in keywords:
                                if keyword in text:
                                    product_names.append(keyword)
            
            # RSS Feed 格式
            if 'summary' in raw_data:
                summary = raw_data['summary'].lower()
                keywords = ['windows server', 'sql server', 'vmware', 'esxi', 'microsoft']
                for keyword in keywords:
                    if keyword in summary:
                        product_names.append(keyword)
        
        except json.JSONDecodeError:
            pass
    
    # 2. 從 title 中提取關鍵字
    if intel_data.get('title'):
        title = intel_data['title'].lower()
        # 提取可能的產品名稱
        keywords = {
            'windows server': ['windows server 2008', 'windows server 2016', 'windows server 2022'],
            'sql server': ['sql server', 'mssql'],
            'vmware': ['vmware esxi', 'vmware', 'esxi'],
            'microsoft': ['microsoft'],
        }
        for category, variants in keywords.items():
            for variant in variants:
                if variant in title:
                    product_names.append(variant)
                    product_names.append(category)
    
    # 去重並返回
    return list(set([p.lower().strip() for p in product_names if p]))


def match_cve_with_assets(intel_data: Dict, df_assets: pd.DataFrame) -> List[int]:
    """
    比對 CVE 情資與資產清單
    
    Args:
        intel_data: 情資資料
        df_assets: 資產 DataFrame
    
    Returns:
        匹配的資產 ID 列表
    """
    matched_asset_ids = []
    
    # 提取產品名稱
    product_names = extract_product_name_from_intel(intel_data)
    
    if not product_names:
        return matched_asset_ids
    
    # 對每個資產進行比對
    for _, asset in df_assets.iterrows():
        asset_id = asset['id']
        os_version = str(asset.get('os_version', '')).lower()
        applications = str(asset.get('applications', '')).lower()
        
        # 模糊字串比對
        for product_name in product_names:
            # 檢查產品名稱是否在 OS 或應用程式中
            if (product_name in os_version or product_name in applications or
                os_version in product_name or applications in product_name):
                matched_asset_ids.append(asset_id)
                print(f"[比對] 找到匹配：{product_name} <-> 資產 ID {asset_id} ({asset.get('hostname', 'N/A')})")
                break  # 找到匹配後跳出內層迴圈，避免重複加入
    
    return list(set(matched_asset_ids))  # 去重


def calculate_risk_score(intel_data: Dict, asset_data: Dict) -> float:
    """
    計算風險分數（基於 CVSS 和情境加權）
    
    Args:
        intel_data: 情資資料
        asset_data: 資產資料
    
    Returns:
        風險分數（0-10）
    """
    # 基礎分數：CVSS 分數，如果沒有則使用預設值 7.0
    cvss_score = intel_data.get('cvss_score')
    
    # 處理 None 值或無效值
    if cvss_score is None or cvss_score == '' or cvss_score == 'None':
        base_score = 7.0  # 預設中等風險
        print(f"[評分] CVSS 分數為空或無效，使用預設值：{base_score}")
    else:
        try:
            base_score = float(cvss_score)
            if base_score == 0.0 or base_score < 0 or base_score > 10:
                base_score = 7.0  # 預設中等風險
                print(f"[評分] CVSS 分數無效 ({cvss_score})，使用預設值：{base_score}")
            else:
                print(f"[評分] 基礎分數 (CVSS)：{base_score}")
        except (ValueError, TypeError) as e:
            print(f"[評分] CVSS 分數轉換失敗 ({cvss_score})：{e}，使用預設值")
            base_score = 7.0  # 預設中等風險
    
    # 情境加權（根據 PIR 需求）
    multipliers = []
    
    # 1. 是否對外暴露（Is_Public == 'Y'）
    if asset_data.get('is_public', '').upper() == 'Y':
        base_score *= 1.5
        multipliers.append("對外暴露 (x1.5)")
        print(f"[評分] 套用加權：對外暴露 (x1.5) -> {base_score}")
    
    # 2. 業務關鍵性（高）
    if asset_data.get('business_criticality', '').upper() in ['高', 'HIGH', 'CRITICAL']:
        base_score *= 1.3
        multipliers.append("業務關鍵性-高 (x1.3)")
        print(f"[評分] 套用加權：業務關鍵性-高 (x1.3) -> {base_score}")
    
    # 3. CISA KEV（已被積極利用）
    if intel_data.get('source', '') == 'CISA_KEV':
        base_score *= 2.0
        multipliers.append("CISA KEV (x2.0)")
        print(f"[評分] 套用加權：CISA KEV (x2.0) -> {base_score}")
    
    # 4. 老舊系統（Windows Server 2008）
    os_version = str(asset_data.get('os_version', '')).lower()
    if '2008' in os_version or '2008' in str(asset_data.get('applications', '')).lower():
        base_score *= 1.2
        multipliers.append("老舊系統 (x1.2)")
        print(f"[評分] 套用加權：老舊系統 (x1.2) -> {base_score}")
    
    # 5. 資料敏感度高
    if asset_data.get('data_sensitivity', '').upper() in ['高', 'HIGH', 'CRITICAL']:
        base_score *= 1.1
        multipliers.append("資料敏感度高 (x1.1)")
        print(f"[評分] 套用加權：資料敏感度高 (x1.1) -> {base_score}")
    
    # 限制最大分數為 10.0
    final_score = min(10.0, base_score)
    
    if multipliers:
        print(f"[評分] 最終風險分數：{final_score:.2f} (加權因子：{', '.join(multipliers)})")
    else:
        print(f"[評分] 最終風險分數：{final_score:.2f} (無額外加權)")
    
    return round(final_score, 2)


def run_correlation_analysis(db_conn, config):
    """
    執行關聯分析主函數
    
    Args:
        db_conn: 資料庫連線
        config: 設定檔
    """
    print("=" * 60)
    print(f"[{datetime.now()}] --- 啟動關聯分析引擎 ---")
    print("=" * 60)
    
    try:
        # 步驟 1：載入資產清單
        print("\n[步驟 1] 載入資產清單...")
        df_assets = pd.read_sql_query("SELECT * FROM T_Assets", db_conn)
        asset_count = len(df_assets)
        print(f"[步驟 1] 成功載入 {asset_count} 筆資產")
        
        if asset_count == 0:
            print("警告：資產清單為空，無法進行比對。")
            return
        
        # 步驟 2：提取新情資
        print("\n[步驟 2] 提取新情資...")
        query = """
            SELECT id, source, type, title, url, cve_id, cvss_score, raw_data, status, timestamp
            FROM T_Raw_Intel
            WHERE status = 'new'
            ORDER BY timestamp DESC
        """
        df_new_intel = pd.read_sql_query(query, db_conn)
        intel_count = len(df_new_intel)
        print(f"[步驟 2] 找到 {intel_count} 筆新情資")
        
        if intel_count == 0:
            print("提示：沒有新情資需要處理。")
            return
        
        # 步驟 3：迭代比對
        print("\n[步驟 3] 開始比對情資與資產...")
        validated_threats = []  # 儲存驗證後的威脅
        processed_intel_ids = []  # 儲存已處理的情資 ID
        
        for _, intel_row in df_new_intel.iterrows():
            try:
                intel_data = intel_row.to_dict()
                intel_id = intel_data.get('id')
                intel_type = intel_data.get('type', '').upper() if intel_data.get('type') else ''
                
                if not intel_id:
                    print(f"[警告] 跳過無效情資：缺少 ID")
                    continue
                
                print(f"\n[處理] 情資 ID {intel_id}: {str(intel_data.get('title', 'N/A'))[:50]}")
                print(f"       來源：{intel_data.get('source', 'N/A')}, 類型：{intel_type}, CVSS：{intel_data.get('cvss_score', 'N/A')}")
                
                is_match = False
                matched_asset_ids = []
                
                # 比對邏輯 A：CVE 比對
                if intel_type == 'CVE':
                    matched_asset_ids = match_cve_with_assets(intel_data, df_assets)
                    if matched_asset_ids:
                        is_match = True
                        print(f"[比對] 找到 {len(matched_asset_ids)} 個匹配的資產")
                
                # 比對邏輯 B：IOC 比對（未來實現）
                # elif intel_type == 'IOC_REPORT':
                #     # TODO: 實現 IOC IP 比對邏輯
                #     pass
                
                # 步驟 4：風險評分與寫入
                if is_match and matched_asset_ids:
                    for asset_id in matched_asset_ids:
                        try:
                            # 獲取資產資料
                            asset_row = df_assets[df_assets['id'] == asset_id]
                            if asset_row.empty:
                                print(f"[警告] 找不到資產 ID {asset_id}，跳過")
                                continue
                            
                            asset_data = asset_row.iloc[0].to_dict()
                            
                            # 計算風險分數
                            risk_score = calculate_risk_score(intel_data, asset_data)
                            
                            # 準備寫入資料
                            validated_threat = {
                                'intel_id': intel_id,
                                'asset_id': asset_id,
                                'risk_score': risk_score,
                                'status': 'new',
                                'notes': f"來源：{intel_data.get('source', 'N/A')}, CVE：{intel_data.get('cve_id', 'N/A')}"
                            }
                            validated_threats.append(validated_threat)
                            
                            print(f"[結果] 威脅已驗證：情資 ID {intel_id} -> 資產 ID {asset_id} (風險分數：{risk_score})")
                        except Exception as asset_e:
                            print(f"[錯誤] 處理資產 ID {asset_id} 時失敗：{asset_e}", file=sys.stderr)
                            continue
                    
                    processed_intel_ids.append(intel_id)
                else:
                    # 沒有匹配，標記為已處理（無匹配）
                    processed_intel_ids.append(intel_id)
                    print(f"[結果] 無匹配資產，標記為已記錄（無匹配）")
            
            except Exception as intel_e:
                print(f"[錯誤] 處理情資 ID {intel_id} 時發生錯誤：{intel_e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                # 即使錯誤也要標記為已處理，避免無限重試
                if intel_id and intel_id not in processed_intel_ids:
                    processed_intel_ids.append(intel_id)
                continue
        
        # 步驟 5：批次寫入資料庫
        print(f"\n[步驟 4] 寫入驗證後的威脅...")
        cursor = db_conn.cursor()
        
        threats_written = 0
        threats_failed = 0
        for threat in validated_threats:
            try:
                cursor.execute(
                    """
                    INSERT INTO T_Validated_Threats 
                    (intel_id, asset_id, risk_score, status, notes, timestamp)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (threat['intel_id'], threat['asset_id'], threat['risk_score'], 
                     threat['status'], threat['notes'])
                )
                threats_written += 1
            except sqlite3.Error as e:
                threats_failed += 1
                print(f"[錯誤] 寫入威脅資料失敗（情資 ID {threat.get('intel_id', 'N/A')}）：{e}", file=sys.stderr)
        
        if threats_failed > 0:
            print(f"[警告] {threats_failed} 筆威脅資料寫入失敗")
        
        # 更新 T_Raw_Intel 狀態
        print(f"\n[步驟 5] 更新情資狀態...")
        for intel_id in processed_intel_ids:
            # 檢查是否有匹配的威脅
            has_match = any(t['intel_id'] == intel_id for t in validated_threats)
            new_status = 'processed' if has_match else 'logged (no match)'
            
            cursor.execute(
                "UPDATE T_Raw_Intel SET status = ? WHERE id = ?",
                (new_status, intel_id)
            )
        
        db_conn.commit()
        
        # 結果摘要
        print("\n" + "=" * 60)
        print(f"[{datetime.now()}] --- 關聯分析完成 ---")
        print("=" * 60)
        processed_with_match = len(set(t['intel_id'] for t in validated_threats))
        processed_no_match = intel_count - processed_with_match
        
        print(f"處理情資：{intel_count} 筆")
        print(f"驗證威脅：{threats_written} 筆")
        print(f"匹配資產：{len(set(t['asset_id'] for t in validated_threats))} 個")
        print(f"有匹配情資：{processed_with_match} 筆")
        print(f"無匹配情資：{processed_no_match} 筆")
        
        # 顯示高風險威脅
        if validated_threats:
            high_risk_threats = [t for t in validated_threats if t['risk_score'] >= 7.0]
            critical_threats = [t for t in validated_threats if t['risk_score'] >= 9.0]
            
            if high_risk_threats:
                print(f"\n高風險威脅（風險分數 >= 7.0）：{len(high_risk_threats)} 筆")
                for threat in sorted(high_risk_threats, key=lambda x: x['risk_score'], reverse=True)[:5]:
                    print(f"  - 情資 ID {threat['intel_id']} -> 資產 ID {threat['asset_id']} (風險：{threat['risk_score']})")
            
            # 觸發嚴重威脅通知
            if critical_threats:
                print(f"\n[通知] 發現 {len(critical_threats)} 筆嚴重威脅（風險分數 >= 9.0），觸發通知...")
                try:
                    import notification_handler
                    notification_config = config.get('notification', {})
                    if notification_config.get('enabled', False):
                        # 檢查並發送嚴重威脅通知
                        notification_handler.check_and_notify_critical_threats(db_conn, config)
                    else:
                        print("[通知] 通知功能未啟用（config.yaml 中 notification.enabled = false）")
                except Exception as notify_e:
                    print(f"[警告] 通知處理失敗：{notify_e}", file=sys.stderr)
    
    except Exception as e:
        print(f"\n錯誤：關聯分析引擎執行失敗：{e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        db_conn.rollback()


def main():
    """主函數：執行關聯分析"""
    db_conn = None
    try:
        config = load_config()
        db_conn = get_db_connection()
        
        if db_conn is None:
            print("錯誤：無法獲取資料庫連線。", file=sys.stderr)
            sys.exit(1)
        
        run_correlation_analysis(db_conn, config)
    
    except KeyboardInterrupt:
        print("\n使用者中斷執行。", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n錯誤：執行關聯分析時發生異常：{e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()
            print("\n資料庫連線已關閉。")


if __name__ == "__main__":
    main()
