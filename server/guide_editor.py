from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import re
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Response
import nh3
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from .store import ShopError

ADMIN_PATH = '/api/admin/ticketlink'
PUBLIC_PATH = '/api/help/ticketlink'
DRAFT_LIMIT = 256 * 1024
IMAGE_LIMIT = 5 * 1024 * 1024
IMAGE_QUOTA = 40 * 1024 * 1024
WRITE_LIMITS = {
    ADMIN_PATH + '/draft': DRAFT_LIMIT,
    ADMIN_PATH + '/images': IMAGE_LIMIT,
}
HEADINGS = {'h2', 'h3', 'h4', 'h5'}
IMAGE_ID = re.compile(r'[a-f0-9]{64}')
HEADING_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,90}')
STATIC_IMAGE = re.compile(r'/help/ticketlink/images/[a-z0-9-]+\.(?:png|jpg|webp)')


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


def build_router(store, admin_key):
    router = APIRouter()
    with store.connection(write=True) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS ticketlink_guide (
            id INTEGER PRIMARY KEY CHECK(id=1), draft_html TEXT, revision INTEGER NOT NULL DEFAULT 0,
            published_html TEXT, published_revision INTEGER, published_at TEXT)''')
        db.execute('INSERT OR IGNORE INTO ticketlink_guide(id) VALUES (1)')
        db.execute('''CREATE TABLE IF NOT EXISTS ticketlink_guide_images (
            id TEXT PRIMARY KEY, data BLOB NOT NULL, published INTEGER NOT NULL DEFAULT 0)''')

    def authenticate(request):
        header = request.headers.get('authorization', '')
        if not admin_key or not secrets.compare_digest(header.encode(), ('Bearer ' + admin_key).encode()):
            raise ShopError('unauthorized', 401)

    def status(db):
        return dict(db.execute('''SELECT draft_html AS html, revision, published_revision, published_at
                                  FROM ticketlink_guide WHERE id=1''').fetchone())

    def save(payload):
        html = CLEANER.clean(payload.html)
        fragment = GuideFragment(html)
        if not fragment.has_content:
            raise ShopError('guide_empty_document', 422)
        with store.connection(write=True) as db:
            current = status(db)
            if current['revision'] != payload.revision:
                raise ShopError('guide_revision_conflict', 409)
            available = {row['id'] for row in db.execute('SELECT id FROM ticketlink_guide_images')}
            if not fragment.images <= available:
                raise ShopError('guide_missing_image', 422)
            if current['html'] != html:
                db.execute('UPDATE ticketlink_guide SET draft_html=?, revision=revision+1 WHERE id=1', (html,))
            return status(db)

    def publish(payload):
        with store.connection(write=True) as db:
            current = status(db)
            if payload.revision != current['revision']:
                raise ShopError('guide_revision_conflict', 409)
            if current['html'] is None:
                raise ShopError('guide_empty_document', 422)
            if current['published_revision'] != current['revision']:
                images = GuideFragment(current['html']).images
                db.execute('UPDATE ticketlink_guide_images SET published=0 WHERE published=1')
                db.executemany('UPDATE ticketlink_guide_images SET published=1 WHERE id=?',
                               ((image_id,) for image_id in images))
                db.execute('''UPDATE ticketlink_guide
                    SET published_html=draft_html, published_revision=revision, published_at=? WHERE id=1''',
                           (datetime.now(timezone.utc).isoformat(),))
            return status(db)

    def store_image(data):
        content = encode_image(data)
        image_id = sha256(content).hexdigest()
        with store.connection(write=True) as db:
            if db.execute('SELECT 1 FROM ticketlink_guide_images WHERE id=?', (image_id,)).fetchone():
                return {'id': image_id}
            used = db.execute('SELECT COALESCE(SUM(length(data)), 0) FROM ticketlink_guide_images').fetchone()[0]
            if used + len(content) > IMAGE_QUOTA:
                raise ShopError('guide_image_quota', 413)
            db.execute('INSERT INTO ticketlink_guide_images(id, data) VALUES (?, ?)', (image_id, content))
        return {'id': image_id}

    def image_response(image_id, private=False):
        if not IMAGE_ID.fullmatch(image_id):
            raise ShopError('guide_missing_image', 404)
        with store.connection() as db:
            row = db.execute('SELECT data FROM ticketlink_guide_images WHERE id=? AND (published=1 OR ?)',
                             (image_id, private)).fetchone()
        if row is None:
            raise ShopError('guide_missing_image', 404)
        return Response(row['data'], media_type='image/webp')

    @router.get(PUBLIC_PATH)
    def public_guide():
        with store.connection() as db:
            return dict(db.execute('SELECT published_html AS html FROM ticketlink_guide WHERE id=1').fetchone())

    @router.get(PUBLIC_PATH + '/images/{image_id}')
    def public_image(image_id: str):
        return image_response(image_id)

    @router.get(ADMIN_PATH)
    def admin_guide(request: Request):
        authenticate(request)
        with store.connection() as db:
            return status(db)

    @router.get(ADMIN_PATH + '/images/{image_id}')
    def admin_image(image_id: str, request: Request):
        authenticate(request)
        return image_response(image_id, private=True)

    @router.post(ADMIN_PATH + '/draft')
    async def save_draft(request: Request):
        authenticate(request)
        payload = await read_document(request, Draft, DRAFT_LIMIT)
        return await run_in_threadpool(save, payload)

    @router.post(ADMIN_PATH + '/publish')
    async def publish_guide(request: Request):
        authenticate(request)
        payload = await read_document(request, Revision, 1024)
        return await run_in_threadpool(publish, payload)

    @router.post(ADMIN_PATH + '/images')
    async def upload_image(request: Request):
        authenticate(request)
        data = await read_limited(request, IMAGE_LIMIT)
        return await run_in_threadpool(store_image, data)

    return router
