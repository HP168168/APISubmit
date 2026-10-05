import threading
import time
import re
from urllib.parse import urlparse, urljoin, urldefrag
import requests
from lxml import html
import database

# 忽略的非网页资源后缀
IGNORED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico',
    '.css', '.js', '.map',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt',
    '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso', '.exe', '.apk', '.dmg',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.wav',
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    '.xml', '.json', '.rss'
}

class SiteCrawler:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False
        self.thread = None
        self.status = {
            'state': 'idle',        # 'idle', 'running', 'stopped', 'completed', 'error'
            'start_url': '',
            'site_id': None,
            'max_depth': 2,
            'max_pages': 100,
            'visited_count': 0,
            'found_count': 0,
            'current_url': '',
            'message': '就绪'
        }
        self.lock = threading.Lock()

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def stop(self):
        with self.lock:
            if self.is_running:
                self.stop_requested = True
                self.status['state'] = 'stopping'
                self.status['message'] = '正在停止遍历...'

    def start(self, site_id, start_url, max_depth=2, max_pages=100, delay=0.1):
        with self.lock:
            if self.is_running:
                return False, "已有抓取任务在运行中"
            
            self.is_running = True
            self.stop_requested = False
            self.status = {
                'state': 'running',
                'start_url': start_url,
                'site_id': site_id,
                'max_depth': int(max_depth),
                'max_pages': int(max_pages),
                'visited_count': 0,
                'found_count': 0,
                'current_url': start_url,
                'message': '任务启动中...'
            }

        self.thread = threading.Thread(
            target=self._crawl_worker,
            args=(site_id, start_url, int(max_depth), int(max_pages), float(delay)),
            daemon=True
        )
        self.thread.start()
        return True, "抓取任务已启动"

    def _is_valid_url(self, url, base_netloc):
        """判断是否为同域且合法的 HTML 页面链接"""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            
            # 域名匹配：支持 www 容错
            link_netloc = parsed.netloc.lower()
            norm_base = base_netloc.lower().replace('www.', '')
            norm_link = link_netloc.replace('www.', '')
            if norm_link != norm_base and not norm_link.endswith('.' + norm_base):
                return False

            # 后缀过滤
            path = parsed.path.lower()
            for ext in IGNORED_EXTENSIONS:
                if path.endswith(ext):
                    return False
                
            return True
        except Exception:
            return False

    def _extract_title(self, tree):
        """提取 HTML 网页标题"""
        try:
            title_nodes = tree.xpath('//title/text()')
            if title_nodes:
                return title_nodes[0].strip()[:100]
        except Exception:
            pass
        return ''

    def _crawl_worker(self, site_id, start_url, max_depth, max_pages, delay):
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

        parsed_start = urlparse(start_url)
        base_netloc = parsed_start.netloc

        # 待爬取队列: (url, depth, source_page)
        clean_start_url, _ = urldefrag(start_url)
        queue = [(clean_start_url, 1, '')]
        visited_pages = set()     # 已请求的页面
        discovered_urls = set([clean_start_url]) # 所有发现的链接

        # 先将起始 URL 入库
        database.add_or_update_url(site_id, clean_start_url, title='起始页', depth=1, source_page='用户输入')
        with self.lock:
            self.status['found_count'] = 1

        try:
            while queue and not self.stop_requested:
                if len(visited_pages) >= max_pages:
                    with self.lock:
                        self.status['message'] = f'已达到最大抓取页面限制 ({max_pages} 页)'
                    break

                current_url, current_depth, source_page = queue.pop(0)

                if current_url in visited_pages:
                    continue

                visited_pages.add(current_url)

                if self.stop_requested:
                    break

                with self.lock:
                    self.status['current_url'] = current_url
                    self.status['visited_count'] = len(visited_pages)
                    self.status['message'] = f'正在遍历 (深度 {current_depth}/{max_depth}): {current_url}'

                try:
                    resp = session.get(current_url, timeout=10, allow_redirects=True)
                    content_type = resp.headers.get('Content-Type', '').lower()
                    if 'text/html' not in content_type:
                        continue

                    # 处理重定向后的 URL
                    final_url, _ = urldefrag(resp.url)
                    
                    # 编码处理
                    if resp.encoding is None or resp.encoding.lower() == 'iso-8859-1':
                        resp.encoding = resp.apparent_encoding or 'utf-8'

                    tree = html.fromstring(resp.content)
                    page_title = self._extract_title(tree)
                    
                    # 更新当前页的标题
                    database.add_or_update_url(site_id, final_url, title=page_title, depth=current_depth, source_page=source_page)

                    # 提取链接
                    new_links_batch = []
                    links = tree.xpath('//a/@href')
                    for href in links:
                        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                            continue
                        
                        abs_url = urljoin(final_url, href)
                        clean_url, _ = urldefrag(abs_url)

                        if self._is_valid_url(clean_url, base_netloc):
                            if clean_url not in discovered_urls:
                                discovered_urls.add(clean_url)
                                item = {
                                    'url': clean_url,
                                    'title': '', # 等后续抓取或列表展示
                                    'depth': current_depth + 1,
                                    'source_page': final_url
                                }
                                new_links_batch.append(item)

                                # 若深度未超限，加入抓取队列
                                if current_depth < max_depth:
                                    queue.append((clean_url, current_depth + 1, final_url))

                    if new_links_batch:
                        database.bulk_insert_urls(site_id, new_links_batch)
                        with self.lock:
                            self.status['found_count'] = len(discovered_urls)

                except Exception as e:
                    # 抓取单页出错继续下一页
                    pass

                if delay > 0:
                    time.sleep(delay)

            with self.lock:
                if self.stop_requested:
                    self.status['state'] = 'stopped'
                    self.status['message'] = f'抓取已手动停止。共访问 {len(visited_pages)} 页，发现有效链接 {len(discovered_urls)} 条'
                else:
                    self.status['state'] = 'completed'
                    self.status['message'] = f'抓取完成！共访问 {len(visited_pages)} 页，发现有效链接 {len(discovered_urls)} 条'
        except Exception as e:
            with self.lock:
                self.status['state'] = 'error'
                self.status['message'] = f'抓取发生异常: {str(e)}'
        finally:
            with self.lock:
                self.is_running = False

crawler = SiteCrawler()
