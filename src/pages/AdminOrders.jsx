import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, Check, ChevronLeft, ChevronRight, Copy, Eye, LayoutDashboard, LoaderCircle, LockKeyhole, LogOut, RefreshCw, Search, ShoppingBag, X } from 'lucide-react';
import { shopRequest } from '../commerce';
import './admin-orders.css';

const sessionKey = 'ticketpro.dashboard.session.v1';
const money = value => new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format((value || 0) / 100);
function initialKey() {
  const supplied = new URLSearchParams(window.location.hash.slice(1)).get('key');
  try { return supplied || sessionStorage.getItem(sessionKey) || ''; } catch { return supplied || ''; }
}
function dateTime(value, zone = 'Europe/Berlin') {
  return value ? new Intl.DateTimeFormat('zh-CN', { timeZone: zone, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(value * 1000) : '—';
}
function NotificationStatus({ order }) {
  if (order.status === 'pending') return <span className="ad-muted">付款后通知</span>;
  const states = { sent: ['已通知', 'sent'], pending: ['待发送', 'waiting'], sending: ['发送中', 'waiting'] };
  const [label, kind] = states[order.notification_status] || ['接入前订单', 'historical'];
  return <span className={`ad-notification ${kind}`}><i />{label}</span>;
}
function CopyButton({ value, label = '复制' }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(value); setCopied(true); setFailed(false); }
    catch { setFailed(true); }
  }
  return <span className="ad-copy-wrap"><button className="ad-icon-button" onClick={copy} title={label} aria-label={label}>{copied ? <Check size={15} /> : <Copy size={15} />}</button>{failed && <small role="alert">请手动复制</small>}</span>;
}

function Detail({ id, accessKey, zone, onClose, onUnauthorized }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  const [revealing, setRevealing] = useState(false);
  const closeRef = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    const previous = document.activeElement;
    closeRef.current?.focus();
    shopRequest(`/api/admin/orders/${encodeURIComponent(id)}`, { key: accessKey, signal: controller.signal })
      .then(setDetail).catch(e => { if (e.name !== 'AbortError') { setError('订单详情读取失败，请稍后重试。'); if (e.status === 401) onUnauthorized(); } });
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { controller.abort(); document.body.style.overflow = original; previous?.focus(); };
  }, [id, accessKey, onUnauthorized]);
  async function reveal() {
    setRevealing(true); setError('');
    try { setDetail(await shopRequest(`/api/admin/orders/${encodeURIComponent(id)}?reveal=true`, { key: accessKey })); }
    catch (e) { setError('激活码读取失败，请稍后重试。'); if (e.status === 401) onUnauthorized(); }
    finally { setRevealing(false); }
  }
  function keys(event) {
    if (event.key === 'Escape') onClose();
    if (event.key === 'Tab') {
      const controls = [...event.currentTarget.querySelectorAll('button:not(:disabled),a[href]')];
      if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1)?.focus(); }
      if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0]?.focus(); }
    }
  }
  return <div className="ad-overlay" onClick={onClose}><section className="ad-detail" role="dialog" aria-modal="true" aria-labelledby="ad-detail-title" onClick={e => e.stopPropagation()} onKeyDown={keys}>
    <div className="ad-detail-head"><span className="ad-eyebrow">ORDER DETAILS</span><button ref={closeRef} className="ad-icon-button" onClick={onClose} aria-label="关闭订单详情"><X size={21} /></button></div>
    <h2 id="ad-detail-title">订单详情</h2>
    {error && <p className="ad-error" role="alert">{error}</p>}
    {!detail ? <p className="ad-loading"><LoaderCircle className="ad-spin" size={18} />正在读取订单…</p> : <>
      <div className={`ad-status ${detail.status}`}><i />{detail.status === 'delivered' ? '已付款 · 已自动发货' : '等待付款'}</div>
      <h3>{detail.name}</h3>
      <div className="ad-detail-price">{money(detail.cents)}<span>{detail.duration}{detail.is_test ? ' · 测试订单' : ''}</span></div>
      <dl className="ad-detail-info">
        <div><dt>订单编号</dt><dd><code>{detail.id}</code><CopyButton value={detail.id} label="复制订单号" /></dd></div>
        <div><dt>创建时间</dt><dd>{dateTime(detail.created_at, zone)}</dd></div>
        <div><dt>付款确认</dt><dd>{dateTime(detail.paid_at, zone)}</dd></div>
        <div><dt>支付方式</dt><dd>支付宝</dd></div>
        <div><dt>支付交易号</dt><dd><code>{detail.trade_no || '—'}</code></dd></div>
        <div><dt>飞书提醒</dt><dd><NotificationStatus order={detail} /></dd></div>
        {detail.notification_status && detail.notification_status !== 'sent' && <div><dt>通知处理</dt><dd>{detail.notification_attempts || 0} 次尝试{detail.notification_error ? ' · 将自动重试' : ''}</dd></div>}
      </dl>
      {detail.status === 'delivered' && <div className="ad-fulfillment"><span className="ad-eyebrow">已交付内容</span><div className="ad-code"><code>{detail.code || `•••• •••• •••• ${detail.code_suffix}`}</code>{detail.code ? <CopyButton value={detail.code} label="复制激活码" /> : <button className="ad-icon-button" disabled={revealing} onClick={reveal} aria-label="显示已发出的激活码">{revealing ? <LoaderCircle className="ad-spin" size={17} /> : <Eye size={17} />}</button>}</div><p>{detail.binding_mode === 'machine' ? '单设备绑定' : '按商品授权规则激活'} · {detail.duration}</p>{detail.tutorial_url && <a href={detail.tutorial_url} target="_blank" rel="noopener noreferrer">查看对应安装与使用教程<ArrowUpRight size={16} /></a>}</div>}
    </>}
    <div className="ad-detail-foot">时间显示：{zone} · 本页面仅用于查看订单</div>
  </section></div>;
}

export default function AdminOrders() {
  const [accessKey, setAccessKey] = useState(initialKey);
  const [draftKey, setDraftKey] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ q: '', status: '', product: '', start: '', end: '', include_tests: false });
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState(null);
  const [unauthorized] = useState(() => () => {
    try { sessionStorage.removeItem(sessionKey); } catch { /* Session storage may be unavailable. */ }
    setAccessKey(''); setData(null); setSelected(null); setError('访问凭据无效，请重新解锁。');
  });
  useEffect(() => {
    const previousTitle = document.title;
    document.title = '订单看板 · TicketPro';
    if (window.location.hash) window.history.replaceState(null, '', window.location.pathname);
    return () => { document.title = previousTitle; };
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => { setFilters(previous => previous.q === search.trim() ? previous : ({ ...previous, q: search.trim() })); setPage(1); }, 350);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (!accessKey) return;
    const controller = new AbortController();
    let active = true;
    const load = async () => {
      setBusy(true);
      try {
        const params = new URLSearchParams({ ...filters, page, size: 20 });
        const result = await shopRequest(`/api/admin/dashboard?${params}`, { key: accessKey, signal: controller.signal });
        if (!active) return;
        setData(result); setError('');
        try { sessionStorage.setItem(sessionKey, accessKey); } catch { /* Keep credentials in memory only. */ }
      } catch (e) {
        if (active && e.name !== 'AbortError') {
          if (e.status === 401) unauthorized();
          else setError(e.message === 'invalid_date_range' ? '请选择有效日期，开始日期不能晚于结束日期。' : '暂时无法读取订单，请稍后刷新。');
        }
      } finally { if (active) setBusy(false); }
    };
    load();
    const timer = setInterval(load, 30000);
    return () => { active = false; controller.abort(); clearInterval(timer); };
  }, [accessKey, filters, page, refresh, unauthorized]);
  function change(name, value) { setFilters(previous => ({ ...previous, [name]: value })); setPage(1); }
  function logout() { unauthorized(); setError(''); setDraftKey(''); }
  const stats = data?.stats;
  const max = Math.max(...(data?.trend || []).map(p => p.revenue), 1);

  return <main className="ad-shell">
    <aside className="ad-sidebar"><Link to="/" className="ad-brand">TicketPro<span>MERCHANT CONSOLE</span></Link><div className="ad-workspace"><ShoppingBag size={17} /><div>网站商店<span>ticket-pro-website.vercel.app</span></div></div><div className="ad-sidebar-label">经营管理</div><div className="ad-nav-current"><LayoutDashboard size={18} />订单看板<span>01</span></div><div className="ad-sidebar-bottom"><span className="ad-private-dot" />私密管理空间<Link to="/">访问商品网站<ArrowUpRight size={14} /></Link></div></aside>
    <div className="ad-main"><header className="ad-topbar"><span>商家工作台 <span>/</span> 订单管理</span><div><LockKeyhole size={13} />仅授权访问{data && <button onClick={logout}><LogOut size={14} />退出</button>}</div></header>
      {!data ? <section className="ad-login"><div className="ad-lock"><LockKeyhole size={27} /></div><span className="ad-eyebrow">YOUR BUSINESS, AT A GLANCE</span><h1>欢迎回到你的商店。</h1><p>在一个地方，查看每一笔订单的付款与交付。</p>{accessKey && busy ? <p className="ad-loading"><LoaderCircle className="ad-spin" size={18} />正在验证访问凭据…</p> : <form onSubmit={e => { e.preventDefault(); setError(''); setAccessKey(draftKey.trim()); setRefresh(value => value+1); }}><label htmlFor="dashboard-key">管理访问密钥</label><input id="dashboard-key" type="password" autoComplete="off" value={draftKey} onChange={e => setDraftKey(e.target.value)} required placeholder="输入你的专用访问密钥" /><button className="ad-button primary" type="submit">解锁订单看板<ArrowUpRight size={16} /></button></form>}{error && <p className="ad-error" role="alert">{error}</p>}<small>也可以使用已保存的完整私密入口打开。</small></section> : <>
        <section className="ad-heading"><div><span className="ad-eyebrow">ORDER OVERVIEW</span><h1>每一笔成交，清晰在目<span>。</span></h1><p>付款、交付与消息提醒，都在这里。</p></div><button className="ad-button" onClick={() => setRefresh(value => value+1)} disabled={busy}><RefreshCw size={15} className={busy ? 'ad-spin' : ''} />刷新数据</button></section>
        <div className="ad-update"><span><i />{busy ? '正在同步…' : `更新于 ${dateTime(data.updated_at, data.timezone)}`}<b>每 30 秒自动同步</b></span><small>{filters.include_tests ? '包含测试订单' : '正式订单 · 已排除测试单'}</small></div>
        {error && <p className="ad-error" role="alert">{error}</p>}
        <section className="ad-metrics" aria-label="订单统计">
          <div className="ad-metric revenue"><div>累计实收<span>CNY</span></div><strong>{money(stats.revenue)}</strong><small><ArrowDownLeft size={14} />所选订单中已付款的金额</small></div>
          <div className="ad-metric"><div>已付款订单<Check size={15} /></div><strong>{stats.paid}<em>笔</em></strong><small>均已完成自动发货</small></div>
          <div className="ad-metric"><div>待付款订单<ShoppingBag size={15} /></div><strong>{stats.pending}<em>笔</em></strong><small>尚未计入实收金额</small></div>
          <div className="ad-metric"><div>今日实收<ArrowUpRight size={15} /></div><strong>{money(stats.today_revenue)}</strong><small>按 {data.timezone} 统计</small></div>
        </section>
        <section className="ad-insights"><div className="ad-panel ad-trend"><div className="ad-panel-heading"><div><span className="ad-eyebrow">SALES ACTIVITY</span><h2>收款趋势</h2></div><span>14 天 · 实收金额</span></div><div className="ad-chart" role="img" aria-label={`14天收款趋势，已付款${stats.paid}笔`}>
          {data.trend.map(point => <div className="ad-chart-column" key={point.date}><div className="ad-chart-track"><div className={point.revenue ? 'ad-chart-bar active' : 'ad-chart-bar'} style={{ height: point.revenue ? `${Math.max(5, point.revenue/max*100)}%` : '2px' }} title={`${point.date}：${money(point.revenue)}，${point.orders} 笔订单`}><span>{point.revenue ? money(point.revenue) : ''}</span></div></div><small>{point.date.slice(5).replace('-', '/')}</small></div>)}
        </div></div><div className="ad-panel ad-ranking"><div className="ad-panel-heading"><div><span className="ad-eyebrow">BEST SELLERS</span><h2>商品销售</h2></div><span>按实收排序</span></div>{data.ranking.length ? data.ranking.map((product, index) => <div className="ad-ranking-row" key={product.product_id+product.name}><span className="ad-rank">{String(index+1).padStart(2, '0')}</span><div><strong>{product.name}</strong><small>{product.orders} 笔已付款</small></div><b>{money(product.revenue)}</b></div>) : <p className="ad-empty-small">当前筛选下暂无成交</p>}</div></section>
        <section className="ad-panel ad-orders"><div className="ad-panel-heading"><div><span className="ad-eyebrow">TRANSACTIONS</span><h2>订单明细<span>{data.total}</span></h2></div><label className="ad-test-toggle"><input type="checkbox" checked={filters.include_tests} onChange={e => change('include_tests', e.target.checked)} />显示测试订单</label></div>
          <div className="ad-filters"><label className="ad-search"><Search size={16} /><input aria-label="搜索订单号或商品" placeholder="搜索订单号或商品名称" value={search} onChange={e => setSearch(e.target.value)} /></label><select aria-label="商品筛选" value={filters.product} onChange={e => change('product', e.target.value)}><option value="">全部商品</option>{data.products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><select aria-label="订单状态筛选" value={filters.status} onChange={e => change('status', e.target.value)}><option value="">全部状态</option><option value="delivered">已付款 · 已发货</option><option value="pending">等待付款</option></select><div className="ad-date-range"><input type="date" aria-label="创建开始日期" value={filters.start} onChange={e => change('start', e.target.value)} /><span>至</span><input type="date" aria-label="创建结束日期" value={filters.end} onChange={e => change('end', e.target.value)} /></div></div>
          <div className="ad-table-wrap"><table><thead><tr><th>商品 / 订单编号</th><th>购买期限</th><th>实付金额</th><th>订单状态</th><th>飞书通知</th><th>创建时间</th><th><span className="ad-sr-only">查看详情</span></th></tr></thead><tbody>{data.orders.map(order => <tr key={order.id}><td><button className="ad-order-title" onClick={() => setSelected(order.id)}>{order.name}{order.is_test ? <span>测试</span> : null}</button><code>{order.id}</code></td><td>{order.duration}</td><td className="ad-amount">{money(order.cents)}</td><td><span className={`ad-status ${order.status}`}><i />{order.status === 'delivered' ? '已付款 · 已发货' : '等待付款'}</span></td><td><NotificationStatus order={order} /></td><td className="ad-date">{dateTime(order.created_at, data.timezone)}</td><td><button className="ad-icon-button" aria-label={`查看订单 ${order.id}`} onClick={() => setSelected(order.id)}><ArrowUpRight size={17} /></button></td></tr>)}</tbody></table>{!data.orders.length && <div className="ad-empty"><Search size={24} /><h3>没有找到符合条件的订单</h3><p>试试其他商品、状态或日期范围。</p><button className="ad-button" onClick={() => { setSearch(''); setFilters({ q: '', product: '', status: '', start: '', end: '', include_tests: false }); setPage(1); }}>清除筛选</button></div>}</div>
          <div className="ad-pagination"><span>共 {data.total} 笔 · 每页 {data.size} 笔</span><div><button className="ad-icon-button" disabled={page <= 1 || busy} onClick={() => setPage(value => value-1)} aria-label="上一页"><ChevronLeft size={17} /></button><span>{page} / {Math.max(1, Math.ceil(data.total/data.size))}</span><button className="ad-icon-button" disabled={page*data.size >= data.total || busy} onClick={() => setPage(value => value+1)} aria-label="下一页"><ChevronRight size={17} /></button></div></div>
        </section><footer className="ad-footer"><span>TicketPro · 商店订单管理</span><span>只读看板，不会修改付款或发货记录</span></footer>
      </>}
    </div>{selected && <Detail key={selected} id={selected} accessKey={accessKey} zone={data?.timezone} onClose={() => setSelected(null)} onUnauthorized={unauthorized} />}
  </main>;
}
