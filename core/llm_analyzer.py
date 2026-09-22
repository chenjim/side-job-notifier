# llm_analyzer.py
# 调用 OpenAI 兼容接口，按用户画像批量分析帖子并打分推荐

import json
import os
import uuid
from pathlib import Path
from typing import Dict, List

from openai import OpenAI

from config import LLM_CONFIG, USER_PROFILE, RECOMMEND_THRESHOLD
from core.logger import log_info, log_error
from core.notifier import send_alert

# 项目根目录：告警邮件里给出日志位置，避免写死本机绝对路径
PROJECT_DIR = Path(__file__).resolve().parent.parent

SYSTEM_PROMPT = (
    "你是兼职/外包项目机会筛选助手。根据用户画像，判断每个招聘/外包帖子是否值得推荐，"
    "并给出评分与理由。只输出 JSON，不要输出任何其他内容。"
)

# 用户消息模板：{profile} 用户画像，{posts} JSON 数组
USER_MSG_TEMPLATE = """用户画像：
{profile}

请分析以下每个帖子，判断是否值得推荐给该用户：

{posts}

输出格式（严格 JSON 数组，字段顺序不变）：
[
  {{"link": "帖子链接", "score": 0到10的整数, "recommend": true或false, "reason": "简短中文推荐理由，不推荐时说明原因"}}
]

要求：
1. score >= {threshold} 时 recommend 为 true
2. 帖子数量可能少于批大小，按实际数量输出
3. 必须为每个输入的帖子输出一条结果，link 一一对应"""


class LLMAnalyzer:
    """LLM 帖子推荐分析器。"""

    def __init__(self):
        api_key = os.environ.get("LLM_API_KEY") or LLM_CONFIG.get("api_key", "")
        base_url = LLM_CONFIG["base_url"].rstrip("/")
        # 防御：若用户填了完整 /chat/completions 路径，裁掉让 SDK 拼接
        if base_url.endswith("/chat/completions"):
            base_url = base_url[: -len("/chat/completions")]
        # OpenCode Go 要求每个会话带稳定的 x-opencode-session，否则 400 MissingSessionID
        default_headers = {}
        if "opencode.ai" in base_url:
            default_headers["x-opencode-session"] = os.environ.get(
                "OPENCODE_SESSION_ID"
            ) or f"side-job-notifier-{uuid.uuid4().hex[:12]}"
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=LLM_CONFIG["timeout"],
            default_headers=default_headers,
        )
        self.model = LLM_CONFIG["model"]
        self.batch_size = LLM_CONFIG.get("batch_size", 8)

    def analyze_posts(self, posts: List[Dict[str, str]]) -> List[Dict]:
        """批量分析帖子，返回每条 {link, score, recommend, reason}。

        按 batch_size 分批调用；某批失败（含 JSON 解析失败）则重试一次，
        仍失败返回空列表（该批帖子不入库，下轮自动重试）。
        若有任何批次失败，发送告警邮件避免静默空转。
        """
        results = []
        failed_batches = 0
        for i in range(0, len(posts), self.batch_size):
            batch = posts[i:i + self.batch_size]
            batch_result = self._analyze_batch_with_retry(batch)
            if batch_result is None:
                log_error(f"LLM 分析批次失败（重试后），跳过 {len(batch)} 条帖子")
                failed_batches += 1
                continue
            results.extend(batch_result)

        if failed_batches:
            try:
                send_alert(
                    f"[JobNotifier] LLM 分析异常：{failed_batches} 批失败",
                    f"<p>本轮共 <b>{len(posts)}</b> 条帖子，其中 <b>{failed_batches}</b> 批（约 {failed_batches * self.batch_size} 条）因 API错误被跳过。</p>"
                    "<p>可能原因：API key 无效、额度耗尽、网络问题或 OpenCode 会话头缺失。</p>"
                    f"<p>请检查日志：<code>{PROJECT_DIR / 'log'}/</code></p>"
                )
            except Exception as mail_err:
                log_error(f"告警邮件发送失败: {mail_err}")

        return results

    def _analyze_batch_with_retry(self, batch: List[Dict[str, str]]):
        """单批分析，失败重试一次。"""
        for attempt in (1, 2):
            try:
                return self._analyze_batch(batch)
            except Exception as e:
                log_error(f"LLM 分析批次失败(第{attempt}次): {e}")
        return None

    def _analyze_batch(self, batch: List[Dict[str, str]]) -> List[Dict]:
        """单批分析，解析 LLM 返回的 JSON。"""
        compact = [
            {"link": p["link"], "title": p.get("title", ""), "summary": p.get("summary", "")}
            for p in batch
        ]
        user_msg = USER_MSG_TEMPLATE.format(
            profile=USER_PROFILE,
            posts=json.dumps(compact, ensure_ascii=False),
            threshold=RECOMMEND_THRESHOLD,
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        results = self._parse_json(content)

        # 校验与补全：确保与输入一一对应
        link_map = {r.get("link"): r for r in results}
        validated = []
        for p in batch:
            r = link_map.get(p["link"]) or {}
            validated.append({
                "link": p["link"],
                "score": int(r.get("score", 0)),
                "recommend": bool(r.get("recommend", False)),
                "reason": r.get("reason", ""),
            })
        return validated

    @staticmethod
    def _parse_json(content: str) -> List[Dict]:
        """解析 LLM 输出，容忍 markdown 代码块包裹。"""
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
