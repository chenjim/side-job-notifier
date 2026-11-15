#!/usr/bin/env python3
# scripts/migrate_json_to_sqlite.py
# 历史 data/<site>_android.json → data/jobs.db 一次性迁移。
# 导入成功后原文件改名为 <file>.migrated，重复执行不会重复导入。

import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from config import DB_PATH  # noqa: E402
from core.data_manager import init_db, migrate_from_json, list_posts  # noqa: E402


def main():
    db_path = os.path.join(PROJECT_DIR, DB_PATH) if not os.path.isabs(DB_PATH) else DB_PATH
    data_dir = os.path.join(PROJECT_DIR, 'data')
    init_db(db_path)

    migrated = migrate_from_json(data_dir=data_dir, db_path=db_path)
    if not migrated:
        print("没有可迁移的 JSON 文件（可能已迁移过）。")
    for site, count in migrated.items():
        print(f"  {site}: 导入 {count} 条")

    total = len(list_posts(db_path=db_path))
    print(f"迁移完成，库中现有记录 {total} 条 → {db_path}")


if __name__ == '__main__':
    main()
