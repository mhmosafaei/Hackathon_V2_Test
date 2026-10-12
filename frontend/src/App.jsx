import React, {useEffect, useRef, useState} from 'react';
import {Anchor, ArrowUpRight, FileText, Upload, Plus, Search, ShieldCheck, LoaderCircle, AlertCircle, ChevronDown, Waves} from 'lucide-react';
import {BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell} from 'recharts';

export const phases = ['PRIOR', 'DURING', 'AFTER', 'GENERAL'];
export const categories = ['Notification / Deadline', 'Positioning / Geographic', 'Monitoring / Survey', 'Reporting / Recordkeeping', 'Operational / Safety', 'Approval / Administrative', 'Other'];
const colors = ['#167b88', '#193e57', '#72b5ae', '#bacbd0'];
const pretty = s => s[0] + s.slice(1).toLowerCase();
export function chartData(conditions) {
  return {
    phase: phases.map(name => ({name: pretty(name), value: conditions.filter(c => c.phase === name).length})),
    category: categories.map(name => ({name, value: conditions.filter(c => c.category === name).length})),
    limits: [{name: 'Has explicit limit/deadline', value: conditions.filter(c => c.important_limit?.trim() || c.timing?.trim()).length},
      {name: 'No explicit limit/deadline', value: conditions.filter(c => !c.important_limit?.trim() && !c.timing?.trim()).length}]
  };
}
const fallback = v => v || 'Not stated';
export function geofenceSummary(geofence) {
  // Never place coordinate lists in the compact card, even if a model puts them in name.
  const name = geofence.name?.trim() || '';
  const coordinateLike = /[°º]|\d+\.\d+.*\d+\.\d+/.test(name);
  const label = name && name.length <= 100 && !coordinateLike ? name : geofence.type.replaceAll('_', ' ');
  const radius = geofence.type === 'radius' && geofence.coordinates_or_boundary?.match(/\b\d+(?:\.\d+)?\s*(?:NM|nautical miles?|km|kilometres?|kilometers?|metres?|meters?|m)\b/i)?.[0];
  return radius ? `${label} · ${radius} radius` : label;
}
function GeofenceCard({geofences}) {
  if (!geofences?.length) return null;
  return <section className="card metric geofence-card" aria-label="Geographic restrictions" data-testid="geofence-card"><details>
    <summary data-testid="geofence-summary"><span className="eyebrow">GEOFENCE</span><strong>{geofences.length === 1 ? geofenceSummary(geofences[0]) : `${geofences.length} geographic restrictions`}</strong>
      {geofences.length > 1 && <span className="geofence-lead">{geofenceSummary(geofences[0])}</span>}<span className="geofence-action">View restrictions <ChevronDown size={13}/></span></summary>
    <div className="geofence-details">{geofences.map((g, i) => <article key={i}><h3>{g.name}</h3><p>{g.description}</p><dl>
      <dt>Type</dt><dd>{g.type.replaceAll('_', ' ')}</dd><dt>Restriction</dt><dd>{g.restriction}</dd>
      <dt>Coordinates / boundary</dt><dd className="geofence-boundary">{fallback(g.coordinates_or_boundary)}</dd><dt>Physical source pages</dt><dd>{g.source_pages.join(', ') || 'Unresolved'}</dd>
    </dl><small>{g.source_verified ? 'Source quotation verified · Human review required' : 'Source verification required · Unreviewed'}</small>
      {g.source_spans?.map((s, j) => <blockquote key={j}><b>Physical page {s.page}</b><p>{s.quotation}</p></blockquote>)}
    </article>)}</div>
  </details></section>;
}
function Chart({title, data, type, index}) {
  return <section className="card chart-card" aria-label={title} data-testid="chart"><div className="section-heading"><h3>{title}</h3><span className="eyebrow">CONDITIONS</span></div>
    <div className="chart-area"><ResponsiveContainer width="100%" height="100%">
      {type === 'bar' ? <BarChart data={data} layout={index === 1 ? 'vertical' : 'horizontal'} margin={{top: 10, right: 25, left: index === 1 ? 5 : 0, bottom: 5}}>
        <CartesianGrid strokeDasharray="3 3" horizontal={index !== 1} vertical={index === 1} stroke="#e6edef"/>
        <XAxis type={index === 1 ? 'number' : 'category'} dataKey={index === 1 ? undefined : 'name'} allowDecimals={false} axisLine={false} tickLine={false} fontSize={12}/>
        <YAxis type={index === 1 ? 'category' : 'number'} dataKey={index === 1 ? 'name' : undefined} width={index === 1 ? 164 : 30} allowDecimals={false} axisLine={false} tickLine={false} fontSize={11}/>
        <Tooltip cursor={{fill: '#f1f6f6'}}/><Bar dataKey="value" name="Conditions" fill="#167b88" radius={[4, 4, 4, 4]} maxBarSize={38} isAnimationActive={false}/>
      </BarChart> : <PieChart><Pie data={data} dataKey="value" nameKey="name" innerRadius={62} outerRadius={93} paddingAngle={2} isAnimationActive={false}>
        {data.map((d, i) => <Cell key={d.name} fill={colors[i % colors.length]}/>)}</Pie><Tooltip/></PieChart>}
    </ResponsiveContainer></div>
    {type === 'pie' && <div className="legend">{data.map((d, i) => <span key={d.name}><i style={{background: colors[i % colors.length]}}/>{d.name}<b>{d.value}</b></span>)}</div>}
  </section>;
}
export function Results({analysis}) {
  const [search, setSearch] = useState('');
  const [phase, setPhase] = useState('ALL');
  const data = chartData(analysis.conditions);
  const shown = analysis.conditions.filter(c => (phase === 'ALL' || c.phase === phase) && `${c.number} ${c.requirement} ${c.category} ${c.important_limit || ''} ${c.timing || ''}`.toLowerCase().includes(search.toLowerCase()));
  const unverified = analysis.conditions.filter(c => !c.source_verified).length;
  const summary = analysis.summary;
  return <>
    <div className="page-heading"><div><div className="eyebrow">PERMIT INTELLIGENCE</div><h1>Your permit, at a glance.</h1><p>{analysis.filename} <span className="dot">·</span> {analysis.page_count} pages</p></div><span className="status"><ShieldCheck size={15}/> Human review required</span></div>
    {analysis.mode === 'MOCK' && <div className="notice">Synthetic demonstration · These are mocked records, not extracted Kilkeel evidence.</div>}
    <div className="summary-grid">{[['Permit number', summary.permit_number], ['Licensee', summary.licensee], ['Issuing authority', summary.authority], ['Validity', `${fallback(summary.valid_from)} — ${fallback(summary.valid_until)}`], ['Activity', summary.activity], ['Total conditions', analysis.conditions.length]].map(([label, value]) => <section className="card metric" key={label}><div className="eyebrow">{label}</div><strong>{fallback(value)}</strong></section>)}<GeofenceCard geofences={analysis.geofences}/></div>
    <section className="card limits"><div className="section-heading"><div><h2>Key Permit Limits</h2><p>Important values and deadlines identified in the document</p></div><FileText size={20}/></div>
      {analysis.key_limits.length ? <div className="limits-grid">{analysis.key_limits.map((l, i) => <div key={i} className="limit"><span>{l.label}</span><strong>{l.value}</strong>{!l.source_verified && <small>Source verification required</small>}</div>)}</div> : <p className="muted">No key limits returned. Review the original permit for completeness.</p>}
    </section>
    {!!analysis.warnings?.length && <div className="notice warning">{analysis.warnings.map(w => <p key={w}>{w}</p>)}</div>}
    {!!unverified && <div className="notice warning">{unverified} condition{unverified === 1 ? ' requires' : 's require'} source verification. Exact quotations remain available below.</div>}
    <section className="card conditions"><div className="section-heading"><div><h2>Permit conditions <span className="count">{analysis.conditions.length}</span></h2><p>Every returned condition, with its original source reference</p></div><span className="eyebrow">UNREVIEWED</span></div>
      <div className="table-tools"><label className="search"><Search size={17}/><input aria-label="Search conditions" placeholder="Search conditions, limits or categories…" value={search} onChange={e => setSearch(e.target.value)}/></label><select aria-label="Filter phase" value={phase} onChange={e => setPhase(e.target.value)}><option value="ALL">All phases</option>{phases.map(p => <option key={p}>{p}</option>)}</select><span>{shown.length} of {analysis.conditions.length} conditions</span></div>
      <div className="table-scroll"><table><thead><tr>{['#', 'Phase', 'Requirement', 'Important Limit / Timing', 'Category', 'Page'].map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{shown.map(c => <tr key={c.number} data-testid="condition-row"><td className="number">{c.number}</td><td><span className={`badge phase-${c.phase.toLowerCase()}`}>{pretty(c.phase)}</span></td><td className="requirement">{c.requirement}<details><summary><ChevronDown size={13}/> Source evidence · {c.source_verified ? 'quote verified' : 'verification required'}</summary>{c.source_spans.map((s, i) => <blockquote key={i}><b>Physical page {s.page}</b><p>{s.quotation}</p></blockquote>)}</details></td><td>{c.important_limit && <p>{c.important_limit}</p>}{c.timing && <p>{c.timing}</p>}{!c.important_limit && !c.timing && <span className="muted">Not stated</span>}</td><td><span className="category">{c.category}</span></td><td>{[...new Set(c.source_spans.map(s => s.page))].join(', ') || 'Unresolved'}</td></tr>)}</tbody></table></div>
      {!shown.length && <p className="no-results">No conditions match these filters.</p>}
    </section>
    <div className="chart-grid"><Chart title="Conditions by Phase" data={data.phase} type="bar" index={0}/><Chart title="Conditions by Requirement Type" data={data.category} type="bar" index={1}/><Chart title="Permit Conditions by Phase" data={data.phase} type="pie"/><Chart title="Conditions with Explicit Limits" data={data.limits} type="pie"/></div>
    <footer className="safety"><ShieldCheck size={20}/><p><strong>AI-extracted permit information.</strong> Review against the original licence before operational use.<br/><span>No conditions are approved and no operational authorization is issued.</span></p></footer>
  </>;
}
export default function App() {
  const [session, setSession] = useState(null);
  const [file, setFile] = useState(null);
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [status, setStatus] = useState('empty');
  const [error, setError] = useState('');
  const input = useRef(null);
  const generation = useRef(0);
  const boot = useRef(null);
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const response = await fetch('/api/session');
        if (!response.ok) return;
        const s = await response.json();
        if (!mounted) return;
        if (boot.current && boot.current !== s.boot_id) reset();
        boot.current = s.boot_id; setSession(s);
      } catch { /* A transient health failure never triggers extraction. */ }
    };
    check(); const timer = setInterval(check, 3000);
    return () => {mounted = false; clearInterval(timer);};
  }, []);
  function reset() { generation.current++; setCurrentAnalysis(null); setFile(null); setStatus('empty'); setError(''); if (input.current) input.current.value = ''; }
  async function analyze() {
    if (!file || !session || status === 'loading') return;
    const ticket = ++generation.current;
    setStatus('loading'); setError(''); setCurrentAnalysis(null);
    try {
      const response = await fetch('/api/analyze', {method: 'POST', headers: {'Content-Type': 'application/pdf', 'X-Filename': encodeURIComponent(file.name), 'X-Session-Id': session.boot_id}, body: file});
      if (!response.ok) throw new Error('analysis failed');
      const result = await response.json();
      if (ticket !== generation.current) return;
      setCurrentAnalysis(result); setStatus('complete');
    } catch {
      if (ticket !== generation.current) return;
      setStatus('error'); setError('Permit analysis could not be completed.');
    }
  }
  return <div className="app"><header className="header"><div className="brand"><div className="brand-mark"><Anchor size={25}/></div><div><strong>PermitPulse</strong><span>AI-Powered Maritime Permit Intelligence</span></div></div><button className="button secondary" onClick={reset} disabled={status === 'loading'}><Plus size={16}/> New Analysis</button></header>
    <main>{currentAnalysis ? <Results analysis={currentAnalysis}/> : <>
      <div className="empty-heading"><div className="eyebrow">CLARITY BEFORE YOU OPERATE</div><h1>Analyze a Marine Permit</h1><p>Upload a PDF to extract its conditions, deadlines,<br className="desktop-break"/> operational limits and key compliance requirements.</p></div>
      <section className="upload-card card"><div className="upload-icon">{status === 'loading' ? <LoaderCircle className="spinner" size={30}/> : <Upload size={30}/>}</div>
        {status === 'loading' ? <div role="status"><h2>Analyzing permit…</h2><p>Reading your document and extracting conditions, limits and deadlines.</p><div className="progress-track"><div/></div><small>Preparing your dashboard. Please keep this window open.</small></div> : <>
          <h2>{file ? file.name : 'Start with your permit'}</h2><p>{file ? `${(file.size / 1024).toFixed(0)} KB · Ready to analyze` : 'Select a PDF document. Your original evidence stays intact.'}</p>
          <input ref={input} type="file" accept="application/pdf,.pdf" aria-label="Upload permit PDF" onChange={e => {setFile(e.target.files?.[0] || null); setError(''); setStatus('empty');}}/>
          <div className="upload-actions"><button className="button secondary" onClick={() => input.current?.click()}><Upload size={16}/>{file ? 'Change PDF' : 'Upload Permit'}</button><button className="button primary" disabled={!file || !session} onClick={analyze}>{status === 'error' ? 'Try Again' : 'Analyze'}<ArrowUpRight size={17}/></button></div><small>PDF documents · Up to 25 MB · Small permits analyzed in one pass</small>
        </>}
        {error && <div role="alert" className="error"><AlertCircle size={18}/>{error}</div>}
      </section>
      {session?.mode === 'MOCK' && <div className="mock-label">Offline preview · Synthetic mocked responses · No OpenAI calls</div>}
      <div className="empty-state"><Waves size={26}/><p>No permit analyzed yet. Upload a permit to begin.</p></div>
      <div className="features">{[['Complete conditions', 'Numbered requirements and administrative duties.'], ['Limits & deadlines', 'Important values, timing and restrictions.'], ['Original evidence', 'Source quotations and physical page references.']].map(([title, description]) => <div key={title}><FileText size={18}/><h3>{title}</h3><p>{description}</p></div>)}</div>
    </>}</main><div className="bottom-line"><span>PermitPulse</span><span>Evidence first. Human review always.</span></div></div>;
}
