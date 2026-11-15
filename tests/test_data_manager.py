# tests/test_data_manager.py

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, '.')
from core.data_manager import (get_evaluated_links, get_site_state, init_db,
                               list_posts, mark_site_fetched, migrate_from_json,
                               purge_old_records, save_analyzed_posts,
                               upsert_parsed_posts)


def ts(days_ago: int = 0) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')


class TestDataManager(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "jobs.db")
        init_db(self.db)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def _post(self, link: str, published_at: str = "", title: str = "t") -> dict:
        return {"link": link, "title": title, "summary": "s", "published_at": published_at}

    def _analyze(self, link: str, score: int = 7, recommend: bool = True,
                 published_at: str = "") -> dict:
        return {"link": link, "title": "t", "summary": "s", "published_at": published_at,
                "score": score, "recommend": recommend, "reason": "r", "analyzed_at": ts()}

    def test_init_creates_db(self):
        self.assertTrue(os.path.exists(self.db))
        self.assertEqual(list_posts(db_path=self.db), [])

    def test_insert_then_score_roundtrip(self):
        pending = upsert_parsed_posts("s1", [self._post("http://x/1", ts(1))], db_path=self.db)
        self.assertEqual([p['link'] for p in pending], ["http://x/1"])
        self.assertEqual(get_evaluated_links("s1", db_path=self.db), set())

        save_analyzed_posts("s1", [self._analyze("http://x/1", 8, True, ts(1))], db_path=self.db)
        rows = list_posts(db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['score'], 8)
        self.assertIs(rows[0]['recommend'], True)
        self.assertEqual(get_evaluated_links("s1", db_path=self.db), {"http://x/1"})
        # 评估过的不会再被当成待分析
        self.assertEqual(upsert_parsed_posts("s1", [self._post("http://x/1", ts(1))], db_path=self.db), [])

    def test_duplicate_link_keeps_first(self):
        upsert_parsed_posts("s1", [self._post("http://x/1", ts(1), "first")], db_path=self.db)
        first_seen = list_posts(db_path=self.db)[0]['first_seen_at']
        upsert_parsed_posts("s1", [self._post("http://x/1", ts(0), "second")], db_path=self.db)
        rows = list_posts(db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['title'], "first")
        self.assertEqual(rows[0]['first_seen_at'], first_seen)

    def test_site_isolation(self):
        upsert_parsed_posts("s1", [self._post("http://x/1")], db_path=self.db)
        upsert_parsed_posts("s2", [self._post("http://x/2")], db_path=self.db)
        self.assertEqual(get_evaluated_links("s1", db_path=self.db), set())
        save_analyzed_posts("s1", [self._analyze("http://x/1")], db_path=self.db)
        self.assertEqual(get_evaluated_links("s1", db_path=self.db), {"http://x/1"})
        self.assertEqual(get_evaluated_links("s2", db_path=self.db), set())
        self.assertEqual(len(list_posts(site="s2", db_path=self.db)), 1)

    def test_time_ref_falls_back(self):
        # 无发布时间：入库用首次发现时间，评估后用分析时间
        upsert_parsed_posts("s1", [self._post("http://x/1")], db_path=self.db)
        ref_before = list_posts(db_path=self.db)[0]['time_ref']
        self.assertEqual(ref_before, list_posts(db_path=self.db)[0]['first_seen_at'])
        save_analyzed_posts("s1", [self._analyze("http://x/1")], db_path=self.db)
        row = list_posts(db_path=self.db)[0]
        self.assertEqual(row['time_ref'], row['analyzed_at'])

    def test_time_ref_uses_published_at(self):
        upsert_parsed_posts("s1", [self._post("http://x/1", ts(5))], db_path=self.db)
        self.assertEqual(list_posts(db_path=self.db)[0]['time_ref'], ts(5))

    def test_purge_old_records(self):
        upsert_parsed_posts("s1", [self._post("http://x/old", ts(400)),
                                   self._post("http://x/new", ts(10))], db_path=self.db)
        deleted = purge_old_records(365, db_path=self.db)
        self.assertEqual(deleted, 1)
        self.assertEqual([r['link'] for r in list_posts(db_path=self.db)], ["http://x/new"])

    def test_purge_keeps_record_without_date_when_fresh(self):
        # 无发布时间的老记录用分析时间兜底，不会被误删
        upsert_parsed_posts("s1", [self._post("http://x/1")], db_path=self.db)
        save_analyzed_posts("s1", [self._analyze("http://x/1")], db_path=self.db)
        self.assertEqual(purge_old_records(365, db_path=self.db), 0)
        self.assertEqual(len(list_posts(db_path=self.db)), 1)

    def test_site_state_tracks_fetch_and_empty_streak(self):
        self.assertEqual(get_site_state("s1", db_path=self.db), {})

        self.assertEqual(mark_site_fetched("s1", 3, db_path=self.db), 0)
        state = get_site_state("s1", db_path=self.db)
        self.assertEqual(state['last_status'], 'ok')
        self.assertEqual(state['last_new_count'], 3)
        self.assertEqual(state['consecutive_empty'], 0)
        self.assertIsNotNone(state['last_fetch_at'])

        # 连续 0 新帖累加，有帖则清零
        self.assertEqual(mark_site_fetched("s1", 0, db_path=self.db), 1)
        self.assertEqual(mark_site_fetched("s1", 0, db_path=self.db), 2)
        self.assertEqual(mark_site_fetched("s1", 2, db_path=self.db), 0)

        # 失败也要刷新时间与状态，避免按整天间隔干等
        mark_site_fetched("s1", 0, status='error', db_path=self.db)
        state = get_site_state("s1", db_path=self.db)
        self.assertEqual(state['last_status'], 'error')
        self.assertEqual(state['consecutive_empty'], 1)

    def test_migrate_from_json(self):
        data_dir = os.path.join(self.dir, "data")
        os.makedirs(data_dir)
        posts = [self._analyze("http://x/1", 9), self._analyze("http://x/1", 3),
                 self._analyze("http://x/2", 5), {"link": "http://x/3", "title": "t"}]
        json_path = os.path.join(data_dir, "site1_android.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False)
        # 模拟旧文件：把修改时间回拨 30 天，未评估行的兜底时间应取自它
        old = (datetime.now() - timedelta(days=30)).timestamp()
        os.utime(json_path, (old, old))
        with open(os.path.join(data_dir, ".gitkeep"), "w", encoding="utf-8") as f:
            f.write("")

        migrated = migrate_from_json(data_dir=data_dir, db_path=self.db)
        self.assertEqual(migrated, {"site1": 3})
        rows = list_posts(site="site1", db_path=self.db)
        self.assertEqual(len(rows), 3)
        # 历史遗留的未评估行不会被当成「今天的新帖」
        legacy = [r for r in rows if r['link'] == "http://x/3"][0]
        self.assertIsNone(legacy['score'])
        self.assertEqual(legacy['time_ref'][:10], (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        self.assertFalse(os.path.exists(os.path.join(data_dir, "site1_android.json")))
        self.assertTrue(os.path.exists(os.path.join(data_dir, "site1_android.json.migrated")))
        # 二次执行不重复导入
        self.assertEqual(migrate_from_json(data_dir=data_dir, db_path=self.db), {})


if __name__ == '__main__':
    unittest.main()
