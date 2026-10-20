"""Read-only production checks. Never create orders, consume stock or print secrets."""
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

import httpx

from .config import ROOT
from .gateway import https_url
from .licenses import env_value, load_projects, website_batch
from .store import code_hash
from .tutorials import load_tutorials


def production_check(settings, products=None, config_only=False, online=False):
    checks = []

    def check(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    check('production_mode', not settings.demo, '正式服务必须关闭本地演示模式')
    for name, value in [('ZPAY_PID', settings.pid), ('ZPAY_KEY', settings.key),
                        ('ZPAY_CID', settings.cid)]:
        check(name, bool(value), '已配置' if value else '未配置')
    check('admin_key', len(settings.admin_key) >= 32, '订单管理密钥至少需要 32 个字符')
    site, api = urlsplit(settings.site_url), urlsplit(settings.api_url)
    site_ok = bool(https_url(settings.site_url) and site.path in ('', '/')
                   and not site.query and not site.fragment)
    api_ok = bool(https_url(settings.api_url) and not api.query and not api.fragment)
    check('site_url', site_ok, '正式商品站须使用不带路径、查询参数或 fragment 的 HTTPS 地址')
    check('api_url', api_ok, '正式订单接口须使用 HTTPS，可带部署路径')
    check('cors', site_ok and settings.site_url.rstrip('/') in settings.origins,
          '允许的来源必须包含正式商品站地址')

    catalog = json.loads(Path(settings.catalog).read_text())
    catalog_ids = {p['id'] for p in catalog}
    selected = set(products or catalog_ids)
    check('products', bool(selected) and selected <= catalog_ids, '检查所选商品是否在商品目录中')
    mapping = json.loads(Path(os.getenv('TICKETPRO_PRODUCT_PROJECTS', ROOT / 'product-projects.json')).read_text())
    projects = load_projects(os.getenv('UNIFIED_LICENSE_CONFIG', str(ROOT / 'license-projects.json')))
    tutorials = load_tutorials(settings.tutorials)
    for product in sorted(selected & catalog_ids):
        project = projects.get(mapping.get(product))
        check(product + '.project', project is not None, '授权项目对应关系已核实' if project else '尚未确定授权项目或版本')
        check(product + '.tutorial', product in tutorials, '安装与使用教程已配置' if product in tutorials else '缺少教程')
        if project:
            if project.get('login_path') or project.get('stock_adapter') == 'allticket':
                check(product + '.admin_password', bool(env_value(project.get('admin_password', ''))), '原项目专用批次校验需要管理台登录凭据')
            else:
                check(product + '.license_key', bool(env_value(project.get('console_key', ''))), '原授权服务凭据必须在服务端配置')

    inventory = []
    if not config_only:
        rows = []
        if Path(settings.db).exists():
            try:
                with sqlite3.connect(Path(settings.db).resolve().as_uri() + '?mode=ro', uri=True) as db:
                    db.row_factory = sqlite3.Row
                    db.execute('BEGIN')
                    mode = db.execute("SELECT value FROM shop_metadata WHERE key='mode'").fetchone()
                    check('database_mode', mode and mode['value'] == 'production', '数据库必须属于正式环境')
                    check('database_integrity', db.execute('PRAGMA quick_check').fetchone()[0] == 'ok', 'SQLite 完整性检查')
                    rows = [dict(r) for r in db.execute('SELECT * FROM stock')]
            except sqlite3.Error:
                check('database', False, '数据库不可读或结构不正确')
        else:
            check('database', False, '正式订单数据库尚未创建')
        manifest_path = os.getenv('UNIFIED_RESERVED_CODES_FILE', '')
        manifest = {}
        try:
            data = json.loads(Path(manifest_path).read_text()) if manifest_path else {}
            if not isinstance(data, dict):
                raise ValueError('invalid_manifest')
            manifest = data.get('projects', {})
            valid = (data.get('version') == 1 and isinstance(manifest, dict)
                     and all(isinstance(hashes, list) and all(isinstance(h, str) and re.fullmatch('[a-f0-9]{64}', h)
                            for h in hashes) for hashes in manifest.values()))
            if not valid:
                manifest = {}
            check('inventory_manifest', valid, '统一管理台与网站必须读取同一份有效隔离清单')
        except (OSError, ValueError, TypeError):
            check('inventory_manifest', False, '库存隔离清单未配置、不可读或损坏')
        reserved = {key: set(value) for key, value in manifest.items()}
        check('stock_isolation', all(row['code_hash'] in reserved.get(row['project_id'], set()) for row in rows),
              '全部网站库存（含已售与待付款）必须保留在人工发码隔离清单中')
        check('stock_source', all(not row['code'].startswith('DEMO-') and website_batch(row['batch'])
                                 and row['binding_mode'] == 'machine' and row['code_hash'] == code_hash(row['code'])
                                 and mapping.get(row['product_id']) == row['project_id'] for row in rows),
              '库存必须来自对应项目的网站专用绑机批次，不得含演示码')
        for product in catalog:
            if product['id'] not in selected:
                continue
            plans = [{'days': plan['days'], 'available': sum(row['product_id'] == product['id']
                     and row['days'] == plan['days'] and row['state'] == 'available' for row in rows)}
                     for plan in product['plans']]
            inventory.append({'product_id': product['id'], 'plans': plans})
            check(product['id'] + '.stock', any(p['available'] for p in plans), '至少一个档位有正式可售库存；空档位保持停售')
    if online:
        if not api_ok:
            check('public_api', False, '先配置正式 HTTPS 接口地址')
        else:
            try:
                with httpx.Client(timeout=8) as client:
                    health = client.get(settings.api_url + '/commerce/api/health')
                    health.raise_for_status()
                    status = health.json()
                    check('public_api', status.get('ok') and status.get('demo') is False and status.get('payment_ready'),
                          '公网接口必须为已配置支付的正式服务')
                    callback = client.get(settings.api_url + '/commerce/zpay/notify')
                    check('public_callback', callback.status_code == 400 and callback.text == 'fail',
                          '回调路由可达，并拒绝未签名请求；真实到账通知仍需付款联调')
            except (httpx.HTTPError, ValueError):
                check('public_api', False, '公网订单接口不可用或响应格式错误')
    return {'ready': all(c['ok'] for c in checks), 'scope': 'configuration' if config_only else 'production',
            'checks': checks, 'inventory': inventory, 'real_payment_test': '仍需人工扫码验证支付、回调、领取与插件激活'}
