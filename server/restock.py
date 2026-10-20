"""Bounded, recoverable replenishment. Run separately from the payment web service."""
import argparse
from contextlib import nullcontext
import fcntl
import json
import os
from pathlib import Path

import httpx

from .config import ROOT, Settings
from .licenses import prepare_stock
from .restock_store import RestockJobs
from .stock_sources import StockSource, SourceError, load_sources, new_codes
from .store import ShopError, Store, code_hash
from .tutorials import load_tutorials


def replenish(store, catalog, mapping, sources, registry, manifest, tutorials, *,
              identity=nullcontext, target=5, limit=20, supplier_factory=None, validator=prepare_stock):
    """Only stock/queue operations switch to the website DB's owner identity."""
    with identity():
        jobs = RestockJobs(store)
        scheduled = jobs.schedule(catalog, mapping, target)
        due = jobs.due(limit)
    result = {**scheduled, 'completed': 0, 'available_added': 0, 'spares_added': 0, 'deferred': 0, 'review': 0}
    allowed = {(p['id'], t['days']): mapping[p['id']] for p in catalog for t in p['plans']}
    for job in due:
        supplier = None
        try:
            if (allowed.get((job['product_id'], job['days'])) != job['project_id']
                    or not 1 <= job['quantity'] <= job['target'] <= 100):
                raise ShopError('restock_job_config_mismatch')
            supplier = supplier_factory(job) if supplier_factory else StockSource(sources[job['project_id']], os.getenv('TICKETPRO_STOCK_WORKDIR', '/var/lib/ticketpro-restock'))
            codes = json.loads(job['codes'])
            def validate(values):
                return validator(registry, job['product_id'], job['project_id'], job['days'],
                                 job['batch'], values, tutorials[job['product_id']])
            def quarantine(values):
                with identity():
                    store.quarantine_stock(job['project_id'], values, manifest)

            if supplier.known:
                if not codes:
                    codes = new_codes(job['quantity'])
                    with identity():
                        jobs.update(job['id'], 'pending', codes=codes)
                quarantine(codes)
                missing = []
                for code in codes:
                    try:
                        validate([code])
                    except httpx.HTTPStatusError as error:
                        if error.response.status_code != 404:
                            raise
                        missing.append(code)
                if missing:
                    with identity():
                        jobs.update(job['id'], 'generating', attempted=True)
                    supplier.generate(job, missing)
            elif job['status'] != 'generated' or not codes:
                recovered = supplier.recover(job)
                if recovered:
                    codes = recovered
                elif job['status'] in {'generating', 'review'}:
                    # A previous request may have committed. Never mint another random batch blindly.
                    raise SourceError('source_response_uncertain')
                else:
                    with identity():
                        jobs.update(job['id'], 'generating', attempted=True)
                    codes = supplier.generate(job)
            if codes:
                quarantine(codes)
                with identity():
                    jobs.update(job['id'], 'generated' if len(codes) == job['quantity'] else 'review', codes=codes)
            if len(codes) != job['quantity'] or len({code_hash(c) for c in codes}) != len(codes):
                raise SourceError('source_count_mismatch')
            items = validate(codes)
            with identity():
                added = jobs.finish(job['id'], items, manifest)
            result['completed'] += 1
            for key in ('available_added', 'spares_added'):
                result[key] += added[key]
        except Exception as error:
            with identity():
                current = jobs.get(job['id'])
            if current['status'] == 'complete':
                continue
            known = supplier is not None and supplier.known
            generated = current['status'] == 'generated'
            retry_safe = isinstance(error, SourceError) and error.retry_safe
            uncertain = not known and current['status'] in {'generating', 'review'} and not retry_safe
            review = isinstance(error, ShopError) or uncertain or (isinstance(error, SourceError) and error.code == 'source_count_mismatch')
            status = 'review' if review else ('generated' if generated else 'retry')
            label = error.code if isinstance(error, SourceError) else ('stock_validation_failed' if isinstance(error, ShopError) else 'stock_source_unavailable')
            delay = min(900, 30 * 2 ** min(current['attempts'], 5))
            with identity():
                jobs.update(job['id'], status, error=label, delay=max(300 if review else 30, delay))
            result['review' if review else 'deferred'] += 1
    return result


def main():
    parser = argparse.ArgumentParser(description='自动补充网站专用库存，不输出激活码或密钥')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--check', action='store_true', help='只检查配置和当前缺口，不生成激活码')
    args = parser.parse_args()
    if not 1 <= args.limit <= 64:
        raise ValueError('invalid_batch_limit')
    settings = Settings.from_env()
    if settings.demo or os.getenv('TICKETPRO_AUTO_RESTOCK') != '1':
        raise ValueError('production_auto_restock_not_enabled')
    workdir = Path(os.getenv('TICKETPRO_STOCK_WORKDIR', '/var/lib/ticketpro-restock'))
    workdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (workdir / 'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'already_running': True}))
            return 0
        identity = nullcontext
        if os.geteuid() == 0:
            from contextlib import contextmanager
            import grp
            import pwd
            uid = pwd.getpwnam('ticketpro').pw_uid
            gid = grp.getgrnam('ticketpro-web').gr_gid
            @contextmanager
            def identity():
                old_uid, old_gid = os.geteuid(), os.getegid()
                os.setegid(gid)
                os.seteuid(uid)
                try:
                    yield
                finally:
                    os.seteuid(old_uid)
                    os.setegid(old_gid)
        sources = load_sources(os.environ['TICKETPRO_STOCK_SOURCES'])
        catalog = json.loads(Path(settings.catalog).read_text())
        mapping = json.loads(Path(os.getenv('TICKETPRO_PRODUCT_PROJECTS', ROOT / 'product-projects.json')).read_text())
        if not set(mapping[p['id']] for p in catalog) <= sources.keys():
            raise ValueError('stock_sources_incomplete')
        with identity():
            store = Store(settings.db)
        target = int(os.getenv('TICKETPRO_STOCK_TARGET', '5'))
        if args.check:
            with identity(), store.connection() as db:
                deficits = []
                for product in catalog:
                    for plan in product['plans']:
                        active = db.execute("SELECT count(*) FROM stock WHERE product_id=? AND days=? AND state IN ('available','reserved')", (product['id'], plan['days'])).fetchone()[0]
                        if active < target:
                            deficits.append({'product_id': product['id'], 'days': plan['days'], 'missing': target-active})
            print(json.dumps({'enabled': True, 'target': target, 'sources': len(sources), 'deficits': deficits}))
            return 0
        result = replenish(store, catalog, mapping, sources, os.environ['UNIFIED_LICENSE_CONFIG'],
                           os.environ['UNIFIED_RESERVED_CODES_FILE'], load_tutorials(settings.tutorials),
                           identity=identity, target=target, limit=args.limit)
        print(json.dumps(result))
        return 1 if result['review'] or result['deferred'] else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({'error': 'auto_restock_configuration_or_runtime_error'}))
        raise SystemExit(1)
