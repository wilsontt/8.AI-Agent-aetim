#!/usr/bin/env python3
"""
週報排程診斷腳本
用於快速檢查週報排程是否正常運行
"""

import os
import sys
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from utils import load_config
from job_events import list_recent_events

def check_weekly_schedule():
    """檢查週報排程狀態"""
    print("=" * 60)
    print("週報排程診斷工具")
    print("=" * 60)
    print()
    
    # 1. 檢查設定
    print("【1. 檢查排程設定】")
    try:
        config = load_config()
        reporting = config.get('reporting', {})
        weekly = reporting.get('weekly_report', {})
        enabled = weekly.get('enabled', False)
        schedule_struct = weekly.get('schedule_struct', {})
        
        day = str(schedule_struct.get('day_of_week', '')).lower()
        hour = schedule_struct.get('hour', None)
        minute = schedule_struct.get('minute', None)
        timezone_str = schedule_struct.get('timezone', 'Asia/Taipei')
        
        print(f"  啟用狀態: {'✓ 已啟用' if enabled else '✗ 未啟用'}")
        if enabled:
            print(f"  排程時間: 每週 {day} {hour:02d}:{minute:02d}")
            print(f"  時區: {timezone_str}")
        else:
            print("  ⚠ 週報排程未啟用，請檢查 config.yaml")
            return
    except Exception as e:
        print(f"  ✗ 讀取設定失敗: {e}")
        return
    
    print()
    
    # 2. 檢查排程器進程
    print("【2. 檢查排程器進程】")
    scheduler_pid_file = os.path.join(os.path.dirname(__file__), 'scheduler.pid')
    scheduler_running = False
    scheduler_pid = None
    
    if os.path.exists(scheduler_pid_file):
        try:
            with open(scheduler_pid_file, 'r') as f:
                scheduler_pid = int(f.read().strip())
            # 檢查進程是否存在
            try:
                os.kill(scheduler_pid, 0)  # 發送信號 0 檢查進程是否存在
                scheduler_running = True
                print(f"  ✓ 排程器正在運行 (PID: {scheduler_pid})")
            except OSError:
                print(f"  ✗ PID 文件存在但進程不存在 (PID: {scheduler_pid})")
                print("  ⚠ 可能需要重啟排程器服務")
        except Exception as e:
            print(f"  ✗ 讀取 PID 文件失敗: {e}")
    else:
        print("  ✗ PID 文件不存在")
        print("  ⚠ 排程器可能未啟動")
    
    print()
    
    # 3. 計算下次執行時間
    print("【3. 下次執行時間】")
    if enabled and day and hour is not None and minute is not None:
        from datetime import timedelta
        taipei_tz = ZoneInfo(timezone_str)
        now = datetime.now(taipei_tz)
        
        days_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        target_weekday = days_map.get(day, 0)
        current_weekday = now.weekday()
        
        days_ahead = target_weekday - current_weekday
        if days_ahead < 0 or (days_ahead == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute))):
            days_ahead += 7
        
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        print(f"  當前時間: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"  下次執行: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        diff = next_run - now
        hours = diff.total_seconds() / 3600
        print(f"  倒數時間: {int(hours)} 小時 {int((diff.total_seconds() % 3600) / 60)} 分鐘")
        
        if next_run < now:
            print("  ⚠ 警告：設定的執行時間已過！")
    else:
        print("  ⚠ 無法計算（設定不完整）")
    
    print()
    
    # 4. 檢查最近的觸發記錄
    print("【4. 最近觸發記錄】")
    try:
        events = list_recent_events(limit=5)
        scheduled_events = [e for e in events if e.get('phase') == 'scheduled']
        
        if scheduled_events:
            latest = scheduled_events[0]
            triggered_at = latest.get('triggered_at')
            if triggered_at:
                trigger_time = datetime.fromisoformat(triggered_at.replace('Z', '+00:00'))
                print(f"  最近觸發: {trigger_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  狀態: {latest.get('status', 'N/A')}")
                print(f"  訊息: {latest.get('message', 'N/A')}")
            else:
                print("  （無觸發時間記錄）")
        else:
            print("  （無排程觸發記錄）")
    except Exception as e:
        print(f"  ✗ 讀取記錄失敗: {e}")
    
    print()
    
    # 5. 診斷建議
    print("【5. 診斷建議】")
    issues = []
    
    if not enabled:
        issues.append("週報排程未啟用")
    
    if not scheduler_running:
        issues.append("排程器未運行 - 需要啟動排程器服務")
    
    if enabled and day and hour is not None and minute is not None:
        from datetime import timedelta
        taipei_tz = ZoneInfo(timezone_str)
        now = datetime.now(taipei_tz)
        days_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        target_weekday = days_map.get(day, 0)
        current_weekday = now.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead < 0 or (days_ahead == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute))):
            days_ahead += 7
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        if next_run < now:
            issues.append("設定的執行時間已過 - 排程器可能未正確觸發")
    
    if not issues:
        print("  ✓ 所有檢查通過，排程應該正常運行")
        print()
        print("  如果排程仍未觸發，請檢查：")
        print("  1. 排程器日誌 (scheduler.out) 是否有錯誤訊息")
        print("  2. 系統時區是否正確設定為 Asia/Taipei")
        print("  3. 設定變更後是否已重新載入排程（發送 SIGUSR2 或重啟服務）")
    else:
        print("  發現以下問題：")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("  建議操作：")
        if "排程器未運行" in str(issues):
            print("  - 啟動排程器服務：docker-compose up -d 或 systemctl start aetim-scheduler")
        if "未啟用" in str(issues):
            print("  - 在 config.yaml 中設定 reporting.weekly_report.enabled = true")
        if "執行時間已過" in str(issues):
            print("  - 檢查排程器日誌，確認任務是否已註冊")
            print("  - 嘗試重新載入排程：kill -USR2 <scheduler_pid>")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    check_weekly_schedule()

