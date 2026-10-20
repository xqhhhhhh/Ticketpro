"""Bounded missed-notification recovery; failures remain pending for the next run."""
from .gateway import GatewayError, verified_payment
from .store import ShopError


def reconcile_orders(store, gateway, limit=200):
    with store.connection() as db:
        orders = [dict(r) for r in db.execute("SELECT * FROM orders WHERE status='pending' ORDER BY last_check,created_at LIMIT ?", (limit,))]
    checked = delivered = failed = 0
    for order in orders:
        if not store.claim_check(order['id']):
            continue
        checked += 1
        try:
            data = gateway.query(order['id'])
            if verified_payment(data, order, gateway.pid):
                store.deliver(order['id'], str(data['trade_no']))
                delivered += 1
        except (GatewayError, ShopError):
            failed += 1
    return {'checked': checked, 'delivered': delivered, 'failed': failed}
