import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from server.backup import backup_shop
from server.config import Settings
from server.readiness import production_check
from server.store import ShopError, Store


@pytest.fixture
def production(tmp_path, monkeypatch):
    catalog = tmp_path / 'catalog.json'
    catalog.write_text(json.dumps([{'id': 'interpark', 'plans': [{'days': 30}]}]))
    tutorials = tmp_path / 'tutorials.json'
    tutorials.write_text(json.dumps({'version': 1, 'tutorials': {'interpark': 'https://example.feishu.cn/wiki/Guide'}}))
    mapping = tmp_path / 'products.json'
    mapping.write_text(json.dumps({'interpark': 'interpark'}))
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'projects': [{'id': 'interpark', 'console_key': '$OPS_LICENSE_KEY'}]}))
    manifest = tmp_path / 'reservations.json'
    monkeypatch.setenv('TICKETPRO_PRODUCT_PROJECTS', str(mapping))
    monkeypatch.setenv('UNIFIED_LICENSE_CONFIG', str(registry))
    monkeypatch.setenv('UNIFIED_RESERVED_CODES_FILE', str(manifest))
    monkeypatch.setenv('OPS_LICENSE_KEY', 'private-license-key')
    settings = Settings(db=str(tmp_path / 'shop.sqlite3'), catalog=str(catalog), tutorials=str(tutorials),
                        pid='merchant', key='private-payment-key', cid='channel', admin_key='a' * 40,
                        site_url='https://shop.example.com', api_url='https://api.example.com/ticketpro',
                        origins=('https://shop.example.com',))
    store = Store(settings.db)
    store.import_stock([{'product_id': 'interpark', 'project_id': 'interpark', 'days': 30,
                         'code': 'OPS-PRIVATE-0001', 'binding_mode': 'machine', 'batch': 'ticketpro-web:ops-test',
                         'tutorial_url': 'https://example.feishu.cn/wiki/Guide'}], manifest)
    return settings, store, manifest


def test_production_check_requires_inventory_and_never_exposes_credentials(production):
    settings, _, _ = production
    report = production_check(settings)
    assert report['ready']
    assert report['inventory'][0]['plans'] == [{'days': 30, 'available': 1}]
    text = json.dumps(report)
    for private in ['OPS-PRIVATE-0001', settings.key, settings.admin_key, 'private-license-key']:
        assert private not in text


def test_production_check_rejects_demo_and_wrong_cors(production):
    settings, _, _ = production
    settings.demo = True
    settings.origins = ('https://another.example.com',)
    report = production_check(settings)
    failed = {c['name'] for c in report['checks'] if not c['ok']}
    assert {'production_mode', 'cors'} <= failed


def test_production_check_does_not_create_missing_database(production, tmp_path):
    settings, _, _ = production
    settings.db = str(tmp_path / 'not-created.sqlite3')
    report = production_check(settings)
    assert not report['ready']
    assert not Path(settings.db).exists()
    assert production_check(settings, config_only=True)['ready']


def test_check_requires_all_imported_codes_in_manual_exclusion_manifest(production):
    settings, _, manifest = production
    manifest.write_text('{"version":1,"projects":{}}')
    report = production_check(settings)
    assert not report['ready']
    assert next(c for c in report['checks'] if c['name'] == 'stock_isolation')['ok'] is False


def test_corrupted_manifest_cannot_report_production_ready(production):
    settings, _, manifest = production
    manifest.write_text('[]')
    report = production_check(settings)
    assert not report['ready']
    assert next(c for c in report['checks'] if c['name'] == 'inventory_manifest')['ok'] is False


def test_check_detects_changed_project_mapping(production, monkeypatch, tmp_path):
    settings, _, _ = production
    mapping = tmp_path / 'wrong.json'
    mapping.write_text('{"interpark":"another-project"}')
    monkeypatch.setenv('TICKETPRO_PRODUCT_PROJECTS', str(mapping))
    report = production_check(settings)
    assert not report['ready']
    assert next(c for c in report['checks'] if c['name'] == 'stock_source')['ok'] is False


def test_public_check_verifies_real_mode_and_rejects_unsigned_callback(production, monkeypatch):
    settings, _, _ = production
    original = httpx.Client
    def respond(request):
        assert request.url.host == 'api.example.com'
        if request.url.path.endswith('/health'):
            return httpx.Response(200, json={'ok': True, 'demo': False, 'payment_ready': True})
        assert request.url.path == '/ticketpro/commerce/zpay/notify'
        assert not request.url.query
        return httpx.Response(400, text='fail')
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    assert production_check(settings, online=True)['ready']


def test_backup_restores_matching_stock_and_is_not_changed_by_new_orders(production, tmp_path):
    settings, store, manifest = production
    backup = backup_shop(settings, tmp_path / 'backups')
    directory = Path(backup['directory'])
    assert backup['integrity'] == 'ok' and backup['stock_count'] == 1
    assert (directory.stat().st_mode & 0o777) == 0o700
    assert (directory / 'shop.sqlite3').stat().st_mode & 0o777 == 0o600
    store.create({'id': 'interpark', 'name': 'ITP'}, {'days': 30, 'duration': '1个月', 'cents': 8800},
                 'request-for-backup-test', 'private-access-key', 'client')
    with sqlite3.connect(directory / 'shop.sqlite3') as restored:
        assert restored.execute('SELECT count(*) FROM orders').fetchone()[0] == 0
        assert restored.execute("SELECT count(*) FROM stock WHERE state='available'").fetchone()[0] == 1
    assert json.loads((directory / 'web-reserved-codes.json').read_text()) == json.loads(manifest.read_text())
    assert (directory / 'complete.json').is_file()


def test_incomplete_inventory_backup_is_removed(production, tmp_path):
    settings, _, manifest = production
    manifest.write_text('{"version":1,"projects":{}}')
    directory = tmp_path / 'backups'
    with pytest.raises(ShopError):
        backup_shop(settings, directory)
    assert list(directory.iterdir()) == []
