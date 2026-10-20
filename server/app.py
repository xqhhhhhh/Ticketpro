import hashlib
import ipaddress
import json
from pathlib import Path
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from .gateway import GatewayError, Zpay, cents, verified_payment, verify_signature
from .store import ShopError, Store
from .tutorials import load_tutorials
from .config import Settings

PREFIX = '/commerce'


class NewOrder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(min_length=1, max_length=80)
    days: int = Field(ge=0, le=3650)
    request_id: str = Field(pattern=r'^[a-zA-Z0-9-]{20,80}$')
    access_key: str = Field(pattern=r'^[a-f0-9]{64}$')


class DemoGateway:
    def __init__(self):
        self.pid, self.key = 'demo', 'demo-local-only'
        self.paid = {}

    def ready(self):
        return True

    def create(self, order, _ip):
        return {'demo': True, 'payurl': f'/commerce/demo-pay/{order["id"]}'}

    def query(self, order_id):
        return self.paid.get(order_id, {'code': 1, 'status': 0})


def create_app(settings=None, gateway=None):
    settings = settings or Settings.from_env()
    store = Store(settings.db, demo=settings.demo, tutorials=load_tutorials(settings.tutorials))
    catalog = json.loads(Path(settings.catalog).read_text())
    gateway = gateway or (DemoGateway() if settings.demo else Zpay(
        settings.pid, settings.key, settings.cid, settings.api_url, settings.site_url))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.gateway = store, gateway
    app.state.settings = settings
    origins = settings.origins or (('http://127.0.0.1:5173', 'http://localhost:5173') if settings.demo else ())
    app.add_middleware(CORSMiddleware, allow_origins=list(origins),
                       allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])

    @app.middleware('http')
    async def security(request, call_next):
        if settings.demo and (request.url.hostname not in {'127.0.0.1', 'localhost', 'testserver'}
                              or request.client.host not in {'127.0.0.1', '::1', 'testclient'}):
            return JSONResponse({'detail': '演示服务仅可在本机运行'}, status_code=403)
        origin = request.headers.get('origin')
        if request.method == 'POST' and origin and origin not in origins:
            return JSONResponse({'detail': f'origin_not_allowed: {origin}' if settings.demo else 'origin_not_allowed'}, status_code=403)
        try:
            length = int(request.headers.get('content-length', '0') or '0')
        except ValueError:
            return JSONResponse({'detail': 'invalid_content_length'}, status_code=400)
        if length > 16384 or len(request.url.query) > 8192:
            return JSONResponse({'detail': 'request_too_large'}, status_code=413)
        response = await call_next(request)
        # HTML form navigations with no-referrer can send Origin:null. Demo forms
        # need their same-origin Origin; private order/API pages still suppress referrers.
        policy = 'same-origin' if settings.demo and request.url.path.startswith(PREFIX + '/demo-pay/') else 'no-referrer'
        response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': policy,
                                 'X-Content-Type-Options': 'nosniff'})
        return response

    @app.exception_handler(ShopError)
    async def shop_error(_request, exc):
        return JSONResponse({'detail': exc.message}, status_code=exc.status)

    @app.exception_handler(GatewayError)
    async def gateway_error(_request, _exc):
        return JSONResponse({'detail': '支付接口暂时未响应，请保留订单并稍后检查，勿重复下单。'}, status_code=502)

    def authenticated(request, order_id):
        header = request.headers.get('authorization', '')
        if not header.startswith('Bearer ') or len(header) != 71:
            raise ShopError('order_not_found', 404)
        return store.order(order_id, header[7:])

    def check_payment(order, trade_no=None):
        data = gateway.query(order['id'])
        if not verified_payment(data, order, gateway.pid, trade_no):
            return False
        store.deliver(order['id'], str(data['trade_no']))
        return True

    @app.get(PREFIX + '/api/health')
    def health():
        return {'ok': True, 'demo': settings.demo, 'payment_ready': gateway.ready()}

    @app.get(PREFIX + '/api/catalog')
    def get_catalog():
        counts = store.counts()
        return {'demo': settings.demo, 'payment_ready': gateway.ready(), 'products': [
            {**p, 'plans': [{**plan, 'stock': counts.get((p['id'], plan['days']), 0)} for plan in p['plans']]}
            for p in catalog]}

    @app.post(PREFIX + '/api/orders')
    def create_order(payload: NewOrder, request: Request):
        if not gateway.ready():
            raise ShopError('自动支付尚未开放，请联系微信客服购买。', 503)
        product = next((p for p in catalog if p['id'] == payload.product_id), None)
        plan = next((p for p in product['plans'] if p['days'] == payload.days), None) if product else None
        if not product or not plan:
            raise ShopError('invalid_product_or_plan')
        client_ip = request.client.host
        if settings.trusted_proxy and client_ip in {'127.0.0.1', '::1'}:
            try:
                client_ip = str(ipaddress.ip_address(request.headers.get('x-real-ip', client_ip)))
            except ValueError:
                raise ShopError('invalid_client_ip') from None
        order, created = store.create(product, plan, payload.request_id, payload.access_key,
                                      hashlib.sha256((gateway.key + client_ip).encode()).hexdigest())
        if created:
            try:
                store.save_payment(order['id'], gateway.create(order, client_ip))
            except GatewayError:
                # A timeout can happen after ZPAY accepted the order. Keep its stock and ID.
                pass
        return store.public_order(store.order(order['id']))

    @app.get(PREFIX + '/api/orders/{order_id}')
    def read_order(order_id: str, request: Request):
        return store.public_order(authenticated(request, order_id))

    @app.post(PREFIX + '/api/orders/{order_id}/refresh')
    def refresh_order(order_id: str, request: Request):
        order = authenticated(request, order_id)
        if order['status'] != 'delivered' and store.claim_check(order_id):
            check_payment(order)
        return store.public_order(store.order(order_id))

    @app.get(PREFIX + '/zpay/notify', response_class=PlainTextResponse)
    def notify(request: Request):
        params = dict(request.query_params)
        if (len(request.query_params.multi_items()) != len(params)
                or not verify_signature(params, gateway.key)
                or params.get('pid') != gateway.pid or params.get('type') != 'alipay'
                or params.get('trade_status') != 'TRADE_SUCCESS'):
            return PlainTextResponse('fail', status_code=400)
        try:
            order = store.order(params.get('out_trade_no', ''))
            if cents(params.get('money')) != order['cents'] or not params.get('trade_no'):
                return PlainTextResponse('fail', status_code=400)
            # Replay is acknowledged only after verifying it matches the persisted transaction.
            if order['status'] == 'delivered':
                return PlainTextResponse('success' if order['trade_no'] == params['trade_no'] else 'fail')
            if not check_payment(order, params['trade_no']):
                return PlainTextResponse('fail', status_code=503)
        except (GatewayError, ShopError):
            return PlainTextResponse('fail', status_code=503)
        return PlainTextResponse('success')

    @app.get(PREFIX + '/zpay/return')
    def payment_return(request: Request):
        params = dict(request.query_params)
        if len(request.query_params.multi_items()) != len(params) or not verify_signature(params, gateway.key):
            raise ShopError('invalid_return_signature')
        order = store.order(params.get('out_trade_no', ''))
        if params.get('pid') != gateway.pid or cents(params.get('money')) != order['cents']:
            raise ShopError('invalid_return_order')
        # Returning to the site is not proof of payment. The authenticated order page checks it.
        return RedirectResponse(f'{settings.site_url}/order/{order["id"]}', status_code=303)

    @app.get(PREFIX + '/api/admin/summary')
    def admin_summary(request: Request):
        if not settings.admin_key or not secrets.compare_digest(request.headers.get('authorization', ''),
                                                               'Bearer ' + settings.admin_key):
            raise ShopError('unauthorized', 401)
        return store.summary()

    if settings.demo:
        @app.get(PREFIX + '/demo-pay/{order_id}')
        def demo_page(order_id: str):
            order = store.order(order_id)
            return HTMLResponse(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
                <meta name="viewport" content="width=device-width,initial-scale=1"><title>本地模拟付款</title>
                <body style="background:#080b10;color:#fff;font:18px system-ui;padding:40px">
                <h1>本地模拟付款</h1><p>演示订单 ¥{order['cents']/100:.2f}，不会发生真实扣款。</p>
                <form method="post"><button style="padding:16px">模拟付款成功</button></form></body></html>''')

        @app.post(PREFIX + '/demo-pay/{order_id}')
        def demo_pay(order_id: str):
            order = store.order(order_id)
            gateway.paid[order_id] = {'code': 1, 'status': 1, 'pid': 'demo', 'type': 'alipay',
                                     'out_trade_no': order_id, 'money': f"{order['cents']/100:.2f}",
                                     'trade_no': 'demo-' + order_id}
            check_payment(order)
            return RedirectResponse(f'{settings.site_url}/order/{order_id}', status_code=303)

    return app


app = create_app()
