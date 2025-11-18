#!/usr/bin/env python3
"""
AETIM 報告生成引擎 (Reporting Engine)
功能：自動產生兩種不同受眾的報告
- 報告模板 A：CISO 威脅情資週報（管理層）
- 報告模板 B：IT 維運工單（技術層）
"""

import sys
import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Optional
from jinja2 import Template, Environment, FileSystemLoader
from utils import get_db_connection, load_config

# 設定時區為 Asia/Taipei
TAIPEI_TZ = ZoneInfo('Asia/Taipei')

def get_taipei_time():
    """取得 Asia/Taipei 時區的當前時間"""
    return datetime.now(TAIPEI_TZ)


def generate_ai_summary(threats_data: List[Dict], config: Dict) -> Optional[str]:
    """
    使用 AI 生成威脅摘要（150 字內）
    
    Args:
        threats_data: 威脅資料列表
        config: 設定檔
    
    Returns:
        AI 生成的摘要文字，如果 AI 無法使用則返回 None
    """
    # 安全處理 None 值：先取得值，如果不是 None 才調用 strip()
    openai_key_raw = config['api_keys'].get('openai')
    openai_key = str(openai_key_raw).strip() if openai_key_raw is not None else ''
    
    if not openai_key or openai_key == '${OPENAI_API_KEY}' or openai_key == 'YOUR_OPENAI_API_KEY_HERE' or openai_key == 'None':
        print("[AI 摘要] OpenAI API 金鑰未設定，跳過 AI 摘要生成。")
        return None
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        # 準備威脅摘要資料
        threats_summary = []
        for threat in threats_data[:10]:  # 最多處理前 10 筆
            threats_summary.append({
                'cve_id': threat.get('cve_id', 'N/A'),
                'title': threat.get('title', 'N/A')[:100],
                'risk_score': threat.get('risk_score', 0),
                'hostname': threat.get('hostname', 'N/A')
            })
        
        prompt = f"""你是一位企業資安諮詢顧問。請用 150 字內的繁體中文，總結以下威脅對本公司（一家擁有對外文件倉儲系統的公司）的潛在業務衝擊，並建議本週的管理層應關注的焦點。

威脅列表：
{json.dumps(threats_summary, ensure_ascii=False, indent=2)}

請以專業、簡潔的方式回應，重點強調業務風險和行動建議。"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # 使用較便宜的模型
            messages=[
                {"role": "system", "content": "你是一位資安顧問，專精於將技術威脅轉化為業務風險描述。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        summary = response.choices[0].message.content.strip()
        print(f"[AI 摘要] 成功生成摘要（{len(summary)} 字）")
        return summary
    
    except ImportError:
        print("[AI 摘要] openai 套件未安裝，跳過 AI 摘要生成。")
        return None
    except Exception as e:
        print(f"[AI 摘要] 生成摘要時發生錯誤：{e}")
        return None


def generate_ciso_weekly_report(db_conn, config, days: int = 7) -> Dict:
    """
    生成 CISO 威脅情資週報（管理層）
    
    Args:
        db_conn: 資料庫連線
        config: 設定檔
        days: 報告涵蓋天數（預設 7 天）
    
    Returns:
        報告資料字典
    """
    print(f"\n[報告生成] 開始生成 CISO 週報（過去 {days} 天）...")
    
    # 計算日期範圍（使用 Asia/Taipei 時區）
    end_date = get_taipei_time()
    start_date = end_date - timedelta(days=days)
    
    # 查詢高風險以上的威脅（過去 7 天）
    query = """
        SELECT 
            vt.id,
            vt.intel_id,
            vt.asset_id,
            vt.risk_score,
            vt.status,
            vt.timestamp,
            ri.cve_id,
            ri.title,
            ri.source,
            ri.cvss_score,
            a.hostname,
            a.ip_address,
            a.is_public,
            a.business_criticality,
            a.owner
        FROM T_Validated_Threats vt
        JOIN T_Raw_Intel ri ON vt.intel_id = ri.id
        JOIN T_Assets a ON vt.asset_id = a.id
        WHERE vt.timestamp >= ? 
          AND vt.risk_score >= 4.0
        ORDER BY vt.risk_score DESC
    """
    
    df_threats = pd.read_sql_query(query, db_conn, params=(start_date.isoformat(),))
    
    # 分類威脅
    critical_threats = df_threats[df_threats['risk_score'] >= 9.0].to_dict('records')
    high_threats = df_threats[(df_threats['risk_score'] >= 7.0) & (df_threats['risk_score'] < 9.0)].to_dict('records')
    medium_threats = df_threats[(df_threats['risk_score'] >= 4.0) & (df_threats['risk_score'] < 7.0)].to_dict('records')
    
    # 統計資料
    stats = {
        'total_threats': len(df_threats),
        'critical_count': len(critical_threats),
        'high_count': len(high_threats),
        'medium_count': len(medium_threats),
        'remediated_count': len(df_threats[df_threats['status'] == 'remediated']),
        'new_count': len(df_threats[df_threats['status'] == 'new']),
        'date_range': {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
    }
    
    # Top 5 曝險最嚴重的資產
    asset_risk_query = """
        SELECT 
            a.id,
            a.hostname,
            a.ip_address,
            a.business_criticality,
            COUNT(vt.id) as threat_count,
            AVG(vt.risk_score) as avg_risk_score,
            MAX(vt.risk_score) as max_risk_score
        FROM T_Assets a
        JOIN T_Validated_Threats vt ON a.id = vt.asset_id
        WHERE vt.timestamp >= ?
        GROUP BY a.id
        ORDER BY max_risk_score DESC, threat_count DESC
        LIMIT 5
    """
    
    df_top_assets = pd.read_sql_query(asset_risk_query, db_conn, params=(start_date.isoformat(),))
    top_assets = df_top_assets.to_dict('records')
    
    # 未關閉的嚴重威脅（上週）
    unresolved_critical = [t for t in critical_threats if t['status'] != 'remediated']
    
    # 準備 AI 摘要資料（前 10 筆高風險威脅）
    ai_summary_data = (critical_threats[:5] + high_threats[:5])[:10]
    
    # 生成 AI 摘要（如果啟用）
    ai_summary = None
    reporting_config = config.get('reporting', {})
    if reporting_config.get('templates', {}).get('ciso_weekly', {}).get('include_ai_summary', False):
        ai_summary = generate_ai_summary(ai_summary_data, config)
    
    report_data = {
        'report_type': 'CISO Weekly Report',
        'generated_at': get_taipei_time().strftime('%Y-%m-%d %H:%M:%S'),
        'stats': stats,
        'threats': {
            'critical': critical_threats[:10],  # Top 10
            'high': high_threats[:10],
            'medium': medium_threats[:5]
        },
        'top_assets': top_assets,
        'unresolved_critical': unresolved_critical[:5],
        'ai_summary': ai_summary
    }
    
    print(f"[報告生成] CISO 週報資料準備完成：{stats['total_threats']} 筆威脅")
    return report_data


def render_html_report(report_data: Dict, template_name: str = 'ciso_weekly.html') -> str:
    """
    使用 Jinja2 渲染 HTML 報告
    
    Args:
        report_data: 報告資料
        template_name: 模板檔名
    
    Returns:
        HTML 字串
    """
    # 創建模板環境
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    
    # 如果模板目錄不存在，使用內建模板
    if not os.path.exists(template_dir):
        os.makedirs(template_dir, exist_ok=True)
        # 這裡可以創建預設模板，但目前我們使用字串模板
    
    # 使用簡單的字串模板（未來可以改用檔案模板）
    if template_name == 'ciso_weekly.html':
        html_template = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_type }} - {{ generated_at }}</title>
    <style>
        body { font-family: 'Microsoft JhengHei', Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: #ecf0f1; padding: 20px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; color: #e74c3c; }
        .stat-label { color: #7f8c8d; margin-top: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #3498db; color: white; }
        tr:hover { background-color: #f5f5f5; }
        .risk-critical { color: #e74c3c; font-weight: bold; }
        .risk-high { color: #f39c12; font-weight: bold; }
        .risk-medium { color: #f1c40f; }
        .ai-summary { background: #e8f5e9; padding: 20px; border-radius: 8px; border-left: 4px solid #4caf50; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ report_type }}</h1>
        <p><strong>生成時間：</strong>{{ generated_at }}</p>
        <p><strong>報告期間：</strong>{{ stats.date_range.start }} 至 {{ stats.date_range.end }}</p>
        
        {% if ai_summary %}
        <div class="ai-summary">
            <h2>AI 執行摘要</h2>
            <p>{{ ai_summary }}</p>
        </div>
        {% endif %}
        
        <h2>關鍵指標</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ stats.total_threats }}</div>
                <div class="stat-label">總威脅數</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.critical_count }}</div>
                <div class="stat-label">嚴重威脅</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.high_count }}</div>
                <div class="stat-label">高風險威脅</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.remediated_count }}</div>
                <div class="stat-label">已修復</div>
            </div>
        </div>
        
        <h2>Top 5 曝險最嚴重的資產</h2>
        <table>
            <thead>
                <tr>
                    <th>主機名稱</th>
                    <th>IP 位址</th>
                    <th>威脅數量</th>
                    <th>平均風險分數</th>
                    <th>最高風險分數</th>
                    <th>業務關鍵性</th>
                </tr>
            </thead>
            <tbody>
                {% for asset in top_assets %}
                <tr>
                    <td>{{ asset.hostname }}</td>
                    <td>{{ asset.ip_address }}</td>
                    <td>{{ asset.threat_count }}</td>
                    <td>{{ "%.2f"|format(asset.avg_risk_score) }}</td>
                    <td class="risk-{% if asset.max_risk_score >= 9 %}critical{% elif asset.max_risk_score >= 7 %}high{% else %}medium{% endif %}">{{ "%.2f"|format(asset.max_risk_score) }}</td>
                    <td>{{ asset.business_criticality }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <h2>嚴重威脅（風險分數 >= 9.0）</h2>
        <table>
            <thead>
                <tr>
                    <th>CVE ID</th>
                    <th>標題</th>
                    <th>主機名稱</th>
                    <th>風險分數</th>
                    <th>狀態</th>
                    <th>來源</th>
                </tr>
            </thead>
            <tbody>
                {% for threat in threats.critical %}
                <tr>
                    <td>{{ threat.cve_id or 'N/A' }}</td>
                    <td>{{ threat.title[:50] }}{% if threat.title|length > 50 %}...{% endif %}</td>
                    <td>{{ threat.hostname }}</td>
                    <td class="risk-critical">{{ "%.2f"|format(threat.risk_score) }}</td>
                    <td>{{ threat.status }}</td>
                    <td>{{ threat.source }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        {% if unresolved_critical %}
        <h2>未解決的嚴重威脅</h2>
        <table>
            <thead>
                <tr>
                    <th>CVE ID</th>
                    <th>主機名稱</th>
                    <th>風險分數</th>
                    <th>發現時間</th>
                </tr>
            </thead>
            <tbody>
                {% for threat in unresolved_critical %}
                <tr>
                    <td>{{ threat.cve_id or 'N/A' }}</td>
                    <td>{{ threat.hostname }}</td>
                    <td class="risk-critical">{{ "%.2f"|format(threat.risk_score) }}</td>
                    <td>{{ threat.timestamp }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
        
    </div>
</body>
</html>
        """
        
        template = Template(html_template)
        return template.render(**report_data)
    
    return ""


def generate_it_ticket(validated_threat: Dict, asset_data: Dict, intel_data: Dict, config: Dict) -> Dict:
    """
    生成 IT 維運工單（技術層）
    
    Args:
        validated_threat: 已驗證威脅資料
        asset_data: 資產資料
        intel_data: 情資資料
        config: 設定檔
    
    Returns:
        工單資料字典（可用於 Email、JSON 等格式）
    """
    ticket_data = {
        'ticket_id': f"AETIM-{validated_threat['id']}-{get_taipei_time().strftime('%Y%m%d%H%M%S')}",
        'priority': 'P0' if validated_threat['risk_score'] >= 9.0 else 'P1',
        'title': f"資安威脅：{intel_data.get('cve_id', 'N/A')} - {asset_data.get('hostname', 'N/A')}",
        'affected_asset': {
            'hostname': asset_data.get('hostname', 'N/A'),
            'ip_address': asset_data.get('ip_address', 'N/A'),
            'owner': asset_data.get('owner', 'N/A')
        },
        'threat': {
            'cve_id': intel_data.get('cve_id', 'N/A'),
            'title': intel_data.get('title', 'N/A'),
            'risk_score': validated_threat['risk_score'],
            'source': intel_data.get('source', 'N/A'),
            'cvss_score': intel_data.get('cvss_score', 'N/A')
        },
        'recommendations': generate_recommendations(intel_data, asset_data),
        'created_at': get_taipei_time().isoformat()
    }
    
    return ticket_data


def generate_recommendations(intel_data: Dict, asset_data: Dict) -> str:
    """
    生成修補建議
    
    Args:
        intel_data: 情資資料
        asset_data: 資產資料
    
    Returns:
        建議文字
    """
    cve_id = intel_data.get('cve_id', '')
    source = intel_data.get('source', '')
    
    recommendations = []
    
    if cve_id:
        recommendations.append(f"1. 查閱 CVE 詳細資訊：https://nvd.nist.gov/vuln/detail/{cve_id}")
    
    if source == 'CISA_KEV':
        recommendations.append("2. 此漏洞已被 CISA 列入已知遭利用漏洞列表，建議立即修補")
        recommendations.append("3. 參考 CISA KEV Catalog：https://www.cisa.gov/known-exploited-vulnerabilities-catalog")
    
    if 'Windows' in str(asset_data.get('os_version', '')):
        recommendations.append("4. 檢查 Windows Update 是否有相關安全性更新")
        recommendations.append("5. 參考 Microsoft Security Response Center (MSRC) 公告")
    
    if 'VMware' in str(asset_data.get('applications', '')) or 'VMware' in str(asset_data.get('os_version', '')):
        recommendations.append("4. 參考 VMware Security Advisories (VMSA)")
        recommendations.append("5. 檢查 VMware 支援頁面是否有修補程式")
    
    if not recommendations:
        recommendations.append("1. 請查閱相關廠商的安全公告")
        recommendations.append("2. 聯絡資產負責人進行威脅評估")
        recommendations.append("3. 考慮實施臨時緩解措施")
    
    return "\n".join(recommendations)


def save_report(report_data: Dict, report_type: str, format: str = 'html') -> Optional[str]:
    """
    儲存報告到檔案
    報告將按照年月目錄結構儲存：reports/yyyy/yyyymm/
    
    Args:
        report_data: 報告資料
        report_type: 報告類型（'ciso_weekly' 或 'it_ticket'）
        format: 格式（'html', 'text', 'json'）
    
    Returns:
        檔案路徑，如果失敗則返回 None
    """
    try:
        # 獲取當前日期（使用 Asia/Taipei 時區）
        now = get_taipei_time()
        year = now.strftime('%Y')  # yyyy
        year_month = now.strftime('%Y%m')  # yyyymm
        
        # 建立年月目錄結構：reports/yyyy/yyyymm/
        base_dir = os.path.join(os.path.dirname(__file__), 'reports')
        output_dir = os.path.join(base_dir, year, year_month)
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成檔名（使用 Asia/Taipei 時區的時間戳記）
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        filename = f"{report_type}_{timestamp}.{format}"
        filepath = os.path.join(output_dir, filename)
        
        if format == 'html':
            content = render_html_report(report_data, f"{report_type}.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        elif format == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        elif format == 'text':
            # 文字格式：針對 IT 工單進行格式化
            if report_type == 'it_ticket':
                content = "=" * 80 + "\n"
                content += "IT 維運工單 (IT Operational Ticket)\n"
                content += "=" * 80 + "\n\n"
                
                content += f"工單編號：{report_data.get('ticket_id', 'N/A')}\n"
                content += f"優先級：{report_data.get('priority', 'N/A')}\n"
                content += f"標題：{report_data.get('title', 'N/A')}\n"
                content += f"建立時間：{report_data.get('created_at', 'N/A')}\n\n"
                
                content += "-" * 80 + "\n"
                content += "受影響資產 (Affected Asset)\n"
                content += "-" * 80 + "\n"
                asset = report_data.get('affected_asset', {})
                content += f"主機名稱：{asset.get('hostname', 'N/A')}\n"
                content += f"IP 地址：{asset.get('ip_address', 'N/A')}\n"
                content += f"負責人：{asset.get('owner', 'N/A')}\n\n"
                
                content += "-" * 80 + "\n"
                content += "威脅資訊 (Threat Information)\n"
                content += "-" * 80 + "\n"
                threat = report_data.get('threat', {})
                content += f"CVE ID：{threat.get('cve_id', 'N/A')}\n"
                content += f"威脅標題：{threat.get('title', 'N/A')}\n"
                content += f"風險分數：{threat.get('risk_score', 'N/A')}\n"
                content += f"威脅來源：{threat.get('source', 'N/A')}\n"
                if threat.get('cvss_score'):
                    content += f"CVSS 分數：{threat.get('cvss_score', 'N/A')}\n"
                content += "\n"
                
                content += "-" * 80 + "\n"
                content += "修補建議 (Recommendations)\n"
                content += "-" * 80 + "\n"
                recommendations = report_data.get('recommendations', 'N/A')
                content += recommendations + "\n\n"
                
                content += "=" * 80 + "\n"
                content += "報告結束\n"
                content += "=" * 80 + "\n"
            else:
                # 其他報告類型的文字格式
                content = f"{report_data.get('report_type', 'Report')}\n"
                content += f"生成時間：{report_data.get('generated_at', 'N/A')}\n\n"
                content += json.dumps(report_data, ensure_ascii=False, indent=2)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        print(f"[報告生成] 報告已儲存：{filepath}")
        return filepath
    
    except Exception as e:
        print(f"[錯誤] 儲存報告失敗：{e}", file=sys.stderr)
        return None


def generate_weekly_report(db_conn, config):
    """
    生成週報主函數
    """
    print("\n" + "=" * 60)
    print(f"[{get_taipei_time()}] --- 生成 CISO 週報 ---")
    print("=" * 60)
    
    try:
        report_data = generate_ciso_weekly_report(db_conn, config, days=7)
        
        # 儲存報告
        reporting_config = config.get('reporting', {})
        templates_config = reporting_config.get('templates', {}).get('ciso_weekly', {})
        
        if templates_config.get('enabled', True):
            formats = templates_config.get('format', ['html'])
            
            for fmt in formats:
                if fmt == 'html':
                    save_report(report_data, 'ciso_weekly', 'html')
                elif fmt == 'pdf':
                    print("[報告生成] PDF 格式暫未實現，請使用 HTML 格式")
                elif fmt == 'json':
                    save_report(report_data, 'ciso_weekly', 'json')
        
        return report_data
    
    except Exception as e:
        print(f"[錯誤] 生成週報失敗：{e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def generate_it_tickets_for_high_risk(db_conn, config, risk_threshold: float = 7.0):
    """
    為高風險威脅生成 IT 工單
    
    Args:
        db_conn: 資料庫連線
        config: 設定檔
        risk_threshold: 風險分數閾值（預設 7.0）
    
    Returns:
        工單列表
    """
    print(f"\n[報告生成] 生成高風險威脅 IT 工單（風險分數 >= {risk_threshold}）...")
    
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
            a.id as asset_row_id,
            a.hostname,
            a.ip_address,
            a.owner,
            a.os_version,
            a.applications
        FROM T_Validated_Threats vt
        JOIN T_Raw_Intel ri ON vt.intel_id = ri.id
        JOIN T_Assets a ON vt.asset_id = a.id
        WHERE vt.risk_score >= ?
          AND vt.status = 'new'
        ORDER BY vt.risk_score DESC
    """
    
    df_high_risk = pd.read_sql_query(query, db_conn, params=(risk_threshold,))
    
    tickets = []
    for _, row in df_high_risk.iterrows():
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
            'applications': row['applications']
        }
        
        intel_data = {
            'cve_id': row['cve_id'],
            'title': row['title'],
            'source': row['source'],
            'cvss_score': row['cvss_score'],
            'raw_data': row['raw_data']
        }
        
        ticket = generate_it_ticket(validated_threat, asset_data, intel_data, config)
        tickets.append(ticket)
    
    print(f"[報告生成] 生成 {len(tickets)} 個 IT 工單")
    return tickets


if __name__ == "__main__":
    """主函數：生成週報"""
    db_conn = None
    try:
        config = load_config()
        db_conn = get_db_connection()
        
        if db_conn is None:
            print("錯誤：無法獲取資料庫連線。", file=sys.stderr)
            sys.exit(1)
        
        generate_weekly_report(db_conn, config)
    
    except KeyboardInterrupt:
        print("\n使用者中斷執行。", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n錯誤：執行報告生成時發生異常：{e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()
            print("\n資料庫連線已關閉。")
