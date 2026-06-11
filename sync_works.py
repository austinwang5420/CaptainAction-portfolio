#!/usr/bin/env python3
"""
Sync works data from Feishu Bitable to portfolio site.
Usage: python3 sync_works.py
"""

import json, urllib.request, ssl, os, sys

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '.feishu_config')
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'works.json')

# Feishu Bitable config
APP_TOKEN = "I9UFb9rCsa4OyksLNAIcH7Ujnoh"
TABLE_ID = "tbl8taqOWKFwjPFj"

def get_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    ctx = ssl.create_default_context()
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return json.loads(resp.read().decode())['tenant_access_token']

def get_fields(token):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    ctx = ssl.create_default_context()
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    result = json.loads(resp.read().decode())
    fields = {}
    for item in result['data']['items']:
        fields[item['field_name']] = item['field_id']
    return fields

def get_records(token):
    all_records = []
    page_token = None
    ctx = ssl.create_default_context()
    while True:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
        if page_token:
            url += f"?page_token={page_token}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        result = json.loads(resp.read().decode())
        all_records.extend(result['data']['items'])
        if not result['data'].get('has_more'):
            break
        page_token = result['data'].get('page_token')
    return all_records

def extract_file_token(attachment_value):
    """Extract file tokens from attachment field and return feishu file URLs."""
    if not attachment_value:
        return None
    try:
        attachments = json.loads(attachment_value) if isinstance(attachment_value, str) else attachment_value
        if attachments and len(attachments) > 0:
            # Return the first attachment's file_token for constructing URL
            file_token = attachments[0].get('file_token', '')
            if file_token:
                return f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
    except:
        pass
    return None

def sync():
    # Load config
    config_path = os.path.abspath(CONFIG_PATH)
    with open(config_path) as f:
        config = json.load(f)

    print("🔑 Getting Feishu token...")
    token = get_token(config['app_id'], config['app_secret'])

    print("📋 Getting table fields...")
    fields = get_fields(token)
    print(f"   Fields: {list(fields.keys())}")

    print("📥 Fetching records...")
    records = get_records(token)
    print(f"   Found {len(records)} records")

    # Map field names to IDs
    field_map = {v: k for k, v in fields.items()}

    works = []
    for record in records:
        cells = record.get('fields', {})
        work = {}
        for field_id, value in cells.items():
            field_name = field_map.get(field_id, '')
            if field_name == '作品名称':
                work['title'] = value if isinstance(value, str) else value[0].get('text', '') if value else ''
            elif field_name == '分类':
                work['category'] = value if isinstance(value, str) else value[0].get('text', '') if value else ''
            elif field_name == '描述':
                work['description'] = value if isinstance(value, str) else ''
            elif field_name == '封面图':
                work['cover'] = extract_file_token(value)
            elif field_name == '更多图片':
                work['gallery'] = extract_file_token(value)
            elif field_name == '标签':
                work['tags'] = value if isinstance(value, str) else value[0].get('text', '') if value else ''
            elif field_name == '状态':
                work['status'] = value if isinstance(value, str) else value[0].get('text', '') if value else '已发布'
            elif field_name == '创建日期':
                work['date'] = value if isinstance(value, str) else str(value)[:10] if value else ''
            elif field_name == '外部链接':
                work['link'] = value if isinstance(value, str) else ''

        if work.get('title'):
            if not work.get('status'):
                work['status'] = '已发布'
            works.append(work)

    # Save
    data_path = os.path.abspath(DATA_PATH)
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(works, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Synced {len(works)} works to {data_path}")
    for w in works:
        status_icon = "🟢" if w.get('status') == '已发布' else "🟡"
        print(f"   {status_icon} [{w.get('category', '?')}] {w.get('title', '?')}")

if __name__ == '__main__':
    sync()
