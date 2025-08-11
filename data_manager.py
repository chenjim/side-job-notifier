# data_manager.py

import json
import os
from typing import List, Dict

def load_notified_data(data_file: str) -> List[Dict[str, str]]:
    """从文件中加载已通知过的帖子数据。"""
    if not os.path.exists(data_file):
        return []
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # 如果文件为空，返回空列表
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        # 如果文件损坏或为空，返回空列表
        return []

def save_notified_data(data_file: str, posts: List[Dict[str, str]]):
    """将已通知过的帖子数据保存到文件。"""
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)