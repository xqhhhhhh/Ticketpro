from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import secrets
import sqlite3
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from server.app import DemoGateway, Settings, create_app
from server.gateway import GatewayError, Zpay, cents, sign, verified_payment
from server.store import ShopError, Store
from server.reconcile import reconcile_orders
from server.unified_reservations import is_website_code, website_reservations


class FakeGateway(DemoGateway):
    def __init__(self):
        super().__init__()
        self.pid, self.key = 'merchant-test', 'private-server-key'
        self.query_count = 0

    def create(self, order, _ip):
        return {'qrcode': f'https://zpayz.cn/test/{order["id"]}', 'payurl': 'https://zpayz.cn/test'}

    def query(self, order_id):
        self.query_count += 1
        return super().query(order_id)


@pytest.fixture
def shop(tmp_path):
    settings = Settings(db=str(tmp_path / 'shop.db'), admin_key='admin-secret', tutorials='')
    gateway = FakeGateway()
    app = create_app(settings, gateway)
    store = app.state.store
    items = [{'product_id': 'interpark', 'days': 30, 'project_id': 'interpark',
              'code': f'ITP-WEB-TEST-{n:04}', 'binding_mode': 'machine', 'batch': 'ticketpro-web:test',
              'tutorial_url': 'https://example.com/tutorial'} for n in range(8)]
    manifest = tmp_path / 'manifest.json'
    store.import_stock(items, manifest)
    with TestClient(app) as client:
        yield client, store, gateway, manifest


def new_order(client, **changes):
    key = secrets.token_hex(32)
    body = {'product_id': 'interpark', 'days': 30, 'request_id': secrets.token_hex(16), 'access_key': key}
    body.update(changes)
    response = client.post('/commerce/api/orders', json=body)
    assert response.status_code == 200, response.text
    return response.json(), key, body


def paid(gateway, order, **changes):
    data = {'code': 1, 'status': 1, 'pid': gateway.pid, 'type': 'alipay',
            'money': '88.00', 'out_trade_no': order['id'], 'trade_no': 'transaction-' + order['id']}
    data.update(changes)
    gateway.paid[order['id']] = data
    return data


def callback(gateway, order, **changes):
    params = {'pid': gateway.pid, 'type': 'alipay', 'money': '88.00',
              'out_trade_no': order['id'], 'trade_no': 'transaction-' + order['id'], 'trade_status': 'TRADE_SUCCESS'}
    params.update(changes)
    params['sign'] = sign(params, gateway.key)
    params['sign_type'] = 'MD5'
    return params


def auth(key):
    return {'Authorization': 'Bearer ' + key}


def test_no_code_before_paid_and_private_order_access(shop):
    client, store, gateway, _ = shop
    order, key, _ = new_order(client)
    assert order['cents'] == 8800 and order['delivery'] is None
    assert client.get('/commerce/api/orders/' + order['id']).status_code == 404
    assert client.get('/commerce/api/orders/' + order['id'], headers=auth('0' * 64)).status_code == 404
    assert client.get('/commerce/api/orders/' + order['id'], headers=auth(key)).json()['delivery'] is None
    assert 'private-server-key' not in json.dumps(order)
    assert store.counts()[('interpark', 30)] == 7


def test_price_tampering_not_accepted(shop):
    client, *_ = shop
    body = {'product_id': 'interpark', 'days': 30, 'request_id': secrets.token_hex(16),
            'access_key': secrets.token_hex(32), 'money': '0.01'}
    assert client.post('/commerce/api/orders', json=body).status_code == 422
    body.pop('money'); body['days'] = 123
    assert client.post('/commerce/api/orders', json=body).status_code == 400


def test_idempotent_creation_and_token_isolation(shop):
    client, store, *_ = shop
    first, key, body = new_order(client)
    assert client.post('/commerce/api/orders', json=body).json()['id'] == first['id']
    assert store.counts()[('interpark', 30)] == 7
    body['access_key'] = secrets.token_hex(32)
    assert client.post('/commerce/api/orders', json=body).status_code == 409


def test_verified_callback_ships_once_and_survives_restart(shop):
    client, store, gateway, manifest = shop
    order, key, _ = new_order(client)
    paid(gateway, order)
    params = callback(gateway, order)
    assert client.get('/commerce/zpay/notify', params=params).text == 'success'
    delivered = client.get('/commerce/api/orders/' + order['id'], headers=auth(key)).json()
    assert delivered['status'] == 'delivered'
    code = delivered['delivery']['code']
    assert set(delivered['delivery']) == {'code', 'binding_mode', 'tutorial_url'}
    assert code.startswith('ITP-WEB-TEST-')
    for _ in range(3):
        assert client.get('/commerce/zpay/notify', params=params).text == 'success'
    assert gateway.query_count == 1
    reopened = Store(store.path)
    assert reopened.public_order(reopened.order(order['id'], key))['delivery']['code'] == code


@pytest.mark.parametrize('change', [
    {'money': '0.01'}, {'pid': 'another-shop'}, {'status': 0},
    {'out_trade_no': 'someone-else'}, {'trade_no': 'wrong-trade'}, {'type': 'wxpay'},
])
def test_signed_callback_still_requires_correct_provider_record(shop, change):
    client, store, gateway, _ = shop
    order, key, _ = new_order(client)
    paid(gateway, order, **change)
    assert client.get('/commerce/zpay/notify', params=callback(gateway, order)).text == 'fail'
    assert store.order(order['id'])['status'] == 'pending'


def test_reject_forged_and_duplicate_callback_parameters(shop):
    client, _, gateway, _ = shop
    order, *_ = new_order(client)
    params = callback(gateway, order)
    params['money'] = '0.01'
    assert client.get('/commerce/zpay/notify', params=params).status_code == 400
    params = list(callback(gateway, order).items()) + [('money', '88.00')]
    assert client.get('/commerce/zpay/notify', params=params).status_code == 400
    assert gateway.query_count == 0


def test_duplicate_transaction_cannot_deliver_two_orders(shop):
    client, store, gateway, _ = shop
    first, *_ = new_order(client)
    second, *_ = new_order(client)
    paid(gateway, first)
    paid(gateway, second, trade_no='transaction-' + first['id'])
    assert client.get('/commerce/zpay/notify', params=callback(gateway, first)).text == 'success'
    assert client.get('/commerce/zpay/notify', params=callback(gateway, second, trade_no='transaction-' + first['id'])).text == 'fail'
    assert store.order(second['id'])['status'] == 'pending'


def test_missing_notification_recovered_by_authenticated_recheck(shop):
    client, _, gateway, _ = shop
    order, key, _ = new_order(client)
    paid(gateway, order)
    assert client.post(f'/commerce/api/orders/{order["id"]}/refresh', headers=auth(key)).json()['status'] == 'delivered'


def test_scheduled_reconcile_recovers_missing_callback_once(shop):
    client, store, gateway, _ = shop
    order, key, _ = new_order(client)
    paid(gateway, order)
    assert reconcile_orders(store, gateway) == {'checked': 1, 'delivered': 1, 'failed': 0}
    code = store.public_order(store.order(order['id'], key))['delivery']['code']
    assert reconcile_orders(store, gateway) == {'checked': 0, 'delivered': 0, 'failed': 0}
    assert store.public_order(store.order(order['id'], key))['delivery']['code'] == code


def test_reconcile_does_not_ship_after_gateway_failure_and_reports_failure(shop):
    client, store, gateway, _ = shop
    order, *_ = new_order(client)
    gateway.query = Mock(side_effect=GatewayError('unavailable'))
    assert reconcile_orders(store, gateway) == {'checked': 1, 'delivered': 0, 'failed': 1}
    assert store.order(order['id'])['status'] == 'pending'
    assert store.counts()[('interpark', 30)] == 7


def test_provider_outage_does_not_ship_and_keeps_reservation(shop):
    client, store, gateway, _ = shop
    order, key, _ = new_order(client)
    gateway.query = Mock(side_effect=GatewayError('unavailable'))
    assert client.post(f'/commerce/api/orders/{order["id"]}/refresh', headers=auth(key)).status_code == 502
    assert store.order(order['id'])['status'] == 'pending'
    assert store.counts()[('interpark', 30)] == 7


def test_concurrent_orders_cannot_reserve_same_code(shop):
    _, store, *_ = shop
    product = {'id': 'interpark', 'name': 'Interpark'}
    plan = {'days': 30, 'duration': '1个月', 'cents': 8800}
    def create(n):
        try:
            return store.create(product, plan, secrets.token_hex(16), secrets.token_hex(32), str(n))[0]['id']
        except ShopError as error:
            assert error.message == 'out_of_stock'
            return None
    with ThreadPoolExecutor(max_workers=12) as pool:
        orders = list(pool.map(create, range(12)))
    assert len([o for o in orders if o]) == 8
    with store.connection() as db:
        assert db.execute("SELECT count(DISTINCT order_id) FROM stock WHERE state='reserved'").fetchone()[0] == 8


def test_no_release_of_pending_holds_and_rate_limit(shop):
    client, store, *_ = shop
    for _ in range(5):
        new_order(client)
    response = client.post('/commerce/api/orders', json={
        'product_id': 'interpark', 'days': 30, 'request_id': secrets.token_hex(16), 'access_key': secrets.token_hex(32)})
    assert response.status_code == 429
    assert store.counts()[('interpark', 30)] == 3


def test_return_page_never_delivers_without_query(shop):
    client, store, gateway, _ = shop
    order, *_ = new_order(client)
    response = client.get('/commerce/zpay/return', params=callback(gateway, order), follow_redirects=False)
    assert response.status_code == 303
    assert store.order(order['id'])['status'] == 'pending'
    assert gateway.query_count == 0


def test_unified_inventory_excludes_all_web_codes_and_fails_closed(shop, monkeypatch):
    _, _, _, manifest = shop
    monkeypatch.setenv('UNIFIED_RESERVED_CODES_FILE', str(manifest))
    hashes = website_reservations('interpark')
    assert is_website_code('ITP-WEB-TEST-0000', hashes)
    assert is_website_code('itpwebtest0000', hashes)
    assert not is_website_code('MANUAL-SALE-0000', hashes)
    manifest.unlink()
    with pytest.raises(OSError):
        website_reservations('interpark')


def test_duplicate_import_rolls_back(shop):
    _, store, _, manifest = shop
    item = {'product_id': 'interpark', 'days': 30, 'project_id': 'interpark', 'code': 'ITP-WEB-TEST-0000',
            'binding_mode': 'machine', 'batch': 'ticketpro-web:test', 'tutorial_url': ''}
    before = manifest.read_bytes()
    with pytest.raises(sqlite3.IntegrityError):
        store.import_stock([item], manifest)
    assert manifest.read_bytes() == before
    assert store.counts()[('interpark', 30)] == 8


def test_demo_and_production_databases_cannot_mix(tmp_path):
    Store(tmp_path / 'demo.db', demo=True)
    with pytest.raises(ShopError):
        Store(tmp_path / 'demo.db', demo=False)


def test_no_public_admin_endpoint(shop):
    client, *_ = shop
    assert client.get('/commerce/api/admin/summary').status_code == 401
    data = client.get('/commerce/api/admin/summary', headers={'Authorization': 'Bearer admin-secret'}).json()
    assert len(data['stock']) == 1
    assert 'code' not in data['stock'][0]


def test_delivered_order_uses_its_product_tutorial_without_package_link(shop):
    client, store, gateway, _ = shop
    store.tutorials = {'interpark': 'https://example.feishu.cn/wiki/InterparkGuide',
                       'melon': 'https://example.feishu.cn/wiki/MelonGuide'}
    order, key, _ = new_order(client)
    assert order['delivery'] is None
    paid(gateway, order)
    assert client.get('/commerce/zpay/notify', params=callback(gateway, order)).text == 'success'
    delivery = client.get('/commerce/api/orders/' + order['id'], headers=auth(key)).json()['delivery']
    assert delivery['tutorial_url'] == 'https://example.feishu.cn/wiki/InterparkGuide'
    assert 'download_url' not in delivery


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '0.001'])
def test_invalid_amounts(value):
    with pytest.raises(GatewayError):
        cents(value)


def test_zpay_wire_format_and_no_key_in_checkout(monkeypatch):
    original = httpx.Client
    def respond(request):
        if request.url.path == '/mapi.php':
            assert 'multipart/form-data' in request.headers['content-type']
            body = request.content.decode()
            assert 'name="sign"' in body and 'name="return_url"' in body
            assert 'server-secret' not in body
            return httpx.Response(200, json={'code': 1, 'qrcode': 'https://qr.alipay.com/test'})
        return httpx.Response(200, json={'code': 1, 'status': 0})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    gateway = Zpay('merchant', 'server-secret', '25492', 'https://api.example.com', 'https://shop.example.com')
    payment = gateway.create({'id': '123', 'cents': 8800, 'name': '插件', 'duration': '1个月'}, '127.0.0.1')
    assert payment['qrcode'] == 'https://qr.alipay.com/test'
    assert 'server-secret' not in json.dumps(payment)
    assert gateway.query('123')['status'] == 0
