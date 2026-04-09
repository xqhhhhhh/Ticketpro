import { motion } from 'framer-motion';
import { X, Download } from 'lucide-react';

export default function QRViewerModal({ src, alt, onClose }) {
  const handleSave = () => {
    // 创建一个隐藏的 a 标签来触发下载
    const link = document.createElement('a');
    link.href = src;
    link.download = alt + '.jpg';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 1000, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <button 
        className="modal-close" 
        onClick={onClose}
        style={{ position: 'absolute', top: '24px', right: '24px', background: 'rgba(0,0,0,0.5)', color: '#fff', border: 'none', padding: '12px', borderRadius: '50%', cursor: 'pointer', zIndex: 1001 }}
      >
        <X size={28} />
      </button>

      <motion.div
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.8 }}
        transition={{ duration: 0.2 }}
        style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}
      >
        <img 
          src={src} 
          alt={alt} 
          style={{ 
            maxWidth: '90vw', 
            maxHeight: '70vh', 
            borderRadius: '16px', 
            objectFit: 'contain',
            boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
          }} 
        />
        
        <button 
          onClick={handleSave}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: '#ffffff',
            color: '#000000',
            border: 'none',
            padding: '14px 32px',
            borderRadius: '100px',
            fontSize: '1.1rem',
            fontWeight: '600',
            cursor: 'pointer',
            boxShadow: '0 10px 20px rgba(0,0,0,0.2)'
          }}
        >
          <Download size={20} />
          保存图片
        </button>
      </motion.div>
    </div>
  );
}
