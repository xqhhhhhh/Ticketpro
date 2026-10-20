"""Read the existing unified registry; validate website batches against the original license service."""
import json
import os
from pathlib import Path
import re

import httpx

from .gateway import https_url
from .store import ShopError, code_hash


def env_value(value):
    return os.getenv(value[1:], '') if isinstance(value, str) and value.startswith('$') else value


def website_batch(batch):
    # AllTicket's original batch field accepts only A-Z, digits, underscore and dash.
    return bool(re.fullmatch(r'ticketpro-web:[A-Za-z0-9_-]+|TICKETPRO_WEB_[A-Z0-9_-]+', batch))


def load_projects(path):
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or not isinstance(data.get('projects'), list):
        raise ShopError('授权项目注册表格式错误')
    return {p['id']: p for p in data['projects'] if p.get('enabled', True)}


def matches_lookup_code(info, code):
    reported = info.get('code') or info.get('activation_code')
    if reported:
        return code_hash(str(reported)) == code_hash(code)
    # Older OCR services store only a hash and last four characters. Their
    # authenticated lookup hashes the complete requested code before returning a row.
    normalized = re.sub('[^A-Z0-9]', '', code.upper())
    last4 = str(info.get('code_last4') or '').strip().upper()
    return len(normalized) >= 8 and len(last4) == 4 and last4 == normalized[-4:]


def lookup_code(client, base, project, headers, code):
    if project.get('stock_adapter') == 'allticket':
        response = client.get(base + '/api/admin/codes', params={'code': code})
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or len(rows) != 1:
            raise ShopError('原授权系统未找到唯一的库存记录')
        raw = rows[0]
        return {'code': raw.get('code'), 'status': 'NEW', 'plan_days': raw.get('days'),
                'binding_mode': raw.get('binding_mode'), 'note': raw.get('batch'),
                'activated_at_ms': raw.get('activated_at'), 'expires_at_ms': raw.get('expires_at'),
                'bound_device_id_masked': raw.get('device_id'), 'revoked': raw.get('revoked_at')}
    default_path = '/console/api/lookup' if project['id'] in {
        'galaxyticketing', 'hkticketing', 'fantopia', 'klook'} else '/console/api/code'
    response = client.post(base + (project.get('lookup_path') or default_path),
                           headers=headers, json={'activation_code': code})
    response.raise_for_status()
    data = response.json()
    info = dict(data.get('code_info') or data.get('license') or {})
    # Legacy consoles render an empty device ID as "-". Preserve every actual
    # masked ID so previously bound codes remain ineligible for website stock.
    for field in ('bound_device_id_masked', 'legacy_device_id_masked'):
        if info.get(field) == '-':
            info[field] = ''
    if project.get('stock_adapter') == 'fleet':
        info['note'] = info.get('batch_name')
        if info.get('binding_mode') == 'device' and info.get('device_binding_required') is True:
            info['binding_mode'] = 'machine'
    return info


def prepare_stock(registry_path, product_id, project_id, days, batch, codes, tutorial_url):
    if not website_batch(batch):
        raise ShopError('只能导入 ticketpro-web: 或 TICKETPRO_WEB_ 开头的网站专用批次')
    project = load_projects(registry_path).get(project_id)
    if not project:
        raise ShopError('授权系统中未找到对应项目')
    base = (env_value(project.get('upstream_url', '')) or project['base_url']).rstrip('/')
    if not base.startswith(('https://', 'http://127.0.0.1:', 'http://localhost:')):
        raise ShopError('授权接口必须使用 HTTPS 或服务器本机地址')
    key = env_value(project.get('console_key', ''))
    login_path = project.get('login_path') or ('/api/admin/login' if project.get('stock_adapter') == 'allticket' else '')
    password = env_value(project.get('admin_password', ''))
    if not key and not (login_path and password):
        raise ShopError('授权项目密钥未配置')
    headers = {'X-Console-Key': key, 'X-Admin-Token': key}
    items, seen = [], set()
    with httpx.Client(timeout=8) as client:
        if login_path:
            if not password:
                raise ShopError('原项目管理台登录密码未配置，无法验证专用批次')
            response = client.post(base + login_path, json={'password': password})
            response.raise_for_status()
        if not tutorial_url:
            response = client.get(base + '/console/api/settings', headers=headers)
            response.raise_for_status()
            tutorial_url = response.json().get('tutorial_url', '')
        if not https_url(tutorial_url):
            raise ShopError('每个商品必须配置 HTTPS 安装与使用教程链接')
        for code in codes:
            code = code.strip().upper()
            if not code or code_hash(code) in seen:
                continue
            seen.add(code_hash(code))
            info = lookup_code(client, base, project, headers, code)
            if (not matches_lookup_code(info, code)
                    or info.get('status') != 'NEW' or info.get('revoked') or info.get('activated_at_ms')
                    or info.get('expires_at_ms') or info.get('bound_device_id_masked')
                    or info.get('legacy_device_id_masked') or info.get('device_count')
                    or info.get('plan_days') != days
                    or info.get('binding_mode') != 'machine' or (info.get('note') or info.get('batch')) != batch
                    or (project.get('plan_tier') and info.get('plan_tier') != project['plan_tier'])):
                raise ShopError('库存校验失败：必须是对应项目、期限、未使用的绑机码，且批次备注完全一致')
            items.append({'product_id': product_id, 'project_id': project_id, 'days': days, 'code': code,
                          'binding_mode': 'machine', 'batch': batch,
                          'tutorial_url': tutorial_url})
    if not items:
        raise ShopError('库存文件为空')
    return items
