"""Existing license issuers. Credentials and host-specific paths stay in root-only config."""
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
from urllib.parse import urlsplit

import httpx

from .licenses import env_value


class SourceError(Exception):
    def __init__(self, code, retry_safe=False):
        self.code, self.retry_safe = code, retry_safe


def new_codes(count):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ['TPWB-' + '-'.join(''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4))
            for _ in range(count)]


class StockSource:
    def __init__(self, config, workdir):
        self.config = config
        self.workdir = Path(workdir)
        self.known = config['kind'] == 'known'

    def recover(self, job):
        if self.known:
            return []
        recovery = self.config['recovery']
        identifiers = [recovery[k] for k in ('table', 'code', 'batch')]
        if not all(re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]*', name) for name in identifiers):
            raise SourceError('invalid_source_schema')
        table, code, batch = identifiers
        with sqlite3.connect(Path(recovery['db']).resolve().as_uri() + '?mode=ro', uri=True) as db:
            return [r[0].strip().upper() for r in db.execute(
                f'SELECT "{code}" FROM "{table}" WHERE "{batch}"=? LIMIT ?',
                (job['batch'], job['quantity'] + 1)) if isinstance(r[0], str) and r[0].strip()]

    def generate(self, job, codes=None):
        c = self.config
        kind, days, count, batch = c['kind'], job['days'], job['quantity'], job['batch']
        if kind == 'cli':
            if not re.fullmatch('[a-f0-9]{32}', job['id']):
                raise SourceError('invalid_job_id')
            self.workdir.mkdir(parents=True, exist_ok=True, mode=0o700)
            export = self.workdir / (job['id'] + '.txt')
            env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
                   'PYTHONDONTWRITEBYTECODE': '1'}
            env.update({key: env_value(value) for key, value in c.get('env', {}).items()})
            args = [c['python'], 'manage.py', 'bulk-generate', '--prefix', 'TPWB', '--count', str(count),
                    '--days', str(days), '--notes', batch, '--binding-mode', 'machine',
                    '--expires-at', '0', '--output', str(export), '--format', 'txt']
            try:
                result = subprocess.run(args, cwd=c['cwd'], env=env, capture_output=True, timeout=60)
            except subprocess.TimeoutExpired:
                raise SourceError('source_cli_timeout') from None
            recovered = self.recover(job)
            if recovered:
                return recovered
            if result.returncode:
                raise SourceError('source_cli_failed', retry_safe=True)
            raise SourceError('source_result_missing')

        payload = {'count': count, 'plan_days': days, 'prefix': 'TPWB', 'note': batch, 'binding_mode': 'machine'}
        path = '/console/api/generate'
        if kind == 'known':
            if not codes:
                raise SourceError('source_candidates_missing')
            path = '/license/admin/create'
            payload = {'codes': codes, 'plan_days': days, 'note': batch, 'binding_mode': 'machine'}
        elif kind == 'batch':
            path = '/console/api/generate-batch'
            payload = {'plan_days': days, 'count': count, 'notes': batch, 'binding_mode': 'machine'}
        elif kind == 'simple':
            path = '/admin/generate'
            payload = {'count': count, 'days': days, 'prefix': 'TPWB', 'note': batch, 'binding_mode': 'machine'}
        elif kind == 'ibon':
            payload = {'prefix': 'TPWB', 'count': count, 'days': days, 'binding_mode': 'machine', 'notes': batch}
        elif kind == 'ticketplus':
            payload = {'days': days, 'binding_mode': 'machine', 'count': count, 'batch': batch}
        elif kind == 'allticket':
            path = '/api/admin/generate'
            payload = {'batch': batch, 'count': count, 'days': days, 'binding_mode': 'machine', 'prefix': 'TPWB'}
        elif kind == 'fleet':
            payload = {'count': count, 'plan_tier': 'ultra', 'plan_days': days, 'binding_mode': 'device',
                       'batch_name': batch, 'note': batch}
        else:
            raise SourceError('unknown_source_kind')
        headers = {key: env_value(value) for key, value in c.get('headers', {}).items()}
        if not headers or not all(headers.values()):
            raise SourceError('source_credentials_missing', retry_safe=True)
        base = c['base_url'].rstrip('/')
        parsed = urlsplit(base)
        if (parsed.username or parsed.password or parsed.query or parsed.fragment
                or not ((parsed.scheme == 'https' and parsed.hostname)
                        or (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port and not parsed.path))):
            raise SourceError('invalid_source_url')
        try:
            with httpx.Client(timeout=20) as client:
                if c.get('login_path'):
                    password = env_value(c.get('password', ''))
                    if not password:
                        raise SourceError('source_login_missing', retry_safe=True)
                    response = client.post(base + c['login_path'], json={'password': password})
                    if response.status_code != 200:
                        raise SourceError('source_login_rejected', retry_safe=True)
                response = client.post(base + path, json=payload, headers=headers)
            if response.status_code != 200:
                raise SourceError('source_request_rejected', retry_safe=response.status_code in {400, 401, 403, 404, 422, 429})
            if kind == 'known':
                return codes
            return self.recover(job)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise SourceError('source_connect_failed', retry_safe=True) from None
        except httpx.HTTPError:
            raise SourceError('source_response_uncertain') from None


def load_sources(path):
    data = json.loads(Path(path).read_text())
    if data.get('version') != 1 or not isinstance(data.get('projects'), dict):
        raise ValueError('invalid_stock_sources')
    return data['projects']
