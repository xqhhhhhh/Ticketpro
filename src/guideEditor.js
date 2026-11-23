import defaultGuide from './data/tutorials/ticketlink.html?raw';

export { defaultGuide };

const base = `${(import.meta.env.VITE_COMMERCE_API || '').replace(/\/$/, '')}/commerce/api`;
const adminPath = '/admin/ticketlink';
export const publicImageUrl = (id) => `${base}/help/ticketlink/images/${encodeURIComponent(id)}`;
const imageSelector = 'img[data-guide-image]';

const errors = {
  unauthorized: '管理员密钥无效，请重新登录。',
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

export const readPublishedGuide = (signal) => request('/help/ticketlink', { signal });
export const readGuideDraft = (key) => request(adminPath, { key });
export const saveGuideDraft = (key, revision, html) => request(adminPath + '/draft', { key, body: { revision, html } });
export const publishGuide = (key, revision) => request(adminPath + '/publish', { key, body: { revision } });
export const uploadGuideImage = (key, file) => request(adminPath + '/images', { key, body: file });
export const readDraftImage = (key, id, signal) =>
  request(`${adminPath}/images/${encodeURIComponent(id)}`, { key, signal, image: true });

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
    const proposedId = heading.id || `ticketlink-section-${index + 1}`;
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
