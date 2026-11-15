# data_manager.py
# 解析后的帖子记录统一落 SQLite（默认 data/jobs.db），替代原先每站一个 data/*.json。
#
# 记录语义（去重口径）：
#   score IS NULL  —— 已解析入库、尚未完成 LLM 评估；下轮可重试（含 LLM 失败批次）
#   score NOT NULL —— 已评估过，不再重复分析、不再重复推送
#
# 时间口径 time_ref：published_at 解析成功用发布时间；否则用 analyzed_at；再否则用 first_seen_at。
# 保留期清理与推送时间窗都以 time_ref 为准，规避各站时间格式混杂（ISO / 点分隔 / 空值）。

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from config import DB_PATH, RETENTION_DAYS
from core.time_parser import TS_FMT, parse_published_at

_INSERT_BATCH = 500  # SQLite 单条语句的变量上限是 999

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    link          TEXT PRIMARY KEY,        -- 归一化后的帖子链接，天然去重
    site          TEXT NOT NULL,           -- 站点 key：eleduck / yuanjisong / sxsoft / v2ex ...
    title         TEXT,
    summary       TEXT,
    published_at  TEXT,                    -- 站点原始发布时间文本，可能为空
    first_seen_at TEXT NOT NULL,           -- 首次解析到的时间
    analyzed_at   TEXT,                    -- LLM 评估时间，NULL 表示未评估
    time_ref      TEXT NOT NULL,           -- 保留/推送的时间锚点（见文件头）
    score         INTEGER,
    recommend     INTEGER,                 -- 0/1
    reason        TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_time_ref ON posts(time_ref);
CREATE INDEX IF NOT EXISTS idx_posts_site ON posts(site, analyzed_at);

CREATE TABLE IF NOT EXISTS site_state (
    site              TEXT PRIMARY KEY,   -- 站点 key
    last_fetch_at     TEXT,               -- 上次抓取时间（未到间隔不抓）
    last_status       TEXT,               -- ok / error
    last_new_count    INTEGER,            -- 上次解析到的未评估条数
    consecutive_empty INTEGER NOT NULL DEFAULT 0,  -- 连续 0 新帖次数（站点健康度）
    updated_at        TEXT
);
"""


def _now_ts() -> str:
    return datetime.now().strftime(TS_FMT)


def _to_ts(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime(TS_FMT) if dt else None


def _time_ref(published_at: str, fallback: str) -> str:
    """发布时间可用则用发布时间，否则回落到调用方给出的时间（分析时间/首次发现时间）。"""
    if (published_at or '').strip():
        # 相对时间（如「1 年多前发布」）解析失败属正常，静默回落
        parsed = _to_ts(parse_published_at(published_at, quiet=True))
        if parsed:
            return parsed
    return fallback


@contextmanager
def _connect(db_path: Optional[str] = None):
    """短连接：用完即关，建表幂等。单进程串行写，无并发压力。"""
    path = db_path or DB_PATH
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None):
    """建库建表（幂等），启动时调用一次。"""
    with _connect(db_path):
        pass


def get_evaluated_links(site: str, db_path: Optional[str] = None) -> Set[str]:
    """返回该站点已评估（有评分）的 link 集合，用于去重。"""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT link FROM posts WHERE site = ? AND score IS NOT NULL", (site,)
        ).fetchall()
    return {row['link'] for row in rows}


def _fetch_pending(conn, site: str, links: List[str]) -> List[Dict]:
    """按 link 批量取出「未评估」记录（含上轮 LLM 失败、需要重试的）。"""
    pending: List[Dict] = []
    for i in range(0, len(links), _INSERT_BATCH):
        chunk = links[i:i + _INSERT_BATCH]
        placeholders = ','.join('?' * len(chunk))
        sql = (f"SELECT * FROM posts WHERE site = ? AND score IS NULL "
               f"AND link IN ({placeholders})")
        pending.extend(dict(row) for row in conn.execute(sql, (site, *chunk)))
    return pending


def upsert_parsed_posts(site: str, posts: List[Dict], db_path: Optional[str] = None) -> List[Dict]:
    """把解析结果写入库（已存在的 link 不覆盖），返回其中仍待评估的记录。

    Returns:
        List[Dict]: 这些 link 中 score IS NULL 的记录，供 LLM 分析使用
    """
    now = _now_ts()
    links: List[str] = []
    with _connect(db_path) as conn:
        for post in posts:
            link = (post.get('link') or '').strip()
            if not link:
                continue
            published_at = post.get('published_at') or ''
            conn.execute(
                """INSERT OR IGNORE INTO posts
                   (link, site, title, summary, published_at, first_seen_at, time_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (link, site, post.get('title') or '', post.get('summary') or '',
                 published_at, now, _time_ref(published_at, now))
            )
            links.append(link)
        if not links:
            return []
        return _fetch_pending(conn, site, links)


def save_analyzed_posts(site: str, records: List[Dict], db_path: Optional[str] = None) -> int:
    """写入 LLM 评估结果（有评分即「已处理」），返回写入条数。"""
    if not records:
        return 0
    now = _now_ts()
    with _connect(db_path) as conn:
        for record in records:
            link = (record.get('link') or '').strip()
            if not link:
                continue
            published_at = record.get('published_at') or ''
            analyzed_at = record.get('analyzed_at') or now
            conn.execute(
                """INSERT INTO posts
                   (link, site, title, summary, published_at, first_seen_at, analyzed_at,
                    time_ref, score, recommend, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(link) DO UPDATE SET
                     title = excluded.title,
                     summary = excluded.summary,
                     published_at = excluded.published_at,
                     analyzed_at = excluded.analyzed_at,
                     time_ref = excluded.time_ref,
                     score = excluded.score,
                     recommend = excluded.recommend,
                     reason = excluded.reason""",
                (link, site, record.get('title') or '', record.get('summary') or '',
                 published_at, analyzed_at, analyzed_at,
                 _time_ref(published_at, analyzed_at),
                 record.get('score'), 1 if record.get('recommend') else 0,
                 record.get('reason') or '')
            )
    return len(records)


def get_site_state(site: str, db_path: Optional[str] = None) -> Dict:
    """读取站点抓取状态；没有记录时返回空字典。"""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM site_state WHERE site = ?", (site,)).fetchone()
    return dict(row) if row else {}


def mark_site_fetched(site: str, new_count: int, status: str = 'ok',
                      db_path: Optional[str] = None) -> int:
    """记录一次抓取结果，返回连续 0 新帖的次数（站点健康度用）。"""
    now = _now_ts()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT consecutive_empty FROM site_state WHERE site = ?", (site,)
        ).fetchone()
        empty = 0 if new_count > 0 else ((row['consecutive_empty'] if row else 0) + 1)
        conn.execute(
            """INSERT INTO site_state
               (site, last_fetch_at, last_status, last_new_count, consecutive_empty, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(site) DO UPDATE SET
                 last_fetch_at = excluded.last_fetch_at,
                 last_status = excluded.last_status,
                 last_new_count = excluded.last_new_count,
                 consecutive_empty = excluded.consecutive_empty,
                 updated_at = excluded.updated_at""",
            (site, now, status, new_count, empty, now)
        )
    return empty


def purge_old_records(days: int = RETENTION_DAYS, db_path: Optional[str] = None) -> int:
    """删除 time_ref 早于 days 天的记录，返回删除条数。"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime(TS_FMT)
    with _connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM posts WHERE time_ref < ?", (cutoff,))
        return cursor.rowcount


def list_posts(site: Optional[str] = None, days: Optional[int] = None,
               limit: Optional[int] = None, db_path: Optional[str] = None) -> List[Dict]:
    """查询记录（排查/统计用），按 time_ref 降序；recommend 转为 bool。"""
    sql = "SELECT * FROM posts WHERE 1 = 1"
    params: List = []
    if site:
        sql += " AND site = ?"
        params.append(site)
    if days:
        sql += " AND time_ref >= ?"
        params.append((datetime.now() - timedelta(days=days)).strftime(TS_FMT))
    sql += " ORDER BY time_ref DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with _connect(db_path) as conn:
        rows = [dict(row) for row in conn.execute(sql, params)]
    for row in rows:
        if row.get('recommend') is not None:
            row['recommend'] = bool(row['recommend'])
    return rows


def migrate_from_json(data_dir: str = 'data', suffix: str = '.migrated',
                      db_path: Optional[str] = None) -> Dict[str, int]:
    """把历史 data/<site>_android.json 一次性导入库，成功后改名为 <file>.migrated。

    旧数据里少数记录没有 score/analyzed_at（历史版本留下的未评估行），
    这类记录用文件修改时间兜底，避免被当成「今天的新帖」。

    Returns:
        Dict[str, int]: {站点 key: 导入条数}
    """
    migrated: Dict[str, int] = {}
    if not os.path.isdir(data_dir):
        return migrated
    for name in sorted(os.listdir(data_dir)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(data_dir, name)
        site = name[:-len('.json')].split('_')[0]
        try:
            with open(path, 'r', encoding='utf-8') as f:
                posts = json.load(f) or []
        except (json.JSONDecodeError, IOError):
            continue
        fallback_ts = datetime.fromtimestamp(os.path.getmtime(path)).strftime(TS_FMT)
        evaluated: Dict[str, Dict] = {}
        unevaluated: Dict[str, Dict] = {}
        for post in posts:
            if not isinstance(post, dict) or not (post.get('link') or '').strip():
                continue
            link = post['link'].strip()
            if post.get('score') is None:
                unevaluated[link] = post
            else:
                evaluated[link] = {**post, 'analyzed_at': post.get('analyzed_at') or fallback_ts}

        saved = save_analyzed_posts(site, list(evaluated.values()), db_path=db_path)
        saved += _insert_unevaluated(site, list(unevaluated.values()), fallback_ts, db_path)
        migrated[site] = saved
        os.replace(path, path + suffix)
    return migrated


def _insert_unevaluated(site: str, records: List[Dict], fallback_ts: str,
                        db_path: Optional[str]) -> int:
    """历史遗留的未评估行（无 score）按原样入库，时间锚点回落到文件时间。"""
    saved = 0
    if not records:
        return saved
    with _connect(db_path) as conn:
        for record in records:
            link = (record.get('link') or '').strip()
            published_at = record.get('published_at') or ''
            cursor = conn.execute(
                """INSERT OR IGNORE INTO posts
                   (link, site, title, summary, published_at, first_seen_at, time_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (link, site, record.get('title') or '', record.get('summary') or '',
                 published_at, fallback_ts, _time_ref(published_at, fallback_ts))
            )
            saved += cursor.rowcount
    return saved

