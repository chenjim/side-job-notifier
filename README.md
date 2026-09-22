# 兼职机会智能监控助手 side-job-notifier

[![Python](https://img.shields.io/badge/python-3.10-blue)](https://www.python.org/downloads/) [![Docker](https://img.shields.io/badge/docker-compose-2496ED)](https://docs.docker.com/compose/) [![Playwright](https://img.shields.io/badge/crawler-playwright-2EAD33)](https://playwright.dev/)

[TOC]

> 项目起源文章 <https://h89.cn/archives/486.html>

![工作流程](https://blog-chenjim.oss-cn-shanghai.aliyuncs.com/2026/260922-side-job-notifier-architecture.png-blog)

## 🎯 项目简介

盯兼职/外包平台是件很耗注意力的事：要反复刷站、要在大量无关帖里挑出值得接的那几条。这个工具把这件事全自动做掉——**定时抓取多个平台 → 去重与时间窗过滤 → 交给大模型按你的画像打分 → 只把高分机会汇总成一封邮件推给你**。

它已经不只服务 Android 方向：站点、关键词权重、值不值得推荐，全部由 `USER_PROFILE` 画像决定（真实画像放 `.env`，代码里只留示例），换方向只改画像文案，不用动抓取代码。

- **抓取**：电鸭社区、猿急送、软件项目交易网、实现网、V2EX 外包节点（5 站）
- **筛选**：按 link 去重 + 时间窗（最近 2 天；无时间字段的站点取列表前 30 条兜底）
- **判断**：LLM 按画像给 0–10 分并给出推荐理由，`score >= 5` 才推
- **推送**：按分数降序取 Top 10，163 邮箱 SMTP 汇总邮件
- **兜底**：LLM 批次失败发告警邮件；抓取失败保存 HTML 便于排查；全流程写日志

## 🔄 工作流程

1. **定时调度**：容器常驻，启动后立即跑一轮，之后每天 8:00–22:00 之间每 150–180 分钟随机执行一次（不需要额外 crontab / 系统定时器）。
2. **全量抓取**：工厂模式为每个站点创建抓取器，Playwright 处理动态渲染与基础反爬；被墙站点（V2EX）走宿主机代理，国内站点与邮箱直连。
3. **去重 + 时间窗**：与 `data/*.json` 里已分析过的 link 比对，只留新帖；再按时间窗收敛，把 LLM 调用量压到最小。
4. **LLM 打分**：按 `LLM_BATCH_SIZE`（默认 8 条）分批调用 OpenAI 兼容接口，模型返回 `score / recommend / reason`。
5. **落盘 + 推送**：分析成功（含低分）立即原子写入 `data/*.json`，下轮不再重复分析；`score >= 5` 的按分数降序，最多 `MAX_PUSH_PER_RUN` 条汇总成一封邮件发出。

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
| `USER_PROFILE` | 用户画像，决定「什么值得推」；留空则用代码里的示例画像 | 示例画像 |
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

启动后会立即执行一轮检查，然后按 150–180 分钟随机间隔持续监控（仅在 8:00–22:00 生效）。

## 🏗️ 技术架构

```
main.py                调度 + 主流程（抓取 → 去重 → 打分 → 入库 → 推送）
config.py              站点表、推荐阈值、用户画像、时间窗参数
scrapers/
  base_scraper.py      抓取基类（Playwright、HTML 调试快照、错误通知）
  *_scraper.py         各站点抓取器
  scraper_factory.py   按站点 key 创建抓取器
core/
  llm_analyzer.py      批量打分（分片、重试、失败告警）
  data_manager.py      data/*.json 原子读写、去重
  notifier.py          SMTP 汇总邮件 / 告警邮件
  time_parser.py       发布时间解析与时间窗判定
  logger.py            统一日志
```

设计要点：

- **配置驱动**：站点表与阈值在 `config.py`，密钥、地址与用户画像在 `.env`，逻辑代码不硬编码站点差异
- **抽象接口 + 工厂**：`BaseScraper` 定义统一契约，`ScraperFactory` 负责创建，加站点不改主流程
- **站点独立存储**：每站一个 `data/*.json`，互不干扰，可单独清理
- **失败可重入**：LLM 失败批次不入库，下一轮自然重试；分析成功才算「处理过」

## 🔧 高级配置

### 调推荐口径

`.env`：

```bash
USER_PROFILE="你的画像：技术方向 / 只接远程还是可到岗 / 明确不接的类型 / 报酬要求"
```

`config.py`：

```python
RECOMMEND_THRESHOLD = 5        # 推送门槛，想多收就调低
MAX_PUSH_PER_RUN = 10          # 每轮最多推送条数，防刷屏
RECENT_DAYS = 2                # 只分析最近 N 天的帖子
POSITION_LIMIT = 30            # 无时间字段站点取列表前 N 条
MAX_RECORDS_PER_FILE = 200     # 每站记录上限，防文件无限膨胀
```

### 改调度时间

`main.py` 末尾：`if 8 <= now.hour < 23`（可执行时段）与 `random.randint(150, 180)`（间隔分钟）。

### 添加新站点

1. `config.py` 的 `WEBSITES` 里加一条（`url` / `name` / `data_file` / `time_mode`：有发布时间字段用 `field`，否则用 `position`）
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

- 抓取仅针对公开列表页，请遵守目标站点 robots 与访问频率约定；本项目按 150–180 分钟随机间隔抓取，属于低频访问。
- 邮件里只含标题、摘要、链接与推荐理由，不复制站点正文。

---

**⭐ 如果这个项目对你有帮助，欢迎给个 Star；有问题或建议直接开 Issue。**
