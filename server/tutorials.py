"""Server-only product-to-tutorial mapping, collected from existing license settings."""
import json
import os
from pathlib import Path

from .gateway import https_url
from .store import ShopError

DEFAULT_PATH = str(Path(__file__).with_name('tutorials.local.json'))


def load_tutorials(path=None):
    configured = path if path is not None else os.getenv('TICKETPRO_TUTORIALS', DEFAULT_PATH)
    if not configured or not Path(configured).exists():
        return {}
    data = json.loads(Path(configured).read_text())
    if not isinstance(data, dict):
        raise ShopError('invalid_tutorial_mapping', 503)
    links = data.get('tutorials', {})
    if data.get('version') != 1 or not isinstance(links, dict):
        raise ShopError('invalid_tutorial_mapping', 503)
    if any(not isinstance(url, str) or not https_url(url) for url in links.values()):
        raise ShopError('invalid_tutorial_url', 503)
    return links
