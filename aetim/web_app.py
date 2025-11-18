#!/usr/bin/env python3
"""
AETIM Web 應用程式
功能：提供網頁界面來管理 AETIM 系統
"""

import os
import sys
import json
import yaml
import copy
import threading
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import signal
from utils import get_db_connection, load_config
import collectors
import correlation_engine
import reporting_engine
import notification_handler
import job_events

# 設定時區為 Asia/Taipei
TAIPEI_TZ = ZoneInfo('Asia/Taipei')

def get_taipei_time():
    """取得 Asia/Taipei 時區的當前時間"""
    return datetime.now(TAIPEI_TZ)

app = Flask(__name__)
CORS(app)

# 全域變數：用於追蹤任務狀態
task_status = {
    'collectors': {
        'status': 'idle',  # idle, running, completed, error
        'message': '',
        'timestamp': None,
        'logs': []
    },
    'correlation': {
        'status': 'idle',
        'message': '',
        'timestamp': None,
        'logs': []
    },
    'report_generation': {
        'status': 'idle',
        'message': '',
        'timestamp': None,
        'filepath': None,
        'format': None
    },
    'notification': {
        'status': 'idle',
        'message': '',
        'timestamp': None,
        'recipients': [],
        'result': None
    }
}

# 排程狀態追蹤
scheduler_state = {
    'last_execution_time': None,  # 上次執行時間
    'next_execution_time': None,  # 下次執行時間
    'interval_minutes': None,  # 當前間隔（分鐘）
    'enabled': True  # 排程是否啟用
}

# 任務執行鎖
task_lock = threading.Lock()


@app.route('/')
def index():
    """主頁面"""
    config = load_config()
    return render_template('index.html', config=config)


@app.route('/api/config', methods=['GET'])
def get_config():
    """取得設定（密碼不會返回給前端）"""
    try:
        config = load_config()
        
        # 建立一個副本，移除敏感資訊（密碼）
        safe_config = copy.deepcopy(config)
        if 'notification' in safe_config and 'email' in safe_config['notification']:
            # 不返回實際密碼，只返回是否已設定
            if 'smtp_password' in safe_config['notification']['email']:
                password_value = safe_config['notification']['email']['smtp_password']
                # 如果是加密字串，保留加密字串；如果是環境變數，保留環境變數引用；否則顯示為已設定
                if isinstance(password_value, str):
                    if password_value.startswith('ENCRYPTED:'):
                        safe_config['notification']['email']['smtp_password'] = password_value
                    elif password_value.startswith('${'):
                        safe_config['notification']['email']['smtp_password'] = password_value
                    else:
                        # 明碼或解密後的密碼，不返回實際值
                        safe_config['notification']['email']['smtp_password'] = '***'  # 隱藏密碼
                else:
                    safe_config['notification']['email']['smtp_password'] = '***'
        
        return jsonify({
            'success': True,
            'config': safe_config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新設定"""
    try:
        data = request.json
        
        # 讀取現有設定
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 建立原始設定的快照以便判斷是否需要重排程
        import copy as _copy
        original_config = _copy.deepcopy(config)
        
        # 更新排程設定
        if 'scheduler' in data:
            if 'interval' in data['scheduler']:
                config['scheduler']['interval'] = data['scheduler']['interval']
                # 重新計算下次執行時間（從當前時間開始）
                scheduler_state['last_execution_time'] = get_taipei_time()
        
        # 更新報告 weekly_report 的 schedule_struct（新結構）
        if 'reporting' in data:
            reporting_updates = data['reporting']
            if 'weekly_report' in reporting_updates:
                weekly_updates = reporting_updates['weekly_report']
                if 'schedule_struct' in weekly_updates:
                    # 驗證欄位
                    schedule_struct = weekly_updates['schedule_struct']
                    valid_days = {'mon','tue','wed','thu','fri','sat','sun'}
                    day = str(schedule_struct.get('day_of_week', '')).lower()
                    hour = schedule_struct.get('hour', None)
                    minute = schedule_struct.get('minute', None)
                    if day not in valid_days or not isinstance(hour, int) or not (0 <= hour <= 23) or not isinstance(minute, int) or not (0 <= minute <= 59):
                        return jsonify({
                            'success': False,
                            'error': 'schedule_struct 欄位不合法（day_of_week, hour, minute）'
                        }), 400
                    if 'reporting' not in config:
                        config['reporting'] = {}
                    if 'weekly_report' not in config['reporting']:
                        config['reporting']['weekly_report'] = {}
                    if 'enabled' in weekly_updates:
                        config['reporting']['weekly_report']['enabled'] = bool(weekly_updates['enabled'])
                    config['reporting']['weekly_report']['schedule_struct'] = {
                        'day_of_week': day,
                        'hour': hour,
                        'minute': minute,
                        'timezone': 'Asia/Taipei'
                    }
        
        # 更新通知設定
        if 'notification' in data:
            if 'email' in data['notification']:
                email_updates = data['notification']['email'].copy()
                # 處理密碼更新：如果前端傳送的是 '***' 或空值，則不更新密碼欄位
                if 'smtp_password' in email_updates:
                    password_value = email_updates['smtp_password']
                    if password_value == '***' or password_value == '' or password_value is None:
                        # 不更新密碼欄位，保留原有設定
                        del email_updates['smtp_password']
                config['notification']['email'].update(email_updates)
            # 新增：收件者與類型設定
            if 'recipients' in data['notification']:
                rec = data['notification']['recipients']
                # 驗證 key
                valid_keys = {'ciso','it'}
                for k in list(rec.keys()):
                    if k not in valid_keys:
                        return jsonify({'success': False, 'error': f'不支援的收件者鍵：{k}'}), 400
                if 'notification' not in config:
                    config['notification'] = {}
                config['notification']['recipients'] = rec
            if 'types' in data['notification']:
                types = data['notification']['types']
                valid_types = {'critical','high_daily','weekly_report'}
                for t, val in types.items():
                    if t not in valid_types:
                        return jsonify({'success': False, 'error': f'不支援的通知類型：{t}'}), 400
                    # recipients 驗證
                    r = val.get('recipients', [])
                    if not isinstance(r, list) or any(x not in {'ciso','it'} for x in r):
                        return jsonify({'success': False, 'error': f'類型 {t} 的 recipients 不合法'}), 400
                if 'notification' not in config:
                    config['notification'] = {}
                config['notification']['types'] = types
        
        # 寫回設定檔
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # 檢查 weekly_report 排程是否有變更，若有則發送 SIGUSR2 讓 scheduler 重新載入
        def _extract_weekly(cfg):
            try:
                return cfg.get('reporting', {}).get('weekly_report', {}).get('schedule_struct', {})
            except Exception:
                return {}
        if _extract_weekly(original_config) != _extract_weekly(config):
            try:
                pid_file = os.path.join(os.path.dirname(__file__), 'scheduler.pid')
                if os.path.exists(pid_file):
                    with open(pid_file, 'r') as pf:
                        pid = int(pf.read().strip())
                    os.kill(pid, signal.SIGUSR2)
                    print(f"[設定] 已向 scheduler (PID={pid}) 發送 SIGUSR2 以重載 weekly_report 排程")
                else:
                    print("[設定] 找不到 scheduler.pid，無法發送重載訊號")
            except Exception as e:
                print(f"[設定] 發送重載訊號失敗：{e}", file=sys.stderr)
        
        return jsonify({
            'success': True,
            'message': '設定已更新'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/trigger/collectors', methods=['POST'])
def trigger_collectors():
    """立即觸發收集任務"""
    if task_lock.locked():
        return jsonify({
            'success': False,
            'error': '已有任務正在執行中，請稍候'
        }), 400
    
    def run_task():
        with task_lock:
            task_status['collectors']['status'] = 'running'
            task_status['collectors']['message'] = '開始執行收集任務...'
            task_status['collectors']['timestamp'] = get_taipei_time().isoformat()
            task_status['collectors']['logs'] = []
            
            try:
                config = load_config()
                db_conn = get_db_connection()
                
                if db_conn is None:
                    task_status['collectors']['status'] = 'error'
                    task_status['collectors']['message'] = '無法獲取資料庫連線'
                    return
                
                # 執行收集器
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 CISA KEV 收集器...')
                collectors.fetch_cisa_kev(db_conn, config)
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] CISA KEV 收集器完成')
                
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 NVD 收集器...')
                collectors.fetch_nvd(db_conn, config)
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] NVD 收集器完成')
                
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 RSS Feeds 收集器...')
                collectors.fetch_rss_feeds(db_conn, config)
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] RSS Feeds 收集器完成')
                
                task_status['collectors']['status'] = 'completed'
                task_status['collectors']['message'] = '收集任務執行完成'
                # 更新上次執行時間（用於計算下次執行時間）
                scheduler_state['last_execution_time'] = get_taipei_time()
                db_conn.close()
                
            except Exception as e:
                task_status['collectors']['status'] = 'error'
                task_status['collectors']['message'] = f'執行錯誤：{str(e)}'
                task_status['collectors']['logs'].append(f'錯誤：{str(e)}')
    
    # 在背景執行
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': '收集任務已啟動'
    })


@app.route('/api/trigger/correlation', methods=['POST'])
def trigger_correlation():
    """立即觸發關聯分析"""
    if task_lock.locked():
        return jsonify({
            'success': False,
            'error': '已有任務正在執行中，請稍候'
        }), 400
    
    def run_task():
        with task_lock:
            task_status['correlation']['status'] = 'running'
            task_status['correlation']['message'] = '開始執行關聯分析...'
            task_status['correlation']['timestamp'] = get_taipei_time().isoformat()
            task_status['correlation']['logs'] = []
            
            try:
                config = load_config()
                db_conn = get_db_connection()
                
                if db_conn is None:
                    task_status['correlation']['status'] = 'error'
                    task_status['correlation']['message'] = '無法獲取資料庫連線'
                    return
                
                task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始關聯分析...')
                correlation_engine.run_correlation_analysis(db_conn, config)
                task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 關聯分析完成')
                
                task_status['correlation']['status'] = 'completed'
                task_status['correlation']['message'] = '關聯分析執行完成'
                db_conn.close()
                
            except Exception as e:
                task_status['correlation']['status'] = 'error'
                task_status['correlation']['message'] = f'執行錯誤：{str(e)}'
                task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：{str(e)}')
    
    # 在背景執行
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': '關聯分析已啟動'
    })


@app.route('/api/trigger/all', methods=['POST'])
def trigger_all():
    """立即觸發收集與關聯分析"""
    if task_lock.locked():
        return jsonify({
            'success': False,
            'error': '已有任務正在執行中，請稍候'
        }), 400
    
    def run_task():
        with task_lock:
            # 重置狀態
            task_status['collectors']['status'] = 'running'
            task_status['collectors']['message'] = '開始執行所有收集器...'
            task_status['collectors']['timestamp'] = get_taipei_time().isoformat()
            task_status['collectors']['logs'] = []
            task_status['correlation']['status'] = 'idle'
            task_status['correlation']['logs'] = []
            
            try:
                config = load_config()
                db_conn = get_db_connection()
                
                if db_conn is None:
                    task_status['collectors']['status'] = 'error'
                    task_status['collectors']['message'] = '無法獲取資料庫連線'
                    return
                
                # 執行收集器
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行所有收集器...')
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 CISA KEV 收集器...')
                collectors.fetch_cisa_kev(db_conn, config)
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] CISA KEV 收集器完成')
                
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 NVD 收集器...')
                collectors.fetch_nvd(db_conn, config)
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] NVD 收集器完成')
                
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 RSS Feeds 收集器...')
                collectors.fetch_rss_feeds(db_conn, config)
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] RSS Feeds 收集器完成')
                
                task_status['collectors']['status'] = 'completed'
                task_status['collectors']['message'] = '收集任務執行完成'
                
                # 執行關聯分析
                task_status['correlation']['status'] = 'running'
                task_status['correlation']['message'] = '開始執行關聯分析...'
                task_status['correlation']['timestamp'] = get_taipei_time().isoformat()
                task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始關聯分析...')
                correlation_engine.run_correlation_analysis(db_conn, config)
                task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 關聯分析完成')
                
                task_status['correlation']['status'] = 'completed'
                task_status['correlation']['message'] = '關聯分析執行完成'
                
                # 更新上次執行時間（用於計算下次執行時間）
                scheduler_state['last_execution_time'] = get_taipei_time()
                
                db_conn.close()
                
            except Exception as e:
                task_status['collectors']['status'] = 'error'
                task_status['correlation']['status'] = 'error'
                task_status['collectors']['message'] = f'執行錯誤：{str(e)}'
                task_status['correlation']['message'] = f'執行錯誤：{str(e)}'
                task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：{str(e)}')
                task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：{str(e)}')
    
    # 在背景執行
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': '收集與關聯分析任務已啟動'
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """取得任務狀態"""
    return jsonify({
        'success': True,
        'status': task_status
    })


@app.route('/api/scheduler/next-run', methods=['GET'])
def get_next_run_time():
    """取得下次執行時間和倒數時間"""
    try:
        config = load_config()
        scheduler_config = config.get('scheduler', {})
        interval_config = scheduler_config.get('interval', {})
        
        # 計算間隔（分鐘）
        interval_hours = interval_config.get('hours')
        interval_minutes = interval_config.get('minutes')
        
        # 計算總間隔（分鐘）：小時 + 分鐘
        total_minutes = 0
        if interval_hours and interval_hours > 0:
            total_minutes += interval_hours * 60
        if interval_minutes and interval_minutes > 0:
            total_minutes += interval_minutes
        
        # 如果沒有設定間隔，使用預設值 4 小時
        if total_minutes == 0:
            total_minutes = 240  # 4 小時
        
        # 如果沒有上次執行時間，使用當前時間
        if scheduler_state['last_execution_time'] is None:
            scheduler_state['last_execution_time'] = get_taipei_time()
        
        # 計算下次執行時間
        from datetime import timedelta
        next_execution = scheduler_state['last_execution_time'] + timedelta(minutes=total_minutes)
        
        # 如果下次執行時間已過，重新計算（從當前時間開始）
        now = get_taipei_time()
        if next_execution < now:
            # 重新計算，從當前時間開始
            next_execution = now + timedelta(minutes=total_minutes)
            scheduler_state['last_execution_time'] = now
        
        # 計算倒數時間（秒）
        time_remaining = (next_execution - now).total_seconds()
        
        # 更新排程狀態
        scheduler_state['next_execution_time'] = next_execution.isoformat()
        scheduler_state['interval_minutes'] = total_minutes
        
        # 格式化倒數時間
        hours = int(time_remaining // 3600)
        minutes = int((time_remaining % 3600) // 60)
        seconds = int(time_remaining % 60)
        
        if hours > 0:
            countdown_str = f"{hours}小時 {minutes}分鐘 {seconds}秒"
        elif minutes > 0:
            countdown_str = f"{minutes}分鐘 {seconds}秒"
        else:
            countdown_str = f"{seconds}秒"
        
        return jsonify({
            'success': True,
            'next_execution_time': next_execution.isoformat(),
            'countdown_seconds': int(time_remaining),
            'countdown_str': countdown_str,
            'interval_minutes': total_minutes,
            'enabled': scheduler_state['enabled']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/report/generate', methods=['POST'])
def generate_report():
    """生成報告"""
    data = request.json
    report_type = data.get('type', 'ciso_weekly')
    report_format = data.get('format', 'html')
    
    if task_lock.locked():
        return jsonify({
            'success': False,
            'error': '已有任務正在執行中，請稍候'
        }), 400
    
    def run_task():
        with task_lock:
            task_status['report_generation']['status'] = 'running'
            task_status['report_generation']['message'] = f'開始生成 {report_type} 報告（{report_format} 格式）...'
            task_status['report_generation']['timestamp'] = get_taipei_time().isoformat()
            task_status['report_generation']['format'] = report_format
            task_status['report_generation']['logs'] = []
            
            try:
                config = load_config()
                db_conn = get_db_connection()
                
                if db_conn is None:
                    task_status['report_generation']['status'] = 'error'
                    task_status['report_generation']['message'] = '無法獲取資料庫連線'
                    return
                
                if report_type == 'ciso_weekly':
                    task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始生成 CISO 週報...')
                    report_data = reporting_engine.generate_weekly_report(db_conn, config)
                    if report_data:
                        task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 報告資料生成完成，正在儲存...')
                        filepath = reporting_engine.save_report(report_data, 'ciso_weekly', report_format)
                        if filepath:
                            task_status['report_generation']['status'] = 'completed'
                            task_status['report_generation']['message'] = '報告生成完成'
                            task_status['report_generation']['filepath'] = filepath
                            task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 報告已儲存：{filepath}')
                        else:
                            task_status['report_generation']['status'] = 'error'
                            task_status['report_generation']['message'] = '報告儲存失敗'
                            task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：報告儲存失敗')
                    else:
                        task_status['report_generation']['status'] = 'error'
                        task_status['report_generation']['message'] = '報告生成失敗'
                        task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：報告資料生成失敗')
                
                elif report_type == 'it_ticket':
                    task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始生成 IT 工單...')
                    # 從資料庫獲取最新的高風險威脅來生成工單
                    cursor = db_conn.cursor()
                    cursor.execute("""
                        SELECT vt.id, vt.intel_id, vt.asset_id, vt.risk_score, vt.status, vt.notes,
                               ri.cve_id, ri.title, ri.source, ri.cvss_score, ri.raw_data,
                               a.hostname, a.ip_address, a.owner, a.os_version, a.applications, 
                               a.is_public, a.business_criticality, a.data_sensitivity
                        FROM T_Validated_Threats vt
                        JOIN T_Raw_Intel ri ON vt.intel_id = ri.id
                        JOIN T_Assets a ON vt.asset_id = a.id
                        WHERE vt.risk_score >= ?
                        ORDER BY vt.timestamp DESC
                        LIMIT 1
                    """, (config['notification']['thresholds'].get('high', 7.0),))
                    latest_threat = cursor.fetchone()
                    
                    if latest_threat:
                        task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 找到高風險威脅，開始生成工單...')
                        validated_threat = dict(latest_threat)
                        
                        # 構建 intel_data
                        intel_data = {
                            'cve_id': latest_threat['cve_id'],
                            'title': latest_threat['title'],
                            'source': latest_threat['source'],
                            'cvss_score': latest_threat['cvss_score'],
                            'raw_data': latest_threat['raw_data']
                        }
                        
                        # 構建 asset_data
                        asset_data = {
                            'hostname': latest_threat['hostname'],
                            'ip_address': latest_threat['ip_address'],
                            'owner': latest_threat['owner'],
                            'os_version': latest_threat['os_version'],
                            'applications': latest_threat['applications'],
                            'is_public': latest_threat['is_public'],
                            'business_criticality': latest_threat['business_criticality'],
                            'data_sensitivity': latest_threat['data_sensitivity']
                        }
                        
                        task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 工單資料準備完成，開始生成...')
                        report_data = reporting_engine.generate_it_ticket(validated_threat, asset_data, intel_data, config)
                        
                        if report_data:
                            task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 工單資料生成完成，正在儲存...')
                            filepath = reporting_engine.save_report(report_data, 'it_ticket', report_format)
                            if filepath:
                                task_status['report_generation']['status'] = 'completed'
                                task_status['report_generation']['message'] = 'IT 工單生成完成'
                                task_status['report_generation']['filepath'] = filepath
                                task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 工單已儲存：{filepath}')
                            else:
                                task_status['report_generation']['status'] = 'error'
                                task_status['report_generation']['message'] = '工單儲存失敗'
                                task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：工單儲存失敗')
                        else:
                            task_status['report_generation']['status'] = 'error'
                            task_status['report_generation']['message'] = '工單生成失敗'
                            task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：工單資料生成失敗')
                    else:
                        task_status['report_generation']['status'] = 'error'
                        task_status['report_generation']['message'] = '未找到高風險威脅，無法生成 IT 工單'
                        task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 警告：資料庫中沒有符合條件的高風險威脅')
                
                else:
                    task_status['report_generation']['status'] = 'error'
                    task_status['report_generation']['message'] = f'不支援的報告類型：{report_type}'
                    task_status['report_generation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 錯誤：不支援的報告類型：{report_type}')
                
                db_conn.close()
                
            except Exception as e:
                task_status['report_generation']['status'] = 'error'
                task_status['report_generation']['message'] = f'執行錯誤：{str(e)}'
    
    # 在背景執行
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': '報告生成任務已啟動'
    })

@app.route('/api/weekly-jobs', methods=['GET'])
def list_weekly_jobs():
    """列出最近的週報事件"""
    try:
        limit = int(request.args.get('limit', 20))
        items = job_events.list_recent_events(limit=limit)
        items = job_events.mask_recipients(items)
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/weekly-jobs/test-send', methods=['POST'])
def test_send_weekly():
    """使用最新報告試寄週報到指定收件者（或使用 config 的 to_address）"""
    try:
        data = request.json or {}
        override_to = data.get('to')
        cfg = load_config()
        ev = job_events.start_event({'phase': 'notify', 'message': '測試寄送啟動'})
        # 找到最新 CISO 週報
        report_dir = os.path.join(os.path.dirname(__file__), 'reports')
        latest_report = None
        for root, dirs, files in os.walk(report_dir):
            for file in files:
                if file.endswith('.html') and 'ciso_weekly' in file:
                    filepath = os.path.join(root, file)
                    if latest_report is None or os.path.getmtime(filepath) > os.path.getmtime(latest_report):
                        latest_report = filepath
        if not latest_report:
            return jsonify({'success': False, 'error': '找不到任何 CISO 週報檔案'}), 400
        # 覆寫收件者
        if override_to:
            temp_cfg = copy.deepcopy(cfg)
            if 'notification' not in temp_cfg:
                temp_cfg['notification'] = {}
            if 'email' not in temp_cfg['notification']:
                temp_cfg['notification']['email'] = {}
            temp_cfg['notification']['email']['to_address'] = override_to
            cfg = temp_cfg
        try:
            notification_handler.notify_weekly_report(latest_report, cfg)
            to_addr = cfg.get('notification', {}).get('email', {}).get('to_address')
            recips = [to_addr] if to_addr else []
            job_events.update_event(ev['id'], {
                'phase': 'done',
                'status': 'success',
                'message': '測試寄送成功',
                'report_filepath': latest_report,
                'recipients': recips,
                'email_result': 'success'
            })
        except Exception as ne:
            job_events.update_event(ev['id'], {
                'phase': 'done',
                'status': 'error',
                'message': f'測試寄送失敗：{ne}',
                'report_filepath': latest_report,
                'email_result': 'error'
            })
            raise
        return jsonify({'success': True, 'message': '測試寄送已觸發', 'report': latest_report})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notification/send', methods=['POST'])
def send_notification():
    """發送通知"""
    data = request.json
    notification_type = data.get('type', 'weekly_report')
    recipients = data.get('recipients', [])
    
    if task_lock.locked():
        return jsonify({
            'success': False,
            'error': '已有任務正在執行中，請稍候'
        }), 400
    
    def run_task():
        with task_lock:
            task_status['notification']['status'] = 'running'
            task_status['notification']['message'] = f'開始發送 {notification_type} 通知...'
            task_status['notification']['timestamp'] = get_taipei_time().isoformat()
            task_status['notification']['recipients'] = recipients
            
            try:
                config = load_config()
                email_config = config.get('notification', {}).get('email', {})
                
                # 取得收件者 Email 列表
                recipient_emails = []
                if 'ciso' in recipients:
                    ciso_email = email_config.get('ciso_email')
                    if ciso_email:
                        recipient_emails.append(ciso_email)
                if 'it' in recipients:
                    it_email = email_config.get('it_email')
                    if it_email:
                        recipient_emails.append(it_email)
                
                if not recipient_emails:
                    task_status['notification']['status'] = 'error'
                    task_status['notification']['message'] = '找不到收件者 Email，請先設定收件者 Email'
                    task_status['notification']['result'] = 'error'
                    return
                
                task_status['notification']['recipients'] = recipient_emails
                
                if notification_type == 'weekly_report':
                    # 取得最新的報告檔案
                    report_dir = os.path.join(os.path.dirname(__file__), 'reports')
                    # 找到最新的報告檔案
                    latest_report = None
                    for root, dirs, files in os.walk(report_dir):
                        for file in files:
                            if file.endswith('.html') and 'ciso_weekly' in file:
                                filepath = os.path.join(root, file)
                                if latest_report is None or os.path.getmtime(filepath) > os.path.getmtime(latest_report):
                                    latest_report = filepath
                    
                    if latest_report:
                        # 發送給所有收件者
                        success_count = 0
                        error_messages = []
                        for email in recipient_emails:
                            try:
                                # 修改 config 以使用指定的收件者 Email
                                import copy
                                temp_config = copy.deepcopy(config)
                                if 'notification' not in temp_config:
                                    temp_config['notification'] = {}
                                if 'email' not in temp_config['notification']:
                                    temp_config['notification']['email'] = {}
                                temp_config['notification']['email']['to_address'] = email
                                # 確保使用最新的 SMTP 設定
                                email_config = config.get('notification', {}).get('email', {})
                                # 確保 notification.enabled 和 email.enabled 都設定為 True
                                if 'notification' not in temp_config:
                                    temp_config['notification'] = {}
                                temp_config['notification']['enabled'] = True  # 設定頂層通知功能啟用
                                temp_config['notification']['email'].update({
                                    'smtp_server': email_config.get('smtp_server'),
                                    'smtp_port': email_config.get('smtp_port'),
                                    'smtp_username': email_config.get('smtp_username'),
                                    'smtp_password': email_config.get('smtp_password'),
                                    'from_address': email_config.get('from_address'),
                                    'use_tls': email_config.get('use_tls', True),
                                    'enabled': email_config.get('enabled', True)  # 確保 Email 功能啟用
                                })
                                # 添加日誌輸出，確認傳遞的設定
                                print(f"[通知] 準備發送通知給：{email}")
                                print(f"[通知] 使用的 SMTP 設定：")
                                print(f"  - SMTP 伺服器：{temp_config['notification']['email'].get('smtp_server')}")
                                print(f"  - 發送者：{temp_config['notification']['email'].get('from_address')}")
                                print(f"  - 收件者：{email}")
                                notification_handler.notify_weekly_report(latest_report, temp_config)
                                success_count += 1
                            except Exception as e:
                                error_msg = f"發送給 {email} 失敗：{str(e)}"
                                print(f"[通知] {error_msg}", file=sys.stderr)
                                error_messages.append(error_msg)
                        
                        if success_count > 0:
                            task_status['notification']['status'] = 'completed'
                            if error_messages:
                                task_status['notification']['message'] = f'通知發送完成（{success_count}/{len(recipient_emails)}），部分失敗：' + '; '.join(error_messages)
                            else:
                                task_status['notification']['message'] = f'通知發送完成（{success_count}/{len(recipient_emails)}）'
                            task_status['notification']['result'] = 'success'
                        else:
                            task_status['notification']['status'] = 'error'
                            task_status['notification']['message'] = '所有收件者發送失敗：' + '; '.join(error_messages) if error_messages else '未知錯誤'
                            task_status['notification']['result'] = 'error'
                    else:
                        task_status['notification']['status'] = 'error'
                        task_status['notification']['message'] = '找不到報告檔案'
                
            except Exception as e:
                task_status['notification']['status'] = 'error'
                task_status['notification']['message'] = f'執行錯誤：{str(e)}'
                task_status['notification']['result'] = 'error'
    
    # 在背景執行
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': '通知發送任務已啟動'
    })


@app.route('/api/smtp/test', methods=['POST'])
def test_smtp():
    """測試 SMTP 連線和發送 Email"""
    try:
        data = request.json
        smtp_server = data.get('smtp_server')
        smtp_port = data.get('smtp_port', 587)
        smtp_username = data.get('smtp_username')
        smtp_password = data.get('smtp_password')
        from_address = data.get('from_address')
        to_address = data.get('to_address', from_address)  # 預設發送給自己
        use_tls = data.get('use_tls', True)
        
        # 驗證必填欄位
        if not all([smtp_server, smtp_port, smtp_username, smtp_password, from_address]):
            return jsonify({
                'success': False,
                'error': '請填寫所有必填欄位'
            }), 400
        
        # 測試發送 Email
        from notification_handler import send_email
        
        subject = f"[AETIM SMTP 測試] {get_taipei_time().strftime('%Y-%m-%d %H:%M:%S')}"
        body = f"""
這是一封 SMTP 測試郵件。

測試時間：{get_taipei_time().strftime('%Y-%m-%d %H:%M:%S')}
SMTP 伺服器：{smtp_server}
SMTP 埠口：{smtp_port}
使用 TLS：{use_tls}

如果您收到這封郵件，表示 SMTP 設定正確。

---
此為自動化系統發送的通知，請勿直接回覆。
"""
        
        result = send_email(
            subject=subject,
            body=body,
            to_address=to_address,
            from_address=from_address,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            use_tls=use_tls
        )
        
        if result:
            return jsonify({
                'success': True,
                'message': f'測試 Email 已成功發送至 {to_address}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Email 發送失敗，請檢查 SMTP 設定和日誌'
            }), 500
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'details': error_details
        }), 500


def startup_tasks():
    """服務啟動時的初始化任務"""
    print("=" * 60)
    print("AETIM Web 應用程式啟動中...")
    print("=" * 60)
    
    try:
        # 載入設定
        config = load_config()
        scheduler_config = config.get('scheduler', {})
        interval_config = scheduler_config.get('interval', {})
        
        # 計算間隔（分鐘）
        interval_hours = interval_config.get('hours')
        interval_minutes = interval_config.get('minutes')
        
        # 計算總間隔（分鐘）：小時 + 分鐘
        total_minutes = 0
        if interval_hours and interval_hours > 0:
            total_minutes += interval_hours * 60
        if interval_minutes and interval_minutes > 0:
            total_minutes += interval_minutes
        
        # 如果沒有設定間隔，使用預設值 4 小時
        if total_minutes == 0:
            total_minutes = 240  # 4 小時
        
        # 檢查排程狀態（預設為啟用）
        scheduler_state['enabled'] = True  # 預設啟用
        scheduler_state['interval_minutes'] = total_minutes
        
        # 如果排程狀態為啟用，立即計算下次執行時間並開始倒數
        if scheduler_state['enabled']:
            # 設定上次執行時間為當前時間（服務啟動時間）
            scheduler_state['last_execution_time'] = get_taipei_time()
            
            # 計算下次執行時間
            from datetime import timedelta
            next_execution = get_taipei_time() + timedelta(minutes=total_minutes)
            scheduler_state['next_execution_time'] = next_execution.isoformat()
            
            print(f"[啟動] 排程狀態：啟用")
            print(f"[啟動] 執行間隔：{total_minutes} 分鐘")
            print(f"[啟動] 下次執行時間：{next_execution.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 立即執行一次：觸發全部（收集+分析）+ 生成 CISO 報告
            print("[啟動] 開始執行啟動時的第一次任務...")
            
            def run_startup_task():
                """執行啟動時的任務"""
                with task_lock:
                    try:
                        # 1. 執行收集+分析
                        print("[啟動] 開始執行收集任務...")
                        task_status['collectors']['status'] = 'running'
                        task_status['collectors']['message'] = '啟動時自動執行：開始執行所有收集器...'
                        task_status['collectors']['timestamp'] = get_taipei_time().isoformat()
                        task_status['collectors']['logs'] = []
                        
                        config = load_config()
                        db_conn = get_db_connection()
                        
                        if db_conn is None:
                            task_status['collectors']['status'] = 'error'
                            task_status['collectors']['message'] = '無法獲取資料庫連線'
                            return
                        
                        # 執行收集器
                        task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行所有收集器...')
                        task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 CISA KEV 收集器...')
                        collectors.fetch_cisa_kev(db_conn, config)
                        task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] CISA KEV 收集器完成')
                        
                        task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 NVD 收集器...')
                        collectors.fetch_nvd(db_conn, config)
                        task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] NVD 收集器完成')
                        
                        task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始執行 RSS Feeds 收集器...')
                        collectors.fetch_rss_feeds(db_conn, config)
                        task_status['collectors']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] RSS Feeds 收集器完成')
                        
                        task_status['collectors']['status'] = 'completed'
                        task_status['collectors']['message'] = '啟動時自動執行：收集任務執行完成'
                        print("[啟動] 收集任務完成")
                        
                        # 2. 執行關聯分析
                        print("[啟動] 開始執行關聯分析...")
                        task_status['correlation']['status'] = 'running'
                        task_status['correlation']['message'] = '啟動時自動執行：開始執行關聯分析...'
                        task_status['correlation']['timestamp'] = get_taipei_time().isoformat()
                        task_status['correlation']['logs'] = []
                        task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 開始關聯分析...')
                        correlation_engine.run_correlation_analysis(db_conn, config)
                        task_status['correlation']['logs'].append(f'[{get_taipei_time().strftime("%H:%M:%S")}] 關聯分析完成')
                        
                        task_status['correlation']['status'] = 'completed'
                        task_status['correlation']['message'] = '啟動時自動執行：關聯分析執行完成'
                        print("[啟動] 關聯分析完成")
                        
                        # 3. 生成 CISO 報告
                        print("[啟動] 開始生成 CISO 報告...")
                        task_status['report_generation']['status'] = 'running'
                        task_status['report_generation']['message'] = '啟動時自動執行：開始生成 CISO 週報...'
                        task_status['report_generation']['timestamp'] = get_taipei_time().isoformat()
                        
                        report_data = reporting_engine.generate_weekly_report(db_conn, config)
                        if report_data:
                            report_filepath = reporting_engine.save_report(
                                report_data, 'ciso_weekly', 'html'
                            )
                            if report_filepath:
                                task_status['report_generation']['status'] = 'completed'
                                task_status['report_generation']['message'] = f'啟動時自動執行：CISO 週報生成完成'
                                task_status['report_generation']['filepath'] = report_filepath
                                task_status['report_generation']['format'] = 'html'
                                print(f"[啟動] CISO 報告生成完成：{report_filepath}")
                            else:
                                task_status['report_generation']['status'] = 'error'
                                task_status['report_generation']['message'] = '啟動時自動執行：CISO 週報生成失敗（無法儲存檔案）'
                        else:
                            task_status['report_generation']['status'] = 'error'
                            task_status['report_generation']['message'] = '啟動時自動執行：CISO 週報生成失敗（無資料）'
                        
                        # 更新上次執行時間
                        scheduler_state['last_execution_time'] = get_taipei_time()
                        
                        # 重新計算下次執行時間
                        next_execution = get_taipei_time() + timedelta(minutes=total_minutes)
                        scheduler_state['next_execution_time'] = next_execution.isoformat()
                        
                        print(f"[啟動] 啟動任務完成，下次執行時間：{next_execution.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        db_conn.close()
                        
                    except Exception as e:
                        print(f"[啟動] 啟動任務發生錯誤：{e}", file=sys.stderr)
                        task_status['collectors']['status'] = 'error'
                        task_status['collectors']['message'] = f'啟動時自動執行錯誤：{str(e)}'
                        task_status['correlation']['status'] = 'error'
                        task_status['correlation']['message'] = f'啟動時自動執行錯誤：{str(e)}'
                        task_status['report_generation']['status'] = 'error'
                        task_status['report_generation']['message'] = f'啟動時自動執行錯誤：{str(e)}'
            
            # 在背景執行啟動任務
            thread = threading.Thread(target=run_startup_task)
            thread.daemon = True
            thread.start()
        else:
            print("[啟動] 排程狀態：停用（不執行自動任務）")
            
    except Exception as e:
        print(f"[啟動] 初始化任務發生錯誤：{e}", file=sys.stderr)
    
    print("訪問地址：http://localhost:5001 (容器內端口 5000)")
    print("=" * 60)


if __name__ == '__main__':
    # 執行啟動任務
    startup_tasks()
    
    app.run(host='0.0.0.0', port=5000, debug=True)

