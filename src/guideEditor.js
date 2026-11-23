import guideNames from './data/tutorials/guide-index.json';

export const guides = Object.entries(guideNames).map(([slug, name]) => ({ slug, name }));
export const guideName = (slug) => Object.hasOwn(guideNames, slug) ? guideNames[slug] : '';
const seedImports = import.meta.glob('./data/tutorials/*.html', { query: '?raw', import: 'default' });
export const readGuideSeed = (slug) => seedImports[`./data/tutorials/${slug}.html`]?.();

const base = `${(import.meta.env.VITE_COMMERCE_API || '').replace(/\/$/, '')}/commerce/api`;
const guidePath = (slug) => `/admin/guides/${encodeURIComponent(slug)}`;
export const publicImageUrl = (slug, id) => `${base}/help/${encodeURIComponent(slug)}/images/${encodeURIComponent(id)}`;
const imageSelector = 'img[data-guide-image]';

const errors = {
  unauthorized: '教程后台密码错误，请重试。',
  guide_login_limited: '尝试次数过多，请 10 分钟后重试。',
  guide_too_large: '内容超过大小限制。单张图片最多 5 MB。',
  request_too_large: '内容超过大小限制。单张图片最多 5 MB。',
  guide_invalid_image: '请选择静态 PNG、JPG 或 WebP 图片。',
  guide_revision_conflict: '另一处已保存新草稿。请先复制你的修改，再刷新页面获取最新草稿。',
  guide_missing_image: '无法读取图片，请重新插入。',
  guide_empty_document: '请填写教程正文后再保存。',
  guide_image_quota: '教程图片空间已满。',
};

async function request(path, { key, body, signal, image = false } = {}) {
  const upload = body instanceof Blob;
  const headers = key ? { Authorization: `Bearer ${key}` } : {};
  if (body) headers['Content-Type'] = upload ? 'application/octet-stream' : 'application/json';
  const timeout = AbortSignal.timeout(upload ? 45000 : 15000);
  const response = await fetch(base + path, {
    method: body ? 'POST' : 'GET',
    headers,
    body: upload || !body ? body : JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    cache: 'no-store',
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = new Error(errors[payload?.detail] || (response.status === 413 ? errors.request_too_large : '操作未完成，请稍后重试。'));
    error.status = response.status;
    throw error;
  }
  return image ? response.blob() : response.json();
}

export const readPublishedGuide = (slug, signal) => request(`/help/${encodeURIComponent(slug)}`, { signal });
export const readGuideIndex = (key) => request('/admin/guides', { key });
export const readGuideDraft = (slug, key) => request(guidePath(slug), { key });
export const saveGuideDraft = (slug, key, revision, html) => request(guidePath(slug) + '/draft', { key, body: { revision, html } });
export const publishGuide = (slug, key, revision) => request(guidePath(slug) + '/publish', { key, body: { revision } });
export const uploadGuideImage = (slug, key, file) => request(guidePath(slug) + '/images', { key, body: file });
export const readDraftImage = (slug, key, id, signal) =>
  request(`${guidePath(slug)}/images/${encodeURIComponent(id)}`, { key, signal, image: true });

function fragment(html) {
  const template = document.createElement('template');
  template.innerHTML = html;
  return template;
}

function getSections(template) {
  const ids = new Set();
  return [...template.content.querySelectorAll('h2,h3,h4,h5')].flatMap((heading, index) => {
    const title = heading.textContent.trim();
    if (!title) return [];
    const proposedId = heading.id || `guide-section-${index + 1}`;
    let id = proposedId;
    let suffix = 1;
    while (ids.has(id)) id = `${proposedId}-${suffix++}`;
    ids.add(id);
    heading.id = id;
    return [[id, title, Number(heading.tagName[1]) - 2]];
  });
}

export function renderGuide(html, imageUrl) {
  const template = fragment(html);
  const sections = getSections(template);
  for (const image of template.content.querySelectorAll(imageSelector)) {
    const src = imageUrl(image.dataset.guideImage);
    if (src) image.src = src;
    else image.removeAttribute('src');
  }
  return { html: template.innerHTML, sections };
}

export function draftImageIds(html) {
  return new Set([...fragment(html).content.querySelectorAll(imageSelector)].map(image => image.dataset.guideImage));
}

export function serializeDraft(html) {
  const template = fragment(html);
  getSections(template);
  for (const image of template.content.querySelectorAll(imageSelector)) image.removeAttribute('src');
  return template.innerHTML;
}
