# config.py

# 网站配置
WEBSITES = {
    "eleduck": {
        "url": "https://eleduck.com/",
        "keywords": ["android", "安卓","想找人帮我完成"],
        "data_file": "data/eleduck_android.json",
        "name": "电鸭社区"
    },
    "yuanjisong": {
        "url": "https://www.yuanjisong.com/job/allcity/android/zxfb",
        "keywords": [""],
        "data_file": "data/yuanjisong_android.json",
        "name": "猿急送"
    },
    "sxsoft": {
        "url": "https://www.sxsoft.com/page/project",
        "keywords": [""],
        "data_file": "data/sxsoft_android.json",
        "name": "软件项目交易网"
    },
    "shixian": {
        "url": "https://shixian.com/job/all/android?filter=last",
        "keywords": [""],
        "data_file": "data/shixian_android.json",
        "name": "软件项目交易网"
    }
}

# 为了向后兼容，保留原有变量
TARGET_URL = WEBSITES["eleduck"]["url"]
KEYWORDS = WEBSITES["eleduck"]["keywords"]
DATA_FILE = WEBSITES["eleduck"]["data_file"]

# 收件人邮箱
RECIPIENT_EMAIL = "h89_cn@163.com"

# 发件人邮箱配置 (请务必修改为你自己的)
SENDER_EMAIL = "h89_cn@163.com"  # 例如: "abc@163.com"
SENDER_PASSWORD = "ABCDEFGHIJKLMN"  # 注意：为了安全，推荐使用授权码
SMTP_SERVER = "smtp.163.com" # 根据你的邮箱服务商修改
SMTP_PORT = 465 # 根据你的邮箱服务商修改