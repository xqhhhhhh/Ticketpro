"""Transactional orders and dedicated website stock. Never re-sell an unpaid hold."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager


def code_hash(code):
    return hashlib.sha256(re.sub(r'[^A-Z0-9]', '', code.upper()).encode()).hexdigest()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class ShopError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


class Store:
    def __init__(self, path, demo=False, tutorials=None):
        self.path = Path(path)
        self.tutorials = tutorials or {}
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connection() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS shop_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY, product_id TEXT NOT NULL, days INTEGER NOT NULL,
                project_id TEXT NOT NULL, code TEXT NOT NULL, code_hash TEXT UNIQUE NOT NULL,
                binding_mode TEXT NOT NULL, batch TEXT NOT NULL, tutorial_url TEXT NOT NULL,
                download_url TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT 'available',
                order_id TEXT UNIQUE);
              CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, token_hash TEXT NOT NULL,
                product_id TEXT NOT NULL, name TEXT NOT NULL, days INTEGER NOT NULL,
                duration TEXT NOT NULL, cents INTEGER NOT NULL, status TEXT NOT NULL,
                created_at INTEGER NOT NULL, paid_at INTEGER, trade_no TEXT UNIQUE,
                client_hash TEXT NOT NULL, payment TEXT NOT NULL DEFAULT '{}',
                last_check INTEGER NOT NULL DEFAULT 0);
              CREATE INDEX IF NOT EXISTS stock_sku ON stock(product_id, days, state);
              CREATE INDEX IF NOT EXISTS orders_client ON orders(client_hash, created_at);
              CREATE TABLE IF NOT EXISTS order_notifications (
                order_id TEXT PRIMARY KEY REFERENCES orders(id),
                status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt INTEGER NOT NULL DEFAULT 0, claim_token TEXT NOT NULL DEFAULT '',
                lease_until INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL, sent_at INTEGER);
              CREATE TABLE IF NOT EXISTS settlement_checks (
                order_id TEXT PRIMARY KEY REFERENCES orders(id), status TEXT NOT NULL,
                received_cents INTEGER, received_date TEXT, note TEXT NOT NULL DEFAULT '',
                checked_at INTEGER NOT NULL, revision INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS settlement_history (
                id INTEGER PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
                status TEXT NOT NULL, received_cents INTEGER, received_date TEXT,
                note TEXT NOT NULL DEFAULT '', checked_at INTEGER NOT NULL, revision INTEGER NOT NULL,
                UNIQUE(order_id,revision));
            ''')
            if 'is_test' not in {r['name'] for r in db.execute('PRAGMA table_info(orders)')}:
                db.execute('ALTER TABLE orders ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0')
            mode = 'demo' if demo else 'production'
            previous = db.execute("SELECT value FROM shop_metadata WHERE key='mode'").fetchone()
            if previous and previous['value'] != mode:
                raise ShopError('演示数据库与正式数据库不能混用', 503)
            db.execute("INSERT OR IGNORE INTO shop_metadata VALUES ('mode', ?)", (mode,))
        os.chmod(self.path, 0o600)

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def counts(self):
        with self.connection() as db:
            return {(r['product_id'], r['days']): r['n'] for r in db.execute(
                "SELECT product_id, days, count(*) n FROM stock WHERE state='available' GROUP BY product_id,days")}

    def order(self, order_id, token=None):
        with self.connection() as db:
            row = db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
            if not row or (token is not None and not secrets.compare_digest(row['token_hash'], token_hash(token))):
                raise ShopError('order_not_found', 404)
            return dict(row)

    def create(self, product, plan, request_id, token, client_hash):
        with self.connection(write=True) as db:
            existing = db.execute('SELECT * FROM orders WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                if (existing['token_hash'] != token_hash(token) or existing['product_id'] != product['id']
                        or existing['days'] != plan['days']):
                    raise ShopError('request_conflict', 409)
                return dict(existing), False
            if db.execute('SELECT count(*) FROM orders WHERE client_hash=? AND created_at>?',
                          (client_hash, int(time.time()) - 3600)).fetchone()[0] >= 5:
                raise ShopError('too_many_orders', 429)
            stock = db.execute("SELECT id FROM stock WHERE product_id=? AND days=? AND state='available' ORDER BY id LIMIT 1",
                               (product['id'], plan['days'])).fetchone()
            if not stock:
                raise ShopError('out_of_stock', 409)
            order_id = time.strftime('%Y%m%d%H%M%S', time.gmtime()) + f'{secrets.randbelow(10**14):014d}'
            db.execute('INSERT INTO orders(id,request_id,token_hash,product_id,name,days,duration,cents,status,created_at,client_hash) '
                       'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (order_id, request_id, token_hash(token), product['id'], product['name'], plan['days'],
                        plan['duration'], plan['cents'], 'pending', int(time.time()), client_hash))
            db.execute("UPDATE stock SET state='reserved', order_id=? WHERE id=?", (order_id, stock['id']))
            return dict(db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()), True

    def save_payment(self, order_id, payment):
        with self.connection(write=True) as db:
            db.execute('UPDATE orders SET payment=? WHERE id=?', (json.dumps(payment), order_id))

    def claim_check(self, order_id):
        with self.connection(write=True) as db:
            cursor = db.execute('UPDATE orders SET last_check=? WHERE id=? AND last_check<?',
                                (int(time.time()), order_id, int(time.time()) - 10))
            return bool(cursor.rowcount)

    def deliver(self, order_id, trade_no):
        with self.connection(write=True) as db:
            order = db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
            if order['status'] == 'delivered':
                if order['trade_no'] != trade_no:
                    raise ShopError('transaction_conflict', 409)
                return
            stock = db.execute('SELECT * FROM stock WHERE order_id=?', (order_id,)).fetchone()
            if not stock:
                raise ShopError('reserved_stock_missing', 503)
            try:
                db.execute("UPDATE orders SET status='delivered',trade_no=?,paid_at=? WHERE id=?",
                           (trade_no, int(time.time()), order_id))
            except sqlite3.IntegrityError:
                raise ShopError('transaction_conflict', 409) from None
            db.execute("UPDATE stock SET state='sold' WHERE order_id=?", (order_id,))
            db.execute('INSERT INTO order_notifications(order_id,created_at) VALUES (?,?)',
                       (order_id, int(time.time())))
        # Delivery and its notification event commit together; network calls run separately.
        for name in ('TICKETPRO_RESTOCK_SIGNAL', 'TICKETPRO_NOTIFICATION_SIGNAL'):
            signal = os.getenv(name, '')
            if signal:
                try:
                    Path(signal).touch()
                except OSError:
                    pass

    def public_order(self, order):
        result = {k: order[k] for k in ('id', 'product_id', 'name', 'days', 'duration', 'cents', 'status', 'created_at', 'paid_at')}
        result['payment'] = json.loads(order['payment']) if order['status'] == 'pending' else None
        result['delivery'] = None
        if order['status'] == 'delivered':
            with self.connection() as db:
                stock = db.execute('SELECT * FROM stock WHERE order_id=?', (order['id'],)).fetchone()
            result['delivery'] = {k: stock[k] for k in ('code', 'binding_mode', 'tutorial_url')}
            result['delivery']['tutorial_url'] = self.tutorials.get(order['product_id']) or stock['tutorial_url']
        return result

    def import_stock(self, items, manifest_path):
        """Publish exclusions BEFORE committing sellable stock. An interrupted import fails closed."""
        with self.connection(write=True) as db:
            self._insert_stock(db, items)
            self._publish_manifest(db, manifest_path)

    @staticmethod
    def _insert_stock(db, items, states=None):
        for index, item in enumerate(items):
            db.execute('INSERT INTO stock(product_id,days,project_id,code,code_hash,binding_mode,batch,tutorial_url,download_url,state) '
                       'VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (item['product_id'], item['days'], item['project_id'], item['code'], code_hash(item['code']),
                        item['binding_mode'], item['batch'], item['tutorial_url'], '',
                        states[index] if states else 'available'))

    @staticmethod
    def _publish_manifest(db, manifest_path, extra=None):
        """Caller holds the stock DB write lock, including for quarantine-only writes."""
        path = Path(manifest_path)
        hashes = {}
        if path.exists():
            try:
                previous = json.loads(path.read_text())
                assert previous['version'] == 1 and isinstance(previous['projects'], dict)
                for project, values in previous['projects'].items():
                    assert isinstance(values, list) and all(isinstance(v, str) and re.fullmatch('[a-f0-9]{64}', v) for v in values)
                    hashes[project] = set(values)
            except (ValueError, KeyError, TypeError, AssertionError):
                raise ShopError('库存隔离清单无效，已停止写入') from None
        for row in db.execute('SELECT project_id,code_hash FROM stock'):
            hashes.setdefault(row['project_id'], set()).add(row['code_hash'])
        for project, values in (extra or {}).items():
            hashes.setdefault(project, set()).update(values)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            with temp.open('x', encoding='utf-8') as file:
                os.chmod(temp, 0o640)
                json.dump({'version': 1, 'projects': {p: sorted(v) for p, v in hashes.items()}}, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def quarantine_stock(self, project_id, codes, manifest_path):
        with self.connection(write=True) as db:
            self._publish_manifest(db, manifest_path, {project_id: [code_hash(code) for code in codes]})

    def summary(self):
        with self.connection() as db:
            result = {
                'stock': [dict(r) for r in db.execute('SELECT product_id,days,state,count(*) count FROM stock GROUP BY product_id,days,state')],
                'orders': [dict(r) for r in db.execute('SELECT id,name,duration,cents,status,created_at,paid_at FROM orders ORDER BY created_at DESC LIMIT 100')],
            }
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='restock_jobs'").fetchone():
                result['restock'] = [dict(r) for r in db.execute(
                    'SELECT id,product_id,days,quantity,status,attempts,next_attempt,last_error,created_at,completed_at '
                    'FROM restock_jobs ORDER BY created_at DESC,id DESC LIMIT 100')]
            result['notifications'] = [dict(r) for r in db.execute(
                'SELECT order_id,status,attempts,next_attempt,last_error,created_at,sent_at '
                'FROM order_notifications ORDER BY created_at DESC,order_id DESC LIMIT 100')]
            return result
