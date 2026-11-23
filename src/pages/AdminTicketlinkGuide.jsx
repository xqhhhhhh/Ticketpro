import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowUpRight, Bold, Eye, ImagePlus, Italic, Link2, List, ListOrdered, LockKeyhole, Redo2, Undo2 } from 'lucide-react';
import {
  defaultGuide, draftImageIds, publishGuide, readDraftImage, readGuideDraft, renderGuide,
  saveGuideDraft, serializeDraft, uploadGuideImage,
} from '../guideEditor';
import { TicketlinkGuideLayout } from './TicketlinkGuide';
import './admin-ticketlink-guide.css';

function Login({ onLogin }) {
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function login(event) {
    event.preventDefault();
    const key = password.trim();
    if (!key || busy) return;
    setBusy(true);
    setError('');
    try {
      const draft = await readGuideDraft(key);
      onLogin({ key, draft });
    } catch (error) {
      setError(error.status === 401 ? error.message : '无法连接教程后台，请稍后重试。');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="tled-login">
      <div className="tled-lock"><LockKeyhole size={24} /></div>
      <h1>Ticketlink 教程后台</h1>
      <p>登录后修改正文、插入图片和发布教程。</p>
      <form onSubmit={login}>
        <label htmlFor="ticketlink-admin-password">商城管理员密钥</label>
        <input id="ticketlink-admin-password" type="password" autoComplete="current-password"
          value={password} onChange={(event) => setPassword(event.target.value)} required />
        <button type="submit" className="tled-primary" disabled={busy}>{busy ? '正在登录…' : '登录'}</button>
      </form>
      {error && <p role="alert" className="tled-error">{error}</p>}
    </section>
  );
}

function EditorToolbar({ command, chooseImage, addLink, disabled }) {
  return (
    <div className="tled-tools" role="toolbar" aria-label="正文格式">
      <select aria-label="段落格式" disabled={disabled} value=""
        onChange={(event) => command('formatBlock', event.target.value)}>
        <option value="" disabled>段落格式</option>
        <option value="p">正文</option>
        <option value="h2">一级章节</option>
        <option value="h3">二级章节</option>
        <option value="h4">三级章节</option>
        <option value="h5">四级章节</option>
        <option value="blockquote">引用</option>
      </select>
      <div>
        {[
          ['bold', '加粗', <Bold size={17} />], ['italic', '斜体', <Italic size={17} />],
          ['insertUnorderedList', '项目列表', <List size={17} />], ['insertOrderedList', '编号列表', <ListOrdered size={17} />],
        ].map(([action, label, icon]) => (
          <button key={action} type="button" title={label} aria-label={label} disabled={disabled}
            onMouseDown={(event) => event.preventDefault()} onClick={() => command(action)}>{icon}</button>
        ))}
        <button type="button" title="插入链接" aria-label="插入链接" disabled={disabled}
          onMouseDown={(event) => event.preventDefault()} onClick={addLink}><Link2 size={17} /></button>
        <button type="button" title="插入图片" disabled={disabled}
          onMouseDown={(event) => event.preventDefault()} onClick={chooseImage}><ImagePlus size={17} />插图</button>
      </div>
      <div>
        <button type="button" title="撤销" aria-label="撤销" disabled={disabled}
          onMouseDown={(event) => event.preventDefault()} onClick={() => command('undo')}><Undo2 size={17} /></button>
        <button type="button" title="重做" aria-label="重做" disabled={disabled}
          onMouseDown={(event) => event.preventDefault()} onClick={() => command('redo')}><Redo2 size={17} /></button>
      </div>
    </div>
  );
}

const actionMessages = {
  upload: '正在上传图片…',
  save: '正在保存草稿…',
  preview: '正在准备预览…',
  publish: '正在发布…',
};

function Workspace({ session, onLogout }) {
  const editor = useRef(null);
  const picker = useRef(null);
  const selection = useRef(null);
  const imageUrls = useRef(new Map());
  const initial = useRef(session.draft.html ?? defaultGuide);
  const [draft, setDraft] = useState(session.draft);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState('');
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const key = session.key;

  useEffect(() => {
    const controller = new AbortController();
    const urls = imageUrls.current;
    const element = editor.current;
    async function load() {
      await Promise.all([...draftImageIds(initial.current)].map(async id => {
        const blob = await readDraftImage(key, id, controller.signal);
        if (!controller.signal.aborted) urls.set(id, URL.createObjectURL(blob));
      }));
      if (controller.signal.aborted) return;
      element.innerHTML = renderGuide(initial.current, id => urls.get(id)).html;
      setReady(true);
    }
    load().catch(() => {
      if (!controller.signal.aborted) setError('草稿图片读取失败，请刷新后重试。');
    });
    return () => {
      controller.abort();
      for (const url of urls.values()) URL.revokeObjectURL(url);
      urls.clear();
    };
  }, [key]);

  useEffect(() => {
    if (!dirty) return;
    const warning = (event) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warning);
    return () => window.removeEventListener('beforeunload', warning);
  }, [dirty]);

  function rememberSelection() {
    const active = window.getSelection();
    if (active?.rangeCount && editor.current.contains(active.anchorNode) && editor.current.contains(active.focusNode)) {
      selection.current = active.getRangeAt(0).cloneRange();
    }
  }

  function restoreSelection(range = selection.current) {
    const element = editor.current;
    element.focus();
    const active = window.getSelection();
    if (!active) return;
    const fallback = document.createRange();
    fallback.selectNodeContents(element);
    fallback.collapse(false);
    active.removeAllRanges();
    active.addRange(range && element.contains(range.commonAncestorContainer) ? range : fallback);
  }

  function change() {
    setDirty(true);
    setNotice('');
    rememberSelection();
  }

  function command(action, value = null) {
    restoreSelection();
    if (document.execCommand(action, false, value)) change();
  }

  function addLink() {
    rememberSelection();
    const input = window.prompt('输入 HTTPS 链接');
    if (!input) return;
    try {
      const url = new URL(input.trim());
      if (url.protocol !== 'https:' || url.username || url.password) throw new Error();
      const link = document.createElement('a');
      link.href = url.href;
      link.textContent = url.href;
      if (!selection.current || selection.current.collapsed) command('insertHTML', link.outerHTML);
      else command('createLink', url.href);
    } catch {
      setError('请输入有效的 HTTPS 链接。');
    }
  }

  async function insertImage(file) {
    if (!file || busy) return;
    rememberSelection();
    const range = selection.current;
    if (file.size > 5 * 1024 * 1024) {
      setError('单张图片最多 5 MB。');
      return;
    }
    setBusy('upload');
    setError('');
    try {
      const { id } = await uploadGuideImage(key, file);
      if (!imageUrls.current.has(id)) {
        imageUrls.current.set(id, URL.createObjectURL(await readDraftImage(key, id)));
      }
      const image = document.createElement('img');
      image.dataset.guideImage = id;
      image.src = imageUrls.current.get(id);
      image.alt = file.name.replace(/\.[^.]+$/, '') || '教程图片';
      restoreSelection(range);
      if (document.execCommand('insertHTML', false, image.outerHTML)) change();
      else setError('图片已上传，请将光标放入正文后重新插入。');
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy('');
    }
  }

  function paste(event) {
    event.preventDefault();
    if (busy) return;
    const file = [...event.clipboardData.files].find(item => item.type.startsWith('image/'));
    if (file) void insertImage(file);
    else {
      rememberSelection();
      command('insertText', event.clipboardData.getData('text/plain'));
    }
  }

  async function save(openPreview = false) {
    setBusy(openPreview ? 'preview' : 'save');
    setError('');
    try {
      const result = !dirty && draft.html !== null
        ? draft
        : await saveGuideDraft(key, draft.revision, serializeDraft(editor.current.innerHTML));
      setDraft(result);
      setDirty(false);
      setNotice('草稿已保存');
      if (openPreview) {
        setPreview(true);
        window.scrollTo({ top: 0, behavior: 'instant' });
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy('');
    }
  }

  async function publish() {
    setBusy('publish');
    setError('');
    try {
      setDraft(await publishGuide(key, draft.revision));
      setNotice('已发布到公开教程');
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy('');
    }
  }

  const state = dirty ? '有未保存的修改' : draft.published_revision === draft.revision ? '已发布' : draft.html === null ? '以线上教程为底稿' : '草稿尚未发布';

  return <>
    <header className="tled-workbar">
      <div><strong>{preview ? 'Ticketlink · 草稿预览' : 'Ticketlink · 教程编辑'}</strong><small>{state}</small></div>
      <div className="tled-actions">
        {preview ? <>
          <button type="button" disabled={!!busy} onClick={() => setPreview(false)}><ArrowLeft size={15} />返回编辑</button>
          <button type="button" className="tled-primary" onClick={publish}
            disabled={!!busy || draft.published_revision === draft.revision}>发布教程</button>
        </> : <>
          <button type="button" disabled={!ready || !!busy || !dirty} onClick={() => save()}>保存草稿</button>
          <button type="button" className="tled-primary" disabled={!ready || !!busy} onClick={() => save(true)}><Eye size={16} />预览草稿</button>
        </>}
        <button type="button" disabled={!!busy}
          onClick={() => { if (!dirty || window.confirm('还有未保存的修改，确定退出？')) onLogout(); }}>退出</button>
      </div>
    </header>
    {(busy || notice) && <p className="tled-feedback" role="status">{actionMessages[busy] || notice}</p>}
    {error && <p className="tled-feedback tled-error" role="alert">{error}</p>}
    {preview && <TicketlinkGuideLayout html={draft.html} imageUrl={id => imageUrls.current.get(id)} preview />}
    <section className="tled-sheet" hidden={preview} aria-label="教程编辑区">
      <EditorToolbar command={command} addLink={addLink}
        chooseImage={() => { rememberSelection(); picker.current.click(); }} disabled={!ready || !!busy} />
      <input ref={picker} type="file" accept="image/png,image/jpeg,image/webp" aria-label="选择插入图片" hidden
        onChange={(event) => { void insertImage(event.target.files[0]); event.target.value = ''; }} />
      {!ready && !error && <p className="tled-feedback" role="status">正在读取草稿…</p>}
      <div ref={editor} className="tl-guide-content tled-document" contentEditable={ready && (!busy || busy === 'upload')}
        role="textbox" tabIndex={ready ? 0 : -1} aria-label="教程正文" aria-multiline="true"
        onInput={change} onMouseUp={rememberSelection} onKeyUp={rememberSelection}
        onPaste={paste} onDrop={event => event.preventDefault()}
      />
    </section>
  </>;
}

export default function AdminTicketlinkGuide() {
  const [session, setSession] = useState(null);

  useEffect(() => {
    const previous = document.title;
    document.title = 'Ticketlink 教程后台 · TicketPro';
    return () => { document.title = previous; };
  }, []);

  return (
    <div className="tled">
      <header className="tled-top">
        <a href="/admin/orders">TicketPro 商家工作台</a>
        <a href="/help/ticketlink" target="_blank" rel="noreferrer">查看公开教程<ArrowUpRight size={15} /></a>
      </header>
      {session ? <Workspace session={session} onLogout={() => setSession(null)} /> : <Login onLogin={setSession} />}
    </div>
  );
}
