import requests
import json
from datetime import datetime
import database

BAIDU_PUSH_API = "http://data.zz.baidu.com/urls"

def push_urls_batch(site_id, site_url, token, urls, batch_size=500):
    """
    分批向百度 API 提交链接
    :param site_id: 站点在数据库中的 ID
    :param site_url: 百度站长平台绑定的站点 (如 www.example.com)
    :param token: 准入密钥 token (16位)
    :param urls: 待提交的 URL 字符串列表
    :param batch_size: 单批次数量，官方最大 2000，推荐 500
    :return: 汇总执行结果字典
    """
    if not urls:
        return {
            'success': False,
            'message': '提交的链接列表为空',
            'total_submitted': 0,
            'total_success': 0,
            'remain': -1,
            'batches': []
        }

    # 规范化 site_url，去掉 http:// 或 https://，百度接口通常直接填域名，但也兼容传带协议的
    clean_site = site_url.strip()
    if clean_site.startswith(('http://', 'https://')):
        # 百度 API 传参通常用注册域名，比如 www.example.com
        parsed_site = clean_site.replace('http://', '').replace('https://', '').rstrip('/')
    else:
        parsed_site = clean_site.rstrip('/')

    total_submitted = len(urls)
    total_success = 0
    latest_remain = -1
    batch_reports = []

    headers = {
        'Content-Type': 'text/plain',
        'User-Agent': 'curl/7.12.1'
    }

    # 按 batch_size 切割
    for i in range(0, total_submitted, batch_size):
        chunk = urls[i:i + batch_size]
        post_body = "\n".join(chunk)
        
        target_api = f"{BAIDU_PUSH_API}?site={parsed_site}&token={token.strip()}"

        try:
            resp = requests.post(target_api, data=post_body.encode('utf-8'), headers=headers, timeout=20)
            status_code = resp.status_code
            try:
                res_data = resp.json()
            except Exception:
                res_data = {'raw': resp.text}

            if status_code == 200:
                # 成功返回
                # {"remain": 4999998, "success": 2, "not_same_site": [], "not_valid": []}
                success_count = res_data.get('success', 0)
                remain = res_data.get('remain', -1)
                not_same_site = set(res_data.get('not_same_site', []) or [])
                not_valid = set(res_data.get('not_valid', []) or [])

                total_success += success_count
                latest_remain = remain

                # 计算成功和被忽略的具体 URL
                success_chunk_urls = []
                ignored_list = []

                for u in chunk:
                    if u in not_same_site:
                        ignored_list.append((u, '非本站域名 (not_same_site)'))
                    elif u in not_valid:
                        ignored_list.append((u, '不合法的链接 (not_valid)'))
                    else:
                        success_chunk_urls.append(u)

                # 更新数据库
                database.batch_update_url_push_status(
                    site_id=site_id,
                    success_urls=success_chunk_urls,
                    ignored_urls=ignored_list,
                    result_msg=f"成功推送 (当日余量: {remain})"
                )

                batch_reports.append({
                    'batch_index': (i // batch_size) + 1,
                    'count': len(chunk),
                    'status': 'success',
                    'success_count': success_count,
                    'remain': remain,
                    'not_same_site_count': len(not_same_site),
                    'not_valid_count': len(not_valid),
                    'raw': res_data
                })

            else:
                # 失败返回
                # {"error": 400, "message": "site error"}
                err_code = res_data.get('error', status_code)
                err_msg = res_data.get('message', resp.text)
                
                # 标记该批次为失败
                failed_items = [(u, f"错误 {err_code}: {err_msg}") for u in chunk]
                database.batch_update_url_push_status(
                    site_id=site_id,
                    success_urls=[],
                    failed_urls=failed_items
                )

                batch_reports.append({
                    'batch_index': (i // batch_size) + 1,
                    'count': len(chunk),
                    'status': 'failed',
                    'error_code': err_code,
                    'error_message': err_msg,
                    'raw': res_data
                })

        except requests.exceptions.RequestException as e:
            failed_items = [(u, f"网络请求异常: {str(e)}") for u in chunk]
            database.batch_update_url_push_status(
                site_id=site_id,
                success_urls=[],
                failed_urls=failed_items
            )
            batch_reports.append({
                'batch_index': (i // batch_size) + 1,
                'count': len(chunk),
                'status': 'error',
                'error_message': str(e)
            })

    # 更新站点配额记录
    if latest_remain >= 0:
        database.update_site_quota(site_id, latest_remain)

    return {
        'success': total_success > 0 or all(b['status'] == 'success' for b in batch_reports),
        'message': f"推送完毕！提交 {total_submitted} 条，百度确认新增接收 {total_success} 条",
        'total_submitted': total_submitted,
        'total_success': total_success,
        'remain': latest_remain,
        'batches': batch_reports
    }
