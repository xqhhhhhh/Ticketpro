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
