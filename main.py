# main.py
# 流程: 心跳检查站点是否到期 → 全量抓取 → 按库内已评估 link 去重 → 时间窗过滤
#       → 未评估记录入库 → LLM 批量分析打分 → 回写评分 → 按评分排序限流推送 → 清理超期记录

import schedule
import time
import sys
from datetime import datetime
from config import (WEBSITES, RECOMMEND_THRESHOLD, MAX_PUSH_PER_RUN, RECENT_DAYS,
                    POSITION_LIMIT, RETENTION_DAYS, DB_PATH, LOOP_TICK_MINUTES,
                    DEFAULT_FETCH_INTERVAL)
from core.data_manager import (init_db, get_evaluated_links, upsert_parsed_posts,
                               save_analyzed_posts, purge_old_records,
                               get_site_state, mark_site_fetched)
from core.site_scheduler import is_due
from scrapers.scraper_factory import ScraperFactory
from core.llm_analyzer import LLMAnalyzer
from core.notifier import send_recommendation_batch
from core.logger import log_info, log_error, log_warning
from core.time_parser import is_recent

# 站点连续多次抓不到新帖时提醒（站点可能停更/改版）
EMPTY_STREAK_WARN = 10

def _site_interval(site_key: str):
    """站点最小抓取间隔（分钟，int 或 (min, max) 区间）。"""
    return WEBSITES[site_key].get('min_interval_minutes', DEFAULT_FETCH_INTERVAL)

def _is_site_due(site_key: str) -> bool:
    """按库内记录的「上次抓取时间」判断该站点是否到期。"""
    state = get_site_state(site_key)
    return is_due(state.get('last_fetch_at'), _site_interval(site_key),
                  state.get('last_status') or 'ok')

def _describe_interval(interval) -> str:
    if isinstance(interval, (tuple, list)):
        return f"{interval[0]}-{interval[1]} 分钟"
    minutes = int(interval)
    return f"{minutes // 60} 小时" if minutes >= 60 and minutes % 60 == 0 else f"{minutes} 分钟"

def fetch_and_collect(due_sites) -> dict:
    """抓取到期站点，去重 + 时间窗过滤 + 未评估记录入库，返回 {site_key: [待评估记录]}。"""
    pending = {}
    for site_key in due_sites:
        site_config = WEBSITES[site_key]
        name = site_config['name']
        log_info(f"开始检查 {name} ({site_config['url']})...")
        try:
            scraper = ScraperFactory.create_scraper(site_key, site_config)
            # 去重口径：库里有评分 = 已评估过，不再送 LLM
            evaluated_links = get_evaluated_links(site_key)

            all_posts = scraper.fetch_posts()
            new_posts = [p for p in all_posts if p.get('link') and p['link'] not in evaluated_links]
            new_count = len(new_posts)

            # 时间窗过滤：只保留最近发布的未评估帖子（降低 LLM 成本）
            time_mode = site_config.get('time_mode', 'field')
            if time_mode == 'position':
                # 列表页按最新发布倒序，取前 N 条兜底
                candidates = new_posts[:POSITION_LIMIT]
                log_info(f"  {name}: 未评估 {new_count} 条，位置兜底取前 {len(candidates)} 条")
            else:
                candidates = [p for p in new_posts
                              if is_recent(p.get('published_at', ''), RECENT_DAYS)]
                log_info(f"  {name}: 未评估 {new_count} 条，时间窗内 {len(candidates)} 条")

            # 记录抓取节奏与健康度（失败时按 RETRY_MINUTES 快速重试）
            empty_streak = mark_site_fetched(site_key, new_count)
            if empty_streak and empty_streak % EMPTY_STREAK_WARN == 0:
                log_warning(f"  {name}: 已连续 {empty_streak} 次没有新帖，"
                            f"检查站点是否停更或改版（{site_config['url']}）")

            if not candidates:
                continue

            # 入库（已存在的 link 不覆盖），取回其中仍未评估的记录（含上轮失败的）
            todo = upsert_parsed_posts(site_key, candidates)
            if time_mode == 'field':
                # 按库内时间锚点复核，避免发布时间缺失/异常的老帖占用 LLM 额度
                todo = [r for r in todo if is_recent(r['time_ref'], RECENT_DAYS)]
            if todo:
                pending[site_key] = todo
        except Exception as e:
            # 抓取失败也要落状态，否则调度会按整天间隔干等
            mark_site_fetched(site_key, 0, status='error')
            log_error(f"  {name}: 抓取/过滤时发生错误: {e}")
            continue
    return pending

def analyze_and_store(analyzer: LLMAnalyzer, pending: dict) -> list:
    """批量 LLM 分析并回写评分，返回推荐列表（按评分降序）。"""
    recommendations = []
    for site_key, todo in pending.items():
        site_config = WEBSITES[site_key]
        name = site_config['name']

        log_info(f"  {name}: 提交 {len(todo)} 条帖子给 LLM 分析...")
        results = analyzer.analyze_posts(todo)
        result_by_link = {r['link']: r for r in results}

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        stored = []
        skipped_old = 0
        for post in todo:
            r = result_by_link.get(post['link'])
            if r is None:
                continue  # 整批失败，不入库，下轮重试
            record = {**post,
                      "score": r["score"],
                      "recommend": r["recommend"],
                      "reason": r["reason"],
                      "analyzed_at": now_str}
            stored.append(record)

            if not (r["recommend"] and r["score"] >= RECOMMEND_THRESHOLD):
                continue
            # 推送口径：时间锚点只在最近 RECENT_DAYS 天内才推（发布时间缺失时锚点即首次发现/分析时间）
            if not is_recent(post['time_ref'], RECENT_DAYS):
                skipped_old += 1
                continue
            recommendations.append({
                "site_name": name,
                "title": post['title'],
                "link": post['link'],
                "summary": post['summary'],
                "score": r["score"],
                "reason": r["reason"],
            })

        if stored:
            save_analyzed_posts(site_key, stored)
            log_info(f"  {name}: LLM 分析完成 {len(stored)} 条，已入库")
        if skipped_old:
            log_info(f"  {name}: {skipped_old} 条高分但超出 {RECENT_DAYS} 天时间窗，不推送")

    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return recommendations

def job():
    """心跳任务：只抓到期站点，有结果才做 LLM 分析与推送。"""
    due_sites = [k for k in WEBSITES if _is_site_due(k)]
    if not due_sites:
        log_info(f"所有站点均未到抓取间隔（共 {len(WEBSITES)} 个），本轮跳过")
        return

    log_info(f"到期站点: {', '.join(WEBSITES[k]['name'] for k in due_sites)}")
    pending = fetch_and_collect(due_sites)
    if not pending:
        log_info("到期站点都没有新的待分析帖子。")
    else:
        recommendations = analyze_and_store(LLMAnalyzer(), pending)
        log_info(f"LLM 推荐 {len(recommendations)} 个高分机会")

        if recommendations:
            to_push = recommendations[:MAX_PUSH_PER_RUN]
            log_info(f"推送 Top {len(to_push)} 个机会:")
            for it in to_push:
                log_info(f"  [{it['score']}] {it['site_name']} - {it['title']}: {it['link']}")
            send_recommendation_batch(to_push)
        else:
            log_info("本轮没有达到推荐阈值的帖子。")

    # 清理超过保留期的记录，避免库无限膨胀
    deleted = purge_old_records(RETENTION_DAYS)
    if deleted:
        log_info(f"清理超过 {RETENTION_DAYS} 天（按发布时间，缺失回落到分析时间）的历史记录 {deleted} 条")
    log_info("定时任务执行完成。\n")

def main():
    """主函数，启动调度任务。"""
    init_db()
    log_info(f"程序已启动，记录库: {DB_PATH}（保留最近 {RETENTION_DAYS} 天）")
    log_info(f"调度心跳: 每 {LOOP_TICK_MINUTES} 分钟检查一次，仅 8:00-22:00 执行")
    for key, config in WEBSITES.items():
        log_info(f"  - {config['name']}: 最小抓取间隔 {_describe_interval(_site_interval(key))}")
    log_info(f"支持的网站类型: {', '.join(ScraperFactory.get_supported_sites())}")
    log_info("")

    # 立即执行一次（未到间隔的站点会自动跳过，重启不会集中轰炸站点）
    job()

    schedule.every(LOOP_TICK_MINUTES).minutes.do(job)

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
