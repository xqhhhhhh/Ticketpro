import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, Check, CheckCircle2, Copy, LoaderCircle, RefreshCw, ScanFace, BookOpen } from 'lucide-react';
import QRCode from 'qrcode';
import { orderKey, receiptLink, rememberOrder, savedOrders, shopRequest } from '../commerce';
import '../commerce.css';

function CopyButton({ value, children }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(value); setCopied(true); setFailed(false); }
    catch { setFailed(true); }
  }
  return <><button className="commerce-text-button" onClick={copy}>{copied ? <Check size={16} /> : <Copy size={16} />}{copied ? '已复制' : children}</button>
    {failed && <span className="commerce-error">复制失败，请手动选择并复制。</span>}</>;
}

function PaymentCode({ payment }) {
  const [qr, setQr] = useState(null);
  const source = payment?.qrcode || payment?.payurl;
  useEffect(() => {
    if (!source || payment?.demo || payment?.img) return;
    let active = true;
    QRCode.toDataURL(source, { width: 280, margin: 2 }).then(src => { if (active) setQr({ source, src }); }).catch(() => {});
    return () => { active = false; };
  }, [source, payment]);
  const image = payment?.img || (qr?.source === source ? qr.src : null);
  if (payment?.demo) return <div className="order-demo"><ScanFace size={40} /><strong>本地模拟付款</strong><p>此订单不会扣款，发出的 DEMO 码仅用于验证流程。</p></div>;
  return image ? <img className="order-qr" src={image} alt="该订单的支付宝付款二维码" /> : <div className="order-demo"><ScanFace size={40} /><p>请通过下方按钮打开付款页面。</p></div>;
}

export default function OrderPage() {
  const { id } = useParams();
  const key = useMemo(() => orderKey(id), [id]);
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(false);
  const current = order?.id === id ? order : null;
  useEffect(() => {
    if (!key) return;
    if (!savedOrders().some(o => o.id === id)) rememberOrder({ id, name: '待查询订单', duration: '待查询' }, key);
    let active = true;
    const load = async () => {
      try {
        const data = await shopRequest(`/api/orders/${id}`, { key });
        if (active) { setOrder(data); setError(''); rememberOrder(data, key); }
      } catch (e) { if (active) setError(e.message); }
    };
    load();
    const timer = setInterval(load, 5000);
    if (window.location.hash) window.history.replaceState(null, '', window.location.pathname);
    return () => { active = false; clearInterval(timer); };
  }, [id, key]);

  async function checkPayment() {
    if (checking) return;
    setChecking(true); setError('');
    try {
      const data = await shopRequest(`/api/orders/${id}/refresh`, { key, method: 'POST' });
      setOrder(data); rememberOrder(data, key);
    } catch (e) { setError(e.message); }
    finally { setChecking(false); }
  }

  const delivered = current?.status === 'delivered';
  const payment = current?.payment;
  return <main className="order-page container">
    <Link to="/orders" className="order-back"><ArrowLeft size={16} /> 我的订单</Link>
    <div className="commerce-eyebrow"><span>{delivered ? '03' : '02'}</span> {delivered ? '领取你的商品' : '完成订单付款'}</div>
    <h1>{delivered ? '已付款，可以开始使用了。' : '距离开始使用，只差一步。'}</h1>
    <p className="commerce-muted">{delivered ? '你的激活码已分配到本订单，保存领取链接，随时回来查看。' : '付款成功后，本页会自动显示激活码和安装与使用教程。'}</p>
    {!key ? <div className="order-card"><h2>需要私密领取链接</h2><p className="commerce-muted">请使用付款时的浏览器打开订单，或打开你保存的完整领取链接。</p><Link to="/orders">查看本机已有订单</Link></div>
      : !current && !error ? <p role="status" className="order-loading"><LoaderCircle className="commerce-spin" /> 正在读取订单…</p>
      : current && <div className="order-layout">
        <section className="order-card order-summary">
          <span className={`order-status ${delivered ? 'complete' : ''}`}>{delivered ? <CheckCircle2 size={16} /> : <span className="order-status-dot" />}{delivered ? '已付款 · 已发货' : '等待付款'}</span>
          <h2>{current.name}</h2>
          <dl><div><dt>使用期限</dt><dd>{current.duration}</dd></div><div><dt>支付方式</dt><dd>支付宝</dd></div><div><dt>订单编号</dt><dd className="order-number">{current.id}</dd></div></dl>
          <div className="checkout-total"><span>订单金额</span><strong>¥{(current.cents / 100).toFixed(2)}</strong></div>
          <div className="order-save"><strong>保存你的领取链接</strong><p>链接可查看本订单的激活码，请妥善保管。</p><CopyButton value={receiptLink(id, key)}>复制私密领取链接</CopyButton></div>
          <p className="commerce-muted order-help">需要帮助？微信客服：xxxxqqqhh<br />联系客服时提供订单编号即可。</p>
        </section>
        <section className="order-card order-fulfillment" aria-live="polite">
          {delivered ? <>
            {current.delivery.code.startsWith('DEMO-') && <div className="commerce-notice">演示激活码，不可用于真实插件</div>}
            <div className="commerce-eyebrow"><CheckCircle2 size={20} /> 商品已准备好</div>
            <h2>你的专属激活码</h2>
            <div className="delivered-code"><code>{current.delivery.code}</code><CopyButton value={current.delivery.code}>复制激活码</CopyButton></div>
            <p className="commerce-muted">{current.delivery.binding_mode === 'machine' ? '此码需要绑定设备，请在准备使用的电脑上激活。' : '此码无需绑定设备。'}有效期和使用方式请以商品教程为准。</p>
            <div className="delivery-links"><a href={current.delivery.tutorial_url} target="_blank" rel="noopener noreferrer"><BookOpen size={21} /><span><strong>安装与使用教程</strong><small>打开飞书教程，按步骤安装和激活</small></span><ArrowUpRight size={18} /></a></div>
          </> : <>
            <h2>支付宝扫码付款</h2>
            <PaymentCode payment={payment} />
            {payment?.payurl && <a className="commerce-primary" href={payment.payurl} target="_blank" rel="noopener noreferrer">{payment.demo ? '打开本地模拟付款' : '打开支付宝付款页'}<ArrowUpRight size={17} /></a>}
            {!payment?.payurl && !payment?.img && !payment?.qrcode && <p className="commerce-notice">付款码暂未生成。请保存本订单并联系客服，勿重复下单。</p>}
            <button className="commerce-text-button order-refresh" disabled={checking} onClick={checkPayment}><RefreshCw size={16} className={checking ? 'commerce-spin' : ''} />{checking ? '正在确认付款…' : '我已付款，检查结果'}</button>
            <p className="commerce-muted">确认到账后自动发货，无需发送付款截图。</p>
          </>}
        </section>
      </div>}
    {error && <p className="commerce-error" role="alert">{error}</p>}
  </main>;
}

export function OrdersPage() {
  const orders = savedOrders();
  return <main className="order-page container">
    <Link to="/" className="order-back"><ArrowLeft size={16} /> 返回商品目录</Link>
    <div className="commerce-eyebrow"><span>TicketPro</span> 订单与领取</div>
    <h1>你的商品，都在这里。</h1>
    <p className="commerce-muted">这里显示此浏览器保存的订单。更换设备时，请使用你保存的私密领取链接。</p>
    <div className="order-history">{orders.length ? orders.map(order => <Link key={order.id} to={`/order/${order.id}`} className="order-history-row"><div><strong>{order.name}</strong><span>{order.duration} · {order.id}</span></div><b>{Number.isFinite(order.cents) ? `¥${(order.cents / 100).toFixed(2)}` : '查看订单'}</b><ArrowUpRight size={19} /></Link>) : <div className="order-card"><h2>还没有本机订单</h2><p className="commerce-muted">购买后，订单会保存在当前浏览器。已有订单请打开完整领取链接。</p><Link to="/" className="commerce-text-button">去看看商品 <ArrowUpRight size={16} /></Link></div>}</div>
  </main>;
}
