# scrapers/yuanjisong_scraper.py

from bs4 import BeautifulSoup
from typing import List, Dict
import re
import os
import time
import random
from datetime import datetime
from .base_scraper import BaseScraper
from core.logger import log_info, log_error, log_warning
# 尝试导入 Playwright，如果失败则回退到 requests
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
    log_info("Playwright 可用，将使用浏览器模式")
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    import requests
    log_warning("Playwright 未安装，使用 requests 模式（可能被防火墙拦截）")
    log_warning("建议安装: pip install playwright && playwright install chromium")

class YuanjisongScraper(BaseScraper):
    """猿急送抓取器 - 增强版，优先使用 Playwright 绕过防火墙。"""

    # 多个真实的User-Agent轮换（用于 requests 模式）
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
    ]

    def __init__(self, url: str, keywords: List[str]):
        super().__init__(url, keywords)
        if not PLAYWRIGHT_AVAILABLE:
            self.session = requests.Session()
            self._setup_session()

    def _setup_session(self):
        """设置会话，添加反反爬策略（仅用于 requests 模式）"""
        user_agent = random.choice(self.USER_AGENTS)

        # 更真实的浏览器请求头
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        })

    def _fetch_with_playwright(self, url: str, max_retries: int = 3) -> str:
        """使用 Playwright 获取页面内容（推荐方式）"""
        for attempt in range(max_retries):
            try:
                log_info(f"第{attempt + 1}次使用 Playwright 尝试访问...")

                with sync_playwright() as p:
                    # 使用 chromium，设置为非无头模式可以绕过更多检测
                    # 但在服务器环境建议使用无头模式
                    browser = p.chromium.launch(
                        headless=True,  # 无头模式
                        args=[
                            '--disable-blink-features=AutomationControlled',  # 禁用自动化控制特征
                            '--disable-dev-shm-usage',
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-web-security',
                            '--disable-features=IsolateOrigins,site-per-process'
                        ]
                    )

                    # 创建上下文，设置更真实的浏览器环境
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        locale='zh-CN',
                        timezone_id='Asia/Shanghai',
                        # 添加额外的权限和特性
                        permissions=['geolocation'],
                        geolocation={'longitude': 116.407526, 'latitude': 39.904030},  # 北京坐标
                    )

                    # 注入脚本，隐藏 webdriver 特征
                    context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });

                        // 覆盖 plugins 和 languages
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });

                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['zh-CN', 'zh', 'en']
                        });

                        // 添加 chrome 对象
                        window.chrome = {
                            runtime: {}
                        };

                        // 覆盖 permissions
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                    """)

                    page = context.new_page()

                    # 随机延迟
                    if attempt > 0:
                        delay = random.uniform(3, 8)
                        log_info(f"延迟 {delay:.1f} 秒后重试...")
                        time.sleep(delay)

                    # 先访问主页建立会话
                    log_info("访问主页建立会话...")
                    page.goto('https://www.yuanjisong.com/', wait_until='networkidle', timeout=30000)

                    # 随机滚动页面，模拟人类行为
                    page.evaluate("window.scrollTo(0, Math.floor(Math.random() * 500))")
                    time.sleep(random.uniform(1.5, 3))

                    # 访问目标页面
                    log_info(f"访问目标页面: {url}")
                    response = page.goto(url, wait_until='networkidle', timeout=30000)

                    # 等待页面加载完成
                    time.sleep(random.uniform(2, 4))

                    # 模拟人类滚动行为
                    for _ in range(random.randint(1, 3)):
                        scroll_height = random.randint(300, 800)
                        page.evaluate(f"window.scrollBy(0, {scroll_height})")
                        time.sleep(random.uniform(0.5, 1.5))

                    # 获取页面内容
                    content = page.content()
                    status_code = response.status if response else 0

                    log_info(f"响应状态码: {status_code}, 内容长度: {len(content)}")

                    # 检查是否被拦截
                    if status_code == 403:
                        log_warning(f"第{attempt + 1}次尝试被拦截 (403)")
                        browser.close()
                        if attempt < max_retries - 1:
                            continue
                        raise Exception("访问被拒绝 (403)")

                    # 检查是否有人机验证
                    if '人机验证' in content or 'verifyBox' in content or 'BT_' in content:
                        log_warning(f"第{attempt + 1}次尝试遇到人机验证")
                        # 尝试等待更长时间，看是否能自动通过
                        time.sleep(5)
                        content = page.content()

                        if '人机验证' in content:
                            browser.close()
                            if attempt < max_retries - 1:
                                continue
                            raise Exception("遇到人机验证，无法自动通过")

                    # 检查页面是否包含正常内容
                    if len(content) < 1000 and 'job' not in content.lower():
                        log_warning(f"第{attempt + 1}次尝试获取的内容异常，长度: {len(content)}")
                        browser.close()
                        if attempt < max_retries - 1:
                            continue
                        raise Exception("页面内容异常")

                    browser.close()
                    log_info("成功使用 Playwright 获取页面内容")
                    return content

            except PlaywrightTimeoutError as e:
                log_warning(f"第{attempt + 1}次 Playwright 超时: {e}")
                if attempt == max_retries - 1:
                    raise Exception(f"Playwright 访问超时: {e}")
            except Exception as e:
                log_warning(f"第{attempt + 1}次 Playwright 请求失败: {e}")
                if attempt == max_retries - 1:
                    raise

        raise Exception("所有 Playwright 重试都失败了")

    def _get_with_retry(self, url: str, max_retries: int = 3) -> 'requests.Response':
        """带重试机制的GET请求（仅用于 requests 模式，不推荐）"""
        for attempt in range(max_retries):
            try:
                # 随机延迟，模拟人类行为
                if attempt > 0:
                    delay = random.uniform(3, 8)
                    log_info(f"第{attempt + 1}次尝试访问，延迟{delay:.1f}秒")
                    time.sleep(delay)

                    # 重试时更换User-Agent
                    new_user_agent = random.choice(self.USER_AGENTS)
                    self.session.headers.update({'User-Agent': new_user_agent})
                    log_info(f"更换User-Agent: {new_user_agent[:50]}...")

                # 更新Referer头，模拟从主页访问
                if attempt == 0:
                    log_info("首次访问，先建立会话...")
                    try:
                        home_response = self.session.get('https://www.yuanjisong.com/', timeout=10)
                        log_info(f"主页访问状态: {home_response.status_code}")
                        time.sleep(random.uniform(2, 4))
                    except Exception as e:
                        log_warning(f"主页访问失败: {e}")

                # 设置Referer
                self.session.headers.update({
                    'Referer': 'https://www.yuanjisong.com/'
                })

                response = self.session.get(url, timeout=20)
                log_info(f"响应状态码: {response.status_code}, 内容长度: {len(response.text)}")

                # 检查是否被宝塔防火墙拦截
                if response.status_code == 403:
                    log_warning(f"第{attempt + 1}次尝试被拦截 (403)")
                    if attempt < max_retries - 1:
                        continue

                # 检查是否是JavaScript重定向页面
                if 'window.location.href' in response.text and len(response.text) < 500:
                    log_warning(f"第{attempt + 1}次尝试遇到JS重定向，内容: {response.text[:100]}")
                    if attempt < max_retries - 1:
                        continue

                # 检查是否是人机验证页面
                if '人机验证' in response.text or 'verifyBox' in response.text or 'BT_' in response.text:
                    log_warning(f"第{attempt + 1}次尝试遇到人机验证")
                    if attempt < max_retries - 1:
                        continue

                # 检查页面是否包含正常内容
                if len(response.text) < 1000 and 'job' not in response.text.lower():
                    log_warning(f"第{attempt + 1}次尝试获取的内容异常，长度: {len(response.text)}")
                    if attempt < max_retries - 1:
                        continue

                response.raise_for_status()
                log_info("成功获取页面内容")
                return response

            except Exception as e:
                log_warning(f"第{attempt + 1}次请求失败: {e}")
                if attempt == max_retries - 1:
                    raise

        raise Exception("所有重试都失败了")
    
    def fetch_posts(self) -> List[Dict[str, str]]:
        """获取并解析猿急送的职位列表，筛选出包含关键词的新职位。"""
        html_content = None

        try:
            log_info("开始获取猿急送职位列表...")

            # 优先使用 Playwright
            if PLAYWRIGHT_AVAILABLE:
                html_content = self._fetch_with_playwright(self.url)
                log_info(f"成功使用 Playwright 获取页面，内容长度: {len(html_content)}")
            else:
                # 回退到 requests 模式
                log_warning("使用 requests 模式（可能失败）")
                response = self._get_with_retry(self.url)
                html_content = response.text
                log_info(f"成功获取页面，状态码: {response.status_code}, 内容长度: {len(html_content)}")

        except Exception as e:
            error_msg = f"请求网页失败: {e}"
            log_error(error_msg)
            # 发送访问异常邮件通知
            self._send_error_notification("access_error", error_msg)
            return []

        soup = BeautifulSoup(html_content, 'html.parser')

        # 将完整的HTML内容保存到 urlData 目录
        self._save_html_debug(html_content, "debug")

        posts = []
        try:
            # 新版 v2 布局优先（yjs-job-card），旧版布局兜底
            job_containers = soup.find_all('div', class_='yjs-job-card')
            is_v2_layout = bool(job_containers)
            if not is_v2_layout:
                job_containers = soup.find_all('div', class_=['div_bg_color_fff', 'div_padding_1', 'hover1', 'margin_bottom_1'])

            for container in job_containers:
                if is_v2_layout:
                    post = self._parse_v2_card(container)
                else:
                    post = self._parse_legacy_card(container)
                if post:
                    posts.append(post)

        except Exception as e:
            log_error(f"解析职位时发生未知错误: {e}")
            return []

        return posts

    def _parse_v2_card(self, container) -> Dict[str, str]:
        """解析新版 v2 布局的职位卡片。"""
        title_elem = container.find('a', class_='yjs-job-card-title')
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)

        # 职位链接
        desc_link = container.find('a', class_='yjs-job-card-desc-link')
        link = ""
        if desc_link and desc_link.get('href'):
            href = desc_link.get('href')
            link = href if href.startswith('http') else f"https://www.yuanjisong.com{href}"

        # 完整描述（含技术要求，利于 LLM 分析）
        desc_elem = container.find('div', class_='yjs-job-card-desc')
        description = ""
        if desc_elem:
            description = ' '.join(desc_elem.get_text(' ', strip=True).split())

        # 徽章（工时/远程等）
        badges = ""
        badge_elem = container.find('div', class_='yjs-job-card-badges')
        if badge_elem:
            badges = ' '.join(badge_elem.get_text(' ', strip=True).split())

        # 预算
        price = ""
        budget_elem = container.find('div', class_='yjs-job-budget-value')
        if budget_elem:
            price_text = ' '.join(budget_elem.get_text(' ', strip=True).split())
            price = price_text.replace('元', '').strip()

        # 发布者
        publisher = ""
        name_elem = container.find('span', class_='yjs-job-employer-name')
        if name_elem:
            publisher = name_elem.get_text(strip=True)

        # 构建摘要
        summary_parts = []
        if badges:
            summary_parts.append(badges)
        if price:
            summary_parts.append(f"总价: {price}元")
        if publisher:
            summary_parts.append(f"发布者: {publisher}")
        if description:
            summary_parts.append(f"描述: {description}")
        summary = " | ".join(summary_parts)

        return {
            "title": title,
            "link": link,
            "summary": summary,
            "published_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 列表页无发布时间，取抓取时间
        }

    def _parse_legacy_card(self, container) -> Dict[str, str]:
        """解析旧版布局的职位容器。"""
        # 提取职位标题
        title_element = container.find('b')
        if not title_element:
            return None

        title = title_element.get_text(strip=True)

        # 提取职位链接
        link_element = container.find('a', href=True)
        link = ""
        if link_element and link_element.get('href'):
            href = link_element.get('href')
            if href.startswith('/job/'):
                link = f"https://www.yuanjisong.com{href}"
            elif href.startswith('https://www.yuanjisong.com/job/'):
                link = href

        # 提取职位描述
        description = ""
        desc_elements = container.find_all('p')
        for p in desc_elements:
            text = p.get_text(strip=True)
            if '描述：' in text:
                description = text.replace('描述：', '').strip()
                break

        # 提取工时信息
        duration = ""
        for p in desc_elements:
            text = p.get_text(strip=True)
            if '工时：' in text:
                duration = text.replace('工时：', '').strip()
                break

        # 提取总价信息
        price = ""
        for p in desc_elements:
            text = p.get_text(strip=True)
            if '总价：' in text:
                # 使用正则表达式提取价格数字
                price_match = re.search(r'(\d+)\s*元', text)
                if price_match:
                    price = f"{price_match.group(1)}元"
                break

        # 提取发布者信息
        publisher = ""
        publisher_elements = container.find_all('a')
        for a in publisher_elements:
            if '/employer/' in a.get('href', ''):
                publisher = a.get_text(strip=True)
                break

        # 构建摘要信息
        summary_parts = []
        if duration:
            summary_parts.append(f"工时: {duration}")
        if price:
            summary_parts.append(f"总价: {price}")
        if publisher:
            summary_parts.append(f"发布者: {publisher}")
        if description:
            # 限制描述长度
            desc_short = description[:100] + "..." if len(description) > 100 else description
            summary_parts.append(f"描述: {desc_short}")

        summary = " | ".join(summary_parts)

        return {
            "title": title,
            "link": link,
            "summary": summary,
            "published_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 列表页无发布时间，取抓取时间
        }