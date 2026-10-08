import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests
from lxml import html
import database

class UrlStatusChecker:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False
        self.thread = None
        self.lock = threading.Lock()
        self.status = {
            'state': 'idle',        # 'idle', 'running', 'stopped', 'completed', 'error'
            'site_id': None,
            'total': 0,
            'checked': 0,
            'count_200': 0,
            'count_404': 0,
            'count_other': 0,
            'current_url': '',
            'message': '就绪'
        }

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def stop(self):
        with self.lock:
            if self.is_running:
                self.stop_requested = True
                self.status['state'] = 'stopping'
                self.status['message'] = '正在停止检测...'

    def start(self, site_id, only_unchecked=True, max_workers=20):
        with self.lock:
            if self.is_running:
                return False, "已有状态检测任务正在运行中"

            self.is_running = True
            self.stop_requested = False
            self.status = {
                'state': 'running',
                'site_id': site_id,
                'total': 0,
                'checked': 0,
                'count_200': 0,
                'count_404': 0,
                'count_other': 0,
                'current_url': '',
                'message': '正在读取待检测链接...'
            }

        self.thread = threading.Thread(
            target=self._check_worker,
            args=(site_id, only_unchecked, max_workers),
            daemon=True
        )
        self.thread.start()
        return True, "状态检测任务已启动"

    def _check_worker(self, site_id, only_unchecked, max_workers):
        try:
            # 读取待检测的链接
            http_filter = 'uncheck' if only_unchecked else None
            url_rows = database.get_urls(site_id, http_status=http_filter, limit=50000)

            total = len(url_rows)
            with self.lock:
                self.status['total'] = total
                if total == 0:
                    self.status['state'] = 'completed'
                    self.status['message'] = '所有链接均已检测完毕，无需重复检测'
                    self.is_running = False
                    return

            checked = 0
            count_200 = 0
            count_404 = 0
            count_other = 0

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }

            def check_single_url(row):
                target_url = row['url']
                curr_title = row.get('title', '')
                res_code = 0
                new_title = ''
                
                try:
                    resp = requests.get(target_url, headers=headers, timeout=6, allow_redirects=True)
                    res_code = resp.status_code
                    
                    # 尝试提取标题（如果原本没有标题或为默认占位）
                    if (not curr_title or curr_title == '未获取页面标题') and 'text/html' in resp.headers.get('Content-Type', '').lower():
                        try:
                            m = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE | re.DOTALL)
                            if m:
                                new_title = m.group(1).strip()[:100]
                        except Exception:
                            pass
                            
                    if res_code == 404 and not new_title and (not curr_title or curr_title == '未获取页面标题'):
                        new_title = '404 页面不存在'
                except requests.exceptions.RequestException as e:
                    # 连接异常或 404
                    if hasattr(e, 'response') and e.response is not None:
                        res_code = e.response.status_code
                    else:
                        res_code = 404  # 无法访问/失效当作 404 处理
                    if not curr_title or curr_title == '未获取页面标题':
                        new_title = '无法访问或死链'
                except Exception:
                    res_code = 500

                return target_url, res_code, new_title

            batch_updates = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(check_single_url, r): r for r in url_rows}
                
                for future in as_completed(future_map):
                    if self.stop_requested:
                        break
                        
                    try:
                        u, code, title = future.result()
                        checked += 1
                        
                        if code == 200:
                            count_200 += 1
                        elif code == 404:
                            count_404 += 1
                        else:
                            count_other += 1
                            
                        batch_updates.append({'url': u, 'http_status': code, 'title': title})
                        
                        # 每 10 条或进度有变化时批量入库并更新状态
                        if len(batch_updates) >= 10:
                            database.batch_update_http_status(site_id, batch_updates)
                            batch_updates.clear()
                            
                        with self.lock:
                            self.status['checked'] = checked
                            self.status['count_200'] = count_200
                            self.status['count_404'] = count_404
                            self.status['count_other'] = count_other
                            self.status['current_url'] = u
                            self.status['message'] = f'正在检测: {checked}/{total} (200: {count_200}, 404: {count_404})'
                    except Exception as e:
                        pass

            if batch_updates:
                database.batch_update_http_status(site_id, batch_updates)

            with self.lock:
                if self.stop_requested:
                    self.status['state'] = 'stopped'
                    self.status['message'] = f'检测已停止。共检测 {checked}/{total} 条 (正常: {count_200}, 404死链: {count_404})'
                else:
                    self.status['state'] = 'completed'
                    self.status['message'] = f'检测完成！共检测 {checked}/{total} 条 (正常: {count_200}, 404死链: {count_404})'
        except Exception as e:
            with self.lock:
                self.status['state'] = 'error'
                self.status['message'] = f'检测发生异常: {str(e)}'
        finally:
            with self.lock:
                self.is_running = False

url_checker = UrlStatusChecker()
