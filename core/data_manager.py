# data_manager.py

import json
import os
import tempfile
from typing import List, Dict

from config import MAX_RECORDS_PER_FILE

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
    """将已通知过的帖子数据保存到文件。

    超过 MAX_RECORDS_PER_FILE 时截断保留最近记录（记录按发现顺序追加，末尾最新），
    防止文件无限膨胀。使用临时文件 + 原子替换，避免写入中途异常导致文件损坏。
    """
    if MAX_RECORDS_PER_FILE and len(posts) > MAX_RECORDS_PER_FILE:
        posts = posts[-MAX_RECORDS_PER_FILE:]

    os.makedirs(os.path.dirname(data_file), exist_ok=True)
    dir_path, filename = os.path.split(data_file)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, prefix=filename + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(posts, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, data_file)
    except Exception:
        # 写入失败时清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
