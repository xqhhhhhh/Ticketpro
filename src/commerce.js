const apiBase = (import.meta.env.VITE_COMMERCE_API || '').replace(/\/$/, '');
const historyKey = 'ticketpro.orders.v1';
const pendingKey = 'ticketpro.checkout.v1';
const pendingPrefix = 'ticketpro.checkout.v2:';
const messages = {
  out_of_stock: '这个档位暂时售罄，请选择其他期限或联系微信客服。',
  too_many_orders: '待处理订单较多，请先查看已有订单，或稍后再试。',
  order_not_found: '无法读取订单，请使用付款时的浏览器或完整的私密领取链接。',
  request_conflict: '下单记录发生冲突，请从订单查询中打开已有订单。',
};

export async function shopRequest(path, { key, ...options } = {}) {
  const response = await fetch(`${apiBase}/commerce${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(key ? { Authorization: `Bearer ${key}` } : {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : '';
    const error = new Error(messages[detail] || detail || '暂时无法连接订单服务，请稍后重试或联系微信客服。');
    error.status = response.status;
    throw error;
  }
  return data;
}

export function savedOrders() {
  try {
    return JSON.parse(localStorage.getItem(historyKey) || '[]').filter(o => /^\d{28}$/.test(o.id) && /^[a-f0-9]{64}$/.test(o.key));
  } catch { return []; }
}

export function rememberOrder(order, key) {
  const previous = savedOrders().filter(o => o.id !== order.id);
  localStorage.setItem(historyKey, JSON.stringify([{ ...order, key, payment: undefined, delivery: undefined }, ...previous].slice(0, 100)));
}

export function orderKey(id) {
  const fragmentKey = new URLSearchParams(window.location.hash.slice(1)).get('key');
  if (/^[a-f0-9]{64}$/.test(fragmentKey || '')) return fragmentKey;
  return savedOrders().find(o => o.id === id)?.key || '';
}

export function receiptLink(id, key) {
  return `${window.location.origin}/order/${id}#key=${key}`;
}

function readPending(storageKey) {
  try { return JSON.parse(localStorage.getItem(storageKey) || 'null'); }
  catch { return null; }
}

function pendingFor(pending, productId, days) {
  return pending?.product_id === productId && pending?.days === days
    && /^[a-zA-Z0-9-]{20,80}$/.test(pending.request_id || '')
    && /^[a-f0-9]{64}$/.test(pending.access_key || '');
}

function clearPending(storageKey, pending) {
  const current = readPending(storageKey);
  if (current?.request_id === pending.request_id && current?.access_key === pending.access_key) {
    localStorage.removeItem(storageKey);
  }
}

export async function placeOrder(productId, days) {
  const storageKey = `${pendingPrefix}${encodeURIComponent(productId)}:${days}`;
  let pending = readPending(storageKey);
  if (!pendingFor(pending, productId, days)) {
    const legacy = readPending(pendingKey);
    if (pendingFor(legacy, productId, days)) {
      pending = legacy;
      localStorage.setItem(storageKey, JSON.stringify(pending));
      clearPending(pendingKey, legacy);
    } else {
      pending = {
        product_id: productId, days, request_id: crypto.randomUUID(),
        access_key: Array.from(crypto.getRandomValues(new Uint8Array(32)), b => b.toString(16).padStart(2, '0')).join(''),
      };
      // Save BEFORE sending. Each SKU keeps its own recovery credentials.
      localStorage.setItem(storageKey, JSON.stringify(pending));
    }
  }
  const order = await shopRequest('/api/orders', { method: 'POST', body: JSON.stringify(pending) });
  rememberOrder(order, pending.access_key);
  clearPending(storageKey, pending);
  return order;
}
