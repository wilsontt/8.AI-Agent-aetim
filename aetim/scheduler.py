import time
import sys
import os
import signal
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from utils import get_db_connection, load_config
import collectors
from job_events import start_event, update_event

# 全域變數：用於信號處理
scheduler_instance = None
SCHEDULER_PID_FILE = os.path.join(os.path.dirname(__file__), 'scheduler.pid')

VALID_DAYS = {'mon','tue','wed','thu','fri','sat','sun'}

def get_weekly_schedule_from_config(config):
    """
    讀取 weekly_report 的結構化排程設定，並提供相容處理與預設值。
    回傳 (day_of_week, hour, minute)
    """
    try:
        reporting = config.get('reporting', {})
        weekly = reporting.get('weekly_report', {})
        schedule_struct = weekly.get('schedule_struct', {})
        day = str(schedule_struct.get('day_of_week', '')).lower()
        hour = schedule_struct.get('hour', None)
        minute = schedule_struct.get('minute', None)

        # 合法性檢查
        if day in VALID_DAYS and isinstance(hour, int) and 0 <= hour <= 23 and isinstance(minute, int) and 0 <= minute <= 59:
            return day, hour, minute

        # 向後相容：嘗試解析舊字串 "monday 08:00"
        legacy = weekly.get('schedule')
        if isinstance(legacy, str):
            parts = legacy.strip().split()
            if len(parts) == 2:
                day_map = {
                    'monday':'mon','tuesday':'tue','wednesday':'wed',
                    'thursday':'thu','friday':'fri','saturday':'sat','sunday':'sun',
                    'mon':'mon','tue':'tue','wed':'wed','thu':'thu','fri':'fri','sat':'sat','sun':'sun'
                }
                d = day_map.get(parts[0].lower())
                if d:
                    hm = parts[1]
                    if ':' in hm:
                        try:
                            h, m = hm.split(':')
                            h = int(h)
                            m = int(m)
                            if 0 <= h <= 23 and 0 <= m <= 59:
                                return d, h, m
                        except Exception:
                            pass
        # 預設值
        return 'mon', 8, 0
    except Exception:
        return 'mon', 8, 0

def reschedule_weekly_report(scheduler):
    """
    重新讀取設定並重排程 weekly_report 任務
    """
    try:
        config = load_config()
        reporting = config.get('reporting', {})
        weekly = reporting.get('weekly_report', {})
        enabled = weekly.get('enabled', False)

        # 先移除既有 job（若存在）
        try:
            scheduler.remove_job("job_weekly_report")
        except Exception:
            pass

        if not enabled:
            print("--- 週報排程：未啟用（enabled=false），不建立 weekly job ---")
            return

        # 取得新設定
        day, hour, minute = get_weekly_schedule_from_config(config)

        def generate_weekly_report_job():
            """週報生成任務"""
            db_conn = None
            ev = None
            try:
                print(f"\n[{datetime.now()}] --- 觸發週報生成任務 ---")
                ev = start_event({'phase': 'scheduled', 'message': '週報排程已觸發'})
                cfg = load_config()
                
                # 檢查週報通知是否啟用
                notification_config = cfg.get('notification', {})
                types_cfg = notification_config.get('types', {})
                weekly_cfg = types_cfg.get('weekly_report', {})
                weekly_enabled = weekly_cfg.get('enabled', True)  # 預設啟用
                email_enabled = notification_config.get('email', {}).get('enabled', False)
                
                if not weekly_enabled:
                    update_event(ev['id'], {
                        'phase': 'done',
                        'status': 'skipped',
                        'message': '週報通知未啟用（notification.types.weekly_report.enabled = false）'
                    })
                    print("[週報] 週報通知未啟用，跳過執行")
                    return
                
                if not email_enabled:
                    update_event(ev['id'], {
                        'phase': 'done',
                        'status': 'skipped',
                        'message': 'Email 通知未啟用（notification.email.enabled = false）'
                    })
                    print("[週報] Email 通知未啟用，跳過執行")
                    return
                
                db_conn = get_db_connection()
                if not db_conn:
                    update_event(ev['id'], {
                        'phase': 'done',
                        'status': 'error',
                        'message': '無法獲取資料庫連線'
                    })
                    print("[週報] 錯誤：無法獲取資料庫連線")
                    return
                
                update_event(ev['id'], {'phase': 'collect', 'message': '開始收集/分析/報告'})
                # 這裡假設收集與分析已由排程主流程執行；週報任務聚焦於報告+通知
                import reporting_engine
                import notification_handler
                
                # 先取得收件者列表和類型（用於決定生成哪種報告）
                rec_groups = weekly_cfg.get('recipients', [])
                recipients_map = notification_config.get('recipients', {})
                target_emails = []
                recipient_types = {}  # {email: ['ciso', 'it']}
                
                for g in rec_groups:
                    addr = recipients_map.get(g)
                    if addr:
                        target_emails.append(addr)
                        if addr not in recipient_types:
                            recipient_types[addr] = []
                        recipient_types[addr].append(g)
                
                # 相容舊結構
                if not target_emails:
                    to_addr = notification_config.get('email', {}).get('to_address', '')
                    if to_addr:
                        target_emails = [to_addr]
                        recipient_types[to_addr] = ['ciso']  # 預設為 CISO
                
                if not target_emails:
                    update_event(ev['id'], {
                        'phase': 'done',
                        'status': 'error',
                        'message': '沒有指定收件者'
                    })
                    print("[週報] 錯誤：沒有指定收件者")
                    return
                
                # 決定需要生成哪些報告
                needs_ciso_report = any('ciso' in recipient_types.get(addr, []) for addr in target_emails)
                needs_it_tickets = any('it' in recipient_types.get(addr, []) for addr in target_emails)
                
                print(f"[週報] 報告需求：CISO週報={needs_ciso_report}, IT工單={needs_it_tickets}")
                print(f"[週報] 收件者：{', '.join(target_emails)}")
                
                # 生成 CISO 週報（如果需要）
                ciso_report_filepath = None
                if needs_ciso_report:
                    update_event(ev['id'], {'phase': 'report', 'message': '生成 CISO 週報'})
                    report_data = reporting_engine.generate_weekly_report(db_conn, cfg)
                    if report_data:
                        ciso_report_filepath = reporting_engine.save_report(
                            report_data, 'ciso_weekly', 'html'
                        )
                        if ciso_report_filepath:
                            print(f"[週報] CISO 週報已生成：{ciso_report_filepath}")
                        else:
                            print("[週報] 警告：CISO 週報儲存失敗")
                    else:
                        print("[週報] 警告：CISO 週報資料生成失敗")
                
                # 生成 IT 工單（如果需要）
                it_tickets = []
                it_report_filepath = None
                if needs_it_tickets:
                    update_event(ev['id'], {'phase': 'report', 'message': '生成 IT 工單'})
                    # 生成高風險威脅的 IT 工單（風險分數 >= 7.0）
                    it_tickets = reporting_engine.generate_it_tickets_for_high_risk(db_conn, cfg, risk_threshold=7.0)
                    if it_tickets:
                        print(f"[週報] 已生成 {len(it_tickets)} 個 IT 工單")
                        # 將 IT 工單彙總為一個報告檔案（JSON 格式）
                        import json
                        from datetime import datetime
                        it_report_data = {
                            'report_type': 'IT Weekly Tickets Summary',
                            'generated_at': datetime.now().isoformat(),
                            'total_tickets': len(it_tickets),
                            'tickets': it_tickets
                        }
                        it_report_filepath = reporting_engine.save_report(
                            it_report_data, 'it_ticket', 'json'
                        )
                        if it_report_filepath:
                            print(f"[週報] IT 工單報告已生成：{it_report_filepath}")
                        else:
                            print("[週報] 警告：IT 工單報告儲存失敗")
                    else:
                        print("[週報] 本週無高風險威脅，無需生成 IT 工單")
                
                # 更新事件記錄
                report_filepaths = []
                if ciso_report_filepath:
                    report_filepaths.append(ciso_report_filepath)
                if it_report_filepath:
                    report_filepaths.append(it_report_filepath)
                if report_filepaths:
                    update_event(ev['id'], {'report_filepath': '; '.join(report_filepaths)})
                
                # 發送通知
                update_event(ev['id'], {'phase': 'notify', 'message': '開始發送週報通知'})
                
                try:
                    # 根據收件者類型發送對應的報告
                    success_count = 0
                    error_messages = []
                    
                    for addr in target_emails:
                        addr_types = recipient_types.get(addr, [])
                        try:
                            # 決定發送哪些報告
                            send_ciso = 'ciso' in addr_types and ciso_report_filepath
                            send_it = 'it' in addr_types and it_report_filepath
                            
                            if send_ciso:
                                print(f"[週報] 發送 CISO 週報至：{addr}")
                                notification_handler.notify_weekly_report(ciso_report_filepath, cfg, target_email=addr)
                                success_count += 1
                            
                            if send_it:
                                print(f"[週報] 發送 IT 工單報告至：{addr}")
                                notification_handler.notify_it_tickets(it_report_filepath, cfg, target_email=addr)
                                success_count += 1
                            
                            if not send_ciso and not send_it:
                                print(f"[週報] 警告：{addr} 無對應的報告可發送")
                                
                        except Exception as e:
                            error_msg = f"發送給 {addr} 失敗：{str(e)}"
                            error_messages.append(error_msg)
                            print(f"[週報] {error_msg}", file=sys.stderr)
                    
                    if success_count > 0:
                        update_event(ev['id'], {
                            'phase': 'done',
                            'status': 'success',
                            'message': f'週報生成並已寄出（{success_count} 封）',
                            'recipients': target_emails,
                            'email_result': 'success' if not error_messages else 'partial'
                        })
                        print(f"[週報] 週報已成功發送至：{', '.join(target_emails)}")
                    else:
                        update_event(ev['id'], {
                            'phase': 'done',
                            'status': 'error',
                            'message': '所有發送均失敗：' + '; '.join(error_messages) if error_messages else '無報告可發送',
                            'recipients': target_emails,
                            'email_result': 'error'
                        })
                        print(f"[週報] 所有發送均失敗", file=sys.stderr)
                        
                except Exception as ne:
                    error_msg = str(ne)
                    update_event(ev['id'], {
                        'phase': 'done',
                        'status': 'error',
                        'message': f'通知失敗：{error_msg}',
                        'recipients': target_emails,
                        'email_result': 'error'
                    })
                    print(f"[週報] 通知失敗：{error_msg}", file=sys.stderr)
            except Exception as e:
                error_msg = str(e)
                print(f"週報生成任務發生錯誤：{error_msg}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                if ev:
                    try:
                        update_event(ev['id'], {
                            'phase': 'done',
                            'status': 'error',
                            'message': f'例外：{error_msg}'
                        })
                    except Exception:
                        pass
            finally:
                if db_conn:
                    db_conn.close()

        # 建立 CronTrigger（固定 Asia/Taipei）
        trigger = CronTrigger(day_of_week=day, hour=hour, minute=minute, timezone="Asia/Taipei")
        scheduler.add_job(
            generate_weekly_report_job,
            trigger=trigger,
            id="job_weekly_report",
            replace_existing=True
        )
        
        # 計算並顯示下次執行時間
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        taipei_tz = ZoneInfo("Asia/Taipei")
        now = datetime.now(taipei_tz)
        
        # 計算下一個符合條件的時間
        days_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        target_weekday = days_map.get(day, 0)
        current_weekday = now.weekday()
        
        # 計算到下一個目標星期幾的天數
        days_ahead = target_weekday - current_weekday
        if days_ahead < 0 or (days_ahead == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute))):
            days_ahead += 7  # 下週
        
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        
        print(f"--- 週報排程已設定：每週 {day} {hour:02d}:{minute:02d} 生成 CISO 週報 ---")
        print(f"--- 下次執行時間：{next_run.strftime('%Y-%m-%d %H:%M:%S %Z')} ---")
        print(f"--- 當前時間：{now.strftime('%Y-%m-%d %H:%M:%S %Z')} ---")
    except Exception as e:
        print(f"警告：重排程 weekly_report 失敗：{e}", file=sys.stderr)

def run_all_collectors():
    """
    執行所有收集器任務。
    (未來關聯分析引擎也會在這裡被觸發)
    """
    print(f"\n[{datetime.now()}] --- 觸發排程：開始執行所有收集器 ---")
    db_conn = None
    try:
        config = load_config()
        db_conn = get_db_connection()
        
        if db_conn is None:
            print("錯誤：無法獲取資料庫連線，跳過此次執行。", file=sys.stderr)
            return

        # 依照PIR優先級執行
        # P0 (CISA) - 假設我們希望它更頻繁 (雖然這裡和大包一起跑)
        collectors.fetch_cisa_kev(db_conn, config)
        
        # P1 (NVD)
        collectors.fetch_nvd(db_conn, config)
        
        # P1/P2 (RSS Feeds)
        collectors.fetch_rss_feeds(db_conn, config)
        
        # --- 關聯分析引擎 ---
        print("\n--- [Scheduler] 呼叫關聯分析引擎 (Correlation Engine) ---")
        import correlation_engine
        correlation_engine.run_correlation_analysis(db_conn, config)
        # --- (關聯分析引擎完成) ---
        
        print(f"[{datetime.now()}] --- 排程執行完畢 ---")

    except Exception as e:
        print(f"排程任務 'run_all_collectors' 發生嚴重錯誤：{e}", file=sys.stderr)
    finally:
        if db_conn:
            db_conn.close()
            print("資料庫連線已關閉。")


# --- 信號處理函式 ---
def signal_handler(signum, frame):
    """處理 SIGUSR1 信號，立即觸發收集任務"""
    print(f"\n[{datetime.now()}] --- 收到信號 {signum}，立即觸發收集任務 ---")
    run_all_collectors()

def signal_handler_reload(signum, frame):
    """處理 SIGUSR2 信號，重載 weekly_report 排程"""
    print(f"\n[{datetime.now()}] --- 收到信號 {signum}，重新載入週報排程 ---")
    if scheduler_instance:
        reschedule_weekly_report(scheduler_instance)

# --- 主程式 ---
if __name__ == "__main__":
    print("--- 啟動 AETIM 主排程器服務 ---")
    
    # 寫入 PID 檔，供 Web 進程訊號喚醒
    try:
        with open(SCHEDULER_PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        print(f"--- 已寫入 PID 檔：{SCHEDULER_PID_FILE} ---")
    except Exception as e:
        print(f"警告：無法寫入 PID 檔：{e}", file=sys.stderr)

    # 載入設定
    config = load_config()
    
    # 1. 立即執行一次，確保啟動時就有資料
    # 執行：收集+分析+生成 CISO 報告
    print("=" * 60)
    print("--- 啟動 AETIM 主排程器服務 ---")
    print("=" * 60)
    print("... 執行啟動時的第一次任務（收集+分析+生成 CISO 報告）...")
    
    try:
        # 1.1 執行收集任務
        print("[啟動] 開始執行收集任務...")
        run_all_collectors()
        print("[啟動] 收集任務完成")
        
        # 1.2 執行關聯分析
        print("[啟動] 開始執行關聯分析...")
        db_conn = get_db_connection()
        if db_conn:
            import correlation_engine
            correlation_engine.run_correlation_analysis(db_conn, config)
            print("[啟動] 關聯分析完成")
            
            # 1.3 生成 CISO 報告
            print("[啟動] 開始生成 CISO 報告...")
            import reporting_engine
            report_data = reporting_engine.generate_weekly_report(db_conn, config)
            if report_data:
                report_filepath = reporting_engine.save_report(
                    report_data, 'ciso_weekly', 'html'
                )
                if report_filepath:
                    print(f"[啟動] CISO 報告生成完成：{report_filepath}")
                else:
                    print("[啟動] CISO 報告生成失敗（無法儲存檔案）")
            else:
                print("[啟動] CISO 報告生成失敗（無資料）")
            
            db_conn.close()
        else:
            print("[啟動] 無法獲取資料庫連線，跳過關聯分析和報告生成")
    except Exception as e:
        print(f"[啟動] 啟動任務發生錯誤：{e}", file=sys.stderr)
    
    print("=" * 60)
    
    # 2. 設定排程器
    scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    scheduler_instance = scheduler  # 儲存全域變數
    
    # 3. 讀取排程設定
    scheduler_config = config.get('scheduler', {})
    interval_config = scheduler_config.get('interval', {})
    interval_hours = interval_config.get('hours', 4)
    interval_minutes = interval_config.get('minutes')
    
    # 4. 設定觸發器（優先使用 minutes，如果設定）
    if interval_minutes and interval_minutes > 0:
        trigger = IntervalTrigger(minutes=interval_minutes)
        interval_display = f"{interval_minutes} 分鐘"
    elif interval_hours and interval_hours > 0:
        trigger = IntervalTrigger(hours=interval_hours)
        interval_display = f"{interval_hours} 小時"
    else:
        # 預設值：4 小時
        trigger = IntervalTrigger(hours=4)
        interval_display = "4 小時"
        print("警告：未設定有效的排程間隔，使用預設值 4 小時。", file=sys.stderr)
    
    # 5. 添加排程任務：收集與關聯分析
    scheduler.add_job(
        run_all_collectors,
        trigger=trigger,
        id="job_all_collectors",
        replace_existing=True
    )
    
    # 6. 添加週報排程任務（每週一上午 8:00）
    # 依設定建立週報排程（新結構＆相容）
    try:
        reschedule_weekly_report(scheduler)
    except Exception as e:
        print(f"警告：週報排程設定失敗：{e}", file=sys.stderr)
    
    # 7. 設定信號處理器（支援立即觸發）
    # SIGUSR1: 立即執行收集任務（Unix/Linux）
    if hasattr(signal, 'SIGUSR1'):
        signal.signal(signal.SIGUSR1, signal_handler)
        print(f"--- 已啟用信號觸發：發送 SIGUSR1 可立即執行收集任務 ---")
    # SIGUSR2: 重新載入週報排程
    if hasattr(signal, 'SIGUSR2'):
        signal.signal(signal.SIGUSR2, signal_handler_reload)
        print(f"--- 已啟用信號觸發：發送 SIGUSR2 可重新載入週報排程 ---")
    
    scheduler.start()
    print(f"--- 排程器已啟動，將每 {interval_display} 執行一次收集任務。 ---")
    
    # 檢查並顯示所有已設定的任務
    print("--- 已設定的排程任務：---")
    jobs = scheduler.get_jobs()
    for job in jobs:
        next_run = job.next_run_time
        if next_run:
            next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            next_run_str = "未設定"
        print(f"  - Job ID: {job.id}, 下次執行: {next_run_str}")
    
    print("--- 服務運行中... (按 Ctrl+C 停止) ---")
    print("--- 提示：使用 'docker-compose exec aetim python trigger_collectors.py' 可立即執行任務 ---")

    # 8. 保持主程式運行 (讓 Docker 容器保持 'up')
    # 定期檢查週報排程是否正常運行
    last_check_time = time.time()
    check_interval = 3600  # 每小時檢查一次
    
    try:
        while True:
            time.sleep(60) # 每分鐘檢查一次
            
            # 每小時檢查一次週報排程是否正常
            current_time = time.time()
            if current_time - last_check_time >= check_interval:
                last_check_time = current_time
                try:
                    # 檢查週報任務是否存在
                    weekly_job = scheduler.get_job("job_weekly_report")
                    if weekly_job:
                        next_run = weekly_job.next_run_time
                        if next_run:
                            print(f"[檢查] 週報排程正常，下次執行：{next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        else:
                            print("[警告] 週報排程存在但未設定下次執行時間", file=sys.stderr)
                    else:
                        # 檢查設定是否啟用
                        config = load_config()
                        weekly = config.get('reporting', {}).get('weekly_report', {})
                        if weekly.get('enabled', False):
                            print("[警告] 週報排程已啟用但任務不存在，嘗試重新設定...", file=sys.stderr)
                            reschedule_weekly_report(scheduler)
                except Exception as e:
                    print(f"[檢查] 檢查週報排程時發生錯誤：{e}", file=sys.stderr)
            
    except (KeyboardInterrupt, SystemExit):
        print("--- 服務停止中，關閉排程器... ---")
        scheduler.shutdown()
        print("--- 服務已停止 ---")
