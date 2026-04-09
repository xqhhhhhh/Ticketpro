import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Check, Star, Play, MessageCircle, ArrowRight, Image, ScanFace } from 'lucide-react';
import { products } from '../data/products';

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function ProductDetail({ onAction }) {
  const { id } = useParams();
  const product = products.find((p) => p.id === id);

  if (!product) {
    return (
      <div className="detail-not-found">
        <h2>产品未找到</h2>
        <Link to="/" className="btn btn-secondary">返回首页</Link>
      </div>
    );
  }

  return (
    <div className="detail-page">
      {/* Back Nav */}
      <div className="detail-nav">
        <div className="container">
          <Link to="/" className="back-link">
            <ArrowLeft size={18} />
            返回全部产品
          </Link>
        </div>
      </div>

      {/* Hero */}
      <section className="detail-hero">
        <div
          className="detail-hero-glow"
          style={{ background: `radial-gradient(ellipse at center top, ${hexToRgba(product.color, 0.2)}, transparent 70%)` }}
        />
        <div className="container">
          <motion.div
            className="detail-hero-content"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="detail-hero-left">
              <div className={`detail-icon ${product.logo ? 'has-logo' : ''}`} style={product.logo ? {} : { background: product.color }}>
                {product.logo ? (
                  <img src={product.logo} alt={product.shortName} className="detail-logo-img" />
                ) : (
                  product.shortName.charAt(0)
                )}
              </div>
              <div>
                {product.badge && (
                  <span className="detail-badge" style={{ background: product.color }}>{product.badge}</span>
                )}
                <h1>{product.name}</h1>
                <p className="detail-long-desc">{product.longDescription}</p>
                <div className="detail-pricing-tiers" style={{ marginLeft: '12px' }}>
                  {product.pricing.map((tier, i) => (
                    <div key={i} className={`detail-tier ${tier.badge ? 'recommended' : ''}`}>
                      {tier.badge && <span className="detail-tier-badge" style={{ background: product.color }}>{tier.badge}</span>}
                      <span className="detail-tier-label">{tier.label}</span>
                      <div className="detail-tier-price">
                        <span className="detail-tier-currency">{product.currency}</span>
                        <span className="detail-tier-amount">{tier.price}</span>
                      </div>
                      <span className="detail-tier-duration">{tier.duration}</span>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: '16px', marginTop: '16px', marginBottom: '32px' }}>
                  <button className="btn btn-primary" onClick={() => onAction(product, 'alipay')} style={{ background: '#1677ff', borderColor: '#1677ff', flex: 1, padding: '14px 24px', fontSize: '1.05rem', fontWeight: 'bold' }}>
                    <ScanFace size={18} />
                    立即购买
                  </button>
                  <button className="btn btn-primary" onClick={() => onAction(product, 'wechat')} style={{ background: '#07c160', borderColor: '#07c160', flex: 1, padding: '14px 24px', fontSize: '1.05rem', fontWeight: 'bold' }}>
                    <MessageCircle size={18} />
                    联系我们
                  </button>
                </div>

                <div className="detail-features-compact">
                  {product.features.map((f, i) => (
                    <div key={i} className="detail-feature-tag">
                      <Check size={14} strokeWidth={3} style={{ color: product.color }} />
                      {f}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Video Demo */}
      <section className="detail-section">
        <div className="container">
          <div className="section-header" style={{ marginBottom: '40px' }}>
            <div className="section-tag" style={{ margin: '0 auto 16px' }}>
              <Play size={14} />
              DEMO
            </div>
            <h2 className="section-title" style={{ fontSize: '2rem', textAlign: 'center' }}>运行演示</h2>
            <p className="section-subtitle" style={{ textAlign: 'center', margin: 0 }}>
              观看插件的实际运行效果，眼见为实
            </p>
          </div>
          {product.videos && product.videos.length > 0 ? (
            <div className="videos-grid" style={{ display: 'grid', gridTemplateColumns: product.videos.length > 1 ? 'repeat(2, 1fr)' : '1fr', gap: '20px', maxWidth: product.videos.length > 1 ? '100%' : '800px', margin: '0 auto' }}>
              {product.videos.map((vid, idx) => (
                <motion.div
                  key={idx}
                  className="video-container"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: idx * 0.1 }}
                >
                  <video 
                    controls 
                    className="demo-video" 
                    style={{ 
                      width: '100%', 
                      aspectRatio: '16/9', 
                      objectFit: 'contain', 
                      borderRadius: '12px', 
                      border: `1px solid ${hexToRgba(product.color, 0.2)}`, 
                      background: '#000' 
                    }}
                  >
                    <source src={vid} type={vid.endsWith('.mov') ? 'video/quicktime' : 'video/mp4'} />
                    你的浏览器不支持播放此视频。
                  </video>
                </motion.div>
              ))}
            </div>
          ) : (
            <motion.div
              className="video-container"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
            >
              <div className="video-placeholder" style={{ borderColor: hexToRgba(product.color, 0.3) }}>
                <Play size={48} style={{ color: product.color }} />
                <p>视频演示</p>
                <span>上线后替换为实际演示视频</span>
              </div>
            </motion.div>
          )}
        </div>
      </section>

      {/* Highlights (图文介绍) */}
      <section className="detail-section">
        <div className="container">
          <div className="section-header" style={{ marginBottom: '40px' }}>
            <div className="section-tag" style={{ margin: '0 auto 16px' }}>FEATURES</div>
            <h2 className="section-title" style={{ fontSize: '2rem', textAlign: 'center' }}>核心功能详解</h2>
          </div>
          <div className="highlights-grid">
            {product.highlights.map((h, i) => (
              <motion.div
                key={i}
                className="highlight-card"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
              >

                <div className="highlight-text">
                  <h3>{h.title}</h3>
                  <p>{h.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials (用户案例) */}
      <section className="detail-section">
        <div className="container">
          <div className="section-header" style={{ marginBottom: '40px' }}>
            <div className="section-tag" style={{ margin: '0 auto 16px' }}>REVIEWS</div>
            <h2 className="section-title" style={{ fontSize: '2rem', textAlign: 'center' }}>用户真实反馈</h2>
          </div>
          {product.testimonialVideo ? (
            <motion.div
              className="testimonial-video-container"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              style={{ maxWidth: '360px', margin: '0 auto' }} // Vertically oriented video
            >
              <video 
                controls 
                autoPlay
                muted
                loop
                className="demo-video" 
                style={{ 
                  width: '100%', 
                  borderRadius: '16px', 
                  border: `1px solid ${hexToRgba(product.color, 0.2)}`, 
                  background: '#000',
                  boxShadow: '0 20px 40px rgba(0,0,0,0.3)'
                }}
              >
                <source src={product.testimonialVideo} type="video/mp4" />
                你的浏览器不支持播放此视频。
              </video>
            </motion.div>
          ) : product.testimonials && (
            <div className="testimonials-grid">
              {product.testimonials.map((t, i) => (
                <motion.div
                  key={i}
                  className="testimonial-card"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: i * 0.1 }}
                >
                  <div className="testimonial-stars">
                    {Array.from({ length: t.rating }).map((_, j) => (
                      <Star key={j} size={14} fill={product.color} stroke={product.color} />
                    ))}
                  </div>
                  <p className="testimonial-text">"{t.content}"</p>
                  <div className="testimonial-author">
                    <div className="testimonial-avatar" style={{ background: hexToRgba(product.color, 0.2), color: product.color }}>
                      {t.name.charAt(0)}
                    </div>
                    <span>{t.name}</span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="detail-section">
        <div className="container">
          <div className="detail-cta-box" style={{ borderColor: hexToRgba(product.color, 0.3) }}>
            <div className="detail-cta-glow" style={{ background: `radial-gradient(circle, ${hexToRgba(product.color, 0.15)}, transparent 70%)` }} />
            <h2>准备好使用 {product.shortName} 了吗？</h2>
            <p>扫码联系客服，即刻获取专属激活码和使用教程</p>
            <div className="detail-cta-actions">
              <button className="btn btn-primary" onClick={() => onAction(product, 'alipay')} style={{ background: '#1677ff', borderColor: '#1677ff' }}>
                <ScanFace size={18} />
                立即购买
              </button>
              <button className="btn btn-primary" onClick={() => onAction(product, 'wechat')} style={{ background: '#07c160', borderColor: '#07c160' }}>
                <MessageCircle size={18} />
                联系我们
              </button>
              <Link to="/" className="btn btn-secondary">
                浏览其他产品
                <ArrowRight size={18} />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
