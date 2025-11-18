import os
import json
import uuid
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

TAIPEI_TZ = ZoneInfo('Asia/Taipei')
BASE_DIR = os.path.dirname(__file__)
LOG_BASE = os.path.join(BASE_DIR, 'logs', 'weekly_jobs')


def _now_iso() -> str:
    return datetime.now(TAIPEI_TZ).isoformat()


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _mask_email(addr: str) -> str:
    if not addr or '@' not in addr:
        return addr or ''
    name, domain = addr.split('@', 1)
    if len(name) <= 2:
        masked = name[0] + '*'
    else:
        masked = name[0] + '*' * (len(name) - 2) + name[-1]
    return f"{masked}@{domain}"


def _logfile_path(ts: datetime) -> str:
    ym = ts.strftime('%Y%m')
    ymd = ts.strftime('%Y%m%d')
    dir_path = os.path.join(LOG_BASE, ym)
    _ensure_dir(dir_path)
    return os.path.join(dir_path, f'{ymd}.jsonl')


def start_event(metadata: Optional[Dict] = None) -> Dict:
    """
    建立一筆新的週報事件並落地到 JSONL，回傳事件字典。
    """
    ts = datetime.now(TAIPEI_TZ)
    event = {
        'id': uuid.uuid4().hex,
        'triggered_at': ts.isoformat(),
        'phase': 'scheduled',
        'status': 'running',
        'message': '',
        'report_filepath': None,
        'recipients': [],
        'email_result': None,
        'duration_ms': None,
        'updated_at': _now_iso()
    }
    if metadata:
        event.update(metadata)
    path = _logfile_path(ts)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event, ensure_ascii=False) + '\n')
    return event


def update_event(event_id: str, updates: Dict):
    """
    更新事件：採用 append-only 模式，寫入一筆帶有 event_id 的更新行。
    前端與 API 在聚合時以最後一筆為準。
    """
    ts = datetime.now(TAIPEI_TZ)
    record = {'id': event_id, 'updated_at': _now_iso()}
    record.update(updates or {})
    path = _logfile_path(ts)
    _ensure_dir(os.path.dirname(path))
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def list_recent_events(limit: int = 20) -> List[Dict]:
    """
    聚合最近 3 天檔案，彙整每個 id 的最後狀態，回傳依時間排序的前 N 筆。
    """
    out: Dict[str, Dict] = {}
    now = datetime.now(TAIPEI_TZ)
    files = []
    for delta in range(0, 3):
        day = now.fromtimestamp(now.timestamp() - delta * 86400)
        files.append(_logfile_path(day))
    for fp in files:
        if not os.path.exists(fp):
            continue
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        rec = json.loads(line.strip())
                        _id = rec.get('id')
                        if not _id:
                            continue
                        if _id not in out:
                            out[_id] = {}
                        out[_id].update(rec)
                    except Exception:
                        continue
        except Exception:
            continue
    # 轉為列表，依 triggered_at 或 updated_at 排序
    items = list(out.values())
    def _key(x):
        return x.get('triggered_at') or x.get('updated_at') or ''
    items.sort(key=_key, reverse=True)
    return items[:limit]


def mask_recipients(items: List[Dict]) -> List[Dict]:
    for it in items:
        if 'recipients' in it and isinstance(it['recipients'], list):
            it['recipients'] = [_mask_email(x) for x in it['recipients']]
    return items


