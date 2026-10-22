import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Check, Copy, Download, ExternalLink, Network, Terminal } from 'lucide-react';
import scriptTemplate from '../data/tutorials/flclash-melon-multi-port.txt?raw';
import './melon-proxy-guide.css';

const sections = [
  ['overview', '先理解端口和节点'],
  ['automatic', '使用代理中心'],
  ['manual', '手动创建多端口'],
  ['assign', '分配给 Melon 任务'],
  ['verify', '检查出口 IP'],
  ['questions', '常见问题'],
];

function CopyCode({ label, code }) {
  const [status, setStatus] = useState('');
  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setStatus('已复制');
    } catch {
      setStatus('复制失败，请选中下方代码手动复制');
    }
  }
  return <div className="mp-code">
    <div className="mp-code-bar"><span><Terminal size={14} />{label}</span><button type="button" onClick={copy}>{status === '已复制' ? <Check size={14} /> : <Copy size={14} />}{status === '已复制' ? status : '复制代码'}</button></div>
    <pre tabIndex={0} aria-label={label}><code>{code}</code></pre>
    <span className="mp-copy-status" role="status">{status}</span>
  </div>;
}

function Steps({ items }) {
  return <ol className="mp-steps">{items.map((item, index) => <li key={index}><span>{String(index + 1).padStart(2, '0')}</span><div>{item}</div></li>)}</ol>;
}

function SectionTitle({ number, children }) {
  return <div className="mp-section-title"><span>{number}</span><h2>{children}</h2></div>;
}

export default function MelonProxyGuide() {
  const [taskCount, setTaskCount] = useState('10');
  const count = Number(taskCount);
  const validCount = Number.isInteger(count) && count >= 1 && count <= 200;
  const script = scriptTemplate.replace('const TASK_COUNT = 10;', `const TASK_COUNT = ${validCount ? count : 10};`);

  useEffect(() => {
    const title = document.title;
    document.title = '代理中心使用指南 · Melon Fleet';
    return () => { document.title = title; };
  }, []);

  function downloadScript() {
    const url = URL.createObjectURL(new Blob([script], { type: 'text/javascript;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'flclash_melon_multi_port.js';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <div className="mp-guide">
    <a href="#mp-main" className="mp-skip">跳到正文</a>
    <header className="mp-header"><Link to="/" className="mp-brand"><Network size={22} /><strong>Melon Fleet</strong><span>使用指南</span></Link><Link to="/" className="mp-return"><ArrowLeft size={15} />返回商品站</Link></header>
    <div className="mp-layout">
      <aside className="mp-sidebar"><p>本页目录</p><nav aria-label="教程目录">{sections.map(([id, title], index) => <a href={`#${id}`} key={id}><span>{String(index + 1).padStart(2, '0')}</span>{title}</a>)}</nav><div className="mp-side-note"><span className="mp-dot" />适用于 Melon Fleet<p>Clash / FlClash<br />macOS & Windows</p></div></aside>
      <main id="mp-main">
        <div className="mp-hero"><div className="mp-eyebrow">NETWORK SETUP <span>/</span> 代理配置</div><h1>代理中心<span>使用指南</span></h1><p>为每个浏览器分配独立线路。<br className="mp-mobile-break" />从自动识别到手动多端口，一步步完成配置。</p><div className="mp-meta"><span>配置顺序：端口 → 节点 → 任务 → 出口 IP</span><span>更新于 2026.10.22</span></div></div>

        <section id="overview" className="mp-section">
          <SectionTitle number="01">先理解端口和节点</SectionTitle>
          <p>多个浏览器使用同一个代理节点时，会共用网络出口，可能遇到访问限制。代理中心用于为不同的 Melon 任务分配不同线路。</p>
          <div className="mp-route-diagram" aria-label="任务与代理线路对应关系">{['A', 'B', 'C'].map((node, i) => <div key={node}><span>任务 <b>0{i + 1}</b></span><ArrowRight size={16} /><code>127.0.0.1:{17891 + i}</code><ArrowRight size={16} /><span>节点 {node}</span></div>)}</div>
          <div className="mp-note"><strong>端口不同，还要确认出口 IP 不同。</strong><p>多个端口如果仍选择同一个节点，可能继续共用网络出口。完成配置后，请按第 5 节逐个检查出口 IP。</p></div>
          <p>“Chrome 专用代理”留空表示直连。需要代理时，填写代理软件实际显示的地址，例如 <code>http://127.0.0.1:7890</code>；若端口显示为 7897，就填写 <code>http://127.0.0.1:7897</code>。</p>
        </section>

        <section id="automatic" className="mp-section">
          <SectionTitle number="02">先使用代理中心</SectionTitle>
          <p>代理中心会尝试识别电脑上已经运行的 Clash、FlClash 等代理客户端。建议先走这条路径。</p>
          <Steps items={[
            <>打开代理软件，确认当前订阅已启用，节点可以正常连接。</>,
            <>打开 Melon Fleet 的<strong>“代理中心”</strong>，识别当前运行的代理客户端。</>,
            <>为不同任务分配不同的节点或本地端口，再检查各条线路的连接状态与出口 IP。</>,
          ]} />
          <p>如果客户端无法识别，也可以先在代理软件中手动创建端口，再填入 Melon Fleet 的“Chrome 专用代理”。下面以 FlClash 为例。</p>
        </section>

        <section id="manual" className="mp-section">
          <SectionTitle number="03">手动创建多端口</SectionTitle>
          <p>FlClash 的默认端口通常是 <code>127.0.0.1:7890</code>。所有 Chrome 都使用这个端口时，通常会共用当前选中的节点。通过覆写脚本，可以额外创建多个独立端口，同时保留原来的 7890。</p>
          <a className="mp-text-link" href="https://github.com/chen08209/FlClash/releases/tag/v0.8.94" target="_blank" rel="noreferrer">原教程使用的 FlClash v0.8.94 下载页<ExternalLink size={14} /></a>
          <h3>① 准备完整脚本</h3>
          <p>设置需要的任务数量，复制完整代码或下载脚本。默认创建 10 个端口，从 <code>17891</code> 连续排列到 <code>17900</code>。</p>
          <div className="mp-script-settings"><div><label htmlFor="mp-task-count">任务数量</label><input id="mp-task-count" type="number" min="1" max="200" step="1" value={taskCount} onChange={event => setTaskCount(event.target.value)} aria-invalid={!validCount} aria-describedby="mp-port-range" /><span id="mp-port-range">{validCount ? `${count} 个端口 · 17891${count > 1 ? ` — ${17890 + count}` : ''}` : '请输入 1 — 200 之间的整数'}</span></div><button type="button" disabled={!validCount} onClick={downloadScript}><Download size={16} />下载脚本 .js</button></div>
          {validCount && <CopyCode key={script} label="flclash_melon_multi_port.js" code={script} />}
          <h3>② 添加脚本</h3>
          <Steps items={[
            <>打开 FlClash，确认当前订阅已启用。进入<strong>“工具” → “高级配置” → “脚本”或“自定义覆写”</strong>。</>,
            <>点击<strong>“添加”</strong>，名称填写 <code>Melon 多端口</code>。</>,
            <>删除编辑器原有的示例内容，粘贴上面的<strong>完整脚本</strong>。确认 <code>TASK_COUNT</code> 与任务数量一致，然后保存。</>,
          ]} />
          <h3>③ 让当前订阅使用脚本</h3>
          <div className="mp-note"><strong>仅保存脚本还不会生效。</strong><p>还需要把脚本绑定到当前使用的订阅，并重新应用。</p></div>
          <Steps items={[
            <>返回 FlClash 的<strong>“配置”</strong>页面，找到当前使用的订阅卡片，点击右侧三个点。</>,
            <>选择<strong>“更多” → “覆写”</strong>；新版可能直接显示<strong>“自定义覆写”</strong>。</>,
            <>覆写类型选择<strong>“脚本”</strong>，选中刚才创建的 <code>Melon 多端口</code>。</>,
            <>保存并重新应用当前订阅。如果没有生效，先重新选择一次该订阅；仍未生效时，完全退出并重新打开 FlClash。</>,
          ]} />
          <h3>④ 为每个端口选择节点</h3>
          <p>进入 FlClash 的<strong>“代理”</strong>页面，为新出现的 <code>MELON-TASK-01</code>、<code>MELON-TASK-02</code>、<code>MELON-TASK-03</code> 等选择组分别选择节点。不同任务应选择不同线路。</p>
        </section>

        <section id="assign" className="mp-section">
          <SectionTitle number="04">分配给 Melon 任务</SectionTitle>
          <p>保持 FlClash 运行。打开 Melon Fleet → <strong>“配置列表”</strong>，编辑对应任务，在<strong>“Chrome 专用代理”</strong>中填写：</p>
          <div className="mp-table-scroll"><table><thead><tr><th>任务</th><th>Chrome 专用代理</th><th>FlClash 选择组</th></tr></thead><tbody>{[1, 2, 3].map(i => <tr key={i}><td>任务 {i}</td><td><code>http://127.0.0.1:{17890 + i}</code></td><td><code>MELON-TASK-0{i}</code></td></tr>)}</tbody></table></div>
          <p>后续任务依次使用下一个端口。端口数量由脚本中的 <code>TASK_COUNT</code> 决定。</p>
        </section>

        <section id="verify" className="mp-section">
          <SectionTitle number="05">最后，检查出口 IP</SectionTitle>
          <p>每条线路都能连接，并且出口 IP 不同时，才说明网络出口已经分开。</p>
          <h3>方法一 · 在 Melon Fleet 中检查</h3><p>进入<strong>“代理中心”</strong>，查看每个已配置端口对应的出口 IP，确认不同任务的 IP 不重复。</p>
          <h3>方法二 · 使用命令检查</h3><p>保持 FlClash 开启。macOS 打开“终端”，逐行执行：</p>
          <CopyCode label="macOS · 终端" code={[17891, 17892, 17893].map(port => `curl -x http://127.0.0.1:${port} https://api.ipify.org`).join('\n')} />
          <p>Windows 打开 PowerShell 或 CMD，逐行执行：</p>
          <CopyCode label="Windows · PowerShell / CMD" code={[17891, 17892, 17893].map(port => `curl.exe -x http://127.0.0.1:${port} https://api.ipify.org`).join('\n')} />
          <p>每条命令返回一个出口 IP。对比返回结果；更多端口按实际任务数量继续检查。</p>
        </section>

        <section id="questions" className="mp-section">
          <SectionTitle number="06">常见问题</SectionTitle>
          <details><summary>代理中心没有识别到客户端？</summary><p>先确认代理软件正在运行，订阅已启用。如果仍不能识别，按第 3 节手动创建端口，然后在“Chrome 专用代理”填写对应地址。</p></details>
          <details><summary>保存了脚本，却没有出现 MELON-TASK 选择组？</summary><p>确认当前订阅已选用“Melon 多端口”脚本，并重新应用。仅在编辑器中保存不会生效；必要时重新选择订阅，或完全退出并重新打开 FlClash。</p></details>
          <details><summary>端口不同，查到的 IP 却相同？</summary><p>检查每个 MELON-TASK 选择组是否选择了不同节点。不同名称的节点也可能共用同一个出口，最终以实际查到的出口 IP 为准。</p></details>
          <details><summary>Chrome 专用代理应该填什么？</summary><p>填写完整地址，例如 http://127.0.0.1:17891。不要只填端口号；端口必须已由代理软件创建。留空表示直连。</p></details>
        </section>
        <footer className="mp-footer"><div><Network size={18} /><strong>Melon Fleet</strong><span>代理中心使用指南</span></div><a href="#mp-main">回到顶部 ↑</a></footer>
      </main>
    </div>
  </div>;
}
