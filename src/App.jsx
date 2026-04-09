import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Shield, Globe, Headphones, ArrowRight, Sparkles, MessageCircle, Check } from 'lucide-react';
import { products, features } from './data/products';
import ProductDetail from './pages/ProductDetail';
import ContactModal from './components/ContactModal';
import './App.css';

import QRViewerModal from './components/QRViewerModal';

const iconMap = { Zap, Shield, Globe, Headphones };

function ClickableQR({ src, alt, style }) {
  const [viewingQR, setViewingQR] = useState(false);
  return (
    <>
      <div onClick={() => setViewingQR(true)} title="点击放大图片" style={{ cursor: 'zoom-in', display: 'inline-block' }}>
        <img src={src} alt={alt} style={style} />
      </div>
      <AnimatePresence>
        {viewingQR && (
          <QRViewerModal 
            src={src} 
            alt={alt} 
            onClose={() => setViewingQR(false)} 
          />
        )}
      </AnimatePresence>
    </>
  );
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* Scroll to top on route change */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

/* ===== Navbar ===== */
function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav className={`navbar ${scrolled ? 'scrolled' : ''}`}>
      <div className="container nav-inner">
        <Link to="/" className="brand">TicketPro</Link>
        <div className="nav-links">
          <a href="/#products">核心产品</a>
          <a href="/#features">高级特性</a>
          <a href="/#contact-section">联系我们</a>

        </div>
        <a href="/#products" className="nav-cta">立即选购</a>
      </div>
    </nav>
  );
}

/* ===== Hero ===== */
function Hero() {
  return (
    <section className="hero">
      <div className="ambient-bg" />
      <div className="ambient-grid" />
      <motion.div
        className="hero-content"
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="hero-status">
          <span className="status-dot" />
          全平台自动化抢票引擎已就绪
        </div>
        <h1>
          抢票捡漏，本该如此<br />
          <span className="gradient-text">毫不费力</span>
        </h1>

        <div className="btn-group">
          <a href="#products" className="btn btn-primary">
            浏览产品目录
            <ArrowRight size={18} />
          </a>
        </div>
      </motion.div>
    </section>
  );
}

/* ===== Product Card ===== */
function ProductCard({ product, index, onAction }) {
  const glowColor = hexToRgba(product.color, 0.15);
  return (
    <motion.div
      className="product-card"
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-100px' }}
      transition={{ duration: 0.6, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
      style={{
        '--card-color': product.color,
        '--card-color-light': glowColor,
        '--card-color-glow': hexToRgba(product.color, 0.4),
      }}
    >
      <div className="product-header">
        <div className={`product-icon-wrapper ${product.logo ? 'has-logo' : ''}`} style={product.logo ? {} : { background: product.color }}>
          {product.logo ? (
            <img src={product.logo} alt={product.shortName} className="product-logo-img" />
          ) : (
            product.name.charAt(0)
          )}
        </div>
        {product.badge && (
          <div className="product-badge" style={{ background: product.color }}>
            {product.badge}
          </div>
        )}
      </div>
      <div className="product-content">
        <h3>{product.name}</h3>
        <p>{product.description}</p>
        <div className="product-features-list">
          {product.features.map((f, i) => (
            <div key={i} className="feature-item">
              <div className="feature-check" style={{ color: product.color }}>
                <Check size={12} strokeWidth={3} />
              </div>
              {f}
            </div>
          ))}
        </div>
      </div>
      <div className="product-footer">
        <div className="pricing-tiers">
          {product.pricing.map((tier, i) => (
            <div key={i} className={`pricing-tier ${tier.badge ? 'recommended' : ''}`}>
              {tier.badge && <span className="tier-badge">{tier.badge}</span>}
              <span className="tier-label">{tier.label}</span>
              <div className="tier-price">
                <span className="tier-currency">{product.currency}</span>
                <span className="tier-amount">{tier.price}</span>
              </div>
              <span className="tier-duration">{tier.duration}</span>
            </div>
          ))}
        </div>
        <div className="product-actions-grid">
          <Link to={`/product/${product.id}`} className="buy-btn" style={{ textDecoration: 'none', background: 'var(--glass-bg)', color: 'var(--text-primary)', border: '1px solid var(--glass-border)' }}>
            查看详情
          </Link>
          <button className="buy-btn" onClick={() => onAction(product, 'alipay')} style={{ background: '#1677ff', color: '#fff' }}>
            立即购买
          </button>
          <button className="buy-btn" onClick={() => onAction(product, 'wechat')} style={{ background: '#07c160', color: '#fff' }}>
            联系我们
          </button>
        </div>
      </div>
    </motion.div>
  );
}

/* ===== Products Section ===== */
function ProductsSection({ onAction }) {
  return (
    <section className="section" id="products">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">PRODUCTS</div>
          <h2 className="section-title">实现技术平权</h2>
          <p className="section-subtitle">
            打破技术壁垒，让每一位普通粉丝都能零门槛享受全自动科技抢票与捡漏的乐趣。
          </p>
        </div>
        <div className="products-grid">
          {products.map((product, i) => (
            <ProductCard key={product.id} product={product} index={i} onAction={onAction} />
          ))}
        </div>
      </div>
    </section>
  );
}

/* ===== Features ===== */
function FeaturesSection() {
  return (
    <section className="section" id="features">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">TECHNOLOGY</div>
          <h2 className="section-title">核心技术优势</h2>
        </div>
        <div className="features-grid">
          {features.map((feature, i) => {
            const Icon = iconMap[feature.icon];
            return (
              <motion.div
                key={i}
                className="feature-box"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
              >
                <div className="icon-container">
                  <Icon size={24} />
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}



/* ===== Contact ===== */
function ContactSection() {
  return (
    <section className="section" id="contact-section">
      <div className="container">
        <div className="section-header">
          <div className="section-tag">CONTACT</div>
          <h2 className="section-title">联系我们</h2>
        </div>
        <div className="contact-grid" style={{ gridTemplateColumns: '1fr', maxWidth: '320px', margin: '0 auto' }}>
          <motion.div
            className="contact-card"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <div className="contact-qr-slot" style={{ border: 'none', background: 'transparent', width: '240px', height: 'auto', padding: 0 }}>
              <ClickableQR 
                src="/wechat-qr.jpg" 
                alt="作者微信" 
                style={{ width: '100%', height: 'auto', borderRadius: '12px', display: 'block' }} 
              />
            </div>
            <h3 className="contact-card-label" style={{ marginBottom: '12px' }}>作者微信</h3>
            <p className="contact-card-sublabel" style={{ fontWeight: 600, color: 'var(--text-primary)', background: 'rgba(255,255,255,0.05)', padding: '6px 16px', borderRadius: '100px', display: 'inline-block' }}>
              微信号：xxxxqqqhh
            </p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ===== CTA ===== */
function CTASection() {
  return (
    <section className="section cta-section">
      <div className="container">
        <div className="cta-box">
          <div className="cta-glow" />
          <h2>不要把运气交给手动点击</h2>
          <p>加入专业玩家行列，让自动化为您锁定每一张门票。</p>
          <a href="#products" className="btn btn-primary" style={{ padding: '14px 40px' }}>
            开始使用 TicketPro
          </a>
        </div>
      </div>
    </section>
  );
}

/* ===== Footer ===== */
function Footer() {
  return (
    <footer className="footer" id="contact">
      <div className="container">
        <div className="footer-grid">
          <div>
            <div className="footer-brand">
              <h3>TicketPro</h3>
              <p>新一代自动化抢票引擎，为您提供极速、稳定、安全的抢票体验。</p>
            </div>
          </div>
          <div className="footer-col">
            <h4>产品列表</h4>
            <ul className="footer-links">
              {products.map((p) => (
                <li key={p.id}><Link to={`/product/${p.id}`}>{p.shortName}</Link></li>
              ))}
            </ul>
          </div>
          <div className="footer-col">
            <h4>客户支持</h4>
            <div className="footer-qr" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <ClickableQR 
                src="/wechat-qr.jpg" 
                alt="作者微信二维码" 
                style={{ width: '120px', height: 'auto', borderRadius: '8px' }} 
              />
              <span style={{ fontSize: '0.85rem', color: '#a1a1aa' }}>
                <MessageCircle size={14} style={{ display: 'inline', verticalAlign: 'text-bottom', marginRight: '4px' }} />
                微信号：xxxxqqqhh
              </span>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <span>&copy; {new Date().getFullYear()} TicketPro. All rights reserved.</span>
          <span>声明：本软件仅作自动化辅助学习交流，请合理合法使用。</span>
        </div>
      </div>
    </footer>
  );
}

/* ===== Home Page ===== */
function HomePage({ onAction }) {
  return (
    <>
      <Hero />
      <ProductsSection onAction={onAction} />
      <FeaturesSection />
      <ContactSection />
      <CTASection />
    </>
  );
}

/* ===== App ===== */
function App() {
  const [modalConfig, setModalConfig] = useState(null);

  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="app-wrapper">
        <Navbar />
        <Routes>
          <Route path="/" element={<HomePage onAction={(p, type) => setModalConfig({ product: p, type })} />} />
          <Route path="/product/:id" element={<ProductDetail onAction={(p, type) => setModalConfig({ product: p, type })} />} />
        </Routes>
        <Footer />

        <AnimatePresence>
          {modalConfig && (
            <ContactModal
              product={modalConfig.product}
              type={modalConfig.type}
              onClose={() => setModalConfig(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </BrowserRouter>
  );
}

export default App;
