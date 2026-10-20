import os
from dataclasses import dataclass
from pathlib import Path

from .tutorials import DEFAULT_PATH as TUTORIALS_PATH

ROOT = Path(__file__).resolve().parent


@dataclass
class Settings:
    db: str = str(ROOT / 'data/shop.sqlite3')
    catalog: str = str(ROOT / 'catalog.json')
    pid: str = ''
    key: str = ''
    cid: str = ''
    site_url: str = ''
    api_url: str = ''
    admin_key: str = ''
    demo: bool = False
    origins: tuple = ()
    trusted_proxy: bool = False
    tutorials: str = TUTORIALS_PATH

    @classmethod
    def from_env(cls):
        return cls(db=os.getenv('TICKETPRO_DB', cls.db),
                   catalog=os.getenv('TICKETPRO_CATALOG', cls.catalog),
                   pid=os.getenv('ZPAY_PID', ''), key=os.getenv('ZPAY_KEY', ''), cid=os.getenv('ZPAY_CID', ''),
                   site_url=os.getenv('TICKETPRO_SITE_URL', '').rstrip('/'),
                   api_url=os.getenv('TICKETPRO_API_URL', '').rstrip('/'),
                   admin_key=os.getenv('TICKETPRO_ADMIN_KEY', ''), demo=os.getenv('TICKETPRO_DEMO') == '1',
                   origins=tuple(filter(None, os.getenv('TICKETPRO_ORIGINS', '').split(','))),
                   trusted_proxy=os.getenv('TICKETPRO_TRUST_LOOPBACK_PROXY') == '1',
                   tutorials=os.getenv('TICKETPRO_TUTORIALS', TUTORIALS_PATH))
