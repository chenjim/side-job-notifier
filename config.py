# config.py

import os

# 网站配置
WEBSITES = {
    "eleduck": {
        "url": "https://eleduck.com/",
        "keywords": [""],
        "data_file": "data/eleduck_android.json",
        "name": "电鸭社区",
        # 时间窗模式: field=按发布时间字段过滤, position=按列表前N条兜底
        "time_mode": "field"
    },
    "yuanjisong": {
        "url": "https://www.yuanjisong.com/job/allcity/zxfb",
        "keywords": [""],
        "data_file": "data/yuanjisong_android.json",
        "name": "猿急送",
        "time_mode": "position"
    },
    "sxsoft": {
        "url": "https://www.sxsoft.com/page/project",
        "keywords": [""],
        "data_file": "data/sxsoft_android.json",
        "name": "软件项目交易网",
        # 发布时间大多为空，按列表位置兜底（列表按发布倒序）
        "time_mode": "position"
    },
    "shixian": {
        "url": "https://shixian.com/job/all/all?filter=last",
        "keywords": [""],
        "data_file": "data/shixian_android.json",
        "name": "实现网",
        # 有"X天前发布"时间字段，按时间窗过滤
        "time_mode": "field"
    },
    "v2ex": {
        "url": "https://www.v2ex.com/go/outsourcing",
        "keywords": [""],
        "data_file": "data/v2ex_android.json",
        "name": "V2EX 外包节点",
        # 有精确发布时间（span[title] ISO 格式），按时间窗过滤
        "time_mode": "field"
    }
}

# 为了向后兼容，保留原有变量
TARGET_URL = WEBSITES["eleduck"]["url"]
KEYWORDS = WEBSITES["eleduck"]["keywords"]
DATA_FILE = WEBSITES["eleduck"]["data_file"]

# ============ LLM 推荐配置 ============
# 用户画像：LLM 据此判断帖子是否值得推荐（本工具定位：兼职/外包机会监控）
# 真实画像放 .env 的 USER_PROFILE（勿写入本文件）；下面是未配置时的示例
DEFAULT_USER_PROFILE = (
    "多年软件开发经验，移动端/后端/全栈出身；"
    "不做 iOS 相关；"
    "只接远程兼职/外包，不考虑驻场、到岗、驻厂项目；"
    "外包项目优先移动端、后端、全栈类，技术栈不限但需明确报酬。"
)
USER_PROFILE = os.environ.get("USER_PROFILE", "").strip() or DEFAULT_USER_PROFILE

# OpenAI 兼容接口配置：全部从环境变量读取（真实值放 .env，勿写入本文件）
LLM_CONFIG = {
    "base_url": os.environ.get("LLM_BASE_URL", "https://opencode.ai/zen/go/v1"),
    "api_key": os.environ.get("LLM_API_KEY", ""),
    "model": os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
    "batch_size": int(os.environ.get("LLM_BATCH_SIZE", "8")),   # 每次 LLM 调用分析的帖子数
    "timeout": int(os.environ.get("LLM_TIMEOUT", "60")),
}

RECOMMEND_THRESHOLD = 5   # 评分 >= 该值才推送
MAX_PUSH_PER_RUN = 10     # 每轮最多推送条数，防刷屏
RECENT_DAYS = 2           # 只分析最近 N 天内发布的帖子
POSITION_LIMIT = 30       # 无时间字段站点，取列表前 N 条兜底
MAX_RECORDS_PER_FILE = 200  # 每个 data 文件最多保留记录数（防无限膨胀），None 表示不限制

# 邮件配置：全部从环境变量读取（真实值放 .env，勿写入本文件）
RECIPIENT_EMAIL = os.environ.get("SMTP_TO", "")        # 收件人（在 .env 里配置）
SENDER_EMAIL = os.environ.get("SMTP_USER", "")         # 发件人（在 .env 里配置）
SENDER_PASSWORD = os.environ.get("SMTP_PASSWORD", "")                # 发件人授权码
SMTP_SERVER = os.environ.get("SMTP_HOST", "smtp.163.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))