# tests/test_data_manager.py

import sys
import os
import tempfile
import unittest

sys.path.insert(0, '.')
from core.data_manager import save_notified_data, load_notified_data


class TestDataManager(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.file = os.path.join(self.dir, "test.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_save_and_load_roundtrip(self):
        posts = [{"link": f"http://x/{i}", "title": f"t{i}"} for i in range(5)]
        save_notified_data(self.file, posts)
        loaded = load_notified_data(self.file)
        self.assertEqual(loaded, posts)

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_notified_data(os.path.join(self.dir, "nope.json")), [])

    def test_atomic_write_no_tmp_left(self):
        save_notified_data(self.file, [{"link": "a"}])
        leftovers = [f for f in os.listdir(self.dir) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])


if __name__ == '__main__':
    unittest.main()
