import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, test } from 'node:test';

// Only replace Vite's build-time environment; all checkout code runs unchanged.
const sourcePath = process.env.TICKETPRO_COMMERCE_TEST_SOURCE || new URL('../src/commerce.js', import.meta.url);
const source = (await readFile(sourcePath, 'utf8')).replaceAll('import.meta.env', '({ VITE_COMMERCE_API: "" })');
const { placeOrder, savedOrders, shopRequest } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const originalGlobals = new Map(['localStorage', 'fetch', 'crypto'].map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
let storage;
let requests;

beforeEach(() => {
  storage = new Map();
  requests = [];
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: key => storage.delete(key),
  } });
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: webcrypto });
  Object.defineProperty(globalThis, 'fetch', { configurable: true, value: (url, options) => new Promise((resolve, reject) => {
    requests.push({ url, payload: JSON.parse(options.body), resolve, reject });
  }) });
});

afterEach(() => {
  for (const [name, descriptor] of originalGlobals) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    else delete globalThis[name];
  }
});

function pendingEntry(productId, days) {
  return [...storage.entries()].find(([, value]) => {
    const record = JSON.parse(value);
    return record?.product_id === productId && record?.days === days && record?.request_id;
  });
}

function succeed(index) {
  const { product_id, days } = requests[index].payload;
  const order = { id: String(index + 1).padStart(28, '0'), product_id, days, status: 'pending' };
  requests[index].resolve({ ok: true, json: async () => order });
  return order;
}

test('a lost response retries the same request and receipt key, then clears that recovery', async () => {
  const first = placeOrder('interpark', 30);
  const original = requests[0].payload;
  requests[0].reject(new Error('response lost'));
  await assert.rejects(first, /暂时无法连接/);
  const retry = placeOrder('interpark', 30);
  assert.deepEqual(requests[1].payload, original);
  const order = succeed(1);
  assert.deepEqual(await retry, order);
  assert.equal(pendingEntry('interpark', 30), undefined);
  assert.equal(savedOrders()[0].key, original.access_key);
});

for (const skus of [[['interpark', 30], ['melon', 30]], [['interpark', 15], ['interpark', 30]]]) {
  for (const firstSuccess of [0, 1]) {
    test(`parallel ${JSON.stringify(skus)} preserves the lost response when request ${firstSuccess} succeeds first`, async () => {
      const attempts = skus.map(([product, days]) => placeOrder(product, days));
      const failed = 1 - firstSuccess;
      const original = { ...requests[failed].payload };
      succeed(firstSuccess);
      await attempts[firstSuccess];
      const entry = pendingEntry(...skus[failed]);
      assert.ok(entry, 'the other SKU must retain its own recovery record');
      assert.equal(JSON.parse(entry[1]).request_id, original.request_id);
      requests[failed].reject(new Error('response lost after server committed'));
      await assert.rejects(attempts[failed], /暂时无法连接/);
      const retry = placeOrder(...skus[failed]);
      assert.deepEqual(requests[2].payload, original);
      succeed(2);
      await retry;
    });
  }
}

test('a late success cannot clear a newer request for the same SKU', async () => {
  const oldAttempt = placeOrder('interpark', 30);
  const [storageKey] = pendingEntry('interpark', 30);
  const newer = { ...requests[0].payload, request_id: webcrypto.randomUUID(), access_key: 'b'.repeat(64) };
  storage.set(storageKey, JSON.stringify(newer));
  const newAttempt = placeOrder('interpark', 30);
  assert.deepEqual(requests[1].payload, newer);
  succeed(0);
  await oldAttempt;
  assert.deepEqual(JSON.parse(storage.get(storageKey)), newer);
  requests[1].reject(new Error('new response lost'));
  await assert.rejects(newAttempt, /暂时无法连接/);
  const retry = placeOrder('interpark', 30);
  assert.deepEqual(requests[2].payload, newer);
  succeed(2);
  await retry;
});

test('a matching legacy v1 recovery migrates before sending and survives a failed response', async () => {
  const legacy = { product_id: 'interpark', days: 30, request_id: webcrypto.randomUUID(), access_key: 'c'.repeat(64) };
  storage.set('ticketpro.checkout.v1', JSON.stringify(legacy));
  const first = placeOrder('interpark', 30);
  assert.deepEqual(requests[0].payload, legacy);
  assert.equal(storage.has('ticketpro.checkout.v1'), false);
  assert.deepEqual(JSON.parse(pendingEntry('interpark', 30)[1]), legacy);
  requests[0].reject(new Error('response lost'));
  await assert.rejects(first, /暂时无法连接/);
  const retry = placeOrder('interpark', 30);
  assert.deepEqual(requests[1].payload, legacy);
  succeed(1);
  await retry;
});

test('buying another SKU preserves the unmatched legacy recovery for later retry', async () => {
  const legacy = { product_id: 'interpark', days: 30, request_id: webcrypto.randomUUID(), access_key: 'd'.repeat(64) };
  storage.set('ticketpro.checkout.v1', JSON.stringify(legacy));
  const other = placeOrder('melon', 30);
  succeed(0);
  await other;
  assert.deepEqual(JSON.parse(storage.get('ticketpro.checkout.v1')), legacy);
  const recovered = placeOrder('interpark', 30);
  assert.deepEqual(requests[1].payload, legacy);
  succeed(1);
  await recovered;
});

for (const [name, response] of [
  ['blank gateway page', () => new Response('')],
  ['gateway HTML error page', () => new Response('<html>unavailable</html>', { status: 502 })],
  ['missing order data', () => new Response('{}')],
  ['incomplete delivery', () => new Response(JSON.stringify({ id: '1'.repeat(28), status: 'delivered' }))],
]) {
  test(`${name} shows a customer-facing error instead of accepting an unusable order`, async () => {
    Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async () => response() });
    await assert.rejects(shopRequest('/api/orders/' + '1'.repeat(28)), /付款问题/);
  });
}

test('payment service rejection preserves order recovery for a later retry', async () => {
  const attempt = placeOrder('interpark', 15);
  const pending = { ...requests[0].payload };
  requests[0].resolve({ ok: false, status: 503, json: async () => ({ detail: 'payment_creation_rejected' }) });
  await assert.rejects(attempt);
  assert.deepEqual(JSON.parse(pendingEntry('interpark', 15)[1]), pending);
  const retry = placeOrder('interpark', 15);
  assert.deepEqual(requests[1].payload, pending);
  succeed(1);
  await retry;
});

test('timeout becomes a customer-facing error and caller cancellation remains AbortError', async () => {
  Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async () => {
    throw new DOMException('timed out', 'TimeoutError');
  } });
  await assert.rejects(shopRequest('/api/catalog'), /付款问题/);
  const controller = new AbortController();
  controller.abort();
  Object.defineProperty(globalThis, 'fetch', { configurable: true, value: async () => { throw controller.signal.reason; } });
  await assert.rejects(shopRequest('/api/catalog', { signal: controller.signal }), { name: 'AbortError' });
});
