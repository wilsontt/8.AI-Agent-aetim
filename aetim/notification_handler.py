#!/usr/bin/env python3
"""
AETIM 通知處理器 (Notification Handler)
功能：根據風險分數執行差異化的通知（Email、Teams、Slack、Jira 等）
"""

import sys
import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
from utils import load_config

# 設定時區為 Asia/Taipei
TAIPEI_TZ = ZoneInfo('Asia/Taipei')

def get_taipei_time():
    """取得 Asia/Taipei 時區的當前時間"""
    return datetime.now(TAIPEI_TZ)


def send_email(subject: str, body: str, to_address: str, from_address: str, 
               smtp_server: str, smtp_port: int, smtp_username: str, 
               smtp_password: str, use_tls: bool = True, attachments: List[str] = None):
    """
    發送 Email
    
    Args:
        subject: 主旨
        body: 內容（HTML 或純文字）
        to_address: 收件者 Email
        from_address: 發送者 Email
        smtp_server: SMTP 伺服器
        smtp_port: SMTP 埠口
        smtp_username: SMTP 使用者名稱
        smtp_password: SMTP 密碼
        use_tls: 是否使用 TLS
        attachments: 附件檔案路徑列表
    """
    try:
        # 驗證必要參數
        if not to_address:
            print(f"[錯誤] 發送 Email 失敗：收件者 Email 為空", file=sys.stderr)
            return False
        
        if not from_address:
            print(f"[錯誤] 發送 Email 失敗：發送者 Email 為空", file=sys.stderr)
            return False
        
        if not smtp_server:
            print(f"[錯誤] 發送 Email 失敗：SMTP 伺服器為空", file=sys.stderr)
            return False
        
        print(f"[通知] 準備發送 Email 至：{to_address}")
        print(f"[通知] SMTP 伺服器：{smtp_server}:{smtp_port}")
        print(f"[通知] 使用 TLS：{use_tls}")
        
        msg = MIMEMultipart('alternative')
        msg['From'] = from_address
        msg['To'] = to_address
        msg['Subject'] = subject
        
        # 判斷是否為 HTML
        if '<html>' in body.lower() or '<body>' in body.lower():
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 添加附件
        if attachments:
            for filepath in attachments:
                if os.path.exists(filepath):
                    with open(filepath, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(filepath)}'
                        )
                        msg.attach(part)
                    print(f"[通知] 已添加附件：{os.path.basename(filepath)}")
        
        # 發送郵件
        print(f"[通知] 正在連線 SMTP 伺服器...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.set_debuglevel(0)  # 關閉除錯模式（避免輸出過多資訊）
        
        if use_tls:
            print(f"[通知] 啟動 TLS...")
            server.starttls()
        
        if smtp_username and smtp_password:
            print(f"[通知] 正在登入 SMTP 伺服器...")
            server.login(smtp_username, smtp_password)
        
        print(f"[通知] 正在發送 Email...")
        server.send_message(msg)
        server.quit()
        
        print(f"[通知] Email 已成功發送至：{to_address}")
        return True
    
    except smtplib.SMTPAuthenticationError as e:
        print(f"[錯誤] SMTP 認證失敗：{e}", file=sys.stderr)
        print(f"[錯誤] 請檢查 SMTP 使用者名稱和密碼是否正確", file=sys.stderr)
        return False
    except smtplib.SMTPConnectError as e:
        print(f"[錯誤] SMTP 連線失敗：{e}", file=sys.stderr)
        print(f"[錯誤] 請檢查 SMTP 伺服器地址和埠口是否正確", file=sys.stderr)
        return False
    except smtplib.SMTPException as e:
        print(f"[錯誤] SMTP 錯誤：{e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[錯誤] 發送 Email 失敗：{e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def notify_critical_threat(threat_data: Dict, config: Dict):
    """
    工作流 1：嚴重威脅（Critical Threat）- 即時觸發
    當 risk_score > 9.0 時立即通知
    
    Args:
        threat_data: 威脅資料（包含 validated_threat, asset_data, intel_data）
        config: 設定檔
    """
    notification_config = config.get('notification', {})
    
    # 檢查通知是否啟用（預設為 false，因為需要設定 Email）
    notification_enabled = notification_config.get('enabled', False)
    email_config = notification_config.get('email', {})
    email_enabled = email_config.get('enabled', False)
    
    if not notification_enabled or not email_enabled:
        print("[通知] 通知功能未啟用（請在 config.yaml 中設定 notification.enabled = true 和 notification.email.enabled = true）")
        return
    
    validated_threat = threat_data.get('validated_threat', {})
    asset_data = threat_data.get('asset_data', {})
    intel_data = threat_data.get('intel_data', {})
    
    risk_score = validated_threat.get('risk_score', 0)
    
    print(f"\n[通知] 觸發嚴重威脅通知（風險分數：{risk_score}）")
    
    # 生成 IT 工單內容
    from reporting_engine import generate_it_ticket
    ticket = generate_it_ticket(validated_threat, asset_data, intel_data, config)
    
    # 通知 IT 團隊
    owner = asset_data.get('owner', 'IT 團隊')
    # 注意：owner_email 需要從設定檔或資產清單中取得
    # 目前先使用資安官的 Email，未來可以擴充
    owner_email = asset_data.get('owner_email', None)
    
    if owner_email and notification_config.get('channels', {}).get('email', False):
        email_config = notification_config.get('email', {})
        if email_config.get('enabled', False):
            it_subject = f"[AETIM 緊急工單] {ticket['title']}"
            it_body = f"""
緊急資安威脅通知

工單編號：{ticket['ticket_id']}
優先級：{ticket['priority']}

受影響資產：
- 主機名稱：{asset_data.get('hostname', 'N/A')}
- IP 位址：{asset_data.get('ip_address', 'N/A')}
- 負責人：{owner}

威脅資訊：
- CVE ID：{intel_data.get('cve_id', 'N/A')}
- 威脅標題：{intel_data.get('title', 'N/A')}
- 風險分數：{risk_score} / 10.0
- 情資來源：{intel_data.get('source', 'N/A')}

建議行動：
{ticket.get('recommendations', '請查閱相關安全公告')}

---
此為自動化系統發送的通知，請勿直接回覆。
"""
            send_email(
                subject=it_subject,
                body=it_body,
                to_address=owner_email,
                from_address=email_config.get('from_address', ''),
                smtp_server=email_config.get('smtp_server', ''),
                smtp_port=email_config.get('smtp_port', 587),
                smtp_username=email_config.get('smtp_username', ''),
                smtp_password=email_config.get('smtp_password', ''),
                use_tls=email_config.get('use_tls', True)
            )
    
    # 通知資安官
    email_config = notification_config.get('email', {})
    if email_config.get('enabled', False):
        # 新結構：critical 類型收件者
        target_emails = []
        types_cfg = notification_config.get('types', {})
        crit_cfg = types_cfg.get('critical', {})
        if crit_cfg.get('enabled', True):
            rec_groups = crit_cfg.get('recipients', [])
            recipients_map = notification_config.get('recipients', {})
            for g in rec_groups:
                addr = recipients_map.get(g)
                if addr:
                    target_emails.append(addr)
        # 回退舊結構
        if not target_emails:
            fallback = email_config.get('to_address', '')
            if fallback:
                target_emails = [fallback]
        for security_officer_email in target_emails:
            subject = f"[AETIM 緊急警報] 發現嚴重威脅 (Risk: {risk_score}) - 影響 {asset_data.get('hostname', 'N/A')}"
            body = f"""
緊急資安威脅警報

系統偵測到嚴重威脅，已自動建立工單並通知 IT 團隊。

威脅摘要：
- CVE ID：{intel_data.get('cve_id', 'N/A')}
- 受影響主機：{asset_data.get('hostname', 'N/A')} ({asset_data.get('ip_address', 'N/A')})
- 風險分數：{risk_score} / 10.0
- 負責人：{owner}

工單編號：{ticket['ticket_id']}
優先級：{ticket['priority']}

---
此為自動化系統發送的通知，請勿直接回覆。
"""
            send_email(
                subject=subject,
                body=body,
                to_address=security_officer_email,
                from_address=email_config.get('from_address', ''),
                smtp_server=email_config.get('smtp_server', ''),
                smtp_port=email_config.get('smtp_port', 587),
                smtp_username=email_config.get('smtp_username', ''),
                smtp_password=email_config.get('smtp_password', ''),
                use_tls=email_config.get('use_tls', True)
            )


def notify_high_risk_daily_summary(db_conn, config):
    """
    工作流 2：高風險威脅（High Threat）- 每日彙總
    當 7.0 < risk_score <= 9.0 時，每日彙總通知
    
    Args:
        db_conn: 資料庫連線
        config: 設定檔
    """
    notification_config = config.get('notification', {})
    
    if not notification_config.get('enabled', False):
        return
    
    thresholds = notification_config.get('thresholds', {})
    high_threshold = thresholds.get('high', 7.0)
    critical_threshold = thresholds.get('critical', 9.0)
    
    # 查詢過去 24 小時內的高風險威脅
    from datetime import timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=24)
    
    import pandas as pd
    query = """
        SELECT 
            vt.id,
            vt.risk_score,
            vt.status,
            ri.cve_id,
            ri.title,
            ri.source,
            a.hostname,
            a.ip_address,
            a.owner
        FROM T_Validated_Threats vt
        JOIN T_Raw_Intel ri ON vt.intel_id = ri.id
        JOIN T_Assets a ON vt.asset_id = a.id
        WHERE vt.timestamp >= ?
          AND vt.risk_score > ?
          AND vt.risk_score <= ?
          AND vt.status = 'new'
        ORDER BY vt.risk_score DESC
    """
    
    df_high_risk = pd.read_sql_query(query, db_conn, params=(
        start_date.isoformat(), high_threshold, critical_threshold
    ))
    
    if len(df_high_risk) == 0:
        print("[通知] 過去 24 小時內無高風險威脅，跳過每日摘要。")
        return
    
    print(f"\n[通知] 生成高風險威脅每日摘要（{len(df_high_risk)} 筆）")
    
    email_config = notification_config.get('email', {})
    if email_config.get('enabled', False):
        # 依新結構決定收件者
        target_emails = []
        types_cfg = notification_config.get('types', {})
        high_cfg = types_cfg.get('high_daily', {})
        if high_cfg.get('enabled', True):
            rec_groups = high_cfg.get('recipients', [])
            recipients_map = notification_config.get('recipients', {})
            for g in rec_groups:
                addr = recipients_map.get(g)
                if addr:
                    target_emails.append(addr)
        # 相容處理
        if not target_emails:
            to_address = email_config.get('to_address', '')
            if to_address:
                target_emails = [to_address]
        for to_address in target_emails:
            subject = f"[AETIM 每日威脅摘要] {get_taipei_time().strftime('%Y-%m-%d')}"
            
            # 生成摘要內容
            body = f"""
高風險威脅每日摘要

報告期間：{start_date.strftime('%Y-%m-%d %H:%M')} 至 {end_date.strftime('%Y-%m-%d %H:%M')}
威脅數量：{len(df_high_risk)} 筆

威脅清單：
"""
            for _, row in df_high_risk.iterrows():
                body += f"""
- CVE: {row['cve_id'] or 'N/A'}
  主機：{row['hostname']} ({row['ip_address']})
  風險分數：{row['risk_score']:.2f}
  來源：{row['source']}
"""
            
            body += """
---
此為自動化系統發送的通知，請勿直接回覆。
"""
            
            send_email(
                subject=subject,
                body=body,
                to_address=to_address,
                from_address=email_config.get('from_address', ''),
                smtp_server=email_config.get('smtp_server', ''),
                smtp_port=email_config.get('smtp_port', 587),
                smtp_username=email_config.get('smtp_username', ''),
                smtp_password=email_config.get('smtp_password', ''),
                use_tls=email_config.get('use_tls', True)
            )


def notify_weekly_report(report_filepath: str, config: Dict, target_email: str = None):
    """
    工作流 3：管理層週報（Weekly Report）- 排程
    每週發送 CISO 週報
    
    Args:
        report_filepath: 報告檔案路徑
        config: 設定檔
        target_email: 指定收件者 Email（如果為 None，則從設定檔讀取）
    """
    print(f"[通知] 開始發送週報通知...")
    print(f"[通知] 報告檔案路徑：{report_filepath}")
    
    notification_config = config.get('notification', {})
    email_config = notification_config.get('email', {})
    
    # 檢查通知功能是否啟用
    # 優先檢查 email.enabled，因為這是用戶在 UI 中設定的
    notification_enabled = notification_config.get('enabled', False)
    email_enabled = email_config.get('enabled', False)
    
    # 如果 email.enabled 為 True，視為通知功能啟用（即使 notification.enabled 為 False）
    # 或者 notification.enabled 為 True 且 email.enabled 為 True
    is_enabled = email_enabled or (notification_enabled and email_enabled)
    
    # 添加詳細的日誌輸出
    print(f"[通知] 通知設定檢查：")
    print(f"  - notification.enabled：{notification_enabled}")
    print(f"  - email.enabled：{email_enabled}")
    print(f"  - 通知功能啟用狀態：{is_enabled}")
    print(f"[通知] Email 設定檢查：")
    print(f"  - SMTP 伺服器：{email_config.get('smtp_server', 'N/A')}")
    print(f"  - SMTP 埠口：{email_config.get('smtp_port', 'N/A')}")
    print(f"  - SMTP 使用者名稱：{email_config.get('smtp_username', 'N/A')}")
    print(f"  - 發送者 Email：{email_config.get('from_address', 'N/A')}")
    print(f"  - 收件者 Email：{email_config.get('to_address', 'N/A')}")
    print(f"  - 使用 TLS：{email_config.get('use_tls', True)}")
    
    # 如果 email.enabled 為 True，就繼續執行（即使 notification.enabled 為 False）
    if not email_enabled:
        print("[通知] Email 功能未啟用（email.enabled 為 False），跳過週報發送。")
        return
    
    # 決定週報收件者
    if target_email:
        # 如果指定了收件者，直接使用
        target_emails = [target_email]
    else:
        # 否則從設定檔讀取（新結構 recipients + types.weekly_report）
        target_emails = []
        types_cfg = notification_config.get('types', {})
        weekly_cfg = types_cfg.get('weekly_report', {})
        if weekly_cfg.get('enabled', True):
            rec_groups = weekly_cfg.get('recipients', [])
            recipients_map = notification_config.get('recipients', {})
            for g in rec_groups:
                addr = recipients_map.get(g)
                if addr:
                    target_emails.append(addr)
        # 相容舊結構：回退 to_address
        if not target_emails:
            to_address = email_config.get('to_address', '')
            if to_address:
                target_emails = [to_address]
    
    if not target_emails:
        print("[通知] 錯誤：收件者 Email 為空，無法發送週報。")
        return
    
    # 驗證必要的 SMTP 設定
    smtp_server = email_config.get('smtp_server', '')
    smtp_port = email_config.get('smtp_port', 587)
    smtp_username = email_config.get('smtp_username', '')
    smtp_password = email_config.get('smtp_password', '')
    from_address = email_config.get('from_address', '')
    
    if not smtp_server:
        print("[通知] 錯誤：SMTP 伺服器未設定，無法發送週報。")
        return
    
    if not from_address:
        print("[通知] 錯誤：發送者 Email 未設定，無法發送週報。")
        return
    
    print(f"[通知] 所有必要設定已檢查，準備發送 Email...")
    
    subject = f"[AETIM 資安情資週報] {get_taipei_time().strftime('%Y-%m-%d')}"
    
    # 讀取報告內容
    body = ""
    attachments = []
    
    if report_filepath and os.path.exists(report_filepath):
        with open(report_filepath, 'r', encoding='utf-8') as f:
            body = f.read()
        attachments = [report_filepath]
        print(f"[通知] 報告檔案已讀取，大小：{len(body)} 字元")
    else:
        body = "本週資安情資週報已生成，請查看系統報告目錄。"
        print(f"[通知] 警告：報告檔案不存在，使用預設內容。")
    
    for to_address in target_emails:
        print(f"[通知] 正在發送 Email 至：{to_address}")
        result = send_email(
            subject=subject,
            body=body,
            to_address=to_address,
            from_address=from_address,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            use_tls=email_config.get('use_tls', True),
            attachments=attachments
        )
        if result:
            print(f"[通知] 週報 Email 已成功發送至：{to_address}")
        else:
            print(f"[通知] 週報 Email 發送失敗：{to_address}")


def notify_it_tickets(report_filepath: str, config: Dict, target_email: str = None):
    """
    發送 IT 工單報告
    
    Args:
        report_filepath: IT 工單報告檔案路徑（JSON 格式）
        config: 設定檔
        target_email: 指定收件者 Email（如果為 None，則從設定檔讀取）
    """
    print(f"[通知] 開始發送 IT 工單報告...")
    print(f"[通知] 報告檔案路徑：{report_filepath}")
    
    notification_config = config.get('notification', {})
    email_config = notification_config.get('email', {})
    
    # 檢查通知功能是否啟用
    email_enabled = email_config.get('enabled', False)
    if not email_enabled:
        print("[通知] Email 功能未啟用（email.enabled 為 False），跳過 IT 工單發送。")
        return
    
    # 決定收件者
    if target_email:
        target_emails = [target_email]
    else:
        # 從設定檔讀取 IT 收件者
        target_emails = []
        types_cfg = notification_config.get('types', {})
        weekly_cfg = types_cfg.get('weekly_report', {})
        if weekly_cfg.get('enabled', True):
            rec_groups = weekly_cfg.get('recipients', [])
            recipients_map = notification_config.get('recipients', {})
            for g in rec_groups:
                if g == 'it':  # 只發送給 IT
                    addr = recipients_map.get(g)
                    if addr:
                        target_emails.append(addr)
        # 相容舊結構
        if not target_emails:
            it_email = email_config.get('it_email', '')
            if it_email:
                target_emails = [it_email]
    
    if not target_emails:
        print("[通知] 錯誤：IT 收件者 Email 為空，無法發送 IT 工單。")
        return
    
    # 驗證必要的 SMTP 設定
    smtp_server = email_config.get('smtp_server', '')
    smtp_port = email_config.get('smtp_port', 587)
    smtp_username = email_config.get('smtp_username', '')
    smtp_password = email_config.get('smtp_password', '')
    from_address = email_config.get('from_address', '')
    
    if not smtp_server or not from_address:
        print("[通知] 錯誤：SMTP 設定不完整，無法發送 IT 工單。")
        return
    
    # 讀取 IT 工單報告內容
    import json
    try:
        with open(report_filepath, 'r', encoding='utf-8') as f:
            it_report_data = json.load(f)
        
        total_tickets = it_report_data.get('total_tickets', 0)
        tickets = it_report_data.get('tickets', [])
        
        # 生成 Email 內容
        subject = f"[AETIM IT 工單週報] {get_taipei_time().strftime('%Y-%m-%d')} - {total_tickets} 個高風險威脅"
        
        # 生成文字格式的 Email 內容
        body_lines = [
            f"本週高風險威脅 IT 工單彙總",
            f"=" * 80,
            f"",
            f"總工單數：{total_tickets}",
            f"生成時間：{get_taipei_time().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"=" * 80,
            f""
        ]
        
        # 列出所有工單摘要
        for idx, ticket in enumerate(tickets[:20], 1):  # 最多顯示前 20 個
            body_lines.extend([
                f"工單 #{idx}",
                f"  工單編號：{ticket.get('ticket_id', 'N/A')}",
                f"  優先級：{ticket.get('priority', 'N/A')}",
                f"  標題：{ticket.get('title', 'N/A')}",
                f"  風險分數：{ticket.get('risk_score', 'N/A')}",
                f"  受影響資產：{ticket.get('asset', {}).get('hostname', 'N/A')}",
                f""
            ])
        
        if total_tickets > 20:
            body_lines.append(f"... 還有 {total_tickets - 20} 個工單，詳見附件。")
        
        body_lines.extend([
            f"",
            f"=" * 80,
            f"完整工單資料請查看附件 JSON 檔案。",
            f"",
            f"---",
            f"此為自動化系統發送的通知，請勿直接回覆。"
        ])
        
        body = "\n".join(body_lines)
        attachments = [report_filepath]
        
    except Exception as e:
        print(f"[通知] 錯誤：讀取 IT 工單報告失敗：{e}", file=sys.stderr)
        return
    
    # 發送 Email
    for to_address in target_emails:
        print(f"[通知] 正在發送 IT 工單報告至：{to_address}")
        result = send_email(
            subject=subject,
            body=body,
            to_address=to_address,
            from_address=from_address,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            use_tls=email_config.get('use_tls', True),
            attachments=attachments
        )
        if result:
            print(f"[通知] IT 工單報告 Email 已成功發送至：{to_address}")
        else:
            print(f"[通知] IT 工單報告 Email 發送失敗：{to_address}")


def check_and_notify_critical_threats(db_conn, config):
    """
    檢查是否有新的嚴重威脅需要立即通知
    此函數應在關聯分析引擎執行後被調用
    """
    notification_config = config.get('notification', {})
    
    if not notification_config.get('enabled', False):
        return
    
    thresholds = notification_config.get('thresholds', {})
    critical_threshold = thresholds.get('critical', 9.0)
    
    import pandas as pd
    query = """
        SELECT 
            vt.id,
            vt.intel_id,
            vt.asset_id,
            vt.risk_score,
            vt.status,
            ri.id as intel_row_id,
            ri.cve_id,
            ri.title,
            ri.source,
            ri.cvss_score,
            ri.raw_data,
            a.hostname,
            a.ip_address,
            a.owner,
            a.os_version,
            a.applications
        FROM T_Validated_Threats vt
        JOIN T_Raw_Intel ri ON vt.intel_id = ri.id
        JOIN T_Assets a ON vt.asset_id = a.id
        WHERE vt.risk_score > ?
          AND vt.status = 'new'
          AND vt.timestamp >= datetime('now', '-1 hour')
        ORDER BY vt.risk_score DESC
    """
    
    df_critical = pd.read_sql_query(query, db_conn, params=(critical_threshold,))
    
    if len(df_critical) == 0:
        return
    
    print(f"\n[通知] 發現 {len(df_critical)} 筆嚴重威脅，開始發送通知...")
    
    for _, row in df_critical.iterrows():
        validated_threat = {
            'id': row['id'],
            'risk_score': row['risk_score'],
            'status': row['status']
        }
        
        asset_data = {
            'hostname': row['hostname'],
            'ip_address': row['ip_address'],
            'owner': row['owner'],
            'os_version': row['os_version'],
            'applications': row['applications'],
            'owner_email': None  # TODO: 從資產清單或設定檔中取得
        }
        
        intel_data = {
            'cve_id': row['cve_id'],
            'title': row['title'],
            'source': row['source'],
            'cvss_score': row['cvss_score'],
            'raw_data': row['raw_data']
        }
        
        threat_data = {
            'validated_threat': validated_threat,
            'asset_data': asset_data,
            'intel_data': intel_data
        }
        
        notify_critical_threat(threat_data, config)


if __name__ == "__main__":
    """測試通知功能"""
    from utils import get_db_connection
    
    config = load_config()
    db_conn = get_db_connection()
    
    if db_conn:
        try:
            check_and_notify_critical_threats(db_conn, config)
        finally:
            db_conn.close()
