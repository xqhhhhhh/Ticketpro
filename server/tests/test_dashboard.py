from datetime import datetime
import json
import secrets
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
import pytest

from server.app import Settings, create_app
from server.notifications import Outbox
from server.store import Store


@pytest.fixture
def merchant(tmp_path):
    settings = Settings(db=str(tmp_path/'shop.sqlite3'), tutorials='', admin_key='root-management-secret',
                        dashboard_key='merchant-read-only-secret')
    app = create_app(settings)
    store = app.state.store
    store.import_stock([{'product_id': 'interpark', 'project_id': 'interpark', 'days': 15,
                         'code': f'MERCHANT-PRIVATE-{i:04}', 'binding_mode': 'machine',
                         'batch': 'ticketpro-web:dashboard', 'tutorial_url': 'https://example.com/guide'}
                        for i in range(4)], tmp_path/'manifest.json')
    orders = []
    for index in range(4):
        order, _ = store.create({'id': 'interpark', 'name': 'Interpark'},
                                {'days': 15, 'duration': '15天', 'cents': 1 if index == 3 else 6600},
                                secrets.token_hex(16), secrets.token_hex(32), 'client')
        created = int(datetime(2026, 10, 21 if index == 0 else 22, 12, tzinfo=ZoneInfo('Europe/Berlin')).timestamp())
        with store.connection(write=True) as db:
            db.execute('UPDATE orders SET created_at=?,is_test=? WHERE id=?', (created, int(index == 3), order['id']))
        if index != 2:
            store.deliver(order['id'], 'trade-'+order['id'])
            with store.connection(write=True) as db:
                db.execute('UPDATE orders SET paid_at=? WHERE id=?', (created+60, order['id']))
        orders.append(order['id'])
    with TestClient(app) as client:
        yield client, store, orders


def headers():
    return {'Authorization': 'Bearer merchant-read-only-secret'}


def get(client, suffix='', **params):
    return client.get('/commerce/api/admin/dashboard'+suffix, params=params, headers=headers())


def test_dashboard_and_detail_require_owner_credentials(merchant):
    client, _, orders = merchant
    for path in ['/commerce/api/admin/dashboard', '/commerce/api/admin/orders/'+orders[0]+'?reveal=true']:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.get('/commerce/api/admin/summary', headers=headers()).status_code == 401
    assert get(client).status_code == 200
    assert get(client).headers['cache-control'] == 'no-store'


def test_totals_exclude_test_payments_and_unpaid_amounts(merchant):
    client, _, orders = merchant
    data = get(client, size=1).json()
    assert data['stats']['revenue'] == 13200
    assert data['stats']['paid'] == 2 and data['stats']['pending'] == 1 and data['total'] == 3
    assert len(data['orders']) == 1 and len(data['trend']) == 14
    assert data['ranking'][0]['revenue'] == 13200
    all_orders = get(client, include_tests=True).json()
    assert all_orders['stats']['revenue'] == 13201 and all_orders['stats']['paid'] == 3
    assert next(o for o in all_orders['orders'] if o['id'] == orders[3])['is_test'] == 1
    text = json.dumps(data)
    for secret in ['MERCHANT-PRIVATE', 'token_hash', 'client_hash', 'root-management-secret', 'merchant-read-only-secret', 'payment']:
        assert secret not in text


def test_filters_pagination_and_injection_do_not_change_statistics(merchant):
    client, _, orders = merchant
    paid = get(client, status='delivered', size=1).json()
    second = get(client, status='delivered', size=1, page=2).json()
    assert paid['stats']['paid'] == 2 and paid['stats']['revenue'] == 13200
    assert paid['orders'][0]['id'] != second['orders'][0]['id']
    assert get(client, q=orders[0]).json()['orders'][0]['id'] == orders[0]
    assert get(client, product='interpark', status='pending').json()['stats']['pending'] == 1
    assert get(client, q="' OR 1=1 --").json()['total'] == 0
    assert get(client, page=99).json()['orders'] == []


def test_date_range_is_inclusive_in_merchant_timezone(merchant):
    client, store, orders = merchant
    with store.connection(write=True) as db:
        boundary = int(datetime(2026, 10, 21, 23, 59, 59, tzinfo=ZoneInfo('Europe/Berlin')).timestamp())
        db.execute('UPDATE orders SET created_at=?,paid_at=? WHERE id=?', (boundary, boundary, orders[0]))
    data = get(client, start='2026-10-21', end='2026-10-21').json()
    assert data['total'] == 1 and data['orders'][0]['id'] == orders[0]
    assert data['trend'][-1]['orders'] == 1 and data['trend'][-1]['revenue'] == 6600


@pytest.mark.parametrize('params', [{'status': 'fake'}, {'product': 'fake'}, {'start': 'bad'},
                                  {'start': '2026-10-22', 'end': '2026-10-21'}, {'end': '9999-12-31'}])
def test_invalid_filters_are_rejected(merchant, params):
    client, *_ = merchant
    assert get(client, **params).status_code == 400


def test_detail_reveals_only_sold_code_and_never_buyer_or_payment_secrets(merchant):
    client, store, orders = merchant
    base = '/commerce/api/admin/orders/'
    detail = client.get(base+orders[0], headers=headers()).json()
    assert 'code' not in detail and detail['code_suffix'] == '0000'
    revealed = client.get(base+orders[0]+'?reveal=true', headers=headers()).json()
    assert revealed['code'] == 'MERCHANT-PRIVATE-0000'
    pending = client.get(base+orders[2]+'?reveal=true', headers=headers()).json()
    assert 'code' not in pending and pending['code_suffix'] == ''
    for field in ('token_hash', 'client_hash', 'payment', 'request_id'):
        assert field not in revealed
    assert client.get(base+'does-not-exist', headers=headers()).status_code == 404
    job = Outbox(store).claim()
    Outbox(store).finish(job)
    assert client.get(base+job['order_id'], headers=headers()).json()['notification_status'] == 'sent'


def test_reading_dashboard_does_not_mutate_orders_stock_or_notifications(merchant):
    client, store, orders = merchant
    def snapshot():
        with store.connection() as db:
            return {table: [tuple(row) for row in db.execute('SELECT * FROM '+table)]
                    for table in ('orders', 'stock', 'order_notifications')}
    before = snapshot()
    for _ in range(3):
        assert get(client).status_code == 200
        assert client.get('/commerce/api/admin/orders/'+orders[0]+'?reveal=true', headers=headers()).status_code == 200
    assert snapshot() == before


def test_legacy_order_table_migrates_without_changing_delivery_records(merchant):
    _, store, orders = merchant
    original = store.order(orders[0])
    with store.connection(write=True) as db:
        db.execute('ALTER TABLE orders DROP COLUMN is_test')
    reopened = Store(store.path)
    migrated = reopened.order(orders[0])
    assert migrated['is_test'] == 0 and migrated['trade_no'] == original['trade_no']
    assert migrated['status'] == 'delivered'
