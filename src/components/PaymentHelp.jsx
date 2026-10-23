import { MessageCircle } from 'lucide-react';

export default function PaymentHelp({ orderId }) {
  return <section className="payment-help" aria-label="付款问题微信客服">
    <div className="payment-help-title"><MessageCircle size={21} /><h3>付款遇到问题？联系微信客服</h3></div>
    <p>如果付款页面空白、无法扫码或付款失败，请添加下面的微信，我们会帮你处理。</p>
    <img src="/wechat-qr.jpg" alt="付款问题客服微信二维码，微信号 xxxxqqqhh" />
    <strong>微信号：xxxxqqqhh</strong>
    <p className="payment-help-note">添加好友时请备注：<b>付款问题</b></p>
    {orderId && <p>请同时提供订单编号：<span className="order-number">{orderId}</span></p>}
    <small>如果已经付款，请勿重复支付。可返回订单检查付款结果。</small>
  </section>;
}
