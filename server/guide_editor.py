from collections import OrderedDict
from datetime import datetime, timezone
from hashlib import scrypt, sha256
from html.parser import HTMLParser
from io import BytesIO
from ipaddress import ip_address
import re
import secrets
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Response
import nh3
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from .store import ShopError

ADMIN_PATH = '/api/admin/ticketlink'
DRAFT_LIMIT = 256 * 1024
IMAGE_LIMIT = 5 * 1024 * 1024
IMAGE_QUOTA = 40 * 1024 * 1024
GUIDE_ADMIN_PATH = '/api/admin/guides'
GUIDE_SLUG = r'[a-z0-9]+(?:-[a-z0-9]+)*'
TOTAL_IMAGE_QUOTA = 100 * 1024 * 1024


def guide_write_limit(path):
    match = re.fullmatch(rf'(?:{ADMIN_PATH}|{GUIDE_ADMIN_PATH}/{GUIDE_SLUG})/(draft|images)', path)
    if not match:
        return 16384
    return DRAFT_LIMIT if match[1] == 'draft' else IMAGE_LIMIT


HEADINGS = {'h2', 'h3', 'h4', 'h5'}
IMAGE_ID = re.compile(r'[a-f0-9]{64}')
HEADING_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,90}')
STATIC_IMAGE = re.compile(r'/help/(?:ticketlink|guides)/images/[a-z0-9-]+\.(?:png|jpg|webp)')


def allowed_attribute(tag, name, value):
    if name == 'src':
        return value if STATIC_IMAGE.fullmatch(value) else None
    if name == 'href':
        if value.startswith('#') and HEADING_ID.fullmatch(value[1:]):
            return value
        try:
            url = urlsplit(value)
            return value if url.scheme == 'https' and url.hostname and not url.username else None
        except ValueError:
            return None
    if name == 'id':
        return value if HEADING_ID.fullmatch(value) else None
    if name == 'data-guide-image':
        return value if IMAGE_ID.fullmatch(value) else None
    return value


CLEANER = nh3.Cleaner(
    tags=HEADINGS | {'p', 'div', 'span', 'b', 'strong', 'em', 'i', 'u', 's', 'strike', 'a',
                     'ul', 'ol', 'li', 'img', 'hr', 'br', 'pre', 'code', 'small', 'blockquote', 'font'},
    clean_content_tags={'script', 'style', 'iframe', 'svg', 'math', 'template'},
    attributes={
        '*': {'style'},
        **{tag: {'id'} for tag in HEADINGS},
        'a': {'href', 'target'},
        'div': {'aria-hidden'},
        'p': {'aria-hidden'},
        'pre': {'aria-label'},
        'ol': {'start'},
        'img': {'src', 'alt', 'width', 'height', 'loading', 'decoding', 'data-guide-image'},
        'font': {'color'},
    },
    allowed_classes={'a': {'tl-guide-attachment'}, 'div': {'tl-guide-grid'}, 'p': {'tl-guide-space'}},
    filter_style_properties={'color', 'background-color', 'text-align', 'font-weight', 'font-style',
                             'text-decoration', 'width', 'height', 'flex'},
    url_schemes={'https'},
    attribute_filter=allowed_attribute,
)


class GuideFragment(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.images = set()
        self.has_content = False
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            image = dict(attrs)
            if image.get('data-guide-image'):
                self.images.add(image['data-guide-image'])
            if image.get('src') or image.get('data-guide-image'):
                self.has_content = True

    def handle_data(self, data):
        if data.strip():
            self.has_content = True


class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0, le=2**53 - 1, strict=True)


class Draft(Revision):
    html: str = Field(max_length=DRAFT_LIMIT)


async def read_limited(request, limit):
    buffer = bytearray()
    async for chunk in request.stream():
        if len(buffer) + len(chunk) > limit:
            raise ShopError('guide_too_large', 413)
        buffer.extend(chunk)
    return bytes(buffer)


async def read_document(request, model, limit):
    try:
        return model.model_validate_json(await read_limited(request, limit))
    except ValidationError as exc:
        raise ShopError('guide_invalid_document', 422) from exc


def encode_image(data):
    try:
        with Image.open(BytesIO(data), formats=('PNG', 'JPEG', 'WEBP')) as image:
            if image.width * image.height > 25_000_000 or image.is_animated:
                raise ShopError('guide_invalid_image', 422)
            image = ImageOps.exif_transpose(image)
            image.thumbnail((2400, 2400))
            pixels = image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB')
            pixels.info.clear()
            output = BytesIO()
            pixels.save(output, format='WEBP', quality=88)
            return output.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ShopError('guide_invalid_image', 422) from exc


def guide_authenticator(settings):
    password_hash = settings.guide_password_hash
    if password_hash and not re.fullmatch(r'[a-f0-9]{32}:[a-f0-9]{64}', password_hash):
        raise ValueError('Invalid TICKETPRO_GUIDE_PASSWORD_HASH format')
    salt, expected = (bytes.fromhex(part) for part in password_hash.split(':')) if password_hash else (b'', b'')
    attempts = OrderedDict()
    lock = Lock()

    def authenticate(request):
        header = request.headers.get('authorization', '')
        if not password_hash:
            if settings.admin_key and secrets.compare_digest(header.encode(), ('Bearer ' + settings.admin_key).encode()):
                return
            raise ShopError('unauthorized', 401)
        if not header.startswith('Bearer ') or not 7 < len(header) <= 263:
            raise ShopError('unauthorized', 401)

        peer = request.client.host
        if settings.trusted_proxy and peer in {'127.0.0.1', '::1'}:
            try:
                peer = str(ip_address(request.headers.get('x-real-ip', peer)))
            except ValueError:
                pass

        with lock:
            now = monotonic()
            failures, expires = attempts.get(peer, (0, 0))
            if now >= expires:
                failures, expires = 0, now + 600
            if failures >= 6:
                raise ShopError('guide_login_limited', 429)
            actual = scrypt(header[7:].encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
            if not secrets.compare_digest(actual, expected):
                attempts[peer] = (failures + 1, expires)
                attempts.move_to_end(peer)
                if len(attempts) > 2048:
                    attempts.popitem(last=False)
                raise ShopError('unauthorized', 401)
            attempts.pop(peer, None)

    return authenticate


def build_router(store, settings, catalog):
    authenticate = guide_authenticator(settings)
    router = APIRouter()
    guides = {item['id']: item['name'] for item in catalog}
    with store.connection(write=True) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS guide_documents (
            slug TEXT PRIMARY KEY, draft_html TEXT, revision INTEGER NOT NULL DEFAULT 0,
            published_html TEXT, published_revision INTEGER, published_at TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS guide_images (
            slug TEXT NOT NULL REFERENCES guide_documents(slug), id TEXT NOT NULL,
            data BLOB NOT NULL, published INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(slug,id))''')
        legacy_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticketlink_guide'").fetchone()
        if legacy_exists:
            migrated = db.execute('''INSERT OR IGNORE INTO guide_documents
                SELECT 'ticketlink',draft_html,revision,published_html,published_revision,published_at
                FROM ticketlink_guide WHERE id=1''').rowcount
            if migrated:
                db.execute('''INSERT OR IGNORE INTO guide_images
                    SELECT 'ticketlink',id,data,published FROM ticketlink_guide_images''')
        db.executemany('INSERT OR IGNORE INTO guide_documents(slug) VALUES (?)', ((slug,) for slug in guides))

    def ensure_guide(slug):
        if slug not in guides:
            raise ShopError('guide_not_found', 404)

    def status(db, slug):
        return dict(db.execute('''SELECT draft_html AS html, revision, published_revision, published_at
                                  FROM guide_documents WHERE slug=?''', (slug,)).fetchone())

    def save(slug, payload):
        html = CLEANER.clean(payload.html)
        fragment = GuideFragment(html)
        if not fragment.has_content:
            raise ShopError('guide_empty_document', 422)
        with store.connection(write=True) as db:
            current = status(db, slug)
            if current['revision'] != payload.revision:
                raise ShopError('guide_revision_conflict', 409)
            available = {row['id'] for row in db.execute('SELECT id FROM guide_images WHERE slug=?', (slug,))}
            if not fragment.images <= available:
                raise ShopError('guide_missing_image', 422)
            if current['html'] != html:
                db.execute('UPDATE guide_documents SET draft_html=?, revision=revision+1 WHERE slug=?', (html, slug))
            return status(db, slug)

    def publish(slug, payload):
        with store.connection(write=True) as db:
            current = status(db, slug)
            if payload.revision != current['revision']:
                raise ShopError('guide_revision_conflict', 409)
            if current['html'] is None:
                raise ShopError('guide_empty_document', 422)
            if current['published_revision'] != current['revision']:
                images = GuideFragment(current['html']).images
                db.execute('UPDATE guide_images SET published=0 WHERE slug=? AND published=1', (slug,))
                db.executemany('UPDATE guide_images SET published=1 WHERE slug=? AND id=?',
                               ((slug, image_id) for image_id in images))
                db.execute('''UPDATE guide_documents
                    SET published_html=draft_html, published_revision=revision, published_at=? WHERE slug=?''',
                           (datetime.now(timezone.utc).isoformat(), slug))
            return status(db, slug)

    def store_image(slug, data):
        content = encode_image(data)
        image_id = sha256(content).hexdigest()
        with store.connection(write=True) as db:
            if db.execute('SELECT 1 FROM guide_images WHERE slug=? AND id=?', (slug, image_id)).fetchone():
                return {'id': image_id}
            used = db.execute('SELECT COALESCE(SUM(length(data)), 0) FROM guide_images WHERE slug=?', (slug,)).fetchone()[0]
            total = db.execute('SELECT COALESCE(SUM(length(data)), 0) FROM guide_images').fetchone()[0]
            if used + len(content) > IMAGE_QUOTA or total + len(content) > TOTAL_IMAGE_QUOTA:
                raise ShopError('guide_image_quota', 413)
            db.execute('INSERT INTO guide_images(slug,id,data) VALUES (?,?,?)', (slug, image_id, content))
        return {'id': image_id}

    def image_response(slug, image_id, private=False):
        ensure_guide(slug)
        if not IMAGE_ID.fullmatch(image_id):
            raise ShopError('guide_missing_image', 404)
        with store.connection() as db:
            row = db.execute('SELECT data FROM guide_images WHERE slug=? AND id=? AND (published=1 OR ?)',
                             (slug, image_id, private)).fetchone()
        if row is None:
            raise ShopError('guide_missing_image', 404)
        return Response(row['data'], media_type='image/webp')

    @router.get('/api/help/{slug}')
    def public_guide(slug: str):
        ensure_guide(slug)
        with store.connection() as db:
            row = db.execute('SELECT published_html AS html FROM guide_documents WHERE slug=?', (slug,)).fetchone()
            return {'html': row['html']}

    @router.get('/api/help/{slug}/images/{image_id}')
    def public_image(slug: str, image_id: str):
        return image_response(slug, image_id)

    @router.get(GUIDE_ADMIN_PATH)
    def guide_index(request: Request):
        authenticate(request)
        with store.connection() as db:
            rows = db.execute('SELECT slug, revision, published_revision FROM guide_documents').fetchall()
            states = {row['slug']: dict(row) for row in rows}
        return {'guides': [{'slug': slug, 'name': name, **states[slug]} for slug, name in guides.items()]}

    @router.get(GUIDE_ADMIN_PATH + '/{slug}')
    @router.get(ADMIN_PATH, include_in_schema=False)
    def admin_guide(request: Request, slug: str = 'ticketlink'):
        authenticate(request)
        ensure_guide(slug)
        with store.connection() as db:
            return status(db, slug)

    @router.get(GUIDE_ADMIN_PATH + '/{slug}/images/{image_id}')
    @router.get(ADMIN_PATH + '/images/{image_id}', include_in_schema=False)
    def admin_image(image_id: str, request: Request, slug: str = 'ticketlink'):
        authenticate(request)
        return image_response(slug, image_id, private=True)

    @router.post(GUIDE_ADMIN_PATH + '/{slug}/draft')
    @router.post(ADMIN_PATH + '/draft', include_in_schema=False)
    async def save_draft(request: Request, slug: str = 'ticketlink'):
        await run_in_threadpool(authenticate, request)
        ensure_guide(slug)
        payload = await read_document(request, Draft, DRAFT_LIMIT)
        return await run_in_threadpool(save, slug, payload)

    @router.post(GUIDE_ADMIN_PATH + '/{slug}/publish')
    @router.post(ADMIN_PATH + '/publish', include_in_schema=False)
    async def publish_guide(request: Request, slug: str = 'ticketlink'):
        await run_in_threadpool(authenticate, request)
        ensure_guide(slug)
        payload = await read_document(request, Revision, 1024)
        return await run_in_threadpool(publish, slug, payload)

    @router.post(GUIDE_ADMIN_PATH + '/{slug}/images')
    @router.post(ADMIN_PATH + '/images', include_in_schema=False)
    async def upload_image(request: Request, slug: str = 'ticketlink'):
        await run_in_threadpool(authenticate, request)
        ensure_guide(slug)
        data = await read_limited(request, IMAGE_LIMIT)
        return await run_in_threadpool(store_image, slug, data)

    return router
