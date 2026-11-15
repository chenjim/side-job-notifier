# 兼职机会智能监控助手 side-job-notifier

[![Python](https://img.shields.io/badge/python-3.10-blue)](https://www.python.org/downloads/) [![Docker](https://img.shields.io/badge/docker-compose-2496ED)](https://docs.docker.com/compose/) [![Playwright](https://img.shields.io/badge/crawler-playwright-2EAD33)](https://playwright.dev/)

[TOC]

> 项目起源文章 <https://h89.cn/archives/486.html>

![工作流程](https://blog-chenjim.oss-cn-shanghai.aliyuncs.com/2026/260922-side-job-notifier-architecture.png-blog)

## 🎯 项目简介

盯兼职/外包平台是件很耗注意力的事：要反复刷站、要在大量无关帖里挑出值得接的那几条。这个工具把这件事全自动做掉——**定时抓取多个平台 → 去重与时间窗过滤 → 交给大模型按你的画像打分 → 只把高分机会汇总成一封邮件推给你**。

它已经不只服务 Android 方向：站点、关键词权重、值不值得推荐，全部由 `USER_PROFILE` 画像决定（真实画像放 `.env`，代码里只留示例），换方向只改画像文案，不用动抓取代码。

- **抓取**：电鸭社区、猿急送、软件项目交易网、实现网、V2EX 外包节点（5 站）
- **筛选**：入库去重（按 link）+ 时间窗（最近 3 天；无时间字段的站点取列表前 30 条兜底）
- **判断**：LLM 按画像给 0–10 分并给出推荐理由，`score >= 5` 才推
- **推送**：按分数降序取 Top 10，163 邮箱 SMTP 汇总邮件
- **存储**：全部记录存 `data/jobs.db`（SQLite 单表多站点），按发布时间保留最近 1 年
- **兜底**：LLM 批次失败发告警邮件；抓取失败保存 HTML 便于排查；全流程写日志

## 🔄 工作流程

1. **定时调度**：容器常驻，每 15 分钟做一次心跳（仅 8:00–22:00 生效），按各站点的最小抓取间隔决定这一轮抓谁：电鸭 / V2EX 3–4 小时、猿急送 1–2 小时、软件项目交易网 24 小时（不需要额外 crontab / 系统定时器）。
2. **全量抓取**：工厂模式为每个站点创建抓取器，Playwright 处理动态渲染与基础反爬；被墙站点（V2EX）走宿主机代理，国内站点与邮箱直连。V2EX 列表页被 Cloudflare 人机验证拦截（403），改抓官方 Atom 订阅源 `/feed/outsourcing.xml`（同样是最新主题，附带正文摘要）。
3. **去重 + 时间窗**：与 `data/jobs.db` 里已评估（有评分）的 link 比对，只留未评估的；再按时间窗收敛，把 LLM 调用量压到最小。
4. **LLM 打分**：按 `LLM_BATCH_SIZE`（默认 8 条）分批调用 OpenAI 兼容接口，模型返回 `score / recommend / reason`。
5. **落盘 + 推送**：解析结果先以「未评估」状态入库，评分回写后即视为已处理，下轮不再重复分析；`score >= 5` 且发布时间在最近 3 天内的，按分数降序取最多 `MAX_PUSH_PER_RUN` 条汇总成一封邮件发出。每轮结束清理超过 `RETENTION_DAYS`（默认 365 天）的记录。

## 📋 功能特性

- ✅ **多平台**：5 个兼职/外包站点，新增站点只需三步（见「添加新站点」）
- ✅ **画像驱动**：推荐口径集中在 `USER_PROFILE`，比关键词匹配更准（能识别「驻场 / 到岗」这类隐性排除项）
- ✅ **不重复打扰**：分析过的帖子入库留痕，同一帖子只判一次、只推一次
- ✅ **成本可控**：时间窗 + 位置兜底 + 批量打分，避免把整站历史帖都送进 LLM
- ✅ **异常不静默**：LLM 批次失败发告警邮件并跳过该批（不入库，下轮自动重试），不会悄悄空转
- ✅ **可排查**：`log/` 留存运行日志，`urlData/` 留存抓取失败时的 HTML 快照
- ✅ **容器化**：Docker Compose 一键部署，Playwright 依赖全在镜像里

## 🛠️ 快速开始

### 环境要求

- Docker + Docker Compose（推荐）；本地开发用 Python 3.10
- 一个可用的 SMTP 邮箱（163 等，需**授权码**而非登录密码）
- 一个 OpenAI 兼容的 LLM 接口（默认 OpenCode Go，`deepseek-v4-flash`）

### 1. 克隆项目

```bash
git clone https://github.com/chenjim/side-job-notifier
cd side-job-notifier
```

### 2. 配置密钥（`.env`）

```bash
cp .env.example .env
```

`.env` 已被 `.gitignore` 忽略，**不要把真实密钥写进 `config.py`**。变量含义：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_BASE_URL` | OpenAI 兼容接口地址 | `https://opencode.ai/zen/go/v1` |
| `LLM_API_KEY` | 接口密钥 | 必填 |
| `LLM_MODEL` | 打分模型 | `deepseek-v4-flash` |
| `LLM_BATCH_SIZE` | 每次调用分析的帖子数 | `8` |
| `LLM_TIMEOUT` | 单次调用超时（秒） | `60` |
| `SMTP_HOST` / `SMTP_PORT` | 发件服务器 | `smtp.163.com` / `465` |
| `SMTP_USER` / `SMTP_PASSWORD` | 发件账号 / 授权码 | 必填 |
| `SMTP_TO` | 收件人 | — |
| `USER_PROFILE` | 用户画像，决定「什么值得推」；**只写硬性条件与风险偏好，不要写技术栈白名单**；留空则用代码里的示例画像 | 示例画像 |
| `PROXY_URL` | 被墙站点走的宿主机代理 | `http://127.0.0.1:7890` |

### 3. 本地运行（开发调试）

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
set -a; . ./.env; set +a          # 把 .env 注入当前 shell
.venv/bin/python main.py
```

改完代码跑测试：

```bash
.venv/bin/python -m pytest tests/
```

### 4. Docker 部署（推荐）

```bash
docker compose up -d --build     # 构建并启动
docker compose logs -f           # 查看运行日志
docker compose down              # 停止并删除容器
```

启动后立即检查一遍（未到间隔的站点自动跳过，重启不会集中轰炸站点），之后每 15 分钟按各站点自己的间隔抓取（仅在 8:00–22:00 生效）。

## 🏗️ 技术架构

```
main.py                调度 + 主流程（抓取 → 去重 → 打分 → 入库 → 推送）
config.py              站点表、推荐阈值、用户画像、时间窗参数
scrapers/
  base_scraper.py      抓取基类（Playwright、HTML 调试快照、错误通知）
  *_scraper.py         各站点抓取器
  scraper_factory.py   按站点 key 创建抓取器
core/
  site_scheduler.py    站点抓取节奏判定（独立间隔、失败快速重试）
  llm_analyzer.py      批量打分（分片、重试、失败告警）
  data_manager.py      data/jobs.db（SQLite）读写、去重、保留期清理、历史 JSON 迁移
  notifier.py          SMTP 汇总邮件 / 告警邮件
  time_parser.py       发布时间解析与时间窗判定
  logger.py            统一日志
scripts/
  migrate_json_to_sqlite.py  历史 data/*.json 一次性迁移入库
```

设计要点：

- **配置驱动**：站点表与阈值在 `config.py`，密钥、地址与用户画像在 `.env`，逻辑代码不硬编码站点差异
- **抽象接口 + 工厂**：`BaseScraper` 定义统一契约，`ScraperFactory` 负责创建，加站点不改主流程
- **单库多站点**：所有解析结果落 `data/jobs.db` 的 `posts` 表，`site` 字段区分来源，`link` 为主键天然去重
- **评分即处理**：`score IS NULL` 表示已解析未评估（含上轮 LLM 失败），下轮自动重试；有评分即视为已处理，不再重复分析推送
- **时间锚点统一**：`time_ref` 优先取发布时间，缺失回落到分析时间/首次发现时间，保留期与推送时间窗都按它算

## 🔧 高级配置

### 调推荐口径

`.env`：

```bash
# 画像只写约束与风险偏好，不要写技术栈 / 行业白名单：
# LLM 只按「需求清晰度、报酬与结算、远程可行性、风险」打分，
# 写死方向反而会把能接的机会判成低分。
USER_PROFILE="15年研发，全栈，任何软件方向都能上手（有 AI 工具）；只接远程，不接受驻场/到岗/出差；必须写明报酬或预算，无报酬试稿不接；只接需求方直发的招人帖"
```

`config.py`：

```python
RECOMMEND_THRESHOLD = 5        # 推送门槛，想多收就调低
MAX_PUSH_PER_RUN = 10          # 每轮最多推送条数，防刷屏
RECENT_DAYS = 3                # 只评估/推送最近 N 天的帖子
POSITION_LIMIT = 30            # 无时间字段站点取列表前 N 条
DB_PATH = "data/jobs.db"       # 记录库路径（可用环境变量 DB_PATH 覆盖）
RETENTION_DAYS = 365           # 记录保留天数，按发布时间（缺失回落分析时间）清理
```

### 改抓取节奏

```python
# config.py
LOOP_TICK_MINUTES = 15              # 心跳：每 15 分钟问一次谁到期了
DEFAULT_FETCH_INTERVAL = (180, 240) # 没单独配置的站点：3-4 小时随机

WEBSITES = {
    "yuanjisong": {"min_interval_minutes": (60, 120), ...},  # 白天天天 1-2 小时
    "sxsoft":     {"min_interval_minutes": 1440, ...},       # 一天一次
}
```

- `min_interval_minutes` 支持整数（固定）或 `(min, max)`（区间内随机）
- 上次抓取时间存在 `data/jobs.db` 的 `site_state` 表，重启不会重置节奏
- 抓取失败按 30 分钟快速重试，不会因为一次异常白等一整天
- 可执行时段改 `main.py` 里的 `if 8 <= now.hour < 23`

### 数据存储与迁移

记录统一存 `data/jobs.db`（SQLite），常用的直查方式：

```bash
sqlite3 data/jobs.db "select site, count(*), max(time_ref) from posts group by site;"
sqlite3 data/jobs.db "select title, score from posts where score >= 5 order by time_ref desc limit 10;"
sqlite3 data/jobs.db "select site, last_fetch_at, last_status, consecutive_empty from site_state;"   # 站点抓取节奏与健康度
```

从旧版（每站一个 `data/*.json`）升级：停容器 → 备份 `data/` → `.venv/bin/python scripts/migrate_json_to_sqlite.py`（导入成功后原文件改名为 `*.json.migrated`）→ 启动容器。库文件在 `data/` 目录内，沿用原有备份策略即可。

### 添加新站点

1. `config.py` 的 `WEBSITES` 里加一条（`url` / `name` / `time_mode`：有发布时间字段用 `field`，否则用 `position`；站点 key 会自动写入库的 `site` 字段）
2. `scrapers/` 下新建抓取器类继承 `BaseScraper`，实现 `fetch_posts()`
3. 在 `scrapers/scraper_factory.py` 的 `_scrapers` 里注册（可见性靠 `scrapers/__init__.py` 导出）

## 🐛 故障排除

| 现象 | 排查方向 |
|------|----------|
| 收不到邮件 | 看 `docker compose logs -f` 里有没有「邮件发送成功」；163 用授权码不是登录密码；先翻垃圾箱 |
| 一封都不推 | 阈值 `RECOMMEND_THRESHOLD` 太高，或 `USER_PROFILE` 与在招项目不匹配；日志里能看到每站「新帖 N 条 / 时间窗内 M 条」和打分结果 |
| 某站点一直抓不到 | 站点改版，`urlData/` 里有当次的 HTML 快照，照着改选择器；同理会收到抓取失败的告警邮件 |
| LLM 报 400 MissingSessionID | OpenCode Go 要求带稳定的 `x-opencode-session` 头，代码已自动生成；换自建接口时确认 base_url 不带 `/chat/completions` |
| 改了 `.env` 不生效 | 环境变量在容器启动时注入：`docker compose up -d --force-recreate`；改 `config.py` 因 bind mount 直接生效 |
| 容器时区/权限异常 | compose 已挂载 `/etc/localtime`、`TZ=Asia/Shanghai`，并按 `${UID}:${GID}` 以宿主机用户身份运行 |

## 📄 说明

- 抓取仅针对公开列表页，请遵守目标站点 robots 与访问频率约定；各站点按 1 小时到 1 天的独立间隔抓取，属于低频访问。
- 邮件里只含标题、摘要、链接与推荐理由，不复制站点正文。

---

**⭐ 如果这个项目对你有帮助，欢迎给个 Star；有问题或建议直接开 Issue。**
