import { useEffect, useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { guideName, guides, publicImageUrl, readGuideSeed, readPublishedGuide, renderGuide } from '../guideEditor';
import './ticketlink-guide.css';

export function TicketlinkGuideLayout({ name, html, imageUrl, preview = false }) {
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
        <h1>{name}</h1>
        {preview ? <span>草稿预览</span> : <Link to="/help">全部教程</Link>}
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

export function GuideDirectory() {
  return (
    <div className="tl-guide">
      <header className="tl-guide-header"><h1>TicketPro</h1><Link to="/">返回商品站</Link></header>
      <main className="tl-guide-directory">
        <h2>插件教程</h2>
        <ul>
          {guides.map(guide => (
            <li key={guide.slug}><Link to={`/help/${guide.slug}`}>{guide.name}<span aria-hidden="true">↗</span></Link></li>
          ))}
        </ul>
      </main>
    </div>
  );
}

function PublishedGuide({ slug, name }) {
  const [html, setHtml] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const previous = document.title;
    const controller = new AbortController();
    document.title = `${name} · 教程`;
    async function load() {
      const result = await readPublishedGuide(slug, controller.signal).catch(() => null);
      if (controller.signal.aborted) return;
      const content = result?.html ?? await readGuideSeed(slug);
      if (!controller.signal.aborted) {
        if (content) setHtml(content);
        else setFailed(true);
      }
    }
    load().catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => {
      controller.abort();
      document.title = previous;
    };
  }, [slug, name]);

  if (failed) return <p className="tl-guide-loading" role="alert">暂时无法加载教程。<Link to="/help">返回教程目录</Link></p>;
  if (html === null) return <p className="tl-guide-loading" role="status">正在加载教程…</p>;
  return <TicketlinkGuideLayout name={name} html={html} imageUrl={id => publicImageUrl(slug, id)} />;
}

export default function TicketlinkGuide() {
  const { slug } = useParams();
  const name = guideName(slug);
  return name
    ? <PublishedGuide key={slug} slug={slug} name={name} />
    : <p className="tl-guide-loading" role="alert">未找到该教程。<Link to="/help">返回教程目录</Link></p>;
}
