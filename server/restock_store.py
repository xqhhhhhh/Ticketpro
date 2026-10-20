"""Durable replenishment jobs; source generation is never part of a payment request."""
import json
import secrets
import time

from .store import ShopError, code_hash


class RestockJobs:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS restock_jobs (
                id TEXT PRIMARY KEY, product_id TEXT NOT NULL, project_id TEXT NOT NULL,
                days INTEGER NOT NULL, quantity INTEGER NOT NULL, target INTEGER NOT NULL,
                batch TEXT UNIQUE NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                codes TEXT NOT NULL DEFAULT '[]', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL, completed_at INTEGER);
              CREATE UNIQUE INDEX IF NOT EXISTS restock_active_sku ON restock_jobs(product_id,days)
                WHERE status != 'complete';
            ''')

    def schedule(self, catalog, mapping, target=5):
        if not 1 <= target <= 100:
            raise ValueError('invalid_stock_target')
        created = promoted = 0
        with self.store.connection(write=True) as db:
            for product in catalog:
                project = mapping[product['id']]
                for plan in product['plans']:
                    sku = (product['id'], plan['days'])
                    # Pending purchases already hold real codes. They must not mint more inventory.
                    active = db.execute("SELECT count(*) FROM stock WHERE product_id=? AND days=? AND state IN ('available','reserved')", sku).fetchone()[0]
                    missing = max(0, target - active)
                    spares = db.execute("SELECT id FROM stock WHERE product_id=? AND days=? AND state='restock_spare' ORDER BY id LIMIT ?", (*sku, missing)).fetchall()
                    for spare in spares:
                        db.execute("UPDATE stock SET state='available' WHERE id=?", (spare['id'],))
                    promoted += len(spares)
                    missing -= len(spares)
                    if not missing or db.execute("SELECT 1 FROM restock_jobs WHERE product_id=? AND days=? AND status!='complete'", sku).fetchone():
                        continue
                    job_id = secrets.token_hex(16)
                    prefix = 'TICKETPRO_WEB_'
                    batch = (prefix + job_id[:32-len(prefix)].upper() if project in {'allticket-leofest', 'ticketplus'}
                             else 'ticketpro-web:auto-' + job_id)
                    db.execute('INSERT INTO restock_jobs(id,product_id,project_id,days,quantity,target,batch,created_at) VALUES (?,?,?,?,?,?,?,?)',
                               (job_id, product['id'], project, plan['days'], missing, target, batch, int(time.time())))
                    created += 1
        return {'scheduled': created, 'promoted': promoted}

    def due(self, limit=20):
        with self.store.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM restock_jobs WHERE status!='complete' AND next_attempt<=? ORDER BY next_attempt,created_at,id LIMIT ?", (int(time.time()), limit))]

    def get(self, job_id):
        with self.store.connection() as db:
            row = db.execute('SELECT * FROM restock_jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                raise ShopError('restock_job_not_found')
            return dict(row)

    def update(self, job_id, status, codes=None, error='', delay=0, attempted=False):
        if status not in {'pending', 'generating', 'generated', 'retry', 'review'}:
            raise ValueError('invalid_restock_status')
        with self.store.connection(write=True) as db:
            row = db.execute('SELECT * FROM restock_jobs WHERE id=?', (job_id,)).fetchone()
            if not row or row['status'] == 'complete':
                return
            db.execute('UPDATE restock_jobs SET status=?,codes=?,last_error=?,next_attempt=?,attempts=attempts+? WHERE id=?',
                       (status, json.dumps(codes) if codes is not None else row['codes'], error,
                        int(time.time()) + delay if delay else 0, int(attempted), job_id))

    def finish(self, job_id, items, manifest_path):
        with self.store.connection(write=True) as db:
            job = db.execute('SELECT * FROM restock_jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise ShopError('restock_job_not_found')
            if job['status'] == 'complete':
                return {'available_added': 0, 'spares_added': 0}
            if job['status'] != 'generated':
                raise ShopError('restock_result_not_validated')
            expected = {code_hash(c) for c in json.loads(job['codes'])}
            if (len(items) != job['quantity'] or len(expected) != len(items)
                    or {code_hash(i['code']) for i in items} != expected
                    or any(i['product_id'] != job['product_id'] or i['project_id'] != job['project_id']
                           or i['days'] != job['days'] or i['batch'] != job['batch']
                           or i['binding_mode'] != 'machine' for i in items)):
                raise ShopError('restock_result_mismatch')
            active = db.execute("SELECT count(*) FROM stock WHERE product_id=? AND days=? AND state IN ('available','reserved')",
                                (job['product_id'], job['days'])).fetchone()[0]
            available = min(len(items), max(0, job['target'] - active))
            states = ['available'] * available + ['restock_spare'] * (len(items) - available)
            self.store._insert_stock(db, items, states)
            self.store._publish_manifest(db, manifest_path)
            # Stock and job completion commit together, including after a lost worker response.
            db.execute("UPDATE restock_jobs SET status='complete',completed_at=?,last_error='' WHERE id=?", (int(time.time()), job_id))
            return {'available_added': available, 'spares_added': len(items) - available}
