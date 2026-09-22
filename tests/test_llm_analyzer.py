# tests/test_llm_analyzer.py

import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

sys.path.insert(0, '.')
from core.time_parser import parse_published_at, is_recent
from core.llm_analyzer import LLMAnalyzer


class TestTimeParser(unittest.TestCase):
    def test_iso8601(self):
        dt = parse_published_at('2025-08-11T14:14:03.701+08:00')
        self.assertIsNotNone(dt)
        self.assertEqual(dt.hour, 14)

    def test_date_dot(self):
        dt = parse_published_at('2025.08.17')
        self.assertEqual(dt.strftime('%Y-%m-%d'), '2025-08-17')

    def test_relative(self):
        dt = parse_published_at('3小时前')
        self.assertAlmostEqual((datetime.now() - dt).total_seconds(), 3 * 3600, delta=60)
        dt = parse_published_at('昨天')
        self.assertIsNotNone(dt)
        dt = parse_published_at('17 天前发布')
        self.assertAlmostEqual((datetime.now() - dt).total_seconds(), 17 * 86400, delta=60)
        dt = parse_published_at('大约 2 个月前发布')
        self.assertAlmostEqual((datetime.now() - dt).total_seconds(), 2 * 30 * 86400, delta=60)

    def test_invalid(self):
        self.assertIsNone(parse_published_at('Job ID: 158371'))
        self.assertIsNone(parse_published_at(''))
        self.assertIsNone(parse_published_at(None))

    def test_is_recent(self):
        recent = (datetime.now() - timedelta(hours=10)).strftime('%Y-%m-%dT%H:%M:%S')
        self.assertTrue(is_recent(recent, days=2))
        old = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%dT%H:%M:%S')
        self.assertFalse(is_recent(old, days=2))
        self.assertFalse(is_recent('无法解析', days=2))


class TestLLMAnalyzer(unittest.TestCase):
    def _make_analyzer(self, content):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = content
        mock_client.chat.completions.create.return_value = mock_resp
        analyzer = LLMAnalyzer.__new__(LLMAnalyzer)
        analyzer.client = mock_client
        analyzer.model = 'test-model'
        analyzer.batch_size = 8
        return analyzer

    def test_parse_json_array(self):
        posts = [
            {'link': 'http://a', 'title': 't1', 'summary': 's1'},
            {'link': 'http://b', 'title': 't2', 'summary': 's2'},
        ]
        content = '[{"link": "http://a", "score": 9, "recommend": true, "reason": "匹配"}, {"link": "http://b", "score": 2, "recommend": false, "reason": "不相关"}]'
        analyzer = self._make_analyzer(content)
        results = analyzer._analyze_batch(posts)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['score'], 9)
        self.assertTrue(results[0]['recommend'])
        self.assertFalse(results[1]['recommend'])

    def test_parse_markdown_wrapped(self):
        content = '```json\n[{"link": "http://a", "score": 8, "recommend": true, "reason": "ok"}]\n```'
        analyzer = self._make_analyzer(content)
        self.assertEqual(analyzer._parse_json(content)[0]['score'], 8)

    def test_missing_entry_filled(self):
        posts = [{'link': 'http://a', 'title': 't1', 'summary': 's1'}]
        content = '[]'
        analyzer = self._make_analyzer(content)
        results = analyzer._analyze_batch(posts)
        self.assertEqual(results[0]['score'], 0)
        self.assertFalse(results[0]['recommend'])

    def test_retry_then_fail(self):
        analyzer = LLMAnalyzer.__new__(LLMAnalyzer)
        analyzer.client = MagicMock()
        analyzer.client.chat.completions.create.side_effect = Exception('network error')
        analyzer.model = 'test-model'
        analyzer.batch_size = 8
        result = analyzer._analyze_batch_with_retry([{'link': 'http://a'}])
        self.assertIsNone(result)
        self.assertEqual(analyzer.client.chat.completions.create.call_count, 2)


if __name__ == '__main__':
    unittest.main()
