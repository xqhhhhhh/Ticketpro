"""Read-only merchant views; buyer credentials and gateway payloads never leave the DB."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import time as clock

from .store import ShopError


def dashboard(store, catalog, *, query='', status='', product='', start='', end='',
              include_tests=False, page=1, size=20, timezone='Europe/Berlin'):
    zone = ZoneInfo(timezone)
    today = datetime.now(zone).date()
    clauses, values = ['1=1'], []
    if not include_tests:
        clauses.append('o.is_test=0')
    if query:
        clauses.append('(instr(o.id,?)>0 OR instr(lower(o.name),lower(?))>0)')
        values += [query, query]
    if status:
        if status not in {'pending', 'delivered'}:
            raise ShopError('invalid_order_status')
        clauses.append('o.status=?')
        values.append(status)
    if product:
        if product not in {p['id'] for p in catalog}:
            raise ShopError('invalid_product')
        clauses.append('o.product_id=?')
        values.append(product)
    try:
        first, last = date.fromisoformat(start) if start else None, date.fromisoformat(end) if end else None
        if any(day and not 1970 <= day.year <= 9998 for day in (first, last)):
            raise ValueError()
        if first and last and first > last:
            raise ValueError()
    except ValueError:
        raise ShopError('invalid_date_range') from None
    def midnight(day):
        return int(datetime.combine(day, time.min, zone).timestamp())
    if first:
        clauses.append('o.created_at>=?')
        values.append(midnight(first))
    if last:
        clauses.append('o.created_at<?')
        values.append(midnight(last + timedelta(days=1)))
    where = ' AND '.join(clauses)
    chart_end = last or today
    chart_start = chart_end - timedelta(days=13)
    with store.connection() as db:
        db.execute('BEGIN')
        stats = dict(db.execute(f'''SELECT count(*) total,
            coalesce(sum(o.status='delivered'),0) paid, coalesce(sum(o.status='pending'),0) pending,
            coalesce(sum(CASE WHEN o.status='delivered' THEN cents ELSE 0 END),0) revenue,
            coalesce(sum(CASE WHEN o.status='delivered' AND paid_at>=? AND paid_at<? THEN cents ELSE 0 END),0) today_revenue,
            coalesce(sum(o.status='delivered' AND coalesce(c.status,'unverified')='received'),0) received_orders,
            coalesce(sum(o.status='delivered' AND coalesce(c.status,'unverified')='not_received'),0) not_received_orders,
            coalesce(sum(o.status='delivered' AND coalesce(c.status,'unverified')='unverified'),0) unverified_orders
            FROM orders o LEFT JOIN settlement_checks c ON c.order_id=o.id WHERE {where}''',
            (midnight(today), midnight(today+timedelta(days=1)), *values)).fetchone())
        rows = [dict(r) for r in db.execute(f'''SELECT o.id,o.product_id,o.name,o.days,o.duration,o.cents,
            o.status,o.created_at,o.paid_at,o.is_test,n.status notification_status,
            coalesce(c.status,'unverified') settlement_status,c.checked_at settlement_checked_at
            FROM orders o LEFT JOIN order_notifications n ON n.order_id=o.id
            LEFT JOIN settlement_checks c ON c.order_id=o.id
            WHERE {where} ORDER BY o.created_at DESC,o.id DESC LIMIT ? OFFSET ?''',
            (*values, size, (page-1)*size))]
        sales = db.execute(f'''SELECT o.paid_at,o.cents FROM orders o WHERE {where}
            AND o.status='delivered' AND o.paid_at>=? AND o.paid_at<?''',
            (*values, midnight(chart_start), midnight(chart_end+timedelta(days=1)))).fetchall()
        ranking = [dict(r) for r in db.execute(f'''SELECT o.product_id,o.name,count(*) orders,sum(o.cents) revenue
            FROM orders o WHERE {where} AND o.status='delivered'
            GROUP BY o.product_id,o.name ORDER BY revenue DESC,o.product_id LIMIT 6''', values)]
    days = {(chart_start+timedelta(days=i)).isoformat(): {'revenue': 0, 'orders': 0} for i in range(14)}
    for sale in sales:
        point = days[datetime.fromtimestamp(sale['paid_at'], zone).date().isoformat()]
        point['revenue'] += sale['cents']
        point['orders'] += 1
    return {'stats': stats, 'orders': rows, 'ranking': ranking,
            'trend': [{'date': day, **point} for day, point in days.items()],
            'products': [{'id': p['id'], 'name': p['name']} for p in catalog],
            'page': page, 'size': size, 'total': stats['total'], 'timezone': timezone,
            'updated_at': int(datetime.now(zone).timestamp())}


def order_detail(store, order_id, reveal=False):
    with store.connection() as db:
        row = db.execute('''SELECT o.id,o.product_id,o.name,o.days,o.duration,o.cents,o.status,
            o.created_at,o.paid_at,o.trade_no,o.is_test,s.project_id,s.binding_mode,s.code,s.tutorial_url,
            n.status notification_status,n.attempts notification_attempts,n.last_error notification_error,
            n.sent_at notification_sent_at FROM orders o
            LEFT JOIN stock s ON s.order_id=o.id LEFT JOIN order_notifications n ON n.order_id=o.id
            WHERE o.id=?''', (order_id,)).fetchone()
    if not row:
        raise ShopError('order_not_found', 404)
    result = dict(row)
    code = result.pop('code') or ''
    result['code_suffix'] = code[-4:] if result['status'] == 'delivered' else ''
    result['tutorial_url'] = store.tutorials.get(result['product_id']) or result['tutorial_url']
    with store.connection() as db:
        check = db.execute('SELECT status,received_cents,received_date,note,checked_at,revision FROM settlement_checks WHERE order_id=?',
                           (order_id,)).fetchone()
        history = [dict(r) for r in db.execute('''SELECT status,received_cents,received_date,note,checked_at,revision
            FROM settlement_history WHERE order_id=? ORDER BY revision DESC LIMIT 10''', (order_id,))]
    result['settlement'] = dict(check) if check else {'status': 'unverified', 'received_cents': None,
                                                   'received_date': None, 'note': '', 'checked_at': None, 'revision': 0}
    result['settlement']['source'] = 'merchant_check' if check else 'unavailable'
    result['settlement_history'] = history
    if reveal and result['status'] == 'delivered':
        result['code'] = code
    return result


def record_settlement(store, order_id, *, status, received_cents=None, received_date=None, note='', revision=0):
    if status not in {'unverified', 'received', 'not_received'}:
        raise ShopError('invalid_settlement_status')
    if status != 'received' and (received_cents is not None or received_date is not None):
        raise ShopError('settlement_amount_requires_received')
    if received_date:
        try:
            date.fromisoformat(received_date)
        except ValueError:
            raise ShopError('invalid_settlement_date') from None
    now = int(clock.time())
    with store.connection(write=True) as db:
        order = db.execute('SELECT status,cents FROM orders WHERE id=?', (order_id,)).fetchone()
        if not order:
            raise ShopError('order_not_found', 404)
        if order['status'] != 'delivered':
            raise ShopError('unpaid_order_cannot_confirm_settlement')
        if received_cents is not None and (received_cents <= 0 or received_cents > order['cents']):
            raise ShopError('invalid_settlement_amount')
        current = db.execute('SELECT revision FROM settlement_checks WHERE order_id=?', (order_id,)).fetchone()
        if revision != (current['revision'] if current else 0):
            raise ShopError('settlement_record_changed', 409)
        values = (order_id, status, received_cents, received_date, note.strip(), now, revision + 1)
        db.execute('''INSERT INTO settlement_checks(order_id,status,received_cents,received_date,note,checked_at,revision)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET status=excluded.status,
            received_cents=excluded.received_cents,received_date=excluded.received_date,note=excluded.note,
            checked_at=excluded.checked_at,revision=excluded.revision''', values)
        db.execute('''INSERT INTO settlement_history(order_id,status,received_cents,received_date,note,checked_at,revision)
            VALUES (?,?,?,?,?,?,?)''', values)
    return order_detail(store, order_id)
