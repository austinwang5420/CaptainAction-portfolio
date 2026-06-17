#!/usr/bin/env python3
"""
Sync works data from Feishu Bitable to portfolio site.
- Downloads cover images to local assets/
- Preserves local views/gallery fields (not in Feishu)
- Skips empty records
- Parses link-type fields ({link, text} format)

Usage: python3 sync_works.py
"""

import json, urllib.request, ssl, os, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, '..', '.feishu_config')
DATA_PATH = os.path.join(SCRIPT_DIR, 'data', 'works.json')
COVER_DIR = os.path.join(SCRIPT_DIR, 'assets', 'images', 'works')

APP_TOKEN = "I9UFb9rCsa4OyksLNAIcH7Ujnoh"
TABLE_ID = "tbl8taqOWKFwjPFj"

ctx = ssl.create_default_context()


def get_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    return json.loads(resp.read().decode())['tenant_access_token']


def get_records(token):
    """Get all records from Feishu Bitable, handling pagination."""
    all_records = []
    page_token = None
    while True:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        result = json.loads(resp.read().decode())
        if result.get('code') != 0:
            raise Exception(f"Feishu API error: {result}")
        items = result.get('data', {}).get('items', [])
        all_records.extend(items)
        if not result.get('data', {}).get('has_more'):
            break
        page_token = result.get('data', {}).get('page_token')
    return all_records


def download_cover(token, file_token, record_id, fallback_name):
    """Download cover image from Feishu to local assets directory."""
    if not file_token:
        return ''
    # Ensure cover directory exists
    os.makedirs(COVER_DIR, exist_ok=True)

    # Determine extension from original name or default to png
    ext = '.png'
    if fallback_name and '.' in fallback_name:
        ext = '.' + fallback_name.rsplit('.', 1)[-1].lower()

    local_filename = f"{record_id}{ext}"
    local_path = os.path.join(COVER_DIR, local_filename)

    # Skip if already downloaded
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        print(f"   📎 Cover already exists: {local_filename}")
        return f"assets/images/works/{local_filename}"

    # Download via Feishu media API
    url = f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = urllib.request.urlopen(req, context=ctx, timeout=30)
            img_data = resp.read()
            if len(img_data) > 0:
                with open(local_path, 'wb') as f:
                    f.write(img_data)
                print(f"   🖼️ Downloaded cover: {local_filename} ({len(img_data)//1024}KB)")
                return f"assets/images/works/{local_filename}"
            else:
                print(f"   ⚠️ Empty image data for {record_id}")
                break
        except urllib.error.HTTPError as e:
            print(f"   ⚠️ Download attempt {attempt+1} failed: HTTP {e.code}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"   ❌ Failed to download cover for {record_id}: {e}")
    return ''


def parse_link(value):
    """Parse Feishu link field ({link, text} or string)."""
    if not value:
        return ''
    if isinstance(value, dict):
        return value.get('link', '') or value.get('text', '')
    if isinstance(value, str):
        return value
    return ''


def parse_tags(value):
    """Parse Feishu multi-select / tags field."""
    if not value:
        return ''
    if isinstance(value, list):
        return ', '.join([str(v) if isinstance(v, str) else v.get('text', str(v)) for v in value])
    if isinstance(value, str):
        return value
    return str(value)


def format_date(value):
    """Format Feishu date field (timestamp in ms) to YYYY.MM."""
    if not value:
        return ''
    try:
        ts = int(value)
        # Feishu timestamps are in milliseconds
        if ts > 1e12:
            ts = ts // 1000
        from datetime import datetime
        d = datetime.fromtimestamp(ts)
        return d.strftime('%Y.%m')
    except Exception:
        return str(value)


def sync():
    # Load config
    config_path = os.path.abspath(CONFIG_PATH)
    if not os.path.exists(config_path):
        print(f"❌ Config not found: {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        config = json.load(f)

    print("🔑 Getting Feishu token...")
    token = get_token(config['app_id'], config['app_secret'])

    print("📋 Fetching records...")
    records = get_records(token)
    print(f"   Found {len(records)} records total")

    # Load existing works.json to preserve local-only fields (views, gallery, cover)
    existing_by_id = {}
    existing_by_title = {}
    data_path = os.path.abspath(DATA_PATH)
    if os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            old_works = json.load(f)
        for w in old_works:
            if w.get('id'):
                existing_by_id[w['id']] = w
            if w.get('title'):
                existing_by_title[w['title']] = w

    works = []
    skipped = 0

    for record in records:
        rid = record.get('record_id', record.get('id', ''))
        fields = record.get('fields', {})

        # Skip empty records
        if not fields or not fields.get('作品名称'):
            skipped += 1
            continue

        title = fields.get('作品名称', '')

        # Parse cover image
        cover = ''
        cover_field = fields.get('封面图', [])
        if isinstance(cover_field, list) and len(cover_field) > 0:
            file_info = cover_field[0]
            file_token = file_info.get('file_token', '')
            file_name = file_info.get('name', '')
            if file_token:
                print(f"   📥 Downloading cover for: {title}")
                cover = download_cover(token, file_token, rid, file_name)

        # Parse gallery images
        gallery = []
        gallery_field = fields.get('更多图片', [])
        if isinstance(gallery_field, list):
            for idx, img_info in enumerate(gallery_field):
                ft = img_info.get('file_token', '')
                fn = img_info.get('name', '')
                if ft:
                    g_path = download_cover(token, ft, f"{rid}_g{idx}", fn)
                    if g_path:
                        gallery.append(g_path)

        # Build work object — match by ID first, then by title (handles Feishu record ID changes)
        old = existing_by_id.get(rid, {})
        if not old and title and title in existing_by_title:
            old = existing_by_title[title]
            print(f"   🔄 ID changed for '{title}': inherited local data")
        work = {
            'id': rid,
            'title': title,
            'category': fields.get('分类', '') if isinstance(fields.get('分类'), str) else parse_tags(fields.get('分类')),
            'description': fields.get('描述', ''),
            'tags': parse_tags(fields.get('标签')),
            'status': fields.get('状态', '已发布') if isinstance(fields.get('状态'), str) else parse_tags(fields.get('状态', '已发布')),
            'link': parse_link(fields.get('外部链接')),
            'date': format_date(fields.get('创建日期')),
            'cover': cover or old.get('cover', ''),
            'views': old.get('views', 0),  # Preserve local views
            'gallery': gallery if gallery else old.get('gallery', [])
        }

        # Preserve backup link if exists
        backup = parse_link(fields.get('备用链接'))
        if backup:
            work['backup_link'] = backup

        if work['title']:
            works.append(work)

    # Sort by date descending (newest first)
    works.sort(key=lambda w: w.get('date', ''), reverse=True)

    # Save
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(works, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Synced {len(works)} works to {data_path}")
    print(f"   Skipped {skipped} empty records")
    for w in works:
        status_icon = "🟢" if w.get('status') == '已发布' else "🟡"
        cover_icon = "🖼️" if w.get('cover') else "❌"
        print(f"   {status_icon} {cover_icon} [{w.get('category', '?')}] {w.get('title', '?')} (views: {w.get('views', 0)})")


if __name__ == '__main__':
    sync()
