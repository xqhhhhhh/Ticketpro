"""Durable merchant notifications. No license codes, buyer keys or payment secrets."""
import argparse
import base64
from datetime import datetime
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from .config import Settings
from .store import Store


class NotificationError(Exception):
    """Only fixed, non-sensitive labels may leave the sender."""
    def __init__(self, label, provider_code=None):
        super().__init__(label)
        self.provider_code = (int(provider_code) if str(provider_code).isdigit()
                              and len(str(provider_code)) <= 9 else None)


class Feishu:
    def __init__(self, webhook, secret='', timezone='Europe/Berlin'):
        parsed = urlsplit(webhook)
        if (parsed.scheme != 'https' or parsed.hostname not in {'open.feishu.cn', 'open.larksuite.com'}
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment
                or not re.fullmatch(r'/open-apis/bot/v2/hook/[A-Za-z0-9_-]{16,100}', parsed.path)):
            raise ValueError('invalid_notification_webhook')
        self.webhook, self.secret, self.timezone = webhook, secret, ZoneInfo(timezone)

    def send(self, text):
        payload = {'msg_type': 'text', 'content': {'text': text}}
        if self.secret:
            timestamp = str(int(time.time()))
            signature = hmac.new((timestamp + '\n' + self.secret).encode(), digestmod=hashlib.sha256).digest()
            payload.update(timestamp=timestamp, sign=base64.b64encode(signature).decode())
        try:
            with httpx.Client(timeout=8, follow_redirects=False) as client:
                response = client.post(self.webhook, json=payload)
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError):
            raise NotificationError('feishu_unavailable') from None
        # HTTP 200 alone is not acknowledgement; Feishu also returns application errors.
        if not isinstance(result, dict) or str(result.get('code')) != '0':
            raise NotificationError('feishu_rejected', result.get('code') if isinstance(result, dict) else None)

    def order(self, order):
        paid_at = datetime.fromtimestamp(order['paid_at'], self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
        cents = order['cents']
        self.send(f'TicketPro 订单通知\n付款成功 · 自动发货完成\n'
                  f'商品：{order["name"]}\n期限：{order["duration"]}\n'
                  f'实付：¥{cents // 100}.{cents % 100:02d}\n'
                  f'订单号：{order["order_id"]}\n付款确认时间：{paid_at}\n'
                  '激活码和对应教程已交付至买家订单页。')


class Outbox:
    def __init__(self, store):
        self.store = store

    def claim(self):
        now, token = int(time.time()), secrets.token_hex(16)
        with self.store.connection(write=True) as db:
            row = db.execute('''SELECT n.order_id,o.name,o.duration,o.cents,o.paid_at
                FROM order_notifications n JOIN orders o ON o.id=n.order_id
                WHERE o.status='delivered' AND
                  ((n.status='pending' AND n.next_attempt<=?) OR
                   (n.status='sending' AND n.lease_until<=?))
                ORDER BY n.next_attempt,n.created_at,n.order_id LIMIT 1''', (now, now)).fetchone()
            if not row:
                return None
            db.execute("UPDATE order_notifications SET status='sending',claim_token=?,lease_until=?,attempts=attempts+1 WHERE order_id=?",
                       (token, now + 120, row['order_id']))
            return {**dict(row), 'claim_token': token}

    def finish(self, job, error=''):
        now = int(time.time())
        with self.store.connection(write=True) as db:
            row = db.execute("SELECT attempts FROM order_notifications WHERE order_id=? AND status='sending' AND claim_token=?",
                             (job['order_id'], job['claim_token'])).fetchone()
            if not row:
                return False
            delay = min(900, 30 * 2 ** min(row['attempts'] - 1, 5))
            db.execute('''UPDATE order_notifications SET status=?,next_attempt=?,last_error=?,
                sent_at=?,claim_token='',lease_until=0 WHERE order_id=? AND claim_token=?''',
                ('pending' if error else 'sent', now + delay if error else 0,
                 error, None if error else now, job['order_id'], job['claim_token']))
            return True

    def summary(self):
        with self.store.connection() as db:
            return {r['status']: r['n'] for r in db.execute(
                'SELECT status,count(*) n FROM order_notifications GROUP BY status')}


def notify_orders(store, sender, limit=20):
    outbox = Outbox(store)
    result = {'sent': 0, 'deferred': 0, 'lease_lost': 0}
    for _ in range(limit):
        job = outbox.claim()
        if not job:
            break
        try:
            sender.order(job)
        except Exception as error:
            # Never save upstream messages or HTTP exception strings: they can contain URLs/tokens.
            label = str(error) if isinstance(error, NotificationError) else 'notification_delivery_failed'
            if label not in {'feishu_unavailable', 'feishu_rejected'}:
                label = 'notification_delivery_failed'
            saved = outbox.finish(job, label)
            result['deferred' if saved else 'lease_lost'] += 1
        else:
            saved = outbox.finish(job)
            result['sent' if saved else 'lease_lost'] += 1
    return result


def main():
    parser = argparse.ArgumentParser(description='飞书商家订单提醒，不输出推送凭据或激活码')
    parser.add_argument('--limit', type=int, default=20)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='只检查配置和队列，不发送消息')
    modes.add_argument('--test', action='store_true', help='仅发送明确标注的接入测试，不修改订单或通知队列')
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        raise ValueError('invalid_notification_limit')
    settings = Settings.from_env()
    if settings.demo:
        raise ValueError('notifications_require_production')
    webhook = os.getenv('TICKETPRO_FEISHU_WEBHOOK', '')
    if not webhook:
        print(json.dumps({'configured': False}))
        return 1
    sender = Feishu(webhook, os.getenv('TICKETPRO_FEISHU_SECRET', ''),
                    os.getenv('TICKETPRO_NOTIFICATION_TIMEZONE', 'Europe/Berlin'))
    if args.test:
        sender.send('TicketPro 订单通知\n接入测试：这是一条测试消息，不代表新增订单或付款。\n'
                    '后续买家付款并自动发货后，将在此群收到商品、期限、实付金额、订单号和发货结果。')
        print(json.dumps({'test_sent': True}))
        return 0
    with (Path(settings.db).parent / 'notify.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'already_running': True}))
            return 0
        store = Store(settings.db)
        if args.check:
            print(json.dumps({'configured': True, 'signed': bool(sender.secret), 'queue': Outbox(store).summary()}))
            return 0
        result = notify_orders(store, sender, args.limit)
        print(json.dumps(result))
        return 1 if result['deferred'] or result['lease_lost'] else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except NotificationError as error:
        print(json.dumps({'error': str(error), 'provider_code': error.provider_code}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'error': 'merchant_notification_configuration_or_runtime_error'}))
        raise SystemExit(1)
