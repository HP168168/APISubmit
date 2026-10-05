import os
import sys
import webbrowser
import threading
from urllib.parse import urlparse

# 确保控制台支持 UTF-8 输出
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from flask import Flask, render_template, request, jsonify, Response
import database
from crawler import crawler
import baidu_pusher

import time

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# 初始化数据库
database.init_db()

@app.route('/')
def index():
    return render_template('index.html', v=int(time.time()))

# ==================== 站点接口 ====================
@app.route('/api/sites', methods=['GET'])
def get_sites():
    sites = database.get_all_sites()
    return jsonify({'code': 0, 'data': sites})

@app.route('/api/sites', methods=['POST'])
def save_site():
    data = request.json or {}
    name = data.get('name', '').strip()
    site = data.get('site', '').strip()
    token = data.get('token', '').strip()
    site_id = data.get('id')

    if not name or not site or not token:
        return jsonify({'code': 1, 'message': '站点名称、域名和Token均为必填项'}), 400

    # 规范化 site：如果填了完整 url，提取域名，例如 https://www.abc.com -> www.abc.com
    if site.startswith(('http://', 'https://')):
        parsed = urlparse(site)
        site = parsed.netloc or site

    new_id = database.save_site(name, site, token, site_id)
    return jsonify({'code': 0, 'message': '保存成功', 'data': {'id': new_id}})

@app.route('/api/sites/<int:site_id>', methods=['DELETE'])
def delete_site(site_id):
    database.delete_site(site_id)
    return jsonify({'code': 0, 'message': '站点已删除'})

@app.route('/api/sites/<int:site_id>/stats', methods=['GET'])
def get_site_stats(site_id):
    site = database.get_site_by_id(site_id)
    if not site:
        return jsonify({'code': 1, 'message': '站点不存在'}), 404
    stats = database.get_url_stats(site_id)
    stats['remain_quota'] = site.get('remain_quota', -1)
    stats['last_push_time'] = site.get('last_push_time', '')
    return jsonify({'code': 0, 'data': stats})

# ==================== 链接管理接口 ====================
@app.route('/api/urls', methods=['GET'])
def list_urls():
    site_id = request.args.get('site_id', type=int)
    if not site_id:
        return jsonify({'code': 1, 'message': '缺少 site_id 参数'}), 400
    
    status = request.args.get('status', 'all')
    keyword = request.args.get('keyword', '').strip()
    limit = request.args.get('limit', default=1000, type=int)
    offset = request.args.get('offset', default=0, type=int)

    urls = database.get_urls(site_id, status=status, keyword=keyword, limit=limit, offset=offset)
    stats = database.get_url_stats(site_id)
    return jsonify({'code': 0, 'data': urls, 'stats': stats})

@app.route('/api/urls/manual', methods=['POST'])
def add_manual_urls():
    data = request.json or {}
    site_id = data.get('site_id')
    urls_text = data.get('urls', '')
    if not site_id or not urls_text:
        return jsonify({'code': 1, 'message': '参数不全'}), 400

    lines = [u.strip() for u in urls_text.splitlines() if u.strip()]
    url_items = []
    for line in lines:
        if line.startswith(('http://', 'https://')):
            url_items.append({'url': line, 'title': '手动录入', 'depth': 1, 'source_page': '手动粘贴'})

    database.bulk_insert_urls(site_id, url_items)
    return jsonify({'code': 0, 'message': f'成功录入 {len(url_items)} 条链接'})

@app.route('/api/urls/clear', methods=['POST'])
def clear_urls():
    data = request.json or {}
    site_id = data.get('site_id')
    if not site_id:
        return jsonify({'code': 1, 'message': '缺少 site_id'}), 400
    database.clear_urls_for_site(site_id)
    return jsonify({'code': 0, 'message': '当前站点链接记录已清空'})

# ==================== 爬虫接口 ====================
@app.route('/api/crawler/start', methods=['POST'])
def start_crawl():
    data = request.json or {}
    site_id = data.get('site_id')
    start_url = data.get('start_url', '').strip()
    max_depth = data.get('max_depth', 2)
    max_pages = data.get('max_pages', 100)

    if not site_id or not start_url:
        return jsonify({'code': 1, 'message': '请选择站点并输入合法的起始网址'}), 400

    if not start_url.startswith(('http://', 'https://')):
        start_url = 'http://' + start_url

    ok, msg = crawler.start(site_id, start_url, max_depth=max_depth, max_pages=max_pages)
    if ok:
        return jsonify({'code': 0, 'message': msg})
    else:
        return jsonify({'code': 1, 'message': msg}), 400

@app.route('/api/crawler/stop', methods=['POST'])
def stop_crawl():
    crawler.stop()
    return jsonify({'code': 0, 'message': '已发出停止请求'})

@app.route('/api/crawler/status', methods=['GET'])
def crawl_status():
    status = crawler.get_status()
    return jsonify({'code': 0, 'data': status})

# ==================== 百度推送接口 ====================
@app.route('/api/baidu/push', methods=['POST'])
def push_baidu():
    data = request.json or {}
    site_id = data.get('site_id')
    urls = data.get('urls', []) # 勾选的 url 列表

    if not site_id:
        return jsonify({'code': 1, 'message': '请选择目标站点'}), 400

    site_info = database.get_site_by_id(site_id)
    if not site_info:
        return jsonify({'code': 1, 'message': '站点配置不存在'}), 404

    site_domain = site_info['site']
    token = site_info['token']

    if not token:
        return jsonify({'code': 1, 'message': '该站点未配置准入 Token'}), 400

    if not urls:
        return jsonify({'code': 1, 'message': '请先勾选需要推送的链接'}), 400

    # 执行分批推送
    result = baidu_pusher.push_urls_batch(
        site_id=site_id,
        site_url=site_domain,
        token=token,
        urls=urls,
        batch_size=500
    )

    stats = database.get_url_stats(site_id)
    return jsonify({
        'code': 0 if result['success'] else 1,
        'message': result['message'],
        'data': result,
        'stats': stats
    })

# ==================== 导出接口 ====================
@app.route('/api/export', methods=['GET'])
def export_urls():
    site_id = request.args.get('site_id', type=int)
    status = request.args.get('status', 'all')
    export_type = request.args.get('type', 'txt') # txt or csv

    if not site_id:
        return "缺少 site_id", 400

    urls = database.get_urls(site_id, status=status, limit=50000)
    
    if export_type == 'csv':
        lines = ["URL,页面标题,状态,推送次数,最近推送时间,推送结果"]
        for row in urls:
            safe_title = (row['title'] or '').replace(',', ' ')
            safe_res = (row['last_push_result'] or '').replace(',', ' ')
            lines.append(f"{row['url']},{safe_title},{row['status']},{row['push_count']},{row['last_push_at']},{safe_res}")
        content = "\ufeff" + "\n".join(lines)
        return Response(
            content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=baidu_urls_site_{site_id}.csv"}
        )
    else:
        # 纯文本，每行一个 URL，方便直接用于其它地方
        lines = [row['url'] for row in urls]
        content = "\n".join(lines)
        return Response(
            content,
            mimetype="text/plain",
            headers={"Content-Disposition": f"attachment;filename=baidu_urls_site_{site_id}.txt"}
        )

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    # 延迟 1 秒后自动弹出浏览器
    threading.Timer(1.2, open_browser).start()
    print("=" * 60)
    print("百度 API 批量推送可视化工具正在启动...")
    print("访问地址: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=False)
