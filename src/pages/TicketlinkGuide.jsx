import { useEffect, useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { defaultGuide, publicImageUrl, readPublishedGuide, renderGuide } from '../guideEditor';
import './ticketlink-guide.css';

export function TicketlinkGuideLayout({ html, imageUrl = publicImageUrl, preview = false }) {
  const { hash, key: locationKey } = useLocation();
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const guide = useMemo(() => renderGuide(html, imageUrl), [html, imageUrl]);

  useEffect(() => {
    if (!hash) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'instant' });
    });
    return () => cancelAnimationFrame(frame);
  }, [hash, locationKey, guide.html]);

  return (
    <div className="tl-guide">
      <header className="tl-guide-header">
        <h1>Ticketlink</h1>
        {preview ? <span>草稿预览</span> : <Link to="/">返回商品站</Link>}
      </header>
      <div className="tl-guide-layout">
        {guide.sections.length > 0 && <nav className="tl-guide-nav" aria-label="教程目录">
          <button
            type="button"
            aria-expanded={directoryOpen}
            aria-controls="ticketlink-directory"
            onClick={() => setDirectoryOpen(!directoryOpen)}
          >
            教程目录
            <ChevronDown size={16} aria-hidden="true" />
          </button>
          <div id="ticketlink-directory">
            {guide.sections.map(([id, title, level]) => (
              <Link
                key={id}
                to={{ hash: `#${id}` }}
                aria-current={hash === `#${id}` ? 'location' : undefined}
                style={{ '--tl-guide-level': level }}
              >
                {title}
              </Link>
            ))}
          </div>
        </nav>}
        <main className="tl-guide-content" dangerouslySetInnerHTML={{ __html: guide.html }} />
      </div>
    </div>
  );
}

export default function TicketlinkGuide() {
  const [html, setHtml] = useState(null);

  useEffect(() => {
    const previous = document.title;
    const controller = new AbortController();
    document.title = 'Ticketlink · 教程';
    readPublishedGuide(controller.signal)
      .then(result => { if (!controller.signal.aborted) setHtml(result.html ?? defaultGuide); })
      .catch(() => { if (!controller.signal.aborted) setHtml(defaultGuide); });
    return () => {
      controller.abort();
      document.title = previous;
    };
  }, []);

  return html === null
    ? <p className="tl-guide-loading" role="status">正在加载教程…</p>
    : <TicketlinkGuideLayout html={html} />;
}
