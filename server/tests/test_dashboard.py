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
                    for table in ('orders', 'stock', 'order_notifications', 'settlement_checks', 'settlement_history')}
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


def settlement(client, order_id, **changes):
    return client.post('/commerce/api/admin/orders/'+order_id+'/settlement',
                       json={'status': 'received', 'revision': 0, **changes}, headers=headers())


def test_paid_orders_never_imply_actual_alipay_credit(merchant):
    client, _, orders = merchant
    data = get(client).json()
    assert data['stats']['received_orders'] == 0
    assert data['stats']['not_received_orders'] == 0
    assert data['stats']['unverified_orders'] == 2
    assert all(o['settlement_status'] == 'unverified' for o in data['orders'])
    detail = client.get('/commerce/api/admin/orders/'+orders[0], headers=headers()).json()
    assert detail['settlement']['source'] == 'unavailable'
    assert detail['settlement']['received_cents'] is None
    assert detail['settlement_history'] == []


def test_owner_confirmation_records_actual_amount_without_changing_payment_or_delivery(merchant):
    client, store, orders = merchant
    before = store.order(orders[0])
    with store.connection() as db:
        stock = [tuple(r) for r in db.execute('SELECT * FROM stock')]
        notifications = [tuple(r) for r in db.execute('SELECT * FROM order_notifications')]
    result = settlement(client, orders[0], received_cents=6500, received_date='2026-10-22', note='账单核对 001')
    assert result.status_code == 200
    check = result.json()['settlement']
    assert check['status'] == 'received' and check['source'] == 'merchant_check'
    assert check['received_cents'] == 6500 and check['received_date'] == '2026-10-22'
    assert check['note'] == '账单核对 001' and check['revision'] == 1
    assert 'code' not in result.json()
    assert store.order(orders[0]) == before
    with store.connection() as db:
        assert stock == [tuple(r) for r in db.execute('SELECT * FROM stock')]
        assert notifications == [tuple(r) for r in db.execute('SELECT * FROM order_notifications')]
    data = get(client).json()
    assert data['stats']['received_orders'] == 1 and data['stats']['unverified_orders'] == 1
    assert data['stats']['revenue'] == 13200


def test_corrections_are_audited_and_do_not_invent_net_amounts(merchant):
    client, _, orders = merchant
    first = settlement(client, orders[0]).json()
    assert first['settlement']['received_cents'] is None
    second = settlement(client, orders[0], status='not_received', revision=1).json()
    assert second['settlement']['status'] == 'not_received'
    assert get(client).json()['stats']['not_received_orders'] == 1
    third = settlement(client, orders[0], status='unverified', revision=2).json()
    assert third['settlement']['status'] == 'unverified'
    assert [h['revision'] for h in third['settlement_history']] == [3, 2, 1]
    assert [h['status'] for h in third['settlement_history']] == ['unverified', 'not_received', 'received']
    assert get(client).json()['stats']['unverified_orders'] == 2


def test_stale_page_cannot_overwrite_another_confirmation(merchant):
    client, _, orders = merchant
    assert settlement(client, orders[0]).status_code == 200
    stale = settlement(client, orders[0], status='not_received')
    assert stale.status_code == 409
    detail = client.get('/commerce/api/admin/orders/'+orders[0], headers=headers()).json()
    assert detail['settlement']['status'] == 'received' and len(detail['settlement_history']) == 1


@pytest.mark.parametrize('payload,expected', [
    ({'received_cents': 6601}, 400), ({'received_cents': 0}, 422),
    ({'status': 'not_received', 'received_cents': 6500}, 400),
    ({'status': 'unverified', 'received_date': '2026-10-22'}, 400),
    ({'received_date': '2026-99-99'}, 422), ({'status': 'settled_by_gateway'}, 422),
    ({'cents': 1}, 422), ({'note': 'x'*301}, 422),
])
def test_invalid_confirmation_is_rejected(merchant, payload, expected):
    client, _, orders = merchant
    assert settlement(client, orders[0], **payload).status_code == expected
    assert get(client).json()['stats']['received_orders'] == 0


def test_unpaid_unknown_and_unauthorized_orders_cannot_be_marked_received(merchant):
    client, _, orders = merchant
    assert settlement(client, orders[2]).status_code == 400
    assert settlement(client, 'unknown').status_code == 404
    path = '/commerce/api/admin/orders/'+orders[0]+'/settlement'
    assert client.post(path, json={'status': 'received', 'revision': 0}).status_code == 401
    assert client.post(path, json={'status': 'received', 'revision': 0},
                       headers={**headers(), 'Origin': 'https://untrusted.example'}).status_code == 403


def test_competing_confirmations_commit_exactly_one_revision(merchant):
    from concurrent.futures import ThreadPoolExecutor
    from server.dashboard import record_settlement
    from server.store import ShopError
    _, store, orders = merchant
    def write(status):
        try:
            record_settlement(store, orders[0], status=status, revision=0)
            return 'saved'
        except ShopError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ['received', 'not_received']))
    assert results.count('saved') == 1 and results.count(409) == 1
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM settlement_history').fetchone()[0] == 1
