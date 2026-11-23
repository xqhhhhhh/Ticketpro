from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from server.app import create_app
from server.config import Settings

PUBLIC = '/commerce/api/help/ticketlink'
ADMIN = '/commerce/api/admin/ticketlink'
AUTH = {'Authorization': 'Bearer test-guide-admin'}


def test_ticketlink_draft_image_and_publication_lifecycle(tmp_path):
    settings = Settings(db=str(tmp_path / 'guide.sqlite3'), admin_key='test-guide-admin',
                        dashboard_key='test-order-dashboard', tutorials='')
    client = TestClient(create_app(settings))
    assert client.get(PUBLIC).json() == {'html': None}
    assert client.get(ADMIN).status_code == 401
    assert client.get(ADMIN, headers={'Authorization': 'Bearer test-order-dashboard'}).status_code == 401

    source = BytesIO()
    Image.new('RGB', (5, 5), 'blue').save(source, format='PNG')
    assert client.post(ADMIN + '/images', content=source.getvalue()).status_code == 401
    invalid = client.post(ADMIN + '/images', content=b'not an image', headers=AUTH)
    assert invalid.status_code == 422
    image = client.post(ADMIN + '/images', content=source.getvalue(), headers=AUTH)
    assert image.status_code == 200
    image_id = image.json()['id']
    assert client.get(PUBLIC + '/images/' + image_id).status_code == 404
    assert client.get(ADMIN + '/images/' + image_id).status_code == 401
    preview = client.get(ADMIN + '/images/' + image_id, headers=AUTH)
    assert preview.headers['content-type'] == 'image/webp'

    content = f'<h2 id="section">教程</h2><img data-guide-image="{image_id}" alt="图解">'
    content += '<iframe src="https://example.com"></iframe><p style="color:red;position:fixed">说明</p>'
    saved = client.post(ADMIN + '/draft', json={'revision': 0, 'html': content}, headers=AUTH)
    assert saved.status_code == 200
    draft = saved.json()
    assert draft['revision'] == 1
    assert '<iframe' not in draft['html']
    assert 'position' not in draft['html']
    assert 'color:red' in draft['html']
    assert client.get(PUBLIC).json() == {'html': None}
    assert client.post(ADMIN + '/publish', json={'revision': 0}, headers=AUTH).status_code == 409
    assert client.post(ADMIN + '/publish', json={'revision': 1}).status_code == 401
    assert client.post(ADMIN + '/publish', json={'revision': 1}, headers=AUTH).status_code == 200
    assert client.get(PUBLIC).json()['html'] == draft['html']
    assert client.get(PUBLIC + '/images/' + image_id).content == preview.content

    new_draft = client.post(ADMIN + '/draft', json={'revision': 1, 'html': '<p>新草稿</p>'}, headers=AUTH)
    assert new_draft.json()['revision'] == 2
    assert client.get(PUBLIC).json()['html'] == draft['html']
    assert client.post(ADMIN + '/publish', json={'revision': 2}, headers=AUTH).status_code == 200
    assert client.get(PUBLIC).json()['html'] == '<p>新草稿</p>'
    assert client.get(PUBLIC + '/images/' + image_id).status_code == 404


def test_configured_guide_password_is_separate_and_rate_limited(tmp_path):
    from hashlib import scrypt

    salt = bytes(range(16))
    expected = scrypt(b'guide-test-password', salt=salt, n=2**14, r=8, p=1, dklen=32)
    settings = Settings(db=str(tmp_path / 'guide.sqlite3'), admin_key='test-guide-admin',
                        guide_password_hash=f'{salt.hex()}:{expected.hex()}', tutorials='')
    client = TestClient(create_app(settings))
    guide = {'Authorization': 'Bearer guide-test-password'}
    assert client.get(ADMIN, headers=AUTH).status_code == 401
    assert client.get(ADMIN, headers=guide).status_code == 200
    assert client.get('/commerce/api/admin/summary', headers=guide).status_code == 401
    assert client.get('/commerce/api/admin/summary', headers=AUTH).status_code == 200
    for _ in range(6):
        assert client.get(ADMIN, headers=AUTH).status_code == 401
    assert client.get(ADMIN, headers=guide).status_code == 429


def test_shared_editor_keeps_guides_separate_and_migrates_existing_ticketlink(tmp_path):
    import sqlite3

    path = tmp_path / 'guide.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript("""
          CREATE TABLE ticketlink_guide (id INTEGER PRIMARY KEY, draft_html TEXT, revision INTEGER,
              published_html TEXT, published_revision INTEGER, published_at TEXT);
          INSERT INTO ticketlink_guide VALUES (1, '<p>旧草稿</p>', 5, '<p>旧教程</p>', 4, '2026-11-23');
          CREATE TABLE ticketlink_guide_images (id TEXT PRIMARY KEY, data BLOB, published INTEGER);
        """)
    settings = Settings(db=str(path), admin_key='test-guide-admin', tutorials='')
    client = TestClient(create_app(settings))
    guides = '/commerce/api/admin/guides'
    melon = '/commerce/api/help/melon'
    assert client.get(guides).status_code == 401
    assert {'ticketlink', 'melon'} <= {item['slug'] for item in client.get(guides, headers=AUTH).json()['guides']}
    assert client.get(PUBLIC).json()['html'] == '<p>旧教程</p>'
    assert client.get(guides + '/ticketlink', headers=AUTH).json()['revision'] == 5

    saved = client.post(guides + '/melon/draft', headers=AUTH, json={'revision': 0, 'html': '<p>Melon 教程</p>'})
    assert saved.json()['revision'] == 1
    assert client.get(melon).json() == {'html': None}
    assert client.post(guides + '/melon/publish', headers=AUTH, json={'revision': 1}).status_code == 200
    assert client.get(melon).json()['html'] == '<p>Melon 教程</p>'
    assert client.get(PUBLIC).json()['html'] == '<p>旧教程</p>'

    new_client = TestClient(create_app(settings))
    assert new_client.get(melon).json()['html'] == '<p>Melon 教程</p>'
    assert new_client.get('/commerce/api/help/nonexistent').status_code == 404
