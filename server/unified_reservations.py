"""Copy this module beside unified_license_console/app.py when deploying the bridge."""
import hashlib
import json
import os
from pathlib import Path
import re


def website_reservations(project_id):
    path = os.getenv('UNIFIED_RESERVED_CODES_FILE', '')
    if not path:
        return set()
    # If explicitly configured, a broken/missing file must stop manual stock allocation.
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('projects'), dict):
        raise ValueError('invalid website inventory manifest')
    hashes = data['projects'].get(project_id, [])
    if not isinstance(hashes, list) or any(not re.fullmatch('[a-f0-9]{64}', h) for h in hashes):
        raise ValueError('invalid website inventory hashes')
    return set(hashes)


def is_website_code(code, reserved):
    normalized = re.sub(r'[^A-Z0-9]', '', code.upper())
    return hashlib.sha256(normalized.encode()).hexdigest() in reserved
