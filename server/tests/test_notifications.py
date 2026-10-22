from concurrent.futures import ThreadPoolExecutor
import json
import secrets
import sqlite3

import httpx
import pytest

from server.notifications import Feishu, NotificationError, Outbox, notify_orders
from server.store import Store


@pytest.fixture
def notifications(tmp_path):
    store = Store(tmp_path / 'shop.sqlite3')
    store.import_stock([{'product_id': 'interpark', 'project_id': 'interpark', 'days': 30,
                         'code': f'NOTIFICATION-PRIVATE-{i}', 'binding_mode': 'machine',
                         'batch': 'ticketpro-web:notify-test', 'tutorial_url': 'https://example.com/guide'}
                        for i in range(5)], tmp_path / 'manifest.json')

    def order():
        value, _ = store.create({'id': 'interpark', 'name': 'Interpark'},
                                {'days': 30, 'duration': '1个月', 'cents': 8800},
                                secrets.token_hex(16), secrets.token_hex(32), secrets.token_hex(16))
        return value

    return store, Outbox(store), order


def test_only_committed_delivery_queues_one_notification(notifications, tmp_path, monkeypatch):
    store, outbox, new_order = notifications
    signal = tmp_path / 'notify.request'
    monkeypatch.setenv('TICKETPRO_NOTIFICATION_SIGNAL', str(signal))
    order = new_order()
    assert outbox.summary() == {} and outbox.claim() is None
    store.deliver(order['id'], 'paid-' + order['id'])
    assert signal.exists() and outbox.summary() == {'pending': 1}
    stamp = signal.stat().st_mtime_ns
    store.deliver(order['id'], 'paid-' + order['id'])
    assert signal.stat().st_mtime_ns == stamp
    assert outbox.summary() == {'pending': 1}
    assert Store(store.path).public_order(store.order(order['id']))['delivery']['code'].startswith('NOTIFICATION-PRIVATE-')


def test_delivery_and_notification_event_rollback_together(notifications):
    store, outbox, new_order = notifications
    order = new_order()
    with store.connection() as db:
        db.execute("CREATE TRIGGER reject_notification BEFORE INSERT ON order_notifications BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.deliver(order['id'], 'trade')
    assert store.order(order['id'])['status'] == 'pending'
    assert outbox.summary() == {}
    with store.connection() as db:
        assert db.execute('SELECT state FROM stock WHERE order_id=?', (order['id'],)).fetchone()[0] == 'reserved'


def test_notification_failure_does_not_undo_delivery_and_retries_after_restart(notifications):
    store, outbox, new_order = notifications
    order = new_order()
    store.deliver(order['id'], 'trade')
    original = store.public_order(store.order(order['id']))['delivery']['code']

    class Broken:
        def order(self, _job):
            raise RuntimeError('https://secret.invalid/private-webhook?key=private-secret')

    assert notify_orders(store, Broken()) == {'sent': 0, 'deferred': 1, 'lease_lost': 0}
    assert store.order(order['id'])['status'] == 'delivered'
    assert outbox.claim() is None
    assert 'private-secret' not in json.dumps(store.summary())
    with store.connection(write=True) as db:
        db.execute('UPDATE order_notifications SET next_attempt=0')
    received = []
    sender = type('Sender', (), {'order': lambda _self, job: received.append(job)})()
    reopened = Store(store.path)
    assert notify_orders(reopened, sender)['sent'] == 1
    assert notify_orders(reopened, sender)['sent'] == 0
    assert len(received) == 1 and outbox.summary() == {'sent': 1}
    assert reopened.public_order(reopened.order(order['id']))['delivery']['code'] == original


def test_concurrent_claims_and_expired_lease_cannot_acknowledge_another_worker(notifications):
    store, outbox, new_order = notifications
    store.deliver(new_order()['id'], 'trade')
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = list(pool.map(lambda _: outbox.claim(), range(5)))
    assert sum(job is not None for job in jobs) == 1
    original = next(job for job in jobs if job)
    with store.connection(write=True) as db:
        db.execute('UPDATE order_notifications SET lease_until=0')
    replacement = Outbox(Store(store.path)).claim()
    assert replacement['order_id'] == original['order_id']
    assert replacement['claim_token'] != original['claim_token']
    assert not outbox.finish(original)
    assert outbox.finish(replacement) and outbox.summary() == {'sent': 1}


def test_reopening_store_does_not_notify_historical_orders(notifications):
    store, _, new_order = notifications
    store.deliver(new_order()['id'], 'trade')
    with store.connection(write=True) as db:
        # This mirrors adding the new table to a database containing old deliveries.
        db.execute('DROP TABLE order_notifications')
    reopened = Store(store.path)
    assert Outbox(reopened).summary() == {}


WEBHOOK = 'https://open.feishu.cn/open-apis/bot/v2/hook/00000000-0000-0000-0000-000000000000'


def transport(monkeypatch, respond):
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))


def test_feishu_payload_contains_correct_order_without_private_code_or_credentials(notifications, monkeypatch):
    store, outbox, new_order = notifications
    order = new_order()
    store.deliver(order['id'], 'trade')
    requests = []

    def respond(request):
        assert request.url == WEBHOOK
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={'code': 0, 'msg': 'success'})

    transport(monkeypatch, respond)
    assert notify_orders(store, Feishu(WEBHOOK))['sent'] == 1
    assert outbox.summary() == {'sent': 1}
    content = requests[0]['content']['text']
    assert requests[0]['msg_type'] == 'text'
    for expected in ('TicketPro 订单通知', 'Interpark', '1个月', '¥88.00', order['id'], '自动发货完成'):
        assert expected in content
    for forbidden in ('NOTIFICATION-PRIVATE-', WEBHOOK, order['token_hash'], 'Bearer', '#key='):
        assert forbidden not in json.dumps(requests)


@pytest.mark.parametrize('reply', [{'code': 19024}, {'code': 19021}, {}, [], {'msg': 'success'}])
def test_http_200_without_feishu_ack_is_not_sent(monkeypatch, reply):
    transport(monkeypatch, lambda _request: httpx.Response(200, json=reply))
    with pytest.raises(NotificationError, match='feishu_rejected'):
        Feishu(WEBHOOK).send('test')


@pytest.mark.parametrize('url', ['http://open.feishu.cn/open-apis/bot/v2/hook/0000000000000000',
                               'https://example.com/open-apis/bot/v2/hook/0000000000000000',
                               WEBHOOK + '?token=secret', WEBHOOK + '#fragment',
                               WEBHOOK.replace('https://', 'https://user:password@'),
                               WEBHOOK.replace('open.feishu.cn', 'open.feishu.cn:444'),
                               'https://open.feishu.cn/other/path'])
def test_reject_non_bot_urls_before_sending(url):
    with pytest.raises(ValueError):
        Feishu(url)


def test_optional_signing_uses_fresh_timestamp(monkeypatch):
    monkeypatch.setattr('server.notifications.time.time', lambda: 1599360473)
    captured = []
    transport(monkeypatch, lambda request: (captured.append(json.loads(request.content))
                                          or httpx.Response(200, json={'code': 0})))
    Feishu(WEBHOOK, secret='signing-test-secret').send('TicketPro 订单通知')
    assert captured[0]['timestamp'] == '1599360473'
    # Fixed vector computed independently from Feishu's documented HMAC convention.
    assert captured[0]['sign'] == 'hlEfdWG/GIYDoa/9puD0HoRM4iitJgVdG7h4GAOLQ3A='


@pytest.mark.parametrize('failure', [httpx.ConnectError, httpx.ReadTimeout])
def test_transport_failures_are_redacted(monkeypatch, failure):
    def respond(request):
        raise failure('private-webhook-and-secret', request=request)
    transport(monkeypatch, respond)
    with pytest.raises(NotificationError) as error:
        Feishu(WEBHOOK).send('test')
    assert str(error.value) == 'feishu_unavailable'
