import React from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, CheckCircle2, CircleAlert, Clock3, Copy, Download, FileVideo, Gauge, Link2, ListTodo, Play, Settings, Upload, X } from 'lucide-react';
import './styles.css';

type Provider = { name: string; kind: 'file' | 'video'; enabled: boolean };
type Task = { id: number; name: string; url: string; progress: number; speed: string; status: string; providers: { name: string; progress: number; status: string; link?: string }[] };

const initialProviders: Provider[] = [
  { name: 'GoFile', kind: 'file', enabled: true },
  { name: 'Pixeldrain', kind: 'file', enabled: true },
  { name: 'Streamtape', kind: 'video', enabled: false },
  { name: 'Vidshare', kind: 'video', enabled: false },
  { name: 'FileMoon', kind: 'video', enabled: false },
];

const demoTasks: Task[] = [
  { id: 1, name: 'sample-video-1080p.mp4', url: 'https://example.com/sample.mp4', progress: 68, speed: '8.4 MB/s', status: 'Uploading', providers: [{ name: 'GoFile', progress: 82, status: 'Uploading' }, { name: 'Pixeldrain', progress: 100, status: 'Completed', link: 'https://pixeldrain.example/abc123' }, { name: 'Streamtape', progress: 0, status: 'Waiting' }] },
];

function App() {
  const [url, setUrl] = React.useState('');
  const [filename, setFilename] = React.useState('');
  const [providers, setProviders] = React.useState(initialProviders);
  const [tasks, setTasks] = React.useState(demoTasks);
  const [page, setPage] = React.useState('Dashboard');

  const toggleProvider = (name: string) => setProviders(p => p.map(x => x.name === name ? { ...x, enabled: !x.enabled } : x));
  const addTask = () => {
    if (!url.trim()) return;
    const selected = providers.filter(p => p.enabled).map(p => ({ name: p.name, progress: 0, status: 'Waiting' }));
    setTasks(t => [{ id: Date.now(), name: filename.trim() || 'Detecting filename…', url: url.trim(), progress: 0, speed: '0 KB/s', status: 'Queued', providers: selected }, ...t]);
    setUrl(''); setFilename('');
  };
  const copy = async (text: string) => { try { await navigator.clipboard.writeText(text); } catch {} };

  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">c</div><div><b>cLOADER</b><span>Download & Upload</span></div></div>
      <nav>{['Dashboard','Queue','History','Providers','Settings'].map(item => <button key={item} className={page === item ? 'nav active' : 'nav'} onClick={() => setPage(item)}>{item === 'Dashboard' ? <Gauge/> : item === 'Queue' ? <ListTodo/> : item === 'History' ? <Clock3/> : item === 'Providers' ? <Upload/> : <Settings/>}{item}</button>)}</nav>
      <div className="server"><span className="dot"/> Core online</div>
    </aside>
    <main>
      <header><div><div className="eyebrow">PERSONAL TRANSFER MANAGER</div><h1>{page}</h1></div><div className="header-status"><Activity size={16}/> Live</div></header>
      {page === 'Dashboard' && <>
        <section className="stats"><Stat icon={<Download/>} label="Downloads" value="1"/><Stat icon={<Upload/>} label="Uploads" value="2"/><Stat icon={<ListTodo/>} label="Queued" value="4"/><Stat icon={<CheckCircle2/>} label="Completed" value="127"/></section>
        <section className="grid">
          <div className="panel add"><div className="panel-title"><div><h2>Add download</h2><p>Paste a direct file or supported media URL.</p></div><Link2/></div>
            <label>Source URL</label><div className="input-wrap"><Link2 size={18}/><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://example.com/video.mp4"/></div>
            <label>Custom filename <span>optional</span></label><div className="input-wrap"><FileVideo size={18}/><input value={filename} onChange={e=>setFilename(e.target.value)} placeholder="Leave empty to detect automatically"/></div>
            <label>Upload to</label><div className="providers">{providers.map(p => <button key={p.name} onClick={()=>toggleProvider(p.name)} className={p.enabled ? 'provider selected' : 'provider'}><span className="check">{p.enabled ? '✓' : ''}</span><span>{p.name}</span><small>{p.kind}</small></button>)}</div>
            <button className="primary" onClick={addTask}><Play size={17} fill="currentColor"/> Add to queue</button>
          </div>
          <div className="panel activity-panel"><div className="panel-title"><div><h2>Live activity</h2><p>Real-time task progress</p></div><span className="live-dot">●</span></div>{tasks.slice(0,3).map(t=><TaskCard key={t.id} task={t} copy={copy}/>)}{tasks.length===0 && <Empty/>}</div>
        </section>
      </>}
      {page === 'Queue' && <section className="panel full"><div className="panel-title"><div><h2>Task queue</h2><p>Manage active and pending transfers.</p></div></div>{tasks.map(t=><TaskCard key={t.id} task={t} copy={copy}/>)}</section>}
      {page === 'History' && <section className="panel full"><Empty title="No completed history yet" text="Completed transfers will appear here."/></section>}
      {page === 'Providers' && <section className="panel full"><div className="panel-title"><div><h2>Providers</h2><p>Enable providers that should receive each upload.</p></div></div><div className="provider-list">{providers.map(p=><div className="provider-row" key={p.name}><div><b>{p.name}</b><span>{p.kind === 'file' ? 'File host' : 'Video host'}</span></div><button className={p.enabled?'switch on':'switch'} onClick={()=>toggleProvider(p.name)}><i/></button></div>)}</div></section>}
      {page === 'Settings' && <section className="panel full"><div className="panel-title"><div><h2>Settings</h2><p>Core preferences will be connected in a later step.</p></div></div><div className="setting"><b>Automatic cleanup</b><span>Delete the temporary file after all selected uploads succeed.</span><div className="switch on"><i/></div></div><div className="setting"><b>Concurrent downloads</b><span>Recommended for a small server.</span><strong>1</strong></div><div className="setting"><b>Concurrent uploads</b><span>Independent from download concurrency.</span><strong>2</strong></div></section>}
    </main>
  </div>;
}

function Stat({icon,label,value}:{icon:React.ReactNode,label:string,value:string}) { return <div className="stat"><div className="stat-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong></div></div> }
function TaskCard({task,copy}:{task:Task,copy:(s:string)=>void}) { return <article className="task"><div className="task-head"><div className="task-file"><div className="file-icon"><FileVideo/></div><div><b>{task.name}</b><span>{task.status} · {task.speed}</span></div></div><span className="badge">{task.progress}%</span></div><div className="progress"><i style={{width:`${task.progress}%`}}/></div><div className="task-meta"><span><Download size={14}/> {task.speed}</span><span><Gauge size={14}/> {task.progress}%</span><span>{task.status}</span></div><div className="uploads">{task.providers.map(p=><div className="upload-row" key={p.name}><div className="upload-name"><span className={p.status==='Completed'?'success-dot':'mini-dot'}/><b>{p.name}</b></div><div className="mini-progress"><i style={{width:`${p.progress}%`}}/></div><span>{p.status === 'Completed' && p.link ? <button className="link-btn" onClick={()=>copy(p.link)}><Copy size={14}/> Copy</button> : p.status === 'Uploading' ? `${p.progress}%` : p.status}</span></div>)}</div></article> }
function Empty({title='Nothing here yet',text='Add a URL to create your first task.'}:{title?:string,text?:string}) { return <div className="empty"><CircleAlert/><h3>{title}</h3><p>{text}</p></div> }

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
