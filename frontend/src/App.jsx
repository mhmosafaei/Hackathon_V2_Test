import React, {useEffect, useRef, useState} from 'react';
import Environmental from './Environmental.jsx';
import HumanReview, {reviewSummary} from './HumanReview.jsx';
import DecisionWorkWindows from './DecisionWorkWindows.jsx';
import './WorkflowStepper.css';
import brandLogo from './assets/permitpulse-logo.png';
import brandWordmark from './assets/permitpulse-wordmark.png';
import {ArrowUpRight, FileText, Upload, Plus, Search, LoaderCircle, AlertCircle, ChevronDown, Waves, Leaf, Users, CalendarDays, Bell, UserCircle, Eye, Download, Printer, Link2, ExternalLink, BarChart3, Info, CheckCircle2, AlertTriangle, Wind, Droplets, Thermometer, Gauge, ArrowRight, ArrowUp, MoveHorizontal, Clock3, PieChart as PieChartIcon, ListChecks, Hash, UserRound, Building2, Anchor, ClipboardList, Shield, MapPin, Settings2} from 'lucide-react';
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
const workflowSteps = [
  ['permit', FileText, 'Permit Intelligence'],
  ['review', Users, 'Human Review'],
  ['environment', Leaf, 'Environmental Intelligence'],
  ['decision', CalendarDays, 'Decision & Work Windows']
];
const workflowCopy = {
  permit: ['Understand the permit', 'Upload a permit and inspect the extracted conditions, limits and source text.', 'Analyze the PDF, then continue to Human Review.'],
  review: ['Check the interpretation', 'Confirm each extracted condition and whether it applies to the planned work.', 'Resolve every review item to unlock Environmental Intelligence. You can return and edit later.'],
  environment: ['Gather environmental evidence', 'See which permit conditions need environmental data, then request evidence for a confirmed point and UTC period.', 'Fetch data, or explicitly continue with an evidence gap if retrieval is unavailable.'],
  decision: ['Assess work windows', 'Compare reviewed conditions with the evidence currently available.', 'Choose the work-window criteria and evaluate. Return to earlier steps whenever needed.']
};
function AppNav({tab, setTab, access, completed}) {
  const reasons = {review:'Analyze a permit first', environment:'Complete Human Review first', decision:'Complete the environmental evidence step first'};
  return <nav className="top-nav" aria-label="Primary navigation">{workflowSteps.map(([id, Icon, label], index) =>
    <button key={id} type="button" aria-pressed={tab === id} disabled={!access[id]}
      title={!access[id] ? reasons[id] : label} onClick={() => setTab(id)}>
      <b className={`workflow-step-number ${completed[id] ? 'is-complete' : ''}`} aria-hidden="true">{index + 1}</b>
      <Icon size={17}/><span>{label}</span><small className="workflow-nav-state" aria-hidden="true">{completed[id] ? 'Done' : !access[id] ? 'Locked' : tab === id ? 'Current' : 'Ready'}</small>
    </button>)}</nav>;
}
function WorkflowGuide({tab, access, reviewProgress, environmentHandled, onStep, onContinueWithoutEvidence, compact=false}) {
  const index = workflowSteps.findIndex(([id]) => id === tab);
  const previous = workflowSteps[index - 1], next = workflowSteps[index + 1];
  const [title, description, task] = workflowCopy[tab];
  const nextReason = tab === 'permit' ? 'Analyze a permit to continue.' : tab === 'review'
    ? reviewProgress ? `${reviewProgress.remaining} review item(s) remain.` : 'Loading review status…' : 'Fetch evidence or acknowledge the gap to continue.';
  return <section className={`workflow-guide ${compact ? 'workflow-guide-compact' : ''}`} aria-label={`Step ${index + 1} ${compact ? 'navigation' : 'guidance'}`}>
    <div><span className="workflow-guide-label">STEP {index + 1} OF 4</span>
      {!compact && <><h2>{title}</h2><p>{description}</p><p className="workflow-guide-task"><strong>What to do:</strong> {task}</p>
        {tab === 'review' && reviewProgress && <p className="workflow-guide-progress">{reviewProgress.resolved} of {reviewProgress.total} review items resolved · {reviewProgress.remaining} remaining</p>}
        {tab === 'environment' && environmentHandled && <p className="workflow-guide-progress">Environmental evidence step handled. You can continue to the decision.</p>}</>}
    </div>
    <div className="workflow-guide-actions">
      {previous && <button type="button" className="button secondary" onClick={() => onStep(previous[0])}>Back</button>}
      {tab === 'environment' && !environmentHandled && <button type="button" className="button secondary" onClick={onContinueWithoutEvidence}>Continue with evidence gap</button>}
      {next && <button type="button" className="button primary" disabled={!access[next[0]]} title={!access[next[0]] ? nextReason : undefined} onClick={() => onStep(next[0])}>Next: {next[2]}</button>}
      {next && !access[next[0]] && <small>{nextReason}</small>}
    </div>
  </section>;
}
function DocumentActions() {
  return <div className="document-actions" aria-label="Document actions"><button title="View original document"><Eye size={16}/><span>View</span></button><button title="Download document"><Download size={16}/><span>Download</span></button><button title="Print document"><Printer size={16}/><span>Print</span></button><button title="Copy document link"><Link2 size={16}/><span>Copy link</span></button><button title="Open in new tab"><ExternalLink size={16}/><span>Open</span></button></div>;
}
const parameterIconEntries = [
  ['wave height', Waves], ['significant wave', Waves], ['wave period', Clock3], ['mean wave', Clock3],
  ['wind speed', Wind], ['wind gust', Wind], ['current speed', MoveHorizontal], ['eastward', ArrowRight],
  ['northward', ArrowUp], ['visibility', Eye], ['turbidity', Droplets], ['dissolved oxygen', Gauge],
  ['oxygen', Gauge], ['temperature', Thermometer]
];
export function EnvironmentalParameterIcon({label}) {
  const normalized = String(label || '').toLowerCase();
  const [, Icon] = parameterIconEntries.find(([term]) => normalized.includes(term)) || [];
  const Component = Icon || Gauge;
  if (normalized.includes('dissolved oxygen') || normalized.includes('oxygen')) return <span className="limit-icon oxygen-icon" aria-hidden="true">O<sub>2</sub></span>;
  if (normalized.includes('gust')) return <span className="limit-icon gust-icon" aria-hidden="true"><Wind size={19}/><i/><i/></span>;
  return <span className="limit-icon" aria-hidden="true"><Component size={19}/></span>;
}
const metadataIcons = { 'Permit number': Hash, Licensee: UserRound, 'Issuing authority': Building2, Validity: CalendarDays, Activity: Anchor, 'Total conditions': ClipboardList };
function MetadataIcon({label}) { const Icon = metadataIcons[label] || Info; return <span className="metadata-icon" aria-hidden="true"><Icon size={18}/></span>; }
const categoryIcons = {'Environmental / Limit': Leaf, 'Operational / Safety': Shield, 'Vessel': Anchor, 'Positioning / Geographic': MapPin, 'Monitoring / Survey': ClipboardList, 'Technical': Settings2, 'Administrative': FileText, Other: Info};
function CategoryIcon({category}) { const Icon = categoryIcons[category] || Info; return <Icon className="category-icon" size={14} aria-hidden="true"/>; }
function ChartIcon({index, type}) {
  const Icon = type === 'pie' ? PieChartIcon : index === 1 ? ListChecks : BarChart3;
  return <Icon size={19} aria-hidden="true"/>;
}
export function Results({analysis,reviewData,onReview}) {
  const [search, setSearch] = useState('');
  const [phase, setPhase] = useState('ALL');
  const data = chartData(analysis.conditions);
  const shown = analysis.conditions.filter(c => (phase === 'ALL' || c.phase === phase) && `${c.number} ${c.requirement} ${c.category} ${c.important_limit || ''} ${c.timing || ''}`.toLowerCase().includes(search.toLowerCase()));
  const unverified = analysis.conditions.filter(c => !c.source_verified).length;
  const summary = analysis.summary;
  const reviewRows = reviewData?.requirements || [];
  const progress = reviewData?.review_progress;
  return <>
    <section className="overview-hero"><div className="page-heading"><div><div className="eyebrow">MARITIME PERMIT INTELLIGENCE</div><h1>Permit Intelligence</h1><h2>Your permit, at a glance.</h2><p>AI-powered extraction and analysis of key permit details, conditions and obligations.</p></div><span className="status"><AlertTriangle size={15}/> {progress?.complete ? 'Human review complete' : 'Human review required'} <ArrowUpRight size={14}/></span></div><div className="document-strip"><div className="document-identity"><span className="document-icon"><FileText size={25}/></span><div><div className="eyebrow">PERMIT DOCUMENT</div><strong className="document-filename" title={analysis.filename}>{analysis.filename}</strong><small>{analysis.page_count} pages <span className="dot">·</span> Run {analysis.analysis_id}</small></div></div><div className="extraction-state"><CheckCircle2 size={27}/><div><div className="eyebrow">EXTRACTION STATUS</div><strong>{analysis.restoration_status === 'INCOMPLETE' ? 'Extraction incomplete' : 'Extraction completed'}</strong><small>{analysis.restored_from_persistence ? 'Restored from persisted analysis.' : 'All returned information is structured.'}</small></div></div><DocumentActions/></div></section>
    <div className="notice" role="status">Human Review: {progress ? `${progress.resolved} of ${progress.total} items resolved; ${progress.remaining} remaining` : 'loading review status'}. <button type="button" className="decision-link" onClick={()=>onReview?.()}>Open Human Review</button></div>
    {analysis.mode === 'MOCK' && <div className="notice">Synthetic demonstration · These are mocked records, not extracted Kilkeel evidence.</div>}
    <div className="summary-grid">{[['Permit number', summary.permit_number], ['Licensee', summary.licensee], ['Issuing authority', summary.authority], ['Validity', `${fallback(summary.valid_from)} — ${fallback(summary.valid_until)}`], ['Activity', summary.activity], ['Total conditions', analysis.conditions.length]].map(([label, value]) => <section className="card metric" key={label}><MetadataIcon label={label}/><div className="eyebrow">{label}</div><strong>{fallback(value)}</strong></section>)}<GeofenceCard geofences={analysis.geofences}/></div>
    <section className="card limits"><div className="section-heading"><div><h2><BarChart3 size={19}/> Key Permit Limits</h2><p>Important values and deadlines identified in the document.</p></div><button className="expand-button" type="button"><span>Expand all limits</span><ChevronDown size={16}/></button></div>
      {analysis.key_limits.length ? <div className="limits-grid">{analysis.key_limits.map((l, i) => { const sourceState = typeof l.source_verified === 'boolean' ? l.source_verified : null; const stop = /\bstop\b/i.test(`${l.label} ${l.value}`); const title = String(l.label || '').replace(/\s+STOP(?:\s+limit)?\b/ig, '').trim() || l.label; return <div key={i} className={`limit ${stop ? 'limit-stop' : ''}`}><EnvironmentalParameterIcon label={l.label}/><div className="limit-copy"><strong>{title}</strong>{stop && <span className="stop-label"><AlertTriangle size={12}/> Permit-defined STOP threshold</span>}<b>{l.value}</b>{sourceState === true && <small className="source-verified"><CheckCircle2 size={13}/> Source quotation verified</small>}{sourceState === false && <small><Info size={13}/> Source verification required</small>}</div></div>; })}</div> : <p className="muted">No key limits returned. Review the original permit for completeness.</p>}
    </section>
    {!!analysis.warnings?.length && <div className="notice warning">{analysis.warnings.map(w => <p key={w}>{w}</p>)}</div>}
    {!!unverified && <div className="notice warning">{unverified} condition{unverified === 1 ? ' requires' : 's require'} source verification. Exact quotations remain available below.</div>}
    <section className="card conditions"><div className="section-heading"><div><h2>Permit conditions <span className="count">{analysis.conditions.length}</span></h2><p>Every returned condition, with its original source reference</p></div><span className="eyebrow">{progress?.complete ? 'REVIEW COMPLETE' : 'REVIEW IN PROGRESS'}</span></div>
      <div className="table-tools"><label className="search"><Search size={17}/><input aria-label="Search conditions" placeholder="Search conditions, limits or categories…" value={search} onChange={e => setSearch(e.target.value)}/></label><select aria-label="Filter phase" value={phase} onChange={e => setPhase(e.target.value)}><option value="ALL">All phases</option>{phases.map(p => <option key={p}>{p}</option>)}</select><span>{shown.length} of {analysis.conditions.length} conditions</span></div>
      <div className="table-scroll"><table><thead><tr>{['#', 'Phase', 'Requirement', 'Important Limit / Timing', 'Category', 'Page'].map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{shown.map(c => <tr key={c.number} data-testid="condition-row"><td className="number">{c.number}</td><td><span className={`badge phase-${c.phase.toLowerCase()}`}>{pretty(c.phase)}</span></td><td className="requirement">{c.requirement}<details><summary><ChevronDown size={13}/> Source evidence · {c.source_verified ? <><CheckCircle2 size={12}/> quote verified</> : <><AlertTriangle size={12}/> verification required</>}</summary>{c.source_spans.map((s, i) => <blockquote key={i}><b>Physical page {s.page}</b><p>{s.quotation}</p></blockquote>)}</details></td><td>{c.important_limit && <p>{c.important_limit}</p>}{c.timing && <p>{c.timing}</p>}{!c.important_limit && !c.timing && <span className="muted">Not stated</span>}</td><td><span className="category"><CategoryIcon category={c.category}/>{c.category}</span></td><td>{[...new Set(c.source_spans.map(s => s.page))].join(', ') || 'Unresolved'}{reviewRows.filter(r=>r.kind==='condition' && String(r.condition_id)===String(c.number)).map(r=><div key={r.target_id}><small>{r.state==='APPROVED'||r.state==='CORRECTED' ? 'Reviewed' : 'Review needed'}</small> <button type="button" className="decision-link" onClick={()=>onReview?.(r.target_id)}>Review</button></div>)}</td></tr>)}</tbody></table></div>
      {!shown.length && <p className="no-results">No conditions match these filters.</p>}
    </section>
    <div className="chart-grid"><Chart title={<><ChartIcon index={0} type="bar"/>Conditions by Phase</>} data={data.phase} type="bar" index={0}/><Chart title={<><ChartIcon index={1} type="bar"/>Conditions by Requirement Type</>} data={data.category} type="bar" index={1}/><Chart title={<><ChartIcon type="pie"/>Permit Conditions by Phase</>} data={data.phase} type="pie"/><Chart title={<><ChartIcon type="pie"/>Conditions with Explicit Limits</>} data={data.limits} type="pie"/></div>
    <footer className="safety"><AlertTriangle size={22}/><p><strong>AI-extracted permit information. Review against the original licence before operational use.</strong><br/><span>Human review and environmental evidence do not issue operational authorization.</span></p></footer>
  </>;
}
export default function App() {
  const [session, setSession] = useState(null);
  const [file, setFile] = useState(null);
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [status, setStatus] = useState('empty');
  const [error, setError] = useState('');
  const [tab, setTab] = useState('permit');
  const [reviewTarget, setReviewTarget] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [environmentAcknowledged, setEnvironmentAcknowledged] = useState(false);
  const [assessmentStale, setAssessmentStale] = useState(false);
  const input = useRef(null);
  const generation = useRef(0);
  const boot = useRef(null);
  const restoredBoot = useRef(null);
  const reviewProgress = reviewData?.review_progress || (Array.isArray(reviewData?.requirements) ? (()=>{const summary=reviewSummary(reviewData.requirements);return {total:summary.total,resolved:summary.resolved,remaining:summary.total-summary.resolved,complete:summary.complete};})() : null);
  const reviewComplete = !!(currentAnalysis && reviewData?.analysis_run_id === currentAnalysis.analysis_id && reviewProgress?.complete);
  const evidenceRetrieved = !!(currentAnalysis && session?.environmental_result?.analysis_id === currentAnalysis.analysis_id);
  const environmentHandled = evidenceRetrieved || environmentAcknowledged;
  const access = {permit:true, review:!!currentAnalysis, environment:reviewComplete, decision:reviewComplete && environmentHandled};
  const completed = {permit:!!currentAnalysis, review:reviewComplete, environment:reviewComplete && environmentHandled,
    decision:!!(access.decision && session?.decision_result && !assessmentStale)};
  useEffect(() => {
    if (tab === 'decision' && !access.decision) setTab(access.environment ? 'environment' : access.review ? 'review' : 'permit');
    else if (tab === 'environment' && !access.environment) setTab(access.review ? 'review' : 'permit');
    else if (tab === 'review' && !access.review) setTab('permit');
  }, [tab, access.review, access.environment, access.decision]);
  function acknowledgeEvidenceGap() {
    if (!currentAnalysis || !reviewComplete) return;
    setEnvironmentAcknowledged(true);
    if (session?.boot_id) sessionStorage.setItem(`permitpulse:environmentGap:${session.boot_id}:${currentAnalysis.analysis_id}`, 'true');
  }
  useEffect(() => {
    if (!currentAnalysis || !session?.boot_id) {setEnvironmentAcknowledged(false);return;}
    setEnvironmentAcknowledged(sessionStorage.getItem(`permitpulse:environmentGap:${session.boot_id}:${currentAnalysis.analysis_id}`) === 'true');
  }, [currentAnalysis?.analysis_id, session?.boot_id]);
  useEffect(() => {
    setReviewData(null);
    if (!currentAnalysis || !session) return;
    let active = true;
    fetch(`/api/reviews?analysis_id=${encodeURIComponent(currentAnalysis.analysis_id)}`, {headers:{'X-Session-Id':session.boot_id}})
      .then(async response => {if(!response.ok) throw new Error('Review status unavailable'); return response.json();})
      .then(data => {if(active && data.analysis_run_id===currentAnalysis.analysis_id){setReviewData(data);}})
      .catch(() => {if(active)setReviewData(null);});
    return () => {active=false;};
  }, [currentAnalysis?.analysis_id, session?.boot_id]);
  function updateReview(data) {
    setReviewData(data);

    setAssessmentStale(true);
    setSession(previous => previous ? {...previous,decision_result:null,invalidated_assessment_id:previous.decision_result?.assessment_id || previous.invalidated_assessment_id} : previous);
  }
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
        if (restoredBoot.current !== s.boot_id) {
          restoredBoot.current = s.boot_id;
          const query = new URLSearchParams(window.location.search);
          const queryHash = query.get('document_sha256'), queryRun = query.get('analysis_run_id');
          const raw = queryHash && queryRun ? JSON.stringify({document_sha256:queryHash, analysis_run_id:queryRun}) : localStorage.getItem('permitpulse:lastAnalysisRef');
          if (raw) {
            try {
              const ref = JSON.parse(raw);
              const restored = await fetch('/api/restore', {method:'POST', headers:{'Content-Type':'application/json','X-Session-Id':s.boot_id}, body:JSON.stringify(ref)});
              if (restored.ok && mounted) { setCurrentAnalysis(await restored.json()); setStatus('complete'); setTab('permit'); }
            } catch { /* A missing or malformed saved reference never triggers analysis. */ }
          }
        }
      } catch { /* A transient health failure never triggers extraction. */ }
    };
    check(); const timer = setInterval(check, 3000);
    return () => {mounted = false; clearInterval(timer);};
  }, []);
  function reset() { generation.current++; setCurrentAnalysis(null); setReviewData(null); setEnvironmentAcknowledged(false); setAssessmentStale(false); setTab('permit'); setFile(null); setStatus('empty'); setError(''); if (input.current) input.current.value = ''; }
  async function analyze() {
    if (!file || !session || status === 'loading') return;
    const ticket = ++generation.current;
    setStatus('loading'); setError(''); setCurrentAnalysis(null);
    try {
      const response = await fetch('/api/analyze', {method: 'POST', headers: {'Content-Type': 'application/pdf', 'X-Filename': encodeURIComponent(file.name), 'X-Session-Id': session.boot_id}, body: file});
      if (!response.ok) {
        const detail = typeof response.json === 'function' ? await response.json().catch(() => ({})) : {};
        if (detail.error === 'EXTRACTION_INCOMPLETE') {
          throw new Error(`Environmental extraction incomplete: ${detail.extracted_count || 0} of ${detail.candidate_count || 0} candidate requirements extracted. Re-analysis or human review is required.`);
        }
        throw new Error('Permit analysis could not be completed.');
      }
      const result = await response.json();
      if (ticket !== generation.current) return;
      localStorage.setItem('permitpulse:lastAnalysisRef', JSON.stringify({document_sha256:result.document_sha256, analysis_run_id:result.analysis_id}));
      setReviewData(null);setEnvironmentAcknowledged(false);setAssessmentStale(false);setCurrentAnalysis(result); setTab('permit'); setStatus('complete');
    } catch (cause) {
      if (ticket !== generation.current) return;
      setStatus('error'); setError(cause?.message || 'Permit analysis could not be completed.');
    }
  }
  return <div className="app"><header className="header"><div className="brand"><img className="brand-symbol" src={brandLogo} alt=""/><div><img className="brand-wordmark" src={brandWordmark} alt="PermitPulse"/><span>Evidence first. Human review always.</span></div></div><AppNav tab={tab} setTab={setTab} access={access} completed={completed}/><div className="header-actions"><button className="icon-button" aria-label="Notifications"><Bell size={18}/><i className="notification-dot"/></button><button className="profile-button" aria-label="User profile"><UserCircle size={25}/><span>JD</span><ChevronDown size={14}/></button></div><button className="button secondary new-analysis" onClick={reset} disabled={status === 'loading'}><Plus size={16}/> New Analysis</button></header>
    <main>
    <WorkflowGuide tab={tab} access={access} reviewProgress={reviewProgress} environmentHandled={environmentHandled} onStep={setTab} onContinueWithoutEvidence={acknowledgeEvidenceGap}/>
    {tab === 'decision' && access.decision && <DecisionWorkWindows key={currentAnalysis?.analysis_id || 'empty'} analysis={currentAnalysis} session={assessmentStale ? {...session,decision_result:null} : session} reviewReady={reviewComplete} reviewProgress={reviewProgress} assessmentStale={assessmentStale} onEvaluated={decision=>{setAssessmentStale(false);setSession(previous=>previous ? {...previous,decision_result:decision,invalidated_assessment_id:null} : previous);}} onReview={id=>{setReviewTarget(id);setTab('review');}}/>}
    {tab === 'review' && <HumanReview key={currentAnalysis?.analysis_id || 'empty'} analysis={currentAnalysis} session={session} initialTargetId={reviewTarget} onUpdated={updateReview} onLoaded={setReviewData}/>}
    <div hidden={tab !== 'environment'}><Environmental key={currentAnalysis?.analysis_id || 'empty'} analysis={currentAnalysis} session={session} reviewData={reviewData ? {...reviewData,review_progress:reviewProgress} : null}/></div>
    <div hidden={tab !== 'permit'}>{currentAnalysis ? <Results analysis={currentAnalysis} reviewData={reviewData ? {...reviewData,review_progress:reviewProgress} : null} onReview={id=>{setReviewTarget(id);setTab('review');}}/> : <>
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
    </>}</div>
    <WorkflowGuide compact tab={tab} access={access} reviewProgress={reviewProgress} environmentHandled={environmentHandled} onStep={setTab} onContinueWithoutEvidence={acknowledgeEvidenceGap}/>
    </main><div className="bottom-line"><span>PermitPulse</span><span>Evidence first. Human review always.</span></div></div>;
}
