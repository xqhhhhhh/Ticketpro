import json
import secrets

import httpx
import pytest

from server.restock import replenish
from server.restock_store import RestockJobs
from server.stock_sources import SourceError
from server.store import ShopError, Store, code_hash


@pytest.fixture
def inventory(tmp_path):
    store = Store(tmp_path / 'shop.db')
    manifest = tmp_path / 'reserved.json'
    product = {'id': 'interpark', 'name': 'Interpark'}
    plan = {'days': 30, 'duration': '1个月', 'cents': 8800}
    catalog = [{**product, 'plans': [plan]}]
    records = {}
    calls = []
    failure = {'mode': None}

    def item(code, batch):
        return {'product_id': 'interpark', 'project_id': 'interpark', 'days': 30, 'code': code,
                'binding_mode': 'machine', 'batch': batch, 'tutorial_url': 'https://example.com/guide'}

    store.import_stock([item('INITIAL-' + str(n), 'ticketpro-web:initial') for n in range(5)], manifest)
    jobs = RestockJobs(store)

    class Supplier:
        known = False

        def recover(self, job):
            return [c for c, i in records.items() if i['batch'] == job['batch']]

        def generate(self, job, codes=None):
            calls.append(job['quantity'])
            if failure['mode'] == 'unreachable':
                failure['mode'] = None
                raise SourceError('source_connect_failed', retry_safe=True)
            if failure['mode'] == 'uncertain_empty':
                raise SourceError('source_response_uncertain')
            created = codes or ['REAL-' + job['id'] + '-' + str(n) for n in range(job['quantity'])]
            for code in created:
                records[code] = item(code, job['batch'])
            if failure['mode'] == 'lost_reply':
                failure['mode'] = None
                raise SourceError('source_response_uncertain')
            if failure['mode'] == 'manual_fill':
                failure['mode'] = None
                store.import_stock([item('MANUAL-FILL', 'ticketpro-web:manual')], manifest)
            return created

    supplier = Supplier()

    def validate(_registry, _product, _project, _days, batch, codes, _tutorial):
        for code in codes:
            if code not in records:
                response = httpx.Response(404, request=httpx.Request('POST', 'https://example.com/code'))
                raise httpx.HTTPStatusError('missing', request=response.request, response=response)
            if records[code]['batch'] != batch or failure['mode'] == 'invalid_stock':
                raise ShopError('invalid_stock')
        return [records[c] for c in codes]

    def run():
        return replenish(store, catalog, {'interpark': 'interpark'}, {}, 'registry', manifest,
                         {'interpark': 'https://example.com/guide'},
                         supplier_factory=lambda _job: supplier, validator=validate)

    def order(deliver=True):
        value, _ = store.create(product, plan, secrets.token_hex(16), secrets.token_hex(32), secrets.token_hex(16))
        if deliver:
            store.deliver(value['id'], 'paid-' + value['id'])
        return value

    def retry_now():
        with store.connection(write=True) as db:
            db.execute('UPDATE restock_jobs SET next_attempt=0')

    return store, jobs, manifest, supplier, records, calls, failure, run, order, retry_now, item


def test_full_inventory_and_pending_orders_do_not_generate(inventory):
    store, jobs, _, _, _, calls, _, run, order, *_ = inventory
    assert run()['scheduled'] == 0
    order(deliver=False)
    assert store.counts()[('interpark', 30)] == 4
    assert run()['scheduled'] == 0
    assert jobs.due() == [] and calls == []


def test_delivery_wakes_worker_and_duplicate_delivery_does_not_restock_twice(inventory, tmp_path, monkeypatch):
    store, _, _, _, _, calls, _, run, order, *_ = inventory
    signal = tmp_path / 'restock.request'
    monkeypatch.setenv('TICKETPRO_RESTOCK_SIGNAL', str(signal))
    value = order()
    original = store.public_order(store.order(value['id']))['delivery']['code']
    stamp = signal.stat().st_mtime_ns
    store.deliver(value['id'], 'paid-' + value['id'])
    assert signal.stat().st_mtime_ns == stamp
    assert run()['available_added'] == 1
    assert run()['scheduled'] == 0
    assert calls == [1] and store.counts()[('interpark', 30)] == 5
    assert store.public_order(store.order(value['id']))['delivery']['code'] == original
    assert 'REAL-' not in json.dumps(store.summary())


def test_multiple_sales_coalesce_into_exact_missing_quantity(inventory):
    store, _, _, _, _, calls, _, run, order, *_ = inventory
    for _ in range(3):
        order()
    assert run()['available_added'] == 3
    assert calls == [3] and store.counts()[('interpark', 30)] == 5


def test_lost_response_recovers_same_source_batch_after_restart(inventory):
    store, jobs, _, _, _, calls, failure, run, order, retry, _ = inventory
    order()
    failure['mode'] = 'lost_reply'
    assert run()['review'] == 1
    assert store.counts()[('interpark', 30)] == 4
    retry()
    assert run()['available_added'] == 1
    assert calls == [1]
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM restock_jobs WHERE status='complete'").fetchone()[0] == 1


def test_uncertain_empty_batch_is_never_dispatched_again_blindly(inventory):
    store, _, _, _, _, calls, failure, run, order, retry, _ = inventory
    order()
    failure['mode'] = 'uncertain_empty'
    assert run()['review'] == 1
    retry()
    assert run()['review'] == 1
    assert calls == [1] and store.counts()[('interpark', 30)] == 4


def test_definite_connection_failure_retries_without_losing_job(inventory):
    store, _, _, _, _, calls, failure, run, order, retry, _ = inventory
    order()
    failure['mode'] = 'unreachable'
    assert run()['deferred'] == 1
    retry()
    assert run()['available_added'] == 1
    assert calls == [1, 1] and store.counts()[('interpark', 30)] == 5


def test_invalid_generated_code_is_quarantined_and_never_sold(inventory):
    store, _, manifest, _, records, calls, failure, run, order, retry, _ = inventory
    order()
    failure['mode'] = 'invalid_stock'
    assert run()['review'] == 1
    excluded = json.loads(manifest.read_text())['projects']['interpark']
    assert all(code_hash(c) in excluded for c in records)
    retry()
    assert run()['review'] == 1
    assert calls == [1] and store.counts()[('interpark', 30)] == 4


def test_manual_fill_during_generation_keeps_excess_as_spare(inventory):
    store, _, _, _, _, calls, failure, run, order, *_ = inventory
    order()
    failure['mode'] = 'manual_fill'
    result = run()
    assert result['available_added'] == 0 and result['spares_added'] == 1
    assert store.counts()[('interpark', 30)] == 5
    order()
    assert run()['promoted'] == 1
    assert store.counts()[('interpark', 30)] == 5 and calls == [1]


def test_job_and_stock_commit_together_on_publish_failure(inventory, monkeypatch):
    store, _, _, _, _, calls, _, run, order, retry, _ = inventory
    order()
    original = RestockJobs.finish
    fail = {'once': True}
    def finish(self, job_id, items, manifest):
        if fail['once']:
            fail['once'] = False
            original_publish = self.store._publish_manifest
            def bad_publish(*_args, **_kwargs):
                raise OSError('disk temporarily unavailable')
            with monkeypatch.context() as patch:
                patch.setattr(self.store, '_publish_manifest', bad_publish)
                return original(self, job_id, items, manifest)
        return original(self, job_id, items, manifest)
    monkeypatch.setattr(RestockJobs, 'finish', finish)
    assert run()['deferred'] == 1
    assert store.counts()[('interpark', 30)] == 4
    retry()
    assert run()['available_added'] == 1
    assert calls == [1]


def test_known_code_candidates_survive_issuer_timeout(inventory):
    store, _, _, supplier, _, calls, failure, run, order, retry, _ = inventory
    supplier.known = True
    order()
    failure['mode'] = 'lost_reply'
    assert run()['deferred'] == 1
    retry()
    assert run()['available_added'] == 1
    assert calls == [1] and store.counts()[('interpark', 30)] == 5


def test_concurrent_schedulers_create_one_active_job(inventory):
    from concurrent.futures import ThreadPoolExecutor
    store, jobs, _, _, _, _, _, _, order, *_ = inventory
    order()
    catalog = [{'id': 'interpark', 'plans': [{'days': 30}]}]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: jobs.schedule(catalog, {'interpark': 'interpark'}), range(4)))
    assert sum(r['scheduled'] for r in results) == 1
    assert len(jobs.due()) == 1


def test_import_preserves_previously_quarantined_codes(inventory):
    store, _, manifest, _, _, _, _, _, _, _, item = inventory
    store.quarantine_stock('interpark', ['NOT-YET-IMPORTED'], manifest)
    store.import_stock([item('MANUAL-NEW', 'ticketpro-web:manual')], manifest)
    assert code_hash('NOT-YET-IMPORTED') in json.loads(manifest.read_text())['projects']['interpark']
