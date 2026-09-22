# main.py
# 流程: 全量抓取 → link去重 → 时间窗过滤 → LLM批量分析打分 → 入库 → 评分排序限流推送汇总邮件

import schedule
import time
import sys
import random
from datetime import datetime
from config import WEBSITES, RECOMMEND_THRESHOLD, MAX_PUSH_PER_RUN, RECENT_DAYS, POSITION_LIMIT
from core.data_manager import load_notified_data, save_notified_data
from scrapers.scraper_factory import ScraperFactory
from core.llm_analyzer import LLMAnalyzer
from core.notifier import send_recommendation_batch
from core.logger import log_info, log_error, log_warning
from core.time_parser import is_recent

def fetch_and_collect(analyzer: LLMAnalyzer) -> dict:
    """抓取所有站点，去重 + 时间窗过滤，返回 {site_key: [新帖列表]}。"""
    pending = {}
    for site_key, site_config in WEBSITES.items():
        log_info(f"开始检查 {site_config['name']} ({site_config['url']})...")
        try:
            scraper = ScraperFactory.create_scraper(site_key, site_config)
            notified_posts = load_notified_data(site_config['data_file'])
            notified_links = {post['link'] for post in notified_posts}

            all_posts = scraper.fetch_posts()
            new_posts = [p for p in all_posts if p['link'] not in notified_links]

            # 时间窗过滤：只保留最近发布的新帖（降低 LLM 成本）
            time_mode = site_config.get('time_mode', 'field')
            recent_posts = []
            if time_mode == 'position':
                # 列表页按最新发布倒序，取前 N 条兜底
                recent_posts = new_posts[:POSITION_LIMIT]
                log_info(f"  {site_config['name']}: 新帖 {len(new_posts)} 条，位置兜底取前 {len(recent_posts)} 条")
            else:
                for p in new_posts:
                    if is_recent(p.get('published_at', ''), RECENT_DAYS):
                        recent_posts.append(p)
                log_info(f"  {site_config['name']}: 新帖 {len(new_posts)} 条，时间窗内 {len(recent_posts)} 条")

            if recent_posts:
                pending[site_key] = recent_posts
        except Exception as e:
            log_error(f"  {site_config['name']}: 抓取/过滤时发生错误: {e}")
            continue
    return pending

def analyze_and_store(analyzer: LLMAnalyzer, pending: dict) -> list:
    """批量 LLM 分析，成功的结果入库（防重复分析），返回推荐列表（按评分降序）。"""
    recommendations = []
    for site_key, new_posts in pending.items():
        site_config = WEBSITES[site_key]
        notified_posts = load_notified_data(site_config['data_file'])
        existing_links = {p['link'] for p in notified_posts}

        # 仅分析本文件内尚未入库的帖子（分析成功的立即入库）
        to_analyze = [p for p in new_posts if p['link'] not in existing_links]
        if not to_analyze:
            continue

        log_info(f"  {site_config['name']}: 提交 {len(to_analyze)} 条帖子给 LLM 分析...")
        results = analyzer.analyze_posts(to_analyze)
        result_by_link = {r['link']: r for r in results}

        stored = []
        for post in to_analyze:
            r = result_by_link.get(post['link'])
            if r is None:
                continue  # 分析失败，不入库，下轮重试
            record = {**post,
                      "score": r["score"],
                      "recommend": r["recommend"],
                      "reason": r["reason"],
                      "analyzed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            notified_posts.append(record)
            stored.append(record)
            if r["recommend"] and r["score"] >= RECOMMEND_THRESHOLD:
                recommendations.append({
                    "site_name": site_config['name'],
                    "title": post['title'],
                    "link": post['link'],
                    "summary": post['summary'],
                    "score": r["score"],
                    "reason": r["reason"],
                })

        if stored:
            save_notified_data(site_config['data_file'], notified_posts)
            log_info(f"  {site_config['name']}: LLM 分析完成 {len(stored)} 条，已入库")

    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return recommendations

def job():
    """定义要周期性执行的任务。"""
    log_info("开始执行定时任务...")
    analyzer = LLMAnalyzer()

    pending = fetch_and_collect(analyzer)
    if not pending:
        log_info("所有网站都没有新的待分析帖子。")
        log_info("定时任务执行完成。\n")
        return

    recommendations = analyze_and_store(analyzer, pending)
    log_info(f"LLM 推荐 {len(recommendations)} 个高分机会")

    if recommendations:
        to_push = recommendations[:MAX_PUSH_PER_RUN]
        log_info(f"推送 Top {len(to_push)} 个机会:")
        for it in to_push:
            log_info(f"  [{it['score']}] {it['site_name']} - {it['title']}: {it['link']}")
        send_recommendation_batch(to_push)
    else:
        log_info("本轮没有达到推荐阈值的帖子。")
    log_info("定时任务执行完成。\n")

def main():
    """主函数，启动调度任务。"""
    log_info("程序已启动，将在每天 8:00-22:00 期间每150-180分钟随机检查一次。")
    log_info(f"配置的网站: {', '.join([config['name'] for config in WEBSITES.values()])}")
    log_info(f"支持的网站类型: {', '.join(ScraperFactory.get_supported_sites())}")
    log_info("")

    # 立即执行一次任务
    job()

    # 设置定时任务
    interval_minutes = random.randint(150, 180)
    log_info(f"设置定时任务间隔: {interval_minutes} 分钟")
    schedule.every(interval_minutes).minutes.do(job)

    while True:
        # 使用本地时区
        now = datetime.now()
        if 8 <= now.hour < 23:
            schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_info("\n程序已手动停止。")
        sys.exit(0)
