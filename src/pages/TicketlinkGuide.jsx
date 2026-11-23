import { useEffect, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import TicketlinkGuideContent from './TicketlinkGuideContent';
import './ticketlink-guide.css';

const sections = [
  ["DE6kdiAG4ovB8PxfVImci7uqnzb", "二、插件教程", 0],
  ["JsZ5dFJKJoJZioxTexUcmT5JnMg", "1、安装教程", 1],
  ["XO7zdtfT3ou3Mpx9MzkcP35YnMd", "2、插件更新教程", 1],
  ["MNbCdIOi3obtiKxUyboccgU8nZg", "3、使用教程", 1],
  ["WVakdyel8opTLOxizokc2gFSnLf", "3.1 鼠标控制器", 2],
  ["CjChdwvbvoJ7sXxCVddco8rZnsg", "3.1.1 Mac系统鼠标控制器安装教程：", 3],
  ["Wtted8Mi6oRwdMxJWrWcvzCwnMf", "3.1.2 Windows系统鼠标控制器安装教程：", 3],
  ["WYardtiDroksLoxcq1EchAuanfg", "3.1.3鼠标控制器更新教程：", 3],
  ["M4nKdYHHOotfsDxgfEXcQpqBnld", "3.2 插件原理", 2],
  ["Yfu1dInPjo1yq0xGWOTcoSMensh", "3.3 参数注意事项", 2],
  ["XEEbd0WRdoMBf4xVBjucFgibnff", "3.3 插件停止快捷键", 2],
  ["EKDaduvNqoJx8SxXnBmc4MsanYf", "三、常见问题（必看）", 0],
  ["Qu70dCDJCoV5n3xjFR6cyolsn4c", "钉钉消息配置", 0],
  ["GeIqd7ELcow192xylxgcbVnAndf", "TG Bot", 0],
  ["IB9edAvp7owiD0xVBDicoYnMnee", "飞书消息提醒", 0],
  ["KYm3dbNJ4oTdYSxjT9zcAylknmf", "多开浏览器", 0],
];

export default function TicketlinkGuide() {
  const { hash, key: locationKey } = useLocation();
  const [directoryOpen, setDirectoryOpen] = useState(false);

  useEffect(() => {
    const previous = document.title;
    document.title = 'Ticketlink · 教程';
    return () => { document.title = previous; };
  }, []);

  useEffect(() => {
    if (!hash) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'instant' });
    });
    return () => cancelAnimationFrame(frame);
  }, [hash, locationKey]);

  return (
    <div className="tl-guide">
      <header className="tl-guide-header">
        <h1>Ticketlink</h1>
        <Link to="/">返回商品站</Link>
      </header>
      <div className="tl-guide-layout">
        <nav className="tl-guide-nav" aria-label="教程目录">
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
            {sections.map(([id, title, level]) => (
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
        </nav>
        <main className="tl-guide-content">
          <TicketlinkGuideContent />
        </main>
      </div>
    </div>
  );
}
