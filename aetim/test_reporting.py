#!/usr/bin/env python3
"""
測試報告生成功能
"""

import sys
from utils import get_db_connection, load_config
import reporting_engine

def main():
    """測試報告生成"""
    print("=" * 60)
    print("測試報告生成引擎")
    print("=" * 60)
    
    db_conn = None
    try:
        config = load_config()
        db_conn = get_db_connection()
        
        if db_conn is None:
            print("錯誤：無法獲取資料庫連線。", file=sys.stderr)
            sys.exit(1)
        
        # 測試 CISO 週報
        print("\n1. 測試 CISO 週報生成...")
        report_data = reporting_engine.generate_ciso_weekly_report(db_conn, config, days=7)
        
        if report_data:
            print(f"   ✓ 成功生成報告資料：{report_data['stats']['total_threats']} 筆威脅")
            
            # 儲存報告
            filepath = reporting_engine.save_report(report_data, 'ciso_weekly', 'html')
            if filepath:
                print(f"   ✓ 報告已儲存：{filepath}")
        else:
            print("   ✗ 報告生成失敗")
        
        # 測試 IT 工單
        print("\n2. 測試 IT 工單生成...")
        tickets = reporting_engine.generate_it_tickets_for_high_risk(db_conn, config, risk_threshold=7.0)
        print(f"   ✓ 生成 {len(tickets)} 個 IT 工單")
        
        if tickets:
            print(f"\n   範例工單：")
            print(f"   工單編號：{tickets[0]['ticket_id']}")
            print(f"   優先級：{tickets[0]['priority']}")
            print(f"   標題：{tickets[0]['title']}")
        
        print("\n" + "=" * 60)
        print("測試完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n錯誤：測試失敗：{e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()

if __name__ == "__main__":
    main()
