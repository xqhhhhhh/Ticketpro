"""Provision issuer adapters on the existing API host; never print credentials.

Without --write this only verifies the live services and their database schemas.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import subprocess
from urllib.parse import urlsplit


def private_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    fd = os.open(temp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    path.chmod(0o600)


def configure(write=False):
    if os.geteuid() != 0:
        raise ValueError('run_on_api_host_as_root')
    root = Path('/opt/ticketpro/server')
    projects = {p['id']: p for p in json.loads((root / 'license-projects.json').read_text())['projects']}
    mapping = json.loads((root / 'product-projects.json').read_text())
    nginx = subprocess.run(['nginx', '-T'], capture_output=True, text=True, check=True).stdout
    known = {'interpark': 'OCR_ADMIN_TOKEN', 'itp': 'OCR_ADMIN_TOKEN', 'melon': 'MELON_OCR_ADMIN_TOKEN',
             'ticketlink': 'TICKETLINK_ADMIN_TOKEN', 'hkticketing': 'HK_LICENSE_ADMIN_TOKEN',
             'galaxyticketing': 'GALAXY_LICENSE_ADMIN_TOKEN'}
    cli = {'ticketmaster_sg', 'tixcraft', 'thaiticketmajor', 'kktix'}
    sources, secrets, writable = {}, {}, set()
    for project_id in sorted(set(mapping.values())):
        project = projects[project_id]
        prefix = urlsplit(project['base_url']).path.rstrip('/') + '/'
        upstreams = []
        for match in re.finditer(r'location\s+([^\{]+)\{([^{}]*)\}', nginx, re.S):
            if match.group(1).strip() == prefix:
                proxy = re.search(r'proxy_pass\s+(http://127\.0\.0\.1:\d+)/?;', match.group(2))
                if proxy:
                    upstreams.append(proxy.group(1))
        if len(set(upstreams)) != 1:
            raise ValueError('source_upstream_ambiguous:' + project_id)
        base = upstreams[0]
        port = urlsplit(base).port
        listeners = subprocess.run(['ss', '-ltnp', 'sport = :' + str(port)], capture_output=True, text=True, check=True).stdout
        pid = re.search(r'pid=(\d+)', listeners).group(1)
        cwd = Path('/proc/' + pid + '/cwd').resolve()
        env = {}
        for entry in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0'):
            if b'=' in entry:
                key, value = entry.split(b'=', 1)
                env[key.decode()] = value.decode()
        source = {'base_url': base, 'headers': {'X-Console-Key': '$TICKETPRO_LICENSE_CONSOLE_KEY',
                                              'X-Admin-Token': '$TICKETPRO_LICENSE_CONSOLE_KEY'}}
        if project_id in known:
            source['kind'] = 'known'
            name = 'TICKETPRO_STOCK_' + project_id.upper() + '_ADMIN_TOKEN'
            secrets[name] = env[known[project_id]]
            source['headers'] = {'X-Admin-Token': '$' + name}
        elif project_id in cli:
            source['kind'] = 'cli'
            source['cwd'] = str(cwd)
            source['python'] = Path('/proc/' + pid + '/cmdline').read_bytes().split(b'\0')[0].decode()
            assert Path(source['python']).is_file() and (cwd / 'manage.py').is_file()
            source['env'] = {}
            for key, value in env.items():
                if re.search(r'ADMIN|CONSOLE|LICENSE|DB_|_DB', key):
                    if re.search(r'KEY|TOKEN|SECRET|PASSWORD', key):
                        name = 'TICKETPRO_STOCK_' + project_id.upper() + '_' + key
                        secrets[name] = value
                        source['env'][key] = '$' + name
                    else:
                        source['env'][key] = value
        elif project_id in {'yes24', 'yes24_kr', 'cityline'}:
            source['kind'] = 'batch'
        elif project_id in {'fantopia', 'klook'}:
            source['kind'] = 'simple'
        elif project_id in {'nol_fleet_professional', 'melon_fleet_professional'}:
            source['kind'] = 'fleet'
        elif project_id == 'allticket-leofest':
            source['kind'] = 'allticket'
        elif project_id in {'ticketplus', 'ibon'}:
            source['kind'] = project_id
        else:
            raise ValueError('unknown_source_project:' + project_id)
        if source['kind'] in {'fleet', 'allticket'}:
            source.update(base_url=project['base_url'], login_path=project.get('login_path') or '/api/admin/login',
                          password='$TICKETPRO_LICENSE_ADMIN_PASSWORD')
        if source['kind'] != 'known':
            if source['kind'] == 'fleet':
                field, default = ('NOL_BACKEND_DATA_DIR', '/var/lib/nol-ultra') if project_id.startswith('nol_') else ('MELON_BACKEND_DATA_DIR', '/var/lib/melon-fleet')
                db_path = Path(env.get(field, default)) / 'ultra.db'
                table, code_field, batch_field = 'licenses', 'code_value', 'batch_name'
            else:
                paths = [v for k, v in env.items() if k.endswith(('_DB_PATH', '_LICENSE_DB', '_DB'))]
                if paths:
                    assert len(paths) == 1
                    db_path = Path(paths[0])
                    if not db_path.is_absolute():
                        db_path = cwd / db_path
                else:
                    filenames = {'yes24': 'yes24_licenses.sqlite3', 'yes24_kr': 'yes24_kr_licenses.sqlite3', 'cityline': 'cityline_licenses.sqlite3'}
                    db_path = cwd / 'data' / filenames[project_id]
                table = 'yes24_licenses' if project_id in {'yes24', 'yes24_kr'} else ('cityline_licenses' if project_id == 'cityline' else ('codes' if source['kind'] == 'allticket' else 'licenses'))
                code_field = 'code' if source['kind'] in {'simple', 'allticket'} else 'activation_code'
                batch_field = 'note' if source['kind'] == 'simple' else ('batch' if source['kind'] in {'allticket', 'ticketplus'} else 'notes')
            with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as db:
                columns = {row[1] for row in db.execute('PRAGMA table_info(' + table + ')')}
                assert {code_field, batch_field} <= columns
            source['recovery'] = {'db': str(db_path.resolve()), 'table': table, 'code': code_field, 'batch': batch_field}
            if source['kind'] == 'cli':
                writable.add(str(db_path.resolve().parent))
        sources[project_id] = source
    if write:
        for filename in ('/etc/ticketpro-stock-sources.json', '/etc/ticketpro-stock.env'):
            path = Path(filename)
            if path.exists():
                private_write(str(path) + '.backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'), path.read_text())
        private_write('/etc/ticketpro-stock-sources.json', json.dumps({'version': 1, 'projects': sources}, indent=2))
        values = {'TICKETPRO_AUTO_RESTOCK': '1', 'TICKETPRO_STOCK_TARGET': '5',
                  'TICKETPRO_STOCK_SOURCES': '/etc/ticketpro-stock-sources.json',
                  'TICKETPRO_STOCK_WORKDIR': '/var/lib/ticketpro-restock', **secrets}
        private_write('/etc/ticketpro-stock.env', '\n'.join(k + '=' + shlex.quote(v) for k, v in values.items()) + '\n')
        path = Path('/etc/ticketpro.env')
        text = path.read_text()
        line = 'TICKETPRO_RESTOCK_SIGNAL=/var/lib/ticketpro/restock.request'
        text = re.sub(r'^TICKETPRO_RESTOCK_SIGNAL=.*$', line, text, flags=re.M) if re.search(r'^TICKETPRO_RESTOCK_SIGNAL=', text, re.M) else text.rstrip() + '\n' + line + '\n'
        private_write(path, text)
        folder = Path('/etc/systemd/system/ticketpro-restock.service.d')
        folder.mkdir(parents=True, exist_ok=True)
        private_write(folder / 'sources.conf', '[Service]\nReadWritePaths=' + ' '.join(json.dumps(p) for p in sorted(writable)) + '\n')
    return {'projects': len(sources), 'private_credential_fields': len(secrets),
            'cli_data_directories': len(writable), 'written': write}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(configure(args.write)))
    except Exception:
        print(json.dumps({'error': 'stock_sources_not_configured; inspect live service mappings and schema'}))
        raise SystemExit(1)
