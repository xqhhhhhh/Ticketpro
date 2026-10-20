import { writeFileSync } from 'node:fs';
import { products } from '../src/data/products.js';

const days = { '15天': 15, '1个月': 30, '1年': 365, '永久': 0 };
const catalog = products.filter(p => p.pricing.length).map(p => ({
  id: p.id, name: p.name,
  plans: p.pricing.filter(t => Number.isFinite(t.price)).map(t => {
    if (!(t.duration in days)) throw new Error(`未知期限：${p.id} ${t.duration}`);
    return { days: days[t.duration], label: t.label, duration: t.duration, cents: Math.round(t.price * 100) };
  }),
}));
writeFileSync(new URL('../server/catalog.json', import.meta.url), `${JSON.stringify(catalog, null, 2)}\n`);
