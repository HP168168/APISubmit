import sqlite3
import os
import json
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'push_tool.db')

def get_connection():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 站点管理表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        site TEXT NOT NULL UNIQUE,
        token TEXT NOT NULL,
        remain_quota INTEGER DEFAULT -1,
        last_push_time TEXT DEFAULT '',
        created_at TEXT NOT NULL
    )
    ''')
    
    # 链接记录与状态表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS urls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        title TEXT DEFAULT '',
        depth INTEGER DEFAULT 1,
        source_page TEXT DEFAULT '',
        discovered_at TEXT NOT NULL,
        status TEXT DEFAULT 'unsubmitted', -- 'unsubmitted', 'success', 'failed', 'ignored'
        push_count INTEGER DEFAULT 0,
        last_push_at TEXT DEFAULT '',
        last_push_result TEXT DEFAULT '',
        FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
        UNIQUE(site_id, url)
    )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_urls_site_status ON urls (site_id, status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_urls_site_url ON urls (site_id, url)')
    
    conn.commit()
    conn.close()

# 站点相关操作
def get_all_sites():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sites ORDER BY id ASC')
    sites = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sites

def get_site_by_id(site_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sites WHERE id = ?', (site_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_site(name, site, token, site_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    site = site.strip().rstrip('/')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if site_id:
        cursor.execute('''
        UPDATE sites SET name = ?, site = ?, token = ? WHERE id = ?
        ''', (name, site, token, site_id))
        res_id = site_id
    else:
        cursor.execute('''
        INSERT INTO sites (name, site, token, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(site) DO UPDATE SET name = excluded.name, token = excluded.token
        ''', (name, site, token, now))
        res_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return res_id

def delete_site(site_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM urls WHERE site_id = ?', (site_id,))
    cursor.execute('DELETE FROM sites WHERE id = ?', (site_id,))
    conn.commit()
    conn.close()

def update_site_quota(site_id, remain_quota):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    UPDATE sites SET remain_quota = ?, last_push_time = ? WHERE id = ?
    ''', (remain_quota, now, site_id))
    conn.commit()
    conn.close()

# 链接相关操作
def add_or_update_url(site_id, url, title='', depth=1, source_page=''):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    INSERT INTO urls (site_id, url, title, depth, source_page, discovered_at, status)
    VALUES (?, ?, ?, ?, ?, ?, 'unsubmitted')
    ON CONFLICT(site_id, url) DO UPDATE SET
        title = CASE WHEN excluded.title != '' THEN excluded.title ELSE urls.title END
    ''', (site_id, url, title, depth, source_page, now))
    conn.commit()
    conn.close()

def bulk_insert_urls(site_id, url_items):
    """
    url_items: list of dict {'url': ..., 'title': ..., 'depth': ..., 'source_page': ...}
    """
    if not url_items:
        return
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for item in url_items:
        cursor.execute('''
        INSERT INTO urls (site_id, url, title, depth, source_page, discovered_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'unsubmitted')
        ON CONFLICT(site_id, url) DO UPDATE SET
            title = CASE WHEN excluded.title != '' THEN excluded.title ELSE urls.title END
        ''', (site_id, item['url'], item.get('title', ''), item.get('depth', 1), item.get('source_page', ''), now))
        
    conn.commit()
    conn.close()

def get_urls(site_id, status=None, keyword=None, limit=2000, offset=0):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM urls WHERE site_id = ?'
    params = [site_id]
    
    if status and status != 'all':
        query += ' AND status = ?'
        params.append(status)
        
    if keyword:
        query += ' AND (url LIKE ? OR title LIKE ?)'
        params.append(f'%{keyword}%')
        params.append(f'%{keyword}%')
        
    query += ' ORDER BY id DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_url_stats(site_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'unsubmitted' THEN 1 ELSE 0 END) as unsubmitted,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
        SUM(CASE WHEN status = 'ignored' THEN 1 ELSE 0 END) as ignored
    FROM urls WHERE site_id = ?
    ''', (site_id,))
    
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'total': row['total'] or 0,
            'unsubmitted': row['unsubmitted'] or 0,
            'success': row['success'] or 0,
            'failed': row['failed'] or 0,
            'ignored': row['ignored'] or 0
        }
    return {'total': 0, 'unsubmitted': 0, 'success': 0, 'failed': 0, 'ignored': 0}

def update_url_push_status(site_id, url, status, result_msg):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    count_inc = 1 if status == 'success' else 0
    cursor.execute('''
    UPDATE urls SET 
        status = ?, 
        push_count = push_count + ?, 
        last_push_at = ?, 
        last_push_result = ?
    WHERE site_id = ? AND url = ?
    ''', (status, count_inc, now, result_msg, site_id, url))
    
    conn.commit()
    conn.close()

def batch_update_url_push_status(site_id, success_urls, failed_urls=None, ignored_urls=None, result_msg=""):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if success_urls:
        for u in success_urls:
            cursor.execute('''
            UPDATE urls SET 
                status = 'success', 
                push_count = push_count + 1, 
                last_push_at = ?, 
                last_push_result = ?
            WHERE site_id = ? AND url = ?
            ''', (now, result_msg or '推送成功', site_id, u))
            
    if failed_urls:
        for u, reason in failed_urls:
            cursor.execute('''
            UPDATE urls SET 
                status = 'failed', 
                last_push_at = ?, 
                last_push_result = ?
            WHERE site_id = ? AND url = ?
            ''', (now, reason, site_id, u))
            
    if ignored_urls:
        for u, reason in ignored_urls:
            cursor.execute('''
            UPDATE urls SET 
                status = 'ignored', 
                last_push_at = ?, 
                last_push_result = ?
            WHERE site_id = ? AND url = ?
            ''', (now, reason, site_id, u))
            
    conn.commit()
    conn.close()

def clear_urls_for_site(site_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM urls WHERE site_id = ?', (site_id,))
    conn.commit()
    conn.close()
