import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { X, ArrowRight, ScanFace, LoaderCircle, Check, MessageCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { placeOrder, shopRequest } from '../commerce';
import '../commerce.css';

export default function CheckoutModal({ product, onClose, onContact }) {
  const navigate = useNavigate();
  const closeRef = useRef(null);
  const [catalog, setCatalog] = useState(null);
  const [days, setDays] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    shopRequest('/api/catalog', { signal: controller.signal }).then(setCatalog).catch(e => {
      if (e.name !== 'AbortError') setError('自动购买暂未开放，你可以联系微信客服购买。');
    });
    const previousFocus = document.activeElement;
    closeRef.current?.focus();
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { controller.abort(); document.body.style.overflow = original; previousFocus?.focus(); };
  }, []);
  const plans = catalog?.products.find(p => p.id === product.id)?.plans || [];
  const chosen = plans.find(p => p.days === days) || plans.find(p => p.stock > 0) || plans[0];
  const ready = catalog?.payment_ready && chosen?.stock > 0;

  async function buy() {
    if (busy || !ready) return;
    setBusy(true); setError('');
    try {
      const order = await placeOrder(product.id, chosen.days);
      onClose();
      navigate(`/order/${order.id}`);
    } catch (e) { setError(e.message); setBusy(false); }
  }

  function onKeys(event) {
    if (event.key === 'Escape' && !busy) onClose();
    if (event.key === 'Tab') {
      const focusable = [...event.currentTarget.querySelectorAll('button:not(:disabled), a[href]')];
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }

  return <div className="modal-overlay" onClick={() => !busy && onClose()}>
    <motion.section className="checkout-dialog" role="dialog" aria-modal="true" aria-labelledby="checkout-title"
      initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 15 }}
      onClick={e => e.stopPropagation()} onKeyDown={onKeys}>
      <button className="modal-close" aria-label="关闭购买窗口" onClick={onClose} disabled={busy} ref={closeRef}><X size={20} /></button>
      <div className="commerce-eyebrow"><span>01</span> 选择使用期限</div>
      <h2 id="checkout-title">{product.shortName}</h2>
      <p className="commerce-muted">选好期限，付款后在订单页领取激活码和安装教程。</p>
      {catalog?.demo && <div className="commerce-notice">本地演示 · 不会扣款，演示激活码不能用于真实插件</div>}
      <div className="checkout-plans" role="group" aria-label="购买期限">
        {plans.map(plan => <button key={plan.days} className={`checkout-plan ${chosen?.days === plan.days ? 'selected' : ''}`}
          aria-pressed={chosen?.days === plan.days} disabled={!plan.stock || busy} onClick={() => setDays(plan.days)}>
          <span>{plan.label}{chosen?.days === plan.days && <Check size={15} />}</span>
          <strong><small>¥</small>{plan.cents / 100}</strong>
          <span className="commerce-muted">{plan.stock ? plan.duration : '暂时售罄'}</span>
        </button>)}
      </div>
      {!catalog && !error && <p className="commerce-muted" role="status"><LoaderCircle className="commerce-spin" size={16} /> 正在查询可售档位…</p>}
      <div className="checkout-method"><ScanFace size={24} /><div><strong>支付宝付款</strong><span>每笔订单生成独立付款码</span></div><Check size={18} /></div>
      <div className="checkout-total"><span>本次支付</span><strong>¥{chosen ? (chosen.cents / 100).toFixed(2) : '—'}</strong></div>
      <p className="commerce-error" role="alert">{error || (catalog && !ready ? '当前档位尚未开放自动购买，请联系微信客服。' : '')}</p>
      <button className="commerce-primary" disabled={!ready || busy} onClick={buy}>
        {busy ? <><LoaderCircle size={18} className="commerce-spin" /> 正在创建订单</> : <>创建订单并付款 <ArrowRight size={18} /></>}
      </button>
      <div className="checkout-foot"><button onClick={onContact} disabled={busy}><MessageCircle size={15} /> 联系微信客服</button><Link to="/orders" onClick={onClose}>查看已有订单</Link></div>
    </motion.section>
  </div>;
}
