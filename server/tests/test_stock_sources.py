import json
import sqlite3

import httpx
import pytest

from server.stock_sources import SourceError, StockSource


@pytest.mark.parametrize('kind', ['known', 'batch', 'simple', 'ibon', 'ticketplus', 'allticket', 'fleet'])
def test_issuer_payloads_preserve_batch_days_and_single_device_mode(tmp_path, monkeypatch, kind):
    seen = []
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={'ok': True})
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setenv('ISSUER_KEY', 'issuer-secret')
    c = {'kind': kind, 'base_url': 'https://issuer.example.com', 'headers': {'X-Admin-Token': '$ISSUER_KEY'}}
    source = StockSource(c, tmp_path)
    monkeypatch.setattr(source, 'recover', lambda _job: ['TEST-CODE'])
    source.generate({'id': 'a'*32, 'days': 365, 'quantity': 1, 'batch': 'TICKETPRO_WEB_TEST'}, ['TEST-CODE'])
    body = json.loads(seen[-1].content)
    assert seen[-1].headers['x-admin-token'] == 'issuer-secret'
    assert (body.get('plan_days') or body.get('days')) == 365
    assert (body.get('note') or body.get('notes') or body.get('batch')) == 'TICKETPRO_WEB_TEST'
    assert body['binding_mode'] == ('device' if kind == 'fleet' else 'machine')
    if kind == 'fleet':
        assert body['plan_tier'] == 'ultra' and body['batch_name'] == 'TICKETPRO_WEB_TEST'
    if kind == 'known':
        assert seen[-1].url.path == '/license/admin/create' and body['codes'] == ['TEST-CODE']


def test_recovery_reads_only_exact_batch_without_changing_source_database(tmp_path):
    path = tmp_path / 'source.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE codes(code TEXT,batch TEXT)')
        db.executemany('INSERT INTO codes VALUES (?,?)', [('OUR-CODE', 'our-batch'), ('OLD-CODE', 'old-batch')])
    source = StockSource({'kind': 'batch', 'recovery': {'db': str(path), 'table': 'codes', 'code': 'code', 'batch': 'batch'}}, tmp_path)
    assert source.recover({'batch': 'our-batch', 'quantity': 1}) == ['OUR-CODE']
    assert source.recover({'batch': "x' OR 1=1--", 'quantity': 1}) == []


@pytest.mark.parametrize('status,safe', [(401, True), (422, True), (500, False), (409, False)])
def test_rejected_and_uncertain_generation_are_distinguished(tmp_path, monkeypatch, status, safe):
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(lambda _: httpx.Response(status)), **kw))
    source = StockSource({'kind': 'known', 'base_url': 'https://issuer.example.com', 'headers': {'X-Admin-Token': 'secret'}}, tmp_path)
    with pytest.raises(SourceError) as raised:
        source.generate({'days': 30, 'quantity': 1, 'batch': 'ticketpro-web:test'}, ['TEST-CODE'])
    assert raised.value.retry_safe is safe
