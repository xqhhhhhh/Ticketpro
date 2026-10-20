"""Consistent SQLite backups with the inventory isolation and delivery configuration."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3

from .config import ROOT
from .store import ShopError, code_hash


def backup_shop(settings, directory):
    source = Path(settings.db)
    if not source.is_file():
        raise ShopError('正式订单数据库不存在，未创建备份')
    manifest = Path(os.environ.get('UNIFIED_RESERVED_CODES_FILE', ''))
    if not manifest.is_file():
        raise ShopError('库存隔离清单不存在，不能创建不完整备份')
    target = Path(directory) / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3))
    target.mkdir(parents=True, mode=0o700)
    target.chmod(0o700)
    try:
        dest = target / 'shop.sqlite3'
        with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as live:
            with sqlite3.connect(dest) as snapshot:
                live.backup(snapshot)
                if snapshot.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ShopError('订单数据库备份校验失败')
                rows = snapshot.execute('SELECT project_id, code_hash, code FROM stock').fetchall()
        dest.chmod(0o600)
        # Read AFTER taking the DB snapshot: imports publish the manifest before the DB commit.
        exclusions = json.loads(manifest.read_text())
        if not isinstance(exclusions, dict) or exclusions.get('version') != 1 or not isinstance(exclusions.get('projects'), dict):
            raise ShopError('库存隔离清单格式错误')
        if any(h != code_hash(code) or h not in exclusions['projects'].get(project, []) for project, h, code in rows):
            raise ShopError('订单备份与隔离清单不一致')
        paths = [(manifest, 'web-reserved-codes.json'), (Path(settings.catalog), 'catalog.json'),
                 (Path(settings.tutorials), 'tutorials.json'),
                 (Path(os.getenv('TICKETPRO_PRODUCT_PROJECTS', ROOT / 'product-projects.json')), 'product-projects.json')]
        for path, name in paths:
            if not path.is_file():
                raise ShopError('交付配置缺失，备份未完成')
            if name == 'web-reserved-codes.json':
                (target / name).write_text(json.dumps(exclusions))
            else:
                shutil.copyfile(path, target / name)
            (target / name).chmod(0o600)
        (target / 'complete.json').write_text(json.dumps({'version': 1, 'stock_count': len(rows),
                                                        'mode': 'demo' if settings.demo else 'production'}))
        (target / 'complete.json').chmod(0o600)
        return {'directory': str(target), 'stock_count': len(rows), 'integrity': 'ok'}
    except Exception:
        shutil.rmtree(target)
        raise
