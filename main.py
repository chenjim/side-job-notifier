# main.py

import schedule
import time
import sys
import random
from datetime import datetime
from config import WEBSITES
from data_manager import load_notified_data, save_notified_data
from scrapers.scraper_factory import ScraperFactory
from notifier import send_notification
from logger import log_info, log_error, log_warning

def job():
    """定义要周期性执行的任务。"""
    log_info("开始执行定时任务...")
    total_new_posts = 0
    
    # 遍历所有配置的网站
    for site_key, site_config in WEBSITES.items():
        log_info(f"开始检查 {site_config['name']} ({site_config['url']})...")
        
        try:
            # 创建对应的抓取器
            scraper = ScraperFactory.create_scraper(site_key, site_config)
            
            # 加载已通知过的帖子
            notified_posts = load_notified_data(site_config['data_file'])
            notified_links = [post['link'] for post in notified_posts]
            
            # 获取最新的帖子
            all_posts = scraper.fetch_posts()
            
            new_posts = []
            for post in all_posts:
                if post['link'] not in notified_links:
                    new_posts.append(post)

            if not new_posts:
                log_info(f"  {site_config['name']}: 没有发现新帖子。")
                continue

            log_info(f"  {site_config['name']}: 发现 {len(new_posts)} 个新帖子:")
            for post in new_posts:
                log_info(f"    - {post['title']}: {post['link']}")
                # 发送邮件通知
                send_notification(post, site_config['name'])
                # 更新已通知列表
                notified_posts.append(post)
            
            # 保存更新后的已通知列表
            save_notified_data(site_config['data_file'], notified_posts)
            total_new_posts += len(new_posts)
            
        except Exception as e:
            log_error(f"  {site_config['name']}: 处理时发生错误: {e}")
            continue
    
    if total_new_posts == 0:
        log_info("所有网站都没有发现新帖子。")
    else:
        log_info(f"总共发现 {total_new_posts} 个新帖子。")
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