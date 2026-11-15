# config.py

import os

# 网站配置
WEBSITES = {
    "eleduck": {
        "url": "https://eleduck.com/",
        "keywords": [""],
        "name": "电鸭社区",
        # 时间窗模式: field=按发布时间字段过滤, position=按列表前N条兜底
        "time_mode": "field"
    },
    "yuanjisong": {
        "url": "https://www.yuanjisong.com/job/allcity/zxfb",
        "keywords": [""],
        "name": "猿急送",
        "time_mode": "position",
        # 白天 1-2 小时一次（区间随机），调度心跳到点才抓
        "min_interval_minutes": (60, 120)
    },
    "sxsoft": {
        "url": "https://www.sxsoft.com/page/project",
        "keywords": [""],
        "name": "软件项目交易网",
        # 发布时间大多为空，按列表位置兜底（列表按发布倒序）
        "time_mode": "position",
        # 站点每周才 1 条左右新项目，一天一次足够
        "min_interval_minutes": 1440
    },
    # 实现网(shixian)已停抓：2026-10-01 站点证书过期(SSL CERTIFICATE_VERIFY_FAILED)，恢复后可解注释
    # "shixian": {
    #     "url": "https://shixian.com/job/all/all?filter=last",
    #     "keywords": [""],
    #     "name": "实现网",
    #     "time_mode": "field"
    # },
    "v2ex": {
        # 列表页 /go/outsourcing 被 Cloudflare 人机验证拦截（403），改抓官方 Atom 订阅源
        "url": "https://www.v2ex.com/feed/outsourcing.xml",
        "keywords": [""],
        "name": "V2EX 外包节点",
        # 订阅源带精确发布时间（Atom published，UTC ISO 格式），按时间窗过滤
        "time_mode": "field"
    }
}

# 为了向后兼容，保留原有变量
TARGET_URL = WEBSITES["eleduck"]["url"]
KEYWORDS = WEBSITES["eleduck"]["keywords"]

# ============ 存储配置 ============
# 解析后的帖子记录统一入库（单表多站点），替代原先每站一个 data/*.json
DB_PATH = os.environ.get("DB_PATH", "data/jobs.db")
RETENTION_DAYS = 365  # 记录保留天数，按 time_ref（发布时间→分析时间→首次发现时间）清理

# ============ LLM 推荐配置 ============
# 用户画像：LLM 据此判断帖子是否值得推荐（本工具定位：兼职/外包机会监控）
# 真实画像放 .env 的 USER_PROFILE（勿写入本文件）；下面是未配置时的示例
DEFAULT_USER_PROFILE = (
    "多年软件开发经验，全栈交付背景，不限技术栈与软件方向（有 AI 工具加持，任何软件方向都能上手）；"
    "只接远程兼职/外包，不考虑驻场、到岗、驻厂、长期出差；"
    "必须写明报酬或预算范围，无报酬试稿、先免费出方案再谈钱的一律不接；"
    "只考虑需求方（甲方）直发的招人/发单帖，同行自荐接单的广告帖不考虑。"
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
RECENT_DAYS = 3           # 只评估/推送最近 N 天内发布的帖子（时间锚点见 data_manager.time_ref）
POSITION_LIMIT = 30       # 无时间字段站点，取列表前 N 条兜底

# ============ 抓取节奏 ============
# 调度心跳：每 N 分钟问一次「哪些站点到期了」，到期才抓。
# 各站点用 WEBSITES 里的 min_interval_minutes 决定自己的频率，没配的按 DEFAULT_FETCH_INTERVAL。
LOOP_TICK_MINUTES = 15
DEFAULT_FETCH_INTERVAL = (180, 240)  # 默认 3-4 小时随机（电鸭 / V2EX）

# 邮件配置：全部从环境变量读取（真实值放 .env，勿写入本文件）
RECIPIENT_EMAIL = os.environ.get("SMTP_TO", "")        # 收件人（在 .env 里配置）
SENDER_EMAIL = os.environ.get("SMTP_USER", "")         # 发件人（在 .env 里配置）
SENDER_PASSWORD = os.environ.get("SMTP_PASSWORD", "")                # 发件人授权码
SMTP_SERVER = os.environ.get("SMTP_HOST", "smtp.163.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))