"""ZPAY protocol. Secrets are used only on the server; never included in responses."""
import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import httpx


class GatewayError(Exception):
    pass


def cents(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('0.01')):
            raise ValueError()
        return int(amount * 100)
    except (InvalidOperation, ValueError, OverflowError):
        raise GatewayError('invalid_amount') from None


def sign(params, key):
    content = '&'.join(f'{k}={params[k]}' for k in sorted(params)
                       if k not in {'sign', 'sign_type'} and params[k] not in ('', None))
    return hashlib.md5((content + key).encode()).hexdigest()


def verify_signature(params, key):
    return bool(key) and params.get('sign_type', 'MD5') == 'MD5' and hmac.compare_digest(
        sign(params, key), str(params.get('sign', '')).lower())


def https_url(value):
    parsed = urlsplit(str(value or ''))
    return str(value) if parsed.scheme == 'https' and parsed.hostname and not parsed.username else ''


class Zpay:
    def __init__(self, pid, key, cid, api_url, site_url):
        self.pid, self.key, self.cid = pid, key, cid
        self.api_url, self.site_url = api_url.rstrip('/'), site_url.rstrip('/')

    def ready(self):
        return bool(self.pid and self.key and https_url(self.api_url) and https_url(self.site_url))

    def create(self, order, client_ip):
        params = {
            'pid': self.pid, 'cid': self.cid, 'type': 'alipay',
            'out_trade_no': order['id'], 'money': f"{order['cents'] / 100:.2f}",
            'name': f"{order['name']} · {order['duration']}",
            'notify_url': f'{self.api_url}/commerce/zpay/notify',
            'return_url': f'{self.api_url}/commerce/zpay/return',
            'clientip': client_ip, 'device': 'pc',
        }
        params['sign'] = sign(params, self.key)
        params['sign_type'] = 'MD5'
        try:
            with httpx.Client(timeout=8) as client:
                response = client.post('https://zpayz.cn/mapi.php',
                                       files={k: (None, str(v)) for k, v in params.items() if v != ''})
                response.raise_for_status()
                data = response.json()
            if str(data.get('code')) != '1':
                raise GatewayError('payment_creation_rejected')
            result = {k: https_url(data.get(k)) for k in ('img', 'qrcode', 'payurl')}
            if not any(result.values()):
                raise GatewayError('payment_url_missing')
            return result
        except (httpx.HTTPError, ValueError):
            raise GatewayError('payment_gateway_unavailable') from None

    def query(self, order_id):
        try:
            with httpx.Client(timeout=3) as client:
                response = client.get('https://zpayz.cn/api.php', params={
                    'act': 'order', 'pid': self.pid, 'key': self.key, 'out_trade_no': order_id,
                })
                response.raise_for_status()
                data = response.json()
            if str(data.get('code')) != '1':
                raise GatewayError('order_query_failed')
            return data
        except (httpx.HTTPError, ValueError):
            raise GatewayError('payment_gateway_unavailable') from None


def verified_payment(data, order, pid, trade_no=None):
    """A redirect or a signed callback alone never releases an activation code."""
    return (str(data.get('code')) == '1' and str(data.get('status')) == '1'
            and str(data.get('pid')) == pid and data.get('out_trade_no') == order['id']
            and data.get('type') == 'alipay' and cents(data.get('money')) == order['cents']
            and bool(data.get('trade_no'))
            and (trade_no is None or str(data['trade_no']) == trade_no))
