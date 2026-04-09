import { motion } from 'framer-motion';
import { X, MessageCircle, Copy, CheckCheck, ScanFace } from 'lucide-react';
import { useState } from 'react';

export default function ContactModal({ product, type = 'wechat', onClose }) {
  const [copied, setCopied] = useState(false);
  const wechatId = 'xxxxqqqhh';

  const handleCopy = () => {
    navigator.clipboard.writeText(wechatId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isAlipay = type === 'alipay';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <motion.div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.25 }}
      >
        <button className="modal-close" onClick={onClose}>
          <X size={20} />
        </button>

        {/* Header */}
        <div className="contact-header">
          {isAlipay ? (
            <ScanFace size={24} style={{ color: '#1677ff' }} />
          ) : (
            <MessageCircle size={24} style={{ color: '#07c160' }} />
          )}
          <h3 className="modal-title">{isAlipay ? '扫码支付结账' : '微信联系我们'}</h3>
        </div>

        {product && (
          <p className="modal-subtitle">{product.name} · {product.currency}{product.pricing[0].price}起</p>
        )}

        {/* QR Code */}
        <div className="qr-section">
          {isAlipay ? (
            <div className="qr-image-wrapper" style={{ margin: '0 auto 16px', display: 'flex', justifyContent: 'center' }}>
              <img 
                src="/alipay-qr.jpg" 
                alt="支付宝收款码" 
                style={{ width: '240px', height: 'auto', borderRadius: '12px', objectFit: 'cover' }} 
              />
            </div>
          ) : (
            <div className="qr-image-wrapper" style={{ margin: '0 auto 16px', display: 'flex', justifyContent: 'center' }}>
              <img 
                src="/wechat-qr.jpg" 
                alt="微信二维码" 
                style={{ width: '240px', height: 'auto', borderRadius: '12px', objectFit: 'cover' }} 
              />
            </div>
          )}
          <p className="qr-hint">{isAlipay ? '打开支付宝扫一扫完成支付' : '长按或扫码添加客服微信'}</p>
        </div>

        {/* WeChat ID Copy (only for WeChat) */}
        {!isAlipay && (
          <div className="wechat-id-row">
            <span className="wechat-label">微信号</span>
            <span className="wechat-value">{wechatId}</span>
            <button className="copy-btn" onClick={handleCopy}>
              {copied ? <CheckCheck size={14} /> : <Copy size={14} />}
              {copied ? '已复制' : '复制'}
            </button>
          </div>
        )}

        {/* Instructions */}
        <div className="contact-steps">
          <div className="step-item">
            <span className="step-num">1</span>
            {isAlipay ? '扫码完成转账付款，并备注产品与订阅时长' : '扫码或搜索微信号添加好友'}
          </div>
          <div className="step-item">
            <span className="step-num">2</span>
            {isAlipay ? '如有问题可添加微信并发送付款截图' : '告知需要购买的产品名称'}
          </div>
          <div className="step-item">
            <span className="step-num">3</span>
            {isAlipay ? '作者确认后即刻下发激活码与详细教程' : '完成转账后即刻获得激活码 + 教程'}
          </div>
          {isAlipay && (
            <div className="step-item">
              <span className="step-num">4</span>
              若不放心可以添加作者的微信
            </div>
          )}
        </div>

      </motion.div>
    </div>
  );
}
