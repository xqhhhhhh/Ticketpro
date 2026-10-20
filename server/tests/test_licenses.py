import json
from pathlib import Path

import httpx
from httpx import Client as HttpClient
import pytest

from server.licenses import prepare_stock
from server.store import ShopError


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'projects': [{
        'id': 'interpark', 'base_url': 'https://license.example.com',
        'console_key': '$SOURCE_TEST_KEY', 'lookup_path': '/console/api/code',
    }]}))
    monkeypatch.setenv('SOURCE_TEST_KEY', 'upstream-secret')
    info = {'code': 'TEST-CODE-001', 'status': 'NEW', 'plan_days': 30, 'binding_mode': 'machine',
            'note': 'ticketpro-web:test', 'revoked': False}
    original = httpx.Client
    def respond(request):
        assert request.headers['x-console-key'] == 'upstream-secret'
        if request.url.path.endswith('/settings'):
            return httpx.Response(200, json={'tutorial_url': 'https://example.com/tutorial'})
        assert json.loads(request.content)['activation_code'] == 'TEST-CODE-001'
        return httpx.Response(200, json={'ok': True, 'code_info': info})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    return registry, info


def prepare(registry):
    return prepare_stock(registry, 'interpark', 'interpark', 30, 'ticketpro-web:test',
                         ['TEST-CODE-001'], '')


def test_import_uses_original_project_auth_and_tutorial(upstream):
    registry, _ = upstream
    item = prepare(registry)[0]
    assert item['code'] == 'TEST-CODE-001'
    assert item['tutorial_url'] == 'https://example.com/tutorial'


def test_hash_only_ocr_lookup_must_match_returned_code_suffix(upstream):
    registry, info = upstream
    info.pop('code')
    info['code_last4'] = 'E001'
    assert prepare(registry)[0]['code'] == 'TEST-CODE-001'
    info['code_last4'] = 'BAD0'
    with pytest.raises(ShopError):
        prepare(registry)
    info.pop('code_last4')
    with pytest.raises(ShopError):
        prepare(registry)


def test_reported_full_code_must_match_even_when_suffix_is_equal(upstream):
    registry, info = upstream
    info.update(code='DIFFERENT-CODE-001', code_last4='E001')
    with pytest.raises(ShopError):
        prepare(registry)
    info['code'] = 'TESTCODE001'
    assert prepare(registry)[0]['code'] == 'TEST-CODE-001'


@pytest.mark.parametrize('changes', [
    {'status': 'ACTIVE'}, {'plan_days': 365}, {'binding_mode': 'none'},
    {'revoked': True}, {'note': 'old-manually-sold-batch'}, {'activated_at_ms': 12345},
    {'code': 'A-DIFFERENT-CODE'}, {'expires_at_ms': 12345}, {'device_count': 1},
    {'legacy_device_id_masked': 'previous-device'},
])
def test_reject_incompatible_or_previously_used_stock(upstream, changes):
    registry, info = upstream
    info.update(changes)
    with pytest.raises(ShopError):
        prepare(registry)


@pytest.mark.parametrize('project', ['galaxyticketing', 'hkticketing', 'fantopia', 'klook'])
def test_project_specific_lookup_endpoints(upstream, monkeypatch, project):
    registry, info = upstream
    data = json.loads(registry.read_text())
    data['projects'][0]['id'] = project
    data['projects'][0].pop('lookup_path', None)
    registry.write_text(json.dumps(data))
    def respond(request):
        assert request.url.path == '/console/api/lookup'
        return httpx.Response(200, json={'code_info': info})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: HttpClient(transport=httpx.MockTransport(respond), **kw))
    item = prepare_stock(registry, project, project, 30, 'ticketpro-web:test', ['TEST-CODE-001'], 'https://example.com/tutorial')[0]
    assert item['project_id'] == project


def test_ticketplus_batch_field_is_verified(upstream):
    registry, info = upstream
    info['batch'] = info.pop('note')
    assert prepare(registry)[0]['batch'] == info['batch']


def test_allticket_checks_actual_admin_batch_and_refuses_used_stock(tmp_path, monkeypatch):
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'projects': [{'id': 'allticket-leofest', 'base_url': 'https://allticket.example.com',
                        'console_key': '$AT_KEY', 'admin_password': '$AT_PASSWORD', 'stock_adapter': 'allticket'}]}))
    monkeypatch.setenv('AT_KEY', 'console-secret')
    monkeypatch.setenv('AT_PASSWORD', 'admin-secret')
    raw = {'code': 'AT-WEB-001', 'batch': 'TICKETPRO_WEB_TEST', 'days': 30, 'binding_mode': 'machine',
           'activated_at': None, 'expires_at': None, 'device_id': '', 'revoked_at': None}
    original = httpx.Client
    def respond(request):
        if request.url.path.endswith('/login'):
            assert json.loads(request.content) == {'password': 'admin-secret'}
            return httpx.Response(200, json={'ok': True})
        assert request.method == 'GET' and request.url.path == '/api/admin/codes'
        assert request.url.params['code'] == raw['code']
        return httpx.Response(200, json=[raw])
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    args = (registry, 'allticket', 'allticket-leofest', 30, 'TICKETPRO_WEB_TEST', ['AT-WEB-001'], 'https://example.com/tutorial')
    assert prepare_stock(*args)[0]['batch'] == raw['batch']
    raw['activated_at'] = 12345
    with pytest.raises(ShopError):
        prepare_stock(*args)


@pytest.mark.parametrize('project', ['galaxyticketing', 'hkticketing'])
def test_console_session_is_used_when_login_password_differs_from_api_key(tmp_path, monkeypatch, project):
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'projects': [{'id': project, 'base_url': 'https://license.example.com',
                        'login_path': '/console/api/login', 'admin_password': '$LOGIN_PASSWORD'}]}))
    monkeypatch.setenv('LOGIN_PASSWORD', 'console-login-secret')
    original = HttpClient
    def respond(request):
        if request.url.path.endswith('/login'):
            assert json.loads(request.content) == {'password': 'console-login-secret'}
            return httpx.Response(200, json={'ok': True}, headers={'Set-Cookie': 'console_session=test-session; Path=/; Secure; HttpOnly'})
        assert request.headers['cookie'] == 'console_session=test-session'
        assert request.url.path == '/console/api/lookup'
        return httpx.Response(200, json={'license': {'code': 'SESSION-TEST-001', 'status': 'NEW',
                              'plan_days': 30, 'binding_mode': 'machine', 'note': 'ticketpro-web:session'}})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    items = prepare_stock(registry, project, project, 30, 'ticketpro-web:session', ['SESSION-TEST-001'], 'https://example.com/tutorial')
    assert len(items) == 1


def test_fleet_device_binding_and_separate_edition_must_match(upstream):
    registry, info = upstream
    data = json.loads(registry.read_text())
    data['projects'][0].update(stock_adapter='fleet', plan_tier='pro')
    registry.write_text(json.dumps(data))
    info.update(binding_mode='device', device_binding_required=True, plan_tier='pro',
                batch_name=info.pop('note'), note='用户自定义说明')
    assert prepare(registry)[0]['binding_mode'] == 'machine'
    info['plan_tier'] = 'ultra'
    with pytest.raises(ShopError):
        prepare(registry)
    info.update(plan_tier='pro', device_binding_required=False)
    with pytest.raises(ShopError):
        prepare(registry)


@pytest.mark.parametrize('product', ['nol-fleet', 'melon-fleet'])
def test_configured_fleet_products_accept_only_professional_stock(upstream, product):
    registry, info = upstream
    root = Path(__file__).resolve().parents[1]
    mapping = json.loads((root / 'product-projects.json').read_text())
    projects = json.loads((root / 'license-projects.json').read_text())['projects']
    project = next(p for p in projects if p['id'] == mapping[product])
    # Keep the real product/edition rules, with the fixture's isolated transport and credentials.
    project = {**project, 'base_url': 'https://license.example.com', 'console_key': '$SOURCE_TEST_KEY'}
    project.pop('login_path', None)
    registry.write_text(json.dumps({'projects': [project]}))
    info.update(binding_mode='device', device_binding_required=True, plan_tier='ultra',
                batch_name=info.pop('note'))
    args = (registry, product, project['id'], 30, 'ticketpro-web:test', ['TEST-CODE-001'], 'https://example.com/tutorial')
    assert prepare_stock(*args)[0]['project_id'] == project['id']
    for lower_tier in ['basic', 'pro']:
        info['plan_tier'] = lower_tier
        with pytest.raises(ShopError):
            prepare_stock(*args)
